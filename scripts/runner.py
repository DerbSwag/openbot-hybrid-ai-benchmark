
"""Load the benchmark from an explicit read-only checkout in isolated Python."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    dependency_dir, operation, *arguments = sys.argv[1:]
    sys.path[:0] = [str(ROOT), dependency_dir]
    if operation == "audit":
        from scripts.audit_tree import main as audit

        return audit(ROOT)
    if operation == "test":
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() and result.testsRun else 1
    from benchmark.cli import main as cli_main

    return cli_main([operation, *arguments], root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
