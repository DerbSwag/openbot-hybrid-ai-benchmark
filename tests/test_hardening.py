"""Regressions use invented sensitive-looking strings only."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from benchmark.contracts import ContractError, scan_publishable_text
from scripts.audit_tree import audit_tree
from scripts.verify_bootstrap import verified_wheel


class HardeningTest(unittest.TestCase):
    def test_bootstrap_uses_lock_version_and_hash(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            lock = root / "bootstrap.lock"
            for version in ("25.2", "99.1.3"):
                with self.subTest(version=version):
                    content = ("invented wheel " + version).encode()
                    wheel = root / f"pip-{version}-py3-none-any.whl"
                    wheel.write_bytes(content)
                    lock.write_text(f"pip=={version} --hash=sha256:{hashlib.sha256(content).hexdigest()}\n")
                    self.assertEqual(verified_wheel(lock, root), wheel)
            wheel.write_bytes(b"changed")
            with self.assertRaisesRegex(SystemExit, "hash differs"):
                verified_wheel(lock, root)

    def test_bootstrap_rejects_invalid_ambiguous_or_missing_lock(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            lock = root / "bootstrap.lock"
            with self.assertRaisesRegex(SystemExit, "unreadable"):
                verified_wheel(lock, root)
            for line in ("pip>=25.2", "pip==../bad", "pip==25.2 --hash=sha256:abc",
                         "pip==25.2\npip==25.3"):
                with self.subTest(line=line):
                    lock.write_text(line)
                    with self.assertRaisesRegex(SystemExit, "one pinned pip hash"):
                        verified_wheel(lock, root)

    def test_scans_code_docs_and_fixtures_without_file_exemptions(self):
        samples = (
            "person" + "@" + "example.invalid",
            "555" + "-010" + "-1000",
            "C:" + "/" + "Users" + "/" + "invented" + "/notes",
            "/" + "home" + "/" + "invented" + "/notes",
            "10." + "22.33.44",
            "fd00:" + ":55",
            "sk-" + "z" * 24,
            "password=" + "invented-secret",
            "https:" + "//" + "synthetic:secret" + "@" + "example.invalid",
            "https:" + "//" + "example.invalid?token=" + "invented-secret",
        )
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            for name in ("README.md", "main.py", "notes.txt", ".github/check.yml", "fixtures/case.json"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                for sample in samples:
                    with self.subTest(name=name, sample_kind=samples.index(sample)):
                        if name.endswith(".json"):
                            import json
                            target.write_text(json.dumps({"note": sample}))
                        else:
                            target.write_text(sample)
                        with self.assertRaises(ContractError):
                            audit_tree(root)
                target.unlink()

    def test_documentation_reference_does_not_exempt_nearby_pii(self):
        safe = "Public " + "https:" + "//pypi.org/simple " + "192.0." + "2.1"
        scan_publishable_text(safe)
        for extra in ("person" + "@" + "example.invalid", "10." + "22.33.44"):
            with self.assertRaises(ContractError):
                scan_publishable_text(safe + " " + extra)

    def test_scanner_source_can_scan_itself(self):
        import benchmark.contracts as contracts
        scan_publishable_text(Path(contracts.__file__).read_text())

    def test_scanner_diagnostics_hide_input(self):
        sample = "person" + "@" + "example.invalid"
        with self.assertRaises(ContractError) as failure:
            scan_publishable_text(sample)
        self.assertNotIn(sample, str(failure.exception))


if __name__ == "__main__":
    unittest.main()
