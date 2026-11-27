"""Derive and verify the pinned pip wheel before importing it."""

import hashlib
import re
import sys
from pathlib import Path


def verified_wheel(lock, directory):
    try:
        text = lock.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        raise SystemExit("BLOCKED: bootstrap lock is unreadable") from None
    match = re.fullmatch(r"pip==([0-9]+(?:\.[0-9]+)+) --hash=sha256:([0-9a-f]{64})", text)
    if match is None:
        raise SystemExit("BLOCKED: bootstrap lock must contain one pinned pip hash")
    wheel = directory / f"pip-{match[1]}-py3-none-any.whl"
    try:
        if directory.is_symlink() or wheel.is_symlink() or not wheel.is_file():
            raise OSError
        with wheel.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError:
        raise SystemExit("BLOCKED: bootstrap wheel is missing or unreadable") from None
    if digest != match[2]:
        raise SystemExit("BLOCKED: bootstrap wheel hash differs")
    return wheel


def main():
    lock, directory = map(Path, sys.argv[1:])
    wheel = verified_wheel(lock, directory)
    print("BOOTSTRAP HASH PASS: pip wheel", file=sys.stderr)
    print(wheel)


if __name__ == "__main__":
    main()
