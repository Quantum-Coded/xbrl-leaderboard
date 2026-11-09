"""Rebuilding from the same raw files gives byte-identical outputs (~1 minute)."""
import hashlib

from fineval import build


def _digest():
    return {p.relative_to(build.OUT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(build.OUT.rglob("*")) if p.is_file()}


def test_build_is_deterministic():
    build.main()
    first = _digest()
    build.main()
    assert _digest() == first
