"""Read-only GitHub Releases client and signed installer verification."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

import certifi
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

REPO = "baturyusuf/academic_chat_manager_complete"
LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
INSTALLER = "AcademicChatManager-Setup.exe"
MANIFEST = "update-manifest.json"
MAX_PACKAGE = 250 * 1024 * 1024
MAX_METADATA = 1024 * 1024


def version_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value):
        raise ValueError("Invalid stable version")
    return tuple(map(int, value.removeprefix("v").split(".")))


@dataclass(frozen=True)
class Update:
    version: str
    size: int
    sha256: str
    envelope: bytes
    notes: str = ""

    @property
    def url(self):
        return asset_url(self.version, INSTALLER)


def asset_url(version: str, name: str) -> str:
    version_tuple(version)
    if name not in (INSTALLER, MANIFEST):
        raise ValueError("Unexpected asset")
    return f"https://github.com/{REPO}/releases/download/v{version.removeprefix('v')}/{name}"


def _trusted_url(url):
    p = urlparse(url)
    if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
        raise ValueError("Untrusted update URL")
    if p.hostname not in ("api.github.com", "github.com", "release-assets.githubusercontent.com",
                          "objects.githubusercontent.com", "github-releases.githubusercontent.com"):
        raise ValueError("Untrusted update host")


class _Redirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _trusted_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url):
    _trusted_url(url)
    opener = build_opener(_Redirect(), HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where())))
    return opener.open(Request(url, headers={"User-Agent": "AcademicChatManager-Updater/1"}), timeout=20)


def _read(url):
    with _open(url) as response:
        data = response.read(MAX_METADATA + 1)
    if len(data) > MAX_METADATA:
        raise ValueError("Oversized update metadata")
    return data


def verify_manifest(envelope: bytes, public_key: str, current_version: str, expected_version: str | None = None) -> Update:
    if len(envelope) > MAX_METADATA or not public_key:
        raise ValueError("Missing trust root or oversized manifest")
    document = json.loads(envelope)
    payload = base64.b64decode(document["payload"], validate=True)
    signature = base64.b64decode(document["signature"], validate=True)
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key, validate=True)).verify(signature, payload)
    fields = json.loads(payload)
    version = fields["version"]
    if fields["schema"] != 1 or fields["repository"] != REPO or fields["asset"] != INSTALLER:
        raise ValueError("Unexpected manifest identity")
    if version != version.removeprefix("v") or version_tuple(version) <= version_tuple(current_version):
        raise ValueError("Update is not newer")
    if expected_version is not None and version != expected_version:
        raise ValueError("Release and manifest versions differ")
    size, digest = fields["size"], fields["sha256"]
    if type(size) is not int or not 0 < size <= MAX_PACKAGE or not re.fullmatch("[0-9a-f]{64}", digest):
        raise ValueError("Invalid installer metadata")
    return Update(version, size, digest, envelope)


def check_update(current_version: str, public_key: str) -> Update | None:
    if not public_key:
        return None
    try:
        release = json.loads(_read(LATEST))
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = release["tag_name"]
    if not tag.startswith("v") or version_tuple(tag) <= version_tuple(current_version):
        return None
    names = {a.get("name") for a in release.get("assets", [])}
    if not {INSTALLER, MANIFEST} <= names:
        raise ValueError("Release has no signed installer")
    update = verify_manifest(_read(asset_url(tag, MANIFEST)), public_key, current_version, tag[1:])
    return Update(update.version, update.size, update.sha256, update.envelope, str(release.get("body") or "")[:4000])


def verify_package(path: Path, update: Update):
    if path.stat().st_size != update.size:
        raise ValueError("Installer size differs")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if not hmac.compare_digest(digest.hexdigest(), update.sha256):
        raise ValueError("Installer hash differs")


def download_update(update: Update, directory: Path, progress=None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / INSTALLER
    partial = directory / (INSTALLER + ".part")
    try:
        total = 0
        with _open(update.url) as response, partial.open("xb") as stream:
            while chunk := response.read(256 * 1024):
                total += len(chunk)
                if total > update.size:
                    raise ValueError("Installer exceeds signed size")
                stream.write(chunk)
                if progress:
                    progress(total, update.size)
        verify_package(partial, update)
        partial.replace(target)
        (directory / MANIFEST).write_bytes(update.envelope)
        return target
    finally:
        partial.unlink(missing_ok=True)
