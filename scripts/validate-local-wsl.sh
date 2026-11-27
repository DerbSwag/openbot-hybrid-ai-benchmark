
#!/usr/bin/env bash
# Run from the checkout root in Linux/WSL after the pinned wheel bootstrap.
set -euo pipefail
root=$(pwd -P)
# Reject unexpected top-level project entries instead of silently omitting them.
for entry in "$root"/* "$root"/.[!.]* "$root"/..?*; do
  test -e "$entry" || test -L "$entry" || continue
  entry_name=$(basename "$entry")
  case "$entry_name" in
    .git|.bootstrap|benchmark|fixtures|tests|schemas|scripts|docs|.github|.gitattributes|.gitignore|README.md|LICENSE|bootstrap.lock|requirements.lock) ;;
    *) printf 'BLOCKED: unreviewed top-level project entry\n' >&2; exit 1 ;;
  esac
done
scratch=$(mktemp -d "$root/.bootstrap/validation.XXXXXX")
mkdir "$scratch/agent"
base=(
  --unshare-all --unshare-user --disable-userns --die-with-parent --clearenv
  --ro-bind /usr /usr --symlink usr/lib /lib --symlink usr/lib64 /lib64
  --symlink usr/bin /bin --symlink usr/sbin /sbin
  --proc /proc --dev /dev --tmpfs /tmp --setenv PATH /usr/bin:/usr/sbin
)
validation=()
for path in benchmark fixtures tests schemas scripts docs .github .gitattributes .gitignore README.md LICENSE bootstrap.lock requirements.lock; do
  validation+=(--ro-bind "$root/$path" "/repo/$path")
done
bwrap "${base[@]}" "${validation[@]}" \
  --ro-bind "$root/.bootstrap/wheelhouse" /wheelhouse \
  --bind "$scratch" /scratch \
  /usr/bin/sh /repo/scripts/validate-offline.sh /repo /wheelhouse /scratch /usr/bin/python3
mv "$scratch/agent-input.json" "$scratch/agent/agent-input.json"
bwrap "${base[@]}" \
  --ro-bind "$scratch/agent" /agent-input \
  --ro-bind "$root/scripts/isolation_probe.py" /isolation_probe.py \
  /usr/bin/python3 -I -B /isolation_probe.py --agent-input /agent-input/agent-input.json
sha256sum "$scratch/report.json"
