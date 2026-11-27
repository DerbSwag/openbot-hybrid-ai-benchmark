
#!/bin/sh
set -eu

repo=$1
wheels=$2
scratch=$3
python_bin=$4
export PIP_CONFIG_FILE=/dev/null
tmp=$(mktemp -d)
# The launcher supplies an ephemeral /tmp mount, discarded at sandbox exit.
"$python_bin" -I -B "$repo/scripts/isolation_probe.py"

pip_wheel=$("$python_bin" -I -B "$repo/scripts/verify_bootstrap.py" "$repo/bootstrap.lock" "$wheels")
"$python_bin" -I -B -c 'import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); runpy.run_module("pip", run_name="__main__")' \
  "$pip_wheel" --isolated --disable-pip-version-check --no-cache-dir install --no-index \
  --find-links "$wheels" --require-hashes --only-binary=:all: --no-compile \
  --target "$tmp/deps" -r "$repo/requirements.lock"

license_files=0
for info in "$tmp"/deps/*.dist-info; do
  test -f "$info/METADATA"
  find "$info" -type f \( -iname '*license*' -o -iname '*notice*' -o -iname 'copying*' \) -print | grep -q .
  license_files=$((license_files + 1))
done
test "$license_files" -eq 5
printf 'LICENSE FILES PASS: %s validation wheels include license/notice files\n' "$license_files"

"$python_bin" -I -B "$repo/scripts/runner.py" "$tmp/deps" audit > "$scratch/publication-inventory.txt"
cat "$scratch/publication-inventory.txt"
"$python_bin" -I -B "$repo/scripts/runner.py" "$tmp/deps" test
"$python_bin" -I -B "$repo/scripts/runner.py" "$tmp/deps" evaluate > "$scratch/report.json"
"$python_bin" -I -B "$repo/scripts/runner.py" "$tmp/deps" evaluate > "$tmp/report.json"
cmp "$scratch/report.json" "$tmp/report.json"
printf 'REPRODUCIBILITY PASS: byte-identical CLI reports\n'
"$python_bin" -I -B "$repo/scripts/runner.py" "$tmp/deps" agent-input synthetic-order-export > "$scratch/agent-input.json"
