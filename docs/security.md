
# Phase 1B security controls

## Fixture intake

Echo-Pi's proposal from channel message 83 was rejected. It describes a profile lookup and contains a request identifier instead of a diagnostic incident with individually identified evidence observations. The content was treated as inert text and was excluded from the repository. No endpoint was contacted. The `synthetic-order-export` case, rubric and six synthetic runs are Forge-authored replacement data. Every observation is invented.

## Offline boundary

Bootstrap retrieves only the pinned public runtime and wheel artifacts. During validation the launcher uses a fresh Linux network namespace, read-only project inputs and wheelhouse, an ephemeral temporary directory and a separate scratch directory. GitHub Actions configures `--network none`, `--pull never`, no extra capabilities, no socket or credential mounts, and no artifact upload. Local WSL uses Bubblewrap with fresh namespaces and a cleared environment. A probe checks loopback-only interfaces, no external IPv4 or IPv6 routes and unreachable documentation-range endpoints. A connected namespace or unverified denial blocks validation. CI rejects lock entries outside the pinned package-and-hash form. The offline installer uses only wheelhouse and verifies hashes, including the bootstrap pip wheel before importing it.

## Data and gold boundary

JSON is parsed as data, with duplicate keys, nonfinite values, unexpected fields, disallowed filenames, symlinks/reparse points, hard links and out-of-contract references rejected. Scans detect common credential forms, raw session fields, email/phone/IP patterns and local paths. Errors report rule names, without echoing contents. Pattern checks can miss sensitive or obfuscated values and can reject benign text. Review new fixture data before committing it.

The `agent-input` CLI exposes only the public case contract. Neither rubric, golden outputs, other runs nor the checkout is mounted in the isolated agent-view test. The agent-view probe also requires no external route, host interop or Docker mount. Future controlled runs must keep gold in evaluator-only storage and enforce an equivalent allowlist for agent input, mount access and network destinations. Public fixtures/expected results may already be seen by a trained model or by an agent with repository access. Use held-out private gold and separately reviewed provider/tool controls before claiming meaningful live scores. Phase 1B does not execute agents or verify a future Cloud runner's isolation.

## Remediation Implemented ? Phase 1B.1

The bootstrap wheel filename is derived from the single exact pip version and SHA-256 entry in bootstrap.lock. Verification occurs before the wheel path is returned to the installer. Malformed, ambiguous, missing and mismatched inputs stop execution. Regression coverage includes changing the lock version without editing the installer.

The publication scanner applies credential, email, phone, user-home path, network-address and credential-bearing URL checks to every source and documentation file in the validation mount. Fixtures additionally retain strict field and payload checks. Operational public URLs and sandbox paths are supported. Only documentation IP ranges are accepted as source test destinations; that exception does not suppress adjacent PII or secrets. No entire file or directory is exempted within the reviewed project mount.

Regression tests plant invented sensitive-looking values in code, Markdown, text, workflow YAML and fixture JSON. The scanner reports rule names without disclosing the offending text. Pattern-based detection still needs human publication review for names, encoded data, obfuscation and other unrecognized formats. The harness mount list defines the files scanned during CI; the complete local Git inventory must be checked before publishing any additional file.

The sanitized aggregate usage snapshot is recorded in usage-evidence-2026-11-27.md with dashboard provenance and scope limitations. It is outside fixtures and benchmark run records. The Phase 1C roadmap and previous synthetic golden expectations remain preserved.

## Verification Evidence ? Phase 1B.1

Local test commands and results are recorded in phase1b1-validation.md. GitHub Actions and Docker runtime verification remain BLOCKED. Atlas independently reviews the changed files and local evidence after this implementation handoff.
