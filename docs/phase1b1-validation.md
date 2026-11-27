# Phase 1B.1 validation record

## Scope and findings

Phase 1B baseline evidence remains 22 passing tests and the original deterministic report hash. The approved follow-up addresses the hardcoded pip wheel filename and the source/document PII scanning gap. The implementation keeps existing synthetic data, metric formulas and Phase 1C roadmap intact.

## Commands

Run from the checkout root in PowerShell. Existing hash-verified wheels are reused.

- wsl -d Ubuntu --exec bash scripts/validate-local-wsl.sh
- wsl -d Ubuntu --exec bash -n scripts/validate-local-wsl.sh
- wsl -d Ubuntu --exec sh -n scripts/validate-offline.sh
- git -c core.autocrlf=false diff --check
- git status --short --branch --untracked-files=all
- git diff --cached --name-only

The complete offline harness includes affected regression tests and the existing suite. The full WSL Bubblewrap harness passed 28 tests in 0.841 seconds, including all six new hardening tests and the 22 existing tests. Scanner and verified-wheel installation passed. Network probes saw loopback only, no external routes, and denied IPv4/IPv6 egress. The separate agent-view sandbox passed gold isolation. CLI reports matched byte for byte with SHA-256 3b97f39b9572d68a92a1eaec74826fb3811c71d679ab1bfc78b925dfd4e0d13a.

During development the scanner stopped on its own path-regex text; the user-home pattern was corrected and self-scanning coverage added. A regression also caught an unquoted secret in fixture prose; all fixture text now receives the common publication scan before strict payload validation. Each verification after a code correction was manually invoked; there are no retry loops.

The harness emits publication-inventory.txt with a relative filename and SHA-256 for each scanned file. Local validation also blocks unexpected top-level entries before constructing its mount list. The Git inventory was compared against this manifest before handoff, including every modified and untracked publishable file. The manifest's final document hash is recorded locally after the document update to avoid a self-referential digest. Bootstrap downloads are unnecessary for this change.

## Remaining gates

Docker and GitHub Actions runtime verification remain BLOCKED. Pattern scanning cannot prove absence of all sensitive content. The aggregate dashboard observation does not provide actual billing or isolated benchmark telemetry. Independent Atlas review is pending.

## Complete publication inventory

Paths are relative to the repository. This inventory includes the unchanged MIT license. M is modified from HEAD; ?? is untracked; tracked is unchanged. The offline manifest supplies exact SHA-256 values for every row, including this document.

| Path | Git status |
| --- | --- |
| .gitattributes | ?? |
| .github/workflows/offline-validation.yml | ?? |
| .gitignore | ?? |
| LICENSE | tracked |
| README.md | M |
| benchmark/__init__.py | ?? |
| benchmark/cli.py | ?? |
| benchmark/contracts.py | ?? |
| benchmark/evaluator.py | ?? |
| benchmark/metrics.py | ?? |
| bootstrap.lock | ?? |
| docs/contracts.md | ?? |
| docs/licenses.md | ?? |
| docs/methodology.md | ?? |
| docs/phase1b1-validation.md | ?? |
| docs/roadmap.md | ?? |
| docs/security.md | ?? |
| docs/usage-evidence-2026-11-27.md | ?? |
| fixtures/synthetic/cases/synthetic-order-export.json | ?? |
| fixtures/synthetic/golden/summary.json | ?? |
| fixtures/synthetic/rubrics/synthetic-order-export.json | ?? |
| fixtures/synthetic/runs/cloud/cloud-matched.json | ?? |
| fixtures/synthetic/runs/cloud/cloud-partial.json | ?? |
| fixtures/synthetic/runs/hybrid/hybrid-partial.json | ?? |
| fixtures/synthetic/runs/hybrid/hybrid-rejected.json | ?? |
| fixtures/synthetic/runs/local/local-success.json | ?? |
| fixtures/synthetic/runs/local/local-unknown.json | ?? |
| requirements.lock | ?? |
| schemas/v1/case.schema.json | ?? |
| schemas/v1/report.schema.json | ?? |
| schemas/v1/rubric.schema.json | ?? |
| schemas/v1/run.schema.json | ?? |
| scripts/audit_tree.py | ?? |
| scripts/isolation_probe.py | ?? |
| scripts/runner.py | ?? |
| scripts/validate-local-wsl.sh | ?? |
| scripts/validate-offline.sh | ?? |
| scripts/verify_bootstrap.py | ?? |
| tests/test_foundation.py | ?? |
| tests/test_hardening.py | ?? |
