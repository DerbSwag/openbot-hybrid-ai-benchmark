
"""Load versioned contracts and reject unsafe input before evaluation."""

import ipaddress
import json
import re
import stat
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class ContractError(ValueError):
    """The input failed a bounded, user-visible validation check."""


KINDS = ("case", "rubric", "run", "report")
ID = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
MAX_FILE_BYTES = 1_000_000
MAX_RECORDS = 500

# Diagnostics emit rule names only. Offending values may contain private data.
SOURCE_RULES = {
    "private_key": re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    "credential": re.compile(
        r"\b(?:gh[pousr]_[a-z0-9_]{16,}|github_pat_[a-z0-9_]{16,}|"
        r"sk-(?:proj-)?[a-z0-9_-]{16,}|AKIA[A-Z0-9]{16})\b", re.I
    ),
    "authorization": re.compile(r"\bBearer\s+[a-z0-9_./+=-]{12,}", re.I),
    "credential_assignment": re.compile(
        r'''\b(?:api[_-]?key|access[_-]?token|password|set-cookie|authorization)\s*["']?\s*[:=]\s*["'][^"'\s]{8,}["']''',
        re.I,
    ),
}

PAYLOAD_RULES = {
    **SOURCE_RULES,
    "email": re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I),
    "phone": re.compile(r"(?<!\w)(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?|\d{2,4}[ -])\d{3,4}[ -]\d{4}(?!\w)"),
    "external_url": re.compile(r"\b(?:https?|file|ftp)://", re.I),
    "absolute_path": re.compile(
        r"(?<![\w/])(?:[A-Z]:[\\/]|\\\\|/(?:[a-z0-9_.-]+/)+[a-z0-9_.-]+)", re.I
    ),
    "profile_lookup": re.compile(r"\b(?:retrieve|lookup|fetch|find|search for)\b.{0,40}\b(?:user profile|email address)\b", re.I),
}



def scan_publishable_text(text):
    """Scan every source/document file; permit only public operational references."""
    for name, pattern in SOURCE_RULES.items():
        if pattern.search(text):
            raise ContractError(f"prohibited source pattern: {name}")
    for name in ("email", "phone"):
        if PAYLOAD_RULES[name].search(text):
            raise ContractError(f"prohibited source pattern: {name}")
    patterns = {
        "personal_path": r"(?:[a-z]:[\\/]+users[\\/]+[a-z0-9_.-]+|/(?:home|Users)/[a-z0-9_.-]+|/mnt/[a-z]/Users/[a-z0-9_.-]+)",
        "url_credentials": r"(?:https?|ftp)://[^\s/]+:[^\s/]+@",
        "url_secret": r"[?&](?:api[_-]?key|access[_-]?token|password|secret|token)=[^&\s\"']+",
        "unquoted_secret": r"\b(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*(?![\"'\s])[\w/+.-]{8,}",
    }
    for name, pattern in patterns.items():
        if re.search(pattern, text, re.I):
            raise ContractError(f"prohibited source pattern: {name}")
    # Documentation ranges are public test destinations used by the isolation
    # probe. No filename or whole-file exceptions bypass the other checks.
    documentation_ranges = tuple(map(ipaddress.ip_network, (
        "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32",
    )))
    candidates = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b|(?<!\w)[0-9a-fA-F:]{2,39}(?!\w)", text)
    for candidate in candidates:
        if "." not in candidate and ":" not in candidate:
            continue
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if not any(address.version == net.version and address in net for net in documentation_ranges):
            raise ContractError("prohibited source pattern: network address")


def blocked_name(name):
    name = name.lower()
    return (
        name == ".env" or name.startswith(".env.") or "session-export" in name
        or "credentials" in name
        or name.endswith((".pem", ".key", ".pfx", ".p12", ".kubeconfig", ".jsonl", ".log"))
    )


