"""Download every pinned source file and (re)write data/raw/MANIFEST.json.

    python -I -m fineval.fetch            # download missing files, hash everything
    python -I -m fineval.fetch --verify   # only check hashes against the manifest
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

from .sources.registry import PAPERS, SOURCES, url

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "MANIFEST.json"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def raw_path(source: str, path: str) -> Path:
    return RAW / source / path


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def verify(manifest=None) -> list:
    """Return a list of problems; empty means every manifest file is present and unchanged."""
    manifest = manifest or load_manifest()
    bad = []
    for key, rec in manifest.items():
        p = RAW / key
        if not p.exists():
            bad.append(f"missing: {key}")
        elif sha256(p) != rec["sha256"]:
            bad.append(f"hash mismatch: {key}")
    return bad


def download(u: str, dest: Path):
    for attempt in range(3):
        try:
            r = requests.get(u, timeout=120)
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        bad = verify()
        print("\n".join(bad) or f"OK: {len(load_manifest())} files match the manifest")
        sys.exit(1 if bad else 0)

    manifest = load_manifest()
    for source, s in SOURCES.items():
        for path in s["files"]:
            key = f"{source}/{path}"
            dest = raw_path(source, path)
            if not dest.exists():
                print("download", key, flush=True)
                download(url(source, path), dest)
            digest = sha256(dest)
            old = manifest.get(key)
            if old and old["sha256"] != digest:
                sys.exit(f"{key}: file changed since it was pinned; refusing to overwrite the manifest")
            manifest[key] = old or {
                "source": source, "repo": s["repo"], "commit": s["commit"], "path": path,
                "url": url(source, path), "licence": s["licence"], "sha256": digest,
                "bytes": dest.stat().st_size, "retrieved": dt.date.today().isoformat(),
            }
    for name, u in PAPERS.items():
        key = f"papers/{name}.pdf"
        dest = RAW / key
        if not dest.exists():
            print("download", key, flush=True)
            download(u, dest)
        digest = sha256(dest)
        old = manifest.get(key)
        if old and old["sha256"] != digest:
            sys.exit(f"{key}: file changed since it was pinned; refusing to overwrite the manifest")
        manifest[key] = old or {"source": "papers", "url": u, "path": key, "licence": "arXiv (author rights)",
                                "sha256": digest, "bytes": dest.stat().st_size,
                                "retrieved": dt.date.today().isoformat()}
        txt = dest.with_suffix(".txt")
        if not txt.exists():
            from pypdf import PdfReader
            pages = PdfReader(dest).pages
            txt.write_text("".join(f"\n\n=== PAGE {i} ===\n" + (p.extract_text() or "")
                                   for i, p in enumerate(pages, 1)), encoding="utf-8")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=1), encoding="utf-8")
    print(f"manifest: {len(manifest)} files")


if __name__ == "__main__":
    main()
