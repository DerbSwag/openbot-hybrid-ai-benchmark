
"""Pure arithmetic for the eight benchmark metrics."""

from collections import Counter, defaultdict
from decimal import Decimal


PROVENANCE = ("measured", "estimated", "expected")
TOKEN_KINDS = ("cached_input", "uncached_input", "output")
CONTEXT_EVENTS = (
    "preflight_context_rejection", "runtime_truncation", "context_limit_error",
    "compaction", "output_limit_truncation",
)
OVERFLOW_EVENTS = frozenset(CONTEXT_EVENTS[:3])


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator}


def context_budget(invocation):
    fields = ("prompt_tokens", "reserved_output_tokens", "safety_margin", "runtime_context")
    used, reserved, margin, capacity = (invocation[field]["value"] for field in fields)
    if None in (used, reserved, margin, capacity):
        status, total = "unknown", None
    else:
        total = used + reserved + margin
        status = "over" if total > capacity else "exact" if total == capacity else "within"
    return {"invocation_id": invocation["id"], "status": status, "tokens_required": total}


def _evaluate_output(output, rubric):
    if output is None:
        return None, "unknown"
    claims = {row["id"]: row for row in output["claims"]}
    rule_ids = {rule["claim_id"] for rule in rubric["assertions"]}
    earned = possible = 0
    for rule in rubric["assertions"]:
        possible += rule["weight"]
        claim = claims.get(rule["claim_id"])
        if (
            claim and claim["value"] == rule["accepted_value"]
            and set(rule["evidence_ids"]) <= set(claim["evidence_ids"])
        ):
            earned += rule["weight"]
    possible += len(set(claims) - rule_ids)
    delivered = {row["id"]: set(row["evidence_ids"]) for row in output["deliverables"]}
    complete = all(
        set(row["evidence_ids"]) <= delivered.get(row["id"], set())
        for row in rubric["required_deliverables"]
    )
    return ratio(earned, possible), "complete" if complete else "incomplete"


def _tokens(invocations):
    result = {}
    for kind in TOKEN_KINDS:
        values = [item["tokens"][kind] for item in invocations if item["executed"]]
        result[kind] = {
            "totals": {
                source: sum(v["value"] for v in values if v.get("provenance") == source)
                for source in PROVENANCE
            },
            "observations": {
                source: sum(v.get("provenance") == source for v in values) for source in PROVENANCE
            },
            "missing_invocations": sum(v["value"] is None for v in values),
        }
    return result


def _decimal(value):
    encoded = format(value, "f")
    return encoded.rstrip("0").rstrip(".") if "." in encoded else encoded


def _cost(invocations):
    totals = {"estimated": Decimal(0), "expected": Decimal(0)}
    covered = missing = not_applicable = 0
    rates = set()
    for item in invocations:
        if not item["executed"] or item["execution_target"] == "local":
            not_applicable += 1
            continue
        price = item["api_pricing"]
        tokens = item["tokens"]
        if price is None or any(value["value"] is None for value in tokens.values()):
            missing += 1
            continue
        segment = price["provenance"]
        if any(value["provenance"] == "expected" for value in tokens.values()):
            segment = "expected"
        totals[segment] += sum(
            Decimal(tokens[name]["value"]) * Decimal(price["per_million"][name])
            for name in TOKEN_KINDS
        ).scaleb(-6)
        rates.add(price["snapshot_id"])
        covered += 1
    return {
        "currency": "USD", **{key: _decimal(total) for key, total in totals.items()},
        "covered_invocations": covered, "missing_invocations": missing,
        "not_applicable_invocations": not_applicable, "rate_snapshots": sorted(rates),
    }


