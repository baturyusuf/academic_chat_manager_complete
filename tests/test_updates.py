import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from academic_chat_manager import update_service as updates


def signed(version="0.1.10", data=b"installer"):
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    payload = json.dumps({"schema": 1, "repository": updates.REPO, "asset": updates.INSTALLER, "version": version,
                          "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}).encode()
    envelope = json.dumps({"payload": base64.b64encode(payload).decode(), "signature": base64.b64encode(key.sign(payload)).decode()}).encode()
    return envelope, public


def test_semantic_versions():
    assert updates.version_tuple("v0.1.10") > updates.version_tuple("0.1.9")
    for version in ("0.1", "v0.1.0-beta", "00.1.0"):
        with pytest.raises(ValueError):
            updates.version_tuple(version)


def test_signed_package(tmp_path):
    envelope, public = signed()
    update = updates.verify_manifest(envelope, public, "0.1.9", "0.1.10")
    package = tmp_path / updates.INSTALLER
    package.write_bytes(b"installer")
    updates.verify_package(package, update)
    package.write_bytes(b"bad bytes")
    with pytest.raises(ValueError):
        updates.verify_package(package, update)


def test_reject_downgrade_and_tampering():
    envelope, public = signed()
    with pytest.raises(ValueError):
        updates.verify_manifest(envelope, public, "0.1.10")
    with pytest.raises(ValueError):
        updates.verify_manifest(envelope, public, "0.1.9", "0.2.0")
    tampered = json.loads(envelope)
    tampered["signature"] = base64.b64encode(bytes(64)).decode()
    with pytest.raises(InvalidSignature):
        updates.verify_manifest(json.dumps(tampered).encode(), public, "0.1.9")


def test_check_stable_release(monkeypatch):
    envelope, public = signed()
    release = {"tag_name": "v0.1.10", "assets": [{"name": updates.INSTALLER}, {"name": updates.MANIFEST}]}
    monkeypatch.setattr(updates, "_read", lambda url: json.dumps(release).encode() if url == updates.LATEST else envelope)
    assert updates.check_update("0.1.9", public).version == "0.1.10"
    assert updates.check_update("0.1.10", public) is None
    release["prerelease"] = True
    assert updates.check_update("0.1.9", public) is None
    assert updates.check_update("0.1.9", "") is None


def test_untrusted_redirect():
    with pytest.raises(ValueError):
        updates._trusted_url("https://example.com/setup.exe")
    with pytest.raises(ValueError):
        updates._trusted_url("http://github.com/setup.exe")
