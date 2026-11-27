
"""Validate cross-record contracts and compute deterministic run results."""

import hashlib

from benchmark import metrics
from benchmark.contracts import ContractError, canonical, case_key, scan_payload, unique, validate


SORT_FIELDS = {
    "evidence": "id", "requested_deliverables": None, "assertions": "claim_id",
    "required_deliverables": "id", "evidence_ids": None, "invocations": "id",
    "events": "id", "claims": "id", "deliverables": "id",
}


def normalized(value, field=None):
    if isinstance(value, dict):
        return {key: normalized(item, key) for key, item in value.items()}
    if isinstance(value, list):
        items = [normalized(item) for item in value]
        if field in SORT_FIELDS:
            key = SORT_FIELDS[field]
            return sorted(items, key=(lambda item: item[key]) if key else None)
        return items
    return value


def rubric_key(record):
    return (*case_key(record), record["rubric_revision"])


def _require_evidence(rows, available):
    if any(set(row["evidence_ids"]) - available for row in rows):
        raise ContractError("unknown evidence ID")


def _rubrics(cases, rubrics):
    result = unique(rubrics, rubric_key, "rubric")
    for rubric in rubrics:
        case = cases.get(case_key(rubric))
        if case is None:
            raise ContractError("rubric references an unknown case revision")
        available = {item["id"] for item in case["evidence"]}
        unique(rubric["assertions"], lambda row: row["claim_id"], "rubric claim")
        required = unique(rubric["required_deliverables"], lambda row: row["id"], "rubric deliverable")
        if set(required) != set(case["requested_deliverables"]):
            raise ContractError("rubric deliverables differ from the case contract")
        _require_evidence(rubric["assertions"] + rubric["required_deliverables"], available)
    return result


def _validate_invocation(item, events):
    types = {event["type"] for event in events}
    if len(types) != len(events):
        raise ContractError("duplicate context event type for invocation")
    native = item["native_context"]["value"]
    runtime = item["runtime_context"]["value"]
    final = item["final_context_tokens"]["value"]
    if runtime == 0 or native == 0 or (runtime is not None and native is not None and runtime > native):
        raise ContractError("invalid native/runtime context relation")
    if final is not None and runtime is not None and final > runtime:
        raise ContractError("effective final context exceeds runtime context")
    flag = item["runtime_truncated"]["value"]
    if ("runtime_truncation" in types) != (flag is True):
        raise ContractError("runtime truncation event and flag differ")
    budget = metrics.context_budget(item)
    preflight = "preflight_context_rejection" in types
    if preflight and (item["status"] != "rejected" or budget["status"] != "over"):
        raise ContractError("preflight context rejection requires a rejected, over-budget invocation")
    if item["executed"]:
        if item["status"] == "rejected" or preflight:
            raise ContractError("preflight rejection cannot execute")
    elif (
        item["status"] not in {"rejected", "unknown"} or types - {"preflight_context_rejection"}
        or flag is not None or final is not None
        or any(value["value"] is not None for value in item["tokens"].values())
    ):
        raise ContractError("nonexecuted invocation has runtime telemetry")
    if "context_limit_error" in types and item["status"] != "failed":
        raise ContractError("context-limit error requires a failed invocation")
    return budget


