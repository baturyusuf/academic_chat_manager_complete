"""Prepare build metadata and sign installer. Private key is CI-only."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import tomllib

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
REPO = "baturyusuf/academic_chat_manager_complete"
INSTALLER = "AcademicChatManager-Setup.exe"


def key():
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(os.environ["ACM_RELEASE_SIGNING_KEY"], validate=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "sign"])
    parser.add_argument("--run-number", type=int)
    parser.add_argument("--version")
    args = parser.parse_args()
    if args.action == "prepare":
        base = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        major, minor, patch = map(int, base.split("."))
        version = f"{major}.{minor}.{patch + (args.run_number or 0)}"
        public = ""
        if args.run_number is not None:
            public = base64.b64encode(key().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        (ROOT / "_build_info.py").write_text(f"APP_VERSION = {version!r}\nUPDATE_PUBLIC_KEY = {public!r}\n", encoding="utf-8")
        print(version)
    else:
        installer = ROOT / "dist" / INSTALLER
        with installer.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        payload = json.dumps({"schema": 1, "repository": REPO, "asset": INSTALLER, "version": args.version,
                              "size": installer.stat().st_size, "sha256": digest}, sort_keys=True, separators=(",", ":")).encode()
        envelope = {"payload": base64.b64encode(payload).decode(), "signature": base64.b64encode(key().sign(payload)).decode()}
        (ROOT / "dist" / "update-manifest.json").write_text(json.dumps(envelope), encoding="utf-8")


if __name__ == "__main__":
    main()
