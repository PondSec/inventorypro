#!/usr/bin/env python3
"""Prepare reviewed artifacts; never publish, deploy or change a running updater."""
import argparse
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sign_release_manifest import build_manifest


def prepare_bridge(version, gitlab_image, legacy_image, private_key, public_key):
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError('Ein Ed25519-Signierschlüssel ist erforderlich.')
    actual = private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    if actual.strip() != public_key.strip():
        raise ValueError('Signierschlüssel passt nicht zum bereits ausgelieferten öffentlichen Schlüssel.')
    if not gitlab_image.startswith('gitlab.pondsec.com/pondsec/inventorypro@sha256:'):
        raise ValueError('GitLab-Image muss aus dem freigegebenen Projekt stammen.')
    if not legacy_image.startswith('ghcr.io/pondsec/inventorypro@sha256:'):
        raise ValueError('Alte Updater benötigen ein kompatibles GHCR-Image.')
    release_url = f'https://gitlab.pondsec.com/PondSec/inventorypro/-/releases/v{version}'
    return (build_manifest(version, gitlab_image, private_key, release_url),
            build_manifest(version, legacy_image, private_key, release_url))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--gitlab-image', required=True)
    parser.add_argument('--legacy-image', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--public-key', type=Path, default=Path(__file__).resolve().parents[1] / 'updater/release-public-key.pem')
    args = parser.parse_args()
    encoded = os.environ.get('INVENTORY_UPDATE_SIGNING_KEY', '')
    if not encoded:
        parser.error('INVENTORY_UPDATE_SIGNING_KEY fehlt; es wird kein neuer Ersatzschlüssel erzeugt.')
    key = serialization.load_pem_private_key(encoded.encode(), password=None)
    modern, legacy = prepare_bridge(args.version, args.gitlab_image, args.legacy_image, key, args.public_key.read_bytes())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, manifest in [('update-manifest.json', modern), ('legacy-update-manifest.json', legacy)]:
        target = args.output_dir / name
        with target.open('x', encoding='utf-8') as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
    print('Manifeste vorbereitet. Keine Veröffentlichung oder Installation ausgeführt.')


if __name__ == '__main__':
    main()