def _validate_run(run, case, prices):
    output = run["output"]
    if output is not None:
        unique(output["claims"], lambda row: row["id"], "output claim")
        deliverables = unique(output["deliverables"], lambda row: row["id"], "output deliverable")
        if set(deliverables) - set(case["requested_deliverables"]):
            raise ContractError("unknown output deliverable ID")
        _require_evidence(
            output["claims"] + output["deliverables"], {item["id"] for item in case["evidence"]}
        )
    invocations = unique(run["invocations"], lambda row: row["id"], "invocation")
    unique(run["events"], lambda row: row["id"], "event")
    context_events = {key: [] for key in invocations}
    for event in run["events"]:
        if event["type"] in metrics.CONTEXT_EVENTS:
            if event["invocation_id"] not in context_events:
                raise ContractError("context event references an unknown invocation")
            context_events[event["invocation_id"]].append(event)
    if run["context_observation"] == "complete" and (
        not invocations or any(
            item["executed"] and item["runtime_truncated"]["value"] is None
            for item in invocations.values()
        )
    ):
        raise ContractError("complete context observation lacks runtime telemetry")
    budgets = []
    for key, invocation in invocations.items():
        budgets.append(_validate_invocation(invocation, context_events[key]))
        price = invocation["api_pricing"]
        tier = invocation["execution_target"]
        if run["mode"] != "hybrid" and tier != run["mode"]:
            raise ContractError("single-agent execution target mismatch")
        if price is not None:
            if tier != "cloud" or not invocation["executed"]:
                raise ContractError("API pricing requires an executed cloud invocation")
            price_key = (price["snapshot_id"], invocation["model"])
            signature = (price["currency"], price["provenance"], price["per_million"])
            if price_key in prices and prices[price_key] != signature:
                raise ContractError("inconsistent rate snapshot for model")
            prices[price_key] = signature
    if run["mode"] != "hybrid" and run["baseline_run_id"] is not None:
        raise ContractError("only a hybrid run may reference a cloud baseline")
    if any(item["status"] != "rejected" for item in invocations.values()) and not any(
        item["model"] == run["decision_model"] and item["tokenizer"] == run["decision_tokenizer"]
        for item in invocations.values()
    ):
        raise ContractError("declared decision model/tokenizer missing from invocations")
    if run["mode"] != "hybrid" and any(
        item["model"] != run["decision_model"] or item["tokenizer"] != run["decision_tokenizer"]
        for item in invocations.values()
    ):
        raise ContractError("single-agent model/tokenizer mismatch")
    return budgets


def _cloud_baseline(run, indexed):
    target_id = run["baseline_run_id"]
    if target_id is None:
        return {"status": "not_requested", "run_id": None}
    target = indexed.get(target_id)
    matches = ("run_kind", "protocol_id", "decision_model", "decision_tokenizer")
    if (
        target is None or target["mode"] != "cloud" or rubric_key(target) != rubric_key(run)
        or any(target[field] != run[field] for field in matches)
    ):
        raise ContractError("unmatched single-cloud baseline")
    for participant in (run, target):
        if not any(
            item["executed"] and item["execution_target"] == "cloud"
            and item["model"] == participant["decision_model"]
            and item["tokenizer"] == participant["decision_tokenizer"]
            for item in participant["invocations"]
        ):
            raise ContractError("matched baseline needs an executed cloud decision invocation")
    return {"status": "matched", "run_id": target_id}


def evaluate(cases, rubrics, runs, schemas):
    for kind, rows in (("case", cases), ("rubric", rubrics), ("run", runs)):
        if not rows:
            raise ContractError(f"missing {kind} records")
        for row in rows:
            scan_payload(row)
            validate(schemas[kind], row, kind)
    checked_cases = sorted((normalized(item) for item in cases), key=case_key)
    checked_rubrics = sorted((normalized(item) for item in rubrics), key=rubric_key)
    checked_runs = sorted((normalized(item) for item in runs), key=lambda item: item["run_id"])
    cases_by_id = unique(checked_cases, case_key, "case revision")
    for case in checked_cases:
        unique(case["evidence"], lambda row: row["id"], "evidence")
    rubrics_by_id = _rubrics(cases_by_id, checked_rubrics)
    runs_by_id = unique(checked_runs, lambda item: item["run_id"], "run")
    results = []
    prices = {}
    for run in checked_runs:
        case = cases_by_id.get(case_key(run))
        rubric = rubrics_by_id.get(rubric_key(run))
        if case is None or rubric is None:
            raise ContractError("run references an unknown case or rubric revision")
        budgets = _validate_run(run, case, prices)
        results.append(metrics.run_result(run, rubric, budgets, _cloud_baseline(run, runs_by_id)))
    payload = {"cases": checked_cases, "rubrics": checked_rubrics, "runs": checked_runs}
    report = {
        "schema_version": "1.0",
        "evaluator_version": "1.0",
        "classification": "synthetic",
        "input_digest": hashlib.sha256(canonical(payload)).hexdigest(),
        "runs": results,
        "summaries": metrics.summaries(results),
    }
    scan_payload(report)
    validate(schemas["report"], report, "report")
    return report
