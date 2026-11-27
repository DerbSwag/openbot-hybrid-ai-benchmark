
"""Command-line entry points. JSON output is written to stdout."""

import argparse
import sys
from pathlib import Path

from benchmark.contracts import ContractError, canonical, load_case, load_dataset, validators
from benchmark.evaluator import evaluate, normalized


ROOT = Path(__file__).resolve().parents[1]


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("evaluate", help="validate and score the synthetic dataset")
    agent_input = commands.add_parser("agent-input", help="export just the approved case fields")
    agent_input.add_argument("case_id")
    args = parser.parse_args(argv)
    try:
        if args.command == "agent-input":
            data = normalized(load_case(root, args.case_id))
        else:
            schemas = validators(root)
            data = evaluate(*load_dataset(root, schemas), schemas)
    except ContractError as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 2
    sys.stdout.buffer.write(canonical(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
