
"""Fail closed unless validation has a loopback-only Linux network namespace."""

import argparse
import errno
import json
import os
import socket
import sys
from pathlib import Path


def verify_network():
    if sys.platform != "linux":
        raise SystemExit("BLOCKED: Linux network namespace is required")
    interfaces = [name for _, name in socket.if_nameindex()]
    ipv4_routes = Path("/proc/net/route").read_text(encoding="ascii").splitlines()[1:]
    ipv6_routes = Path("/proc/net/ipv6_route").read_text(encoding="ascii").splitlines()
    if interfaces != ["lo"] or ipv4_routes or any(row.split()[-1] != "lo" for row in ipv6_routes):
        raise SystemExit("BLOCKED: non-loopback interface or route detected")
    for family, address in ((socket.AF_INET, "192.0.2.1"), (socket.AF_INET6, "2001:db8::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as connection:
                connection.settimeout(1)
                result = connection.connect_ex((address, 443))
        except OSError as error:
            result = error.errno
        if result not in {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EAFNOSUPPORT}:
            raise SystemExit("BLOCKED: egress denial could not be verified")
    print("ISOLATION PASS: loopback only; no external routes; IPv4/IPv6 probes denied")


def verify_agent_view(path):
    for forbidden in (
        "/repo", "/work", "/wheelhouse", "/var/run/docker.sock", "/mnt/c",
        "/workspace", "/github/workspace", "/.git",
    ):
        if Path(forbidden).exists():
            raise SystemExit("BLOCKED: full checkout or host resource is visible to agent")
    if any(os.environ.get(key) for key in ("GITHUB_TOKEN", "GH_TOKEN", "WSL_INTEROP")):
        raise SystemExit("BLOCKED: credential or host interop environment is visible")
    case = json.loads(Path(path).read_bytes())
    projected = {
        "schema_version", "classification", "case_id", "revision", "category",
        "prompt", "evidence", "constraints", "requested_deliverables",
    }
    if (
        set(case) != projected or case["classification"] != "synthetic"
        or any(set(item) != {"id", "fact"} for item in case["evidence"])
    ):
        raise SystemExit("BLOCKED: agent input contains unexpected fields")
    if {item.name for item in Path(path).parent.iterdir()} != {Path(path).name}:
        raise SystemExit("BLOCKED: agent input mount contains additional files")
    print("GOLD ISOLATION PASS: only projected case available; repository not mounted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-input")
    args = parser.parse_args()
    verify_network()
    if args.agent_input:
        verify_agent_view(args.agent_input)


if __name__ == "__main__":
    main()
