
# OpenBot Hybrid AI Benchmark

Phase 1B provides an offline evaluator for three benchmark modes: Single Local Agent (`local`), Single Cloud Agent (`cloud`), and Hybrid Multi-Agent (`hybrid`). The repository contains synthetic incident data and expected telemetry to verify the evaluator. Benchmark observations collected under an approved protocol belong to a separate report group.

## Start locally

Supported foundation target: Linux x86_64, CPython 3.14. The Windows development path uses Ubuntu WSL 2 with unprivileged user namespaces and Bubblewrap (`bwrap`). Dependency bootstrap is the network-enabled step. Use an existing Python installation with pip:

```powershell
$env:PIP_CONFIG_FILE = 'NUL'
python -I -B -m pip --isolated --disable-pip-version-check --no-cache-dir download --retries 0 --index-url https://pypi.org/simple --only-binary=:all: --require-hashes --no-deps --platform manylinux2014_x86_64 --implementation cp --python-version 3.14 --abi cp314 --dest .bootstrap/wheelhouse -r bootstrap.lock -r requirements.lock
wsl -d Ubuntu --exec bash scripts/validate-local-wsl.sh
```

Run these commands from the repository root. The second command verifies the network namespace, installs only the hashed wheels from disk, runs the tests, evaluates twice, and checks that the reports match byte for byte. It then runs a separate sandbox containing only the agent input and the isolation probe. Results stay under ignored `.bootstrap/validation.*` directories. The harness stops if an isolation check fails.

The evaluator CLI exposes `evaluate` (report JSON to stdout) and `agent-input synthetic-order-export` (approved case projection to stdout). The harness invokes both with isolated Python and the verified dependency directory. A rejected input exits with status `2`. A reported benchmark failure is data and does not change the CLI exit status. Unit test or isolation failures stop the validation harness.

## Design and evidence

- [Contracts](docs/contracts.md) covers the versioned case, rubric, run and report.
- [Methodology](docs/methodology.md) defines all eight metrics and how to reproduce the golden arithmetic.
- [Security](docs/security.md) documents isolation, the fixture intake decision, and boundaries of these controls.
- [Licensing](docs/licenses.md) lists pins, notices and redistribution obligations.
- [Roadmap](docs/roadmap.md) preserves Phase 1C as a separate, approval-gated proposal.

GitHub Actions has separate bootstrap and network-isolated validation steps. The Docker offline validation workflow passed on the head of [PR #1](https://github.com/DerbSwag/openbot-hybrid-ai-benchmark/pull/1), on its pull-request run, and on the merge commit on `main`. See the [validation record](docs/phase1b1-validation.md) for run IDs and scope. The project license is [MIT](LICENSE).