def plain_path(root, *parts):
    """Only resolve project-relative, fixed paths and regular entries."""
    if root.is_symlink() or root.is_junction() or not root.is_dir():
        raise ContractError("unsafe or missing repository root")
    path = root
    for part in parts:
        if not isinstance(part, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", part):
            raise ContractError("unsafe path component")
        if part in (".", "..") or blocked_name(part):
            raise ContractError("unsafe path component")
        path = path / part
        try:
            info = path.lstat()
        except OSError:
            raise ContractError("missing required input path") from None
        if (
            path.is_symlink() or path.is_junction()
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
        ):
            raise ContractError("unsafe input path type")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise ContractError("unsafe hard-linked input")
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON property")
        result[key] = value
    return result


def _reject_constant(_):
    raise ContractError("nonfinite JSON number")


def scan_payload(data):
    """A conservative denylist for synthetic payloads, not a PII classifier."""
    if isinstance(data, dict):
        for key, value in data.items():
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized in {
                "password", "token", "apikey", "accesstoken", "authorization", "cookie",
                "sessionexport", "sessionid", "rawlog", "rawlogs", "rawtranscript",
                "transcript", "email", "username", "fullname", "phonenumber", "address",
                "path", "endpoint", "url", "command", "shell",
            }:
                raise ContractError("prohibited data field")
            scan_payload(value)
    elif isinstance(data, list):
        for value in data:
            scan_payload(value)
    elif isinstance(data, str):
        if any(ord(char) < 32 for char in data):
            raise ContractError("prohibited control character in payload")
        for name, pattern in PAYLOAD_RULES.items():
            if pattern.search(data):
                raise ContractError(f"prohibited data pattern: {name}")
        for candidate in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", data):
            try:
                ipaddress.IPv4Address(candidate)
            except ValueError:
                continue
            raise ContractError("prohibited data pattern: network address")
        for candidate in re.findall(r"(?<!\w)[0-9a-fA-F:]{2,39}(?!\w)", data):
            if ":" not in candidate:
                continue
            try:
                ipaddress.IPv6Address(candidate)
            except ValueError:
                continue
            raise ContractError("prohibited data pattern: network address")


def read_json(path, *, payload=False):
    try:
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise ContractError("input must be a bounded JSON file")
        with path.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ContractError("input must be a bounded JSON file")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_constant)
        if payload:
            scan_payload(data)
        return data
    except (OSError, UnicodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError("invalid JSON input") from None


def canonical(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _offline_registry(schemas):
    return Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas.values())


def _validator(schema, registry):
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=registry)


def validators(root):
    schemas = {kind: read_json(plain_path(root, "schemas", "v1", kind + ".schema.json")) for kind in KINDS}
    registry = _offline_registry(schemas)
    return {kind: _validator(schema, registry) for kind, schema in schemas.items()}


def case_validator(root):
    schema = read_json(plain_path(root, "schemas", "v1", "case.schema.json"))
    return _validator(schema, _offline_registry({"case": schema}))


def validate(validator, data, kind):
    error = next(validator.iter_errors(data), None)
    if error is not None:
        # Do not echo input values, unknown field names, or arbitrary paths.
        raise ContractError(f"{kind} contract: {error.validator} constraint failed")


def unique(items, key, description):
    index = {}
    for item in items:
        identity = key(item)
        if identity in index:
            raise ContractError(f"duplicate {description} ID")
        index[identity] = item
    return index


def case_key(item):
    return item["case_id"], item.get("case_revision", item.get("revision"))


def load_case(root, case_id):
    if not ID.fullmatch(case_id):
        raise ContractError("invalid case ID")
    path = plain_path(root, "fixtures", "synthetic", "cases", case_id + ".json")
    data = read_json(path, payload=True)
    validate(case_validator(root), data, "case")
    if data["case_id"] != case_id:
        raise ContractError("case filename and ID differ")
    unique(data["evidence"], lambda item: item["id"], "evidence")
    return data


def _rows(root, subdir, validator, kind):
    folder = plain_path(root, "fixtures", "synthetic", *subdir)
    rows = []
    for entry in sorted(folder.iterdir()):
        if len(rows) >= MAX_RECORDS:
            raise ContractError("too many records")
        path = plain_path(root, "fixtures", "synthetic", *subdir, entry.name)
        if path.suffix != ".json":
            raise ContractError("unexpected fixture entry")
        data = read_json(path, payload=True)
        validate(validator, data, kind)
        if kind == "case" and path.stem != data["case_id"]:
            raise ContractError("case filename and ID differ")
        if kind == "run" and data["mode"] != subdir[-1]:
            raise ContractError("run mode and fixture directory differ")
        rows.append(data)
    return rows


def load_dataset(root, schema):
    cases = _rows(root, ("cases",), schema["case"], "case")
    rubrics = _rows(root, ("rubrics",), schema["rubric"], "rubric")
    runs = [
        data
        for mode in ("local", "cloud", "hybrid")
        for data in _rows(root, ("runs", mode), schema["run"], "run")
    ]
    if len(runs) > MAX_RECORDS:
        raise ContractError("too many run records")
    return cases, rubrics, runs
