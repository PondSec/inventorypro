#!/usr/bin/env python3
"""Create the Ed25519-signed manifest consumed by the Inventory Pro updater."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


VERSION_PATTERN = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
IMAGE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$")


def canonical_manifest(manifest: dict[str, object]) -> bytes:
    unsigned = {key: value for key, value in manifest.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--release-url", default="")
    args = parser.parse_args()

    version = args.version.lstrip("v")
    image = args.image.lower()
    if not VERSION_PATTERN.match(version):
        raise SystemExit("Ungültige semantische Version.")
    if not IMAGE_PATTERN.match(image):
        raise SystemExit("Image muss als unveränderlicher SHA-256-Digest angegeben werden.")
    private_key_value = os.environ.get("INVENTORY_UPDATE_SIGNING_KEY", "")
    if not private_key_value:
        raise SystemExit("INVENTORY_UPDATE_SIGNING_KEY fehlt.")
    private_key = serialization.load_pem_private_key(private_key_value.encode("utf-8"), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit("INVENTORY_UPDATE_SIGNING_KEY muss ein Ed25519-Schlüssel sein.")

    manifest: dict[str, object] = {
        "schemaVersion": 1,
        "version": version,
        "image": image,
        "publishedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "signatureAlgorithm": "ed25519",
    }
    if args.release_url:
        manifest["releaseUrl"] = args.release_url
    signature = private_key.sign(canonical_manifest(manifest))
    manifest["signature"] = base64.b64encode(signature).decode("ascii")
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
