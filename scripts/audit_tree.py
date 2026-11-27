
"""Check the repository paths mounted into offline validation."""

import hashlib
import stat
import sys
from pathlib import Path

from benchmark.contracts import (
    ContractError, MAX_FILE_BYTES, blocked_name, read_json, scan_payload, scan_publishable_text,
)


TEXT_SUFFIXES = {".md", ".json", ".py", ".sh", ".yml", ".yaml", ".lock", ".toml", ".txt", ""}


def audit_tree(root):
    for path in sorted(root.rglob("*")):
        if blocked_name(path.name):
            raise ContractError("prohibited filename in review scope")
        info = path.lstat()
        if (
            path.is_symlink() or path.is_junction()
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ContractError("unsafe linked path in review scope")
        if path.is_dir():
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ContractError("unsafe file type in review scope")
        suffix = path.suffix
        if suffix not in TEXT_SUFFIXES or info.st_size > MAX_FILE_BYTES:
            raise ContractError("unexpected file type or size in review scope")
        source = path.read_text(encoding="utf-8")
        scan_publishable_text(source)
        if path.relative_to(root).parts[0] == "fixtures":
            if suffix != ".json":
                raise ContractError("unexpected fixture file type")
            scan_payload(read_json(path))



def main(root):
    try:
        audit_tree(root)
    except (ContractError, OSError, UnicodeError) as error:
        print(f"BLOCKED: project data scan: {error.args[0] if isinstance(error, ContractError) else 'unreadable input'}",
              file=sys.stderr)
        return 2
    print("PROJECT SCAN PASS: reviewed files and synthetic payloads passed the denylist")
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            print(f"{digest}  {path.relative_to(root).as_posix()}")
    return 0
