
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from jsonschema.exceptions import _WrappedReferencingError

from benchmark.contracts import (
    ContractError, canonical, load_case, load_dataset, plain_path, read_json, scan_payload, validate, validators,
)
from benchmark.evaluator import evaluate
from scripts.audit_tree import audit_tree


ROOT = Path(__file__).resolve().parents[1]
ORIGINS = ("expected", "estimated", "measured")
CONTEXT_TYPES = (
    "preflight_context_rejection", "runtime_truncation", "context_limit_error",
    "compaction", "output_limit_truncation",
)


def ratio_values(ratio):
    return [ratio["numerator"], ratio["denominator"]]


def golden_signature(summary):
    accuracy = summary["accuracy"]
    latency = summary["end_to_end_latency"]
    tokens = summary["token_consumption"]
    completion = summary["completion"]
    overflow = summary["context_overflow"]
    api_cost = summary["api_cost"]
    return {
        "accuracy": ratio_values(accuracy["score"]) + ratio_values(accuracy["coverage"]),
        "latency_ms": [
            latency["by_provenance"][origin][field]
            for origin in ORIGINS for field in ("total_ms", "observations")
        ] + [latency["unknown"]],
        "tokens": {
            key: [row[field][origin] for origin in ORIGINS for field in ("totals", "observations")]
            + [row["missing_invocations"]] for key, row in tokens.items()
        },
        "completion": ratio_values(completion["rate"]) + [completion["unknown"], completion["partial"]],
        "overflow": ratio_values(overflow["rate"]) + [overflow["unknown"]]
        + [overflow["events"][key] for key in CONTEXT_TYPES],
        "api_cost_usd": [api_cost[key] for key in (
            "expected", "estimated", "covered_invocations", "missing_invocations", "not_applicable_invocations",
        )],
        "security": [summary["security"][key] for key in ("pass", "fail", "unknown")],
        "human_intervention": [summary["human_interventions"][key] for key in ("approval", "failure")],
    }


class BenchmarkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = validators(ROOT)
        cls.dataset = load_dataset(ROOT, cls.schemas)

    def setUp(self):
        self.cases, self.rubrics, self.runs = copy.deepcopy(self.dataset)

    def run_record(self, run_id):
        return next(run for run in self.runs if run["run_id"] == run_id)

    def evaluate(self):
        return evaluate(self.cases, self.rubrics, self.runs, self.schemas)

    def result(self, run_id):
        return next(result for result in self.evaluate()["runs"] if result["run_id"] == run_id)

    def test_schema_contracts_cover_inputs_and_output(self):
        report = self.evaluate()
        self.assertEqual({r["mode"] for r in report["runs"]}, {"local", "cloud", "hybrid"})
        self.assertEqual(len(report["runs"]), 6)
        validate(self.schemas["report"], report, "report")
        report["runs"][0]["unexpected"] = 1
        with self.assertRaisesRegex(ContractError, "report contract"):
            validate(self.schemas["report"], report, "report")

    def test_eight_metrics_against_independent_golden_arithmetic(self):
        golden = read_json(ROOT / "fixtures/synthetic/golden/summary.json", payload=True)
        actual = {row["mode"]: golden_signature(row) for row in self.evaluate()["summaries"]}
        self.assertEqual(actual, golden)

    def test_below_exact_over_and_unknown_context_budget(self):
        expected = {
            ("local-success", "invoke-local"): ("within", 64),
            ("cloud-matched", "invoke-cloud"): ("exact", 100),
            ("hybrid-rejected", "invoke-denied"): ("over", 84),
            ("local-unknown", "invoke-local"): ("unknown", None),
        }
        actual = {
            (row["run_id"], budget["invocation_id"]): (budget["status"], budget["tokens_required"])
            for row in self.evaluate()["runs"] for budget in row["context_budget"]
        }
        self.assertEqual({key: actual[key] for key in expected}, expected)

    def test_five_context_events_and_independent_completeness(self):
        self.assertFalse(self.result("cloud-matched")["context_overflow"])  # Compaction only.
        self.assertEqual(self.result("cloud-partial")["output_completeness"], "incomplete")
        self.assertEqual(self.result("local-unknown")["output_completeness"], "unknown")
        self.assertTrue(self.result("local-unknown")["context_overflow"])
        row = self.run_record("cloud-matched")
        row["events"][0]["type"] = "output_limit_truncation"
        self.assertFalse(self.result("cloud-matched")["context_overflow"])
        self.assertEqual(self.result("cloud-matched")["context_events"]["output_limit_truncation"], 1)

    def test_unknown_context_and_vram_stay_unknown(self):
        run = self.run_record("local-unknown")
        run["events"].clear()
        run["invocations"][0]["runtime_truncated"] = {"value": None, "reason": "NOT_MEASURED"}
        result = self.result("local-unknown")
        self.assertIsNone(result["context_overflow"])
        self.assertEqual(result["peak_vram_mib"], {"value": None, "reason": "NOT_MEASURED"})
        run["context_observation"] = "complete"
        with self.assertRaisesRegex(ContractError, "lacks runtime telemetry"):
            self.evaluate()

    def test_missing_numeric_telemetry_requires_reason(self):
        run = self.run_record("local-success")
        for value in ({"value": None}, {"value": None, "reason": "unexpected"}):
            with self.subTest(value=value):
                run["peak_vram_mib"] = value
                with self.assertRaisesRegex(ContractError, "run contract"):
                    self.evaluate()

    def test_measured_observation_is_separate_from_fixture_and_estimates(self):
        run = self.run_record("local-success")
        run["run_kind"] = "benchmark_observation"
        run["elapsed_ms"]["provenance"] = "measured"
        report = self.evaluate()
        groups = {r["run_kind"]: r for r in report["summaries"] if r["mode"] == "local"}
        self.assertEqual(groups["benchmark_observation"]["end_to_end_latency"]["by_provenance"]["measured"],
                         {"observations": 1, "total_ms": 120})
        self.assertEqual(groups["synthetic_fixture"]["end_to_end_latency"]["by_provenance"]["measured"],
                         {"observations": 0, "total_ms": 0})
        self.assertEqual(report["classification"], "synthetic")

    def test_matched_cloud_baseline_and_model_mismatch(self):
        self.assertEqual(self.result("hybrid-partial")["cloud_baseline"],
                         {"status": "matched", "run_id": "cloud-matched"})
        cloud = self.run_record("cloud-matched")
        for field in ("decision_model", "decision_tokenizer", "protocol_id"):
            with self.subTest(field=field):
                hybrid = self.run_record("hybrid-partial")
                hybrid[field] = "other"
                if field in {"decision_model", "decision_tokenizer"}:
                    attr = field.removeprefix("decision_")
                    inv = next(i for i in hybrid["invocations"] if i["id"] == "invoke-decision")
                    inv[attr] = "other"
                with self.assertRaisesRegex(ContractError, "unmatched single-cloud baseline"):
                    self.evaluate()
                hybrid[field] = cloud[field]
                if field in {"decision_model", "decision_tokenizer"}:
                    inv[attr] = cloud[field]
        self.run_record("hybrid-partial")["baseline_run_id"] = "local-success"
        with self.assertRaisesRegex(ContractError, "unmatched single-cloud baseline"):
            self.evaluate()

    def test_baseline_rejects_primary_model_in_wrong_execution_tier(self):
        run = self.run_record("hybrid-partial")
        for invocation in run["invocations"]:
            if invocation["model"] == run["decision_model"]:
                invocation["execution_target"] = "local"
                invocation["api_pricing"] = None
        with self.assertRaisesRegex(ContractError, "executed cloud decision invocation"):
            self.evaluate()

    def test_bootstrap_hash_guard_rejects_missing_and_tampered_wheels(self):
        import subprocess
        import sys

        script = ROOT / "scripts/verify_bootstrap.py"
        with tempfile.TemporaryDirectory() as path:
            wheel = Path(path) / "pip-25.2-py3-none-any.whl"
            for present, expected in ((False, "missing or unreadable"), (True, "hash differs")):
                if present:
                    wheel.write_bytes(b"synthetic wrong content")
                result = subprocess.run(
                    [sys.executable, "-I", "-B", script, ROOT / "bootstrap.lock", wheel.parent],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stderr)

    def test_reversed_records_and_nested_sets_are_byte_identical(self):
        def reverse_lists(data):
            if isinstance(data, list):
                data.reverse()
                for item in data:
                    reverse_lists(item)
            elif isinstance(data, dict):
                for item in data.values():
                    reverse_lists(item)

        original = canonical(self.evaluate())
        for collection in (self.cases, self.rubrics, self.runs):
            reverse_lists(collection)
        self.assertEqual(original, canonical(self.evaluate()))

    def test_rejects_unsupported_contract_and_classification(self):
        self.cases[0]["schema_version"] = "2.0"
        with self.assertRaisesRegex(ContractError, "case contract"):
            self.evaluate()
        self.cases[0]["schema_version"] = "1.0"
        self.cases[0]["classification"] = "production"
        with self.assertRaisesRegex(ContractError, "case contract"):
            self.evaluate()

    def test_duplicate_ids_and_bad_references(self):
        run = self.run_record("hybrid-partial")
        evidence = self.cases[0]["evidence"]
        evidence.append(evidence[0])
        with self.assertRaisesRegex(ContractError, "duplicate evidence"):
            self.evaluate()
        evidence.pop()
        self.runs.append(run)
        with self.assertRaisesRegex(ContractError, "duplicate run"):
            self.evaluate()
        self.runs.pop()
        run["events"].append(run["events"][0])
        with self.assertRaisesRegex(ContractError, "duplicate event"):
            self.evaluate()
        run["events"].pop()
        run["output"]["claims"][0]["evidence_ids"] = ["missing-id"]
        with self.assertRaisesRegex(ContractError, "unknown evidence"):
            self.evaluate()

    def test_rejects_broken_case_rubric_and_invocation_references(self):
        run = self.run_record("hybrid-partial")
        run["case_revision"] = 50
        with self.assertRaisesRegex(ContractError, "unknown case or rubric"):
            self.evaluate()
        run["case_revision"] = 1
        run["rubric_revision"] = 50
        with self.assertRaisesRegex(ContractError, "unknown case or rubric"):
            self.evaluate()
        run["rubric_revision"] = 1
        run["events"][0]["invocation_id"] = "missing-invocation"
        with self.assertRaisesRegex(ContractError, "unknown invocation"):
            self.evaluate()

    def test_rejects_inconsistent_truncation_and_preflight(self):
        run = self.run_record("local-unknown")
        run["invocations"][0]["runtime_truncated"]["value"] = False
        with self.assertRaisesRegex(ContractError, "truncation event and flag differ"):
            self.evaluate()
        run["invocations"][0]["runtime_truncated"]["value"] = True
        preflight = self.run_record("hybrid-rejected")
        preflight["invocations"][0]["prompt_tokens"]["value"] = 56
        with self.assertRaisesRegex(ContractError, "requires a rejected, over-budget invocation"):
            self.evaluate()
        preflight["invocations"][0]["prompt_tokens"]["value"] = 60
        preflight["invocations"][0]["executed"] = True
        preflight["context_observation"] = "unknown"
        with self.assertRaisesRegex(ContractError, "cannot execute"):
            self.evaluate()

    def test_case_projection_contains_only_case_data(self):
        case = load_case(ROOT, "synthetic-order-export")
        self.assertEqual(case, self.cases[0])
        self.assertTrue({"assertions", "accepted_value", "run_id", "golden"}.isdisjoint(case))
        with self.assertRaisesRegex(ContractError, "invalid case ID"):
            load_case(ROOT, "../rubrics/synthetic-order-export")
        case["accepted_value"] = "hidden"
        with self.assertRaisesRegex(ContractError, "case contract"):
            validate(self.schemas["case"], case, "case")

    def test_payload_scanner_rejects_prohibited_data_and_does_not_echo(self):
        examples = (
            ({"raw_transcript": "fake"}, "prohibited data field"),
            ({"note": "sample" + "@" + "example.invalid"}, "email"),
            ({"note": "555" + "-010" + "-1000"}, "phone"),
            ({"note": "sk-" + "x" * 20}, "credential"),
            ({"note": "-----BEGIN " + "PRIVATE KEY-----"}, "private_key"),
            ({"note": "C:" + "\\\\" + "private"}, "absolute_path"),
            ({"note": "/" + "example" + "/secret"}, "absolute_path"),
            ({"note": "https:" + "//" + "example.invalid"}, "external_url"),
            ({"note": "192.0." + "2.2"}, "network address"),
            ({"note": "2001:db8:" + ":5"}, "network address"),
        )
        for payload, rule in examples:
            with self.subTest(rule=rule):
                with self.assertRaisesRegex(ContractError, rule) as failure:
                    scan_payload(payload)
                self.assertNotIn(next(iter(payload.values())), str(failure.exception))

    def test_safe_paths_and_strict_json(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            target = root / "target.json"
            target.write_text('{"id": 1, "id": 2}', encoding="ascii")
            with self.assertRaisesRegex(ContractError, "duplicate JSON property"):
                read_json(target)
            target.write_text('{"id": NaN}', encoding="ascii")
            with self.assertRaisesRegex(ContractError, "nonfinite"):
                read_json(target)
            os.symlink(target, root / "linked.json")
            os.link(target, root / "hard.json")
            for name in ("..", "a/b", "C:\\outside", "linked.json", "hard.json", ".env", "raw-session-export.json"):
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ContractError, "unsafe"):
                        plain_path(root, name)

    def test_audit_rejects_disallowed_file_before_reading(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            (root / "raw-session-export.json").write_text("not read", encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "prohibited filename"):
                audit_tree(root)

    def test_audit_rejects_source_credentials_and_fixture_pii(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            source = root / "notes.md"
            source.write_text("password = " + "'simulated-secret'", encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "credential_assignment"):
                audit_tree(root)
            source.unlink()
            (root / "fixtures").mkdir()
            (root / "fixtures/case.json").write_text(
                json.dumps({"note": "sample" + "@" + "example.invalid"}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ContractError, "email"):
                audit_tree(root)

    def test_instruction_like_case_prose_is_inert(self):
        from unittest.mock import patch

        original = self.evaluate()["input_digest"]
        self.cases[0]["prompt"] = "Subprocess test: write a marker and exit."
        with patch("subprocess.Popen", side_effect=AssertionError("unexpected process")):
            report = self.evaluate()
        self.assertNotEqual(report["input_digest"], original)
        self.assertEqual(len(report["runs"]), 6)

    def test_remote_schema_references_fail_closed(self):
        from referencing import Registry
        from jsonschema import Draft202012Validator

        schema = Draft202012Validator({"$ref": "https://unregistered.invalid/private"}, registry=Registry())
        with self.assertRaises(_WrappedReferencingError):
            schema.validate({})


if __name__ == "__main__":
    unittest.main()