def run_result(run, rubric, budgets, baseline):
    accuracy, completeness = _evaluate_output(run["output"], rubric)
    if run["status"] in {"partial", "failed"} or completeness == "incomplete":
        completed = False
    elif run["status"] == "completed" and completeness == "complete":
        completed = True
    else:
        completed = None
    events = Counter(row["type"] for row in run["events"])
    overflow = (
        True if OVERFLOW_EVENTS.intersection(events)
        else False if run["context_observation"] == "complete"
        else None
    )
    security = (
        "fail" if events["security_violation"]
        else "pass" if run["security_observation"] == "complete"
        else "unknown"
    )
    fields = ("run_id", "case_id", "case_revision", "rubric_revision", "protocol_id", "mode", "run_kind",
              "status", "elapsed_ms", "peak_vram_mib")
    return {
        **{key: run[key] for key in fields},
        "accuracy": accuracy, "output_completeness": completeness, "completed": completed,
        "tokens": _tokens(run["invocations"]), "context_overflow": overflow,
        "context_events": {key: events[key] for key in CONTEXT_EVENTS}, "context_budget": budgets,
        "api_cost": _cost(run["invocations"]), "security": security,
        "human_interventions": {
            "approval": events["human_approval"], "failure": events["human_failure_intervention"],
        },
        "cloud_baseline": baseline,
    }


def _sum_tokens(results):
    return {
        kind: {
            field: {
                source: sum(run["tokens"][kind][field][source] for run in results)
                for source in PROVENANCE
            }
            for field in ("totals", "observations")
        } | {"missing_invocations": sum(run["tokens"][kind]["missing_invocations"] for run in results)}
        for kind in TOKEN_KINDS
    }


def _sum_cost(results):
    costs = [run["api_cost"] for run in results]
    return {
        "currency": "USD",
        **{key: _decimal(sum((Decimal(cost[key]) for cost in costs), Decimal(0)))
           for key in ("estimated", "expected")},
        **{key: sum(cost[key] for cost in costs) for key in (
            "covered_invocations", "missing_invocations", "not_applicable_invocations",
        )},
        "rate_snapshots": sorted({key for cost in costs for key in cost["rate_snapshots"]}),
    }


def _sum_latency(results):
    buckets = {source: {"total_ms": 0, "observations": 0} for source in PROVENANCE}
    unknown = 0
    for run in results:
        elapsed = run["elapsed_ms"]
        if elapsed["value"] is None:
            unknown += 1
            continue
        bucket = buckets[elapsed["provenance"]]
        bucket["total_ms"] += elapsed["value"]
        bucket["observations"] += 1
    return {"by_provenance": buckets, "unknown": unknown}


def summaries(results):
    groups = defaultdict(list)
    for run in results:
        groups[(run["mode"], run["run_kind"])].append(run)
    summaries_by_mode = []
    for (mode, kind), group in sorted(groups.items()):
        scored = [run["accuracy"] for run in group if run["accuracy"] is not None]
        outcomes = Counter(run["completed"] for run in group)
        overflow = Counter(run["context_overflow"] for run in group)
        security = Counter(run["security"] for run in group)
        summaries_by_mode.append({
            "mode": mode, "run_kind": kind, "runs": len(group),
            "accuracy": {
                "score": ratio(sum(a["numerator"] for a in scored), sum(a["denominator"] for a in scored)),
                "coverage": ratio(len(scored), len(group)),
            },
            "end_to_end_latency": _sum_latency(group),
            "token_consumption": _sum_tokens(group),
            "completion": {"rate": ratio(outcomes[True], len(group)), "unknown": outcomes[None],
                           "partial": sum(run["status"] == "partial" for run in group)},
            "context_overflow": {
                "rate": ratio(overflow[True], len(group)), "unknown": overflow[None],
                "events": {name: sum(run["context_events"][name] for run in group) for name in CONTEXT_EVENTS},
            },
            "api_cost": _sum_cost(group),
            "security": {key: security[key] for key in ("pass", "fail", "unknown")},
            "human_interventions": {
                key: sum(run["human_interventions"][key] for run in group) for key in ("approval", "failure")
            },
        })
    return summaries_by_mode
