#!/usr/bin/env python3
"""Prepare a private Docker Compose installation without overwriting existing data."""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def prepare_environment(directory: Path, port: int = 5000) -> bool:
    if not 1 <= port <= 65535:
        raise ValueError('Port muss zwischen 1 und 65535 liegen.')
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / '.env'
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file():
            raise ValueError('.env muss eine reguläre Datei sein.')
        return False
    values = {
        'APP_SECRET_KEY': secrets.token_urlsafe(48),
        'BACKUP_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'INVENTORY_LINKS_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'INVENTORY_PORT': str(port), 'INVENTORY_BIND_ADDRESS': '127.0.0.1',
        'INVENTORY_UPDATER_ENABLED': '0',
    }
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write('# Private installation configuration; keep with encrypted backups.\n')
        for key, value in values.items():
            handle.write(f'{key}={value}\n')
        handle.flush()
        os.fsync(handle.fileno())
    return True


def check_port(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        try:
            listener.bind(('127.0.0.1', port))
        except OSError as error:
            raise ValueError(f'Port {port} ist belegt. Anderen Port mit --port wählen; laufende Instanzen nicht beenden.') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--start', action='store_true', help='Nach Vorbereitung Docker Compose starten')
    args = parser.parse_args()
    try:
        if not shutil.which('docker'):
            raise ValueError('Docker fehlt. Docker Engine oder Docker Desktop mit Compose installieren.')
        subprocess.run(['docker', 'compose', 'version'], check=True, capture_output=True, timeout=20)
        subprocess.run(['docker', 'info'], check=True, capture_output=True, timeout=20)
        created = prepare_environment(ROOT, args.port)
        print('Private .env erzeugt.' if created else 'Vorhandene .env unverändert erhalten.')
        subprocess.run(['docker', 'compose', 'config', '--quiet'], cwd=ROOT, check=True, timeout=20)
        if args.start:
            # Existing deployments are intentionally not stopped or reconfigured.
            existing = subprocess.run(['docker', 'compose', 'ps', '--all', '--quiet', 'app'], cwd=ROOT, check=True, capture_output=True, text=True, timeout=20)
            if existing.stdout.strip():
                raise ValueError('Bestehende Installation erkannt. Für Updates den dokumentierten Updateworkflow verwenden.')
            resolved = subprocess.run(['docker', 'compose', 'config', '--format', 'json'], cwd=ROOT, check=True, capture_output=True, text=True, timeout=20)
            actual_port = int(json.loads(resolved.stdout)['services']['app']['ports'][0]['published'])
            check_port(actual_port)
            subprocess.run(['docker', 'compose', 'up', '--detach', '--build', '--wait', 'app'], cwd=ROOT, check=True)
            print(f'Inventory Pro: http://localhost:{actual_port}')
        print('Erstzugang: docker compose exec app cat /data/instance/initial_admin_credentials.txt')
        print('Beim ersten Login ein eigenes Passwort setzen. .env und Datenvolume geschützt sichern.')
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f'Einrichtung abgebrochen: {error}\n')


if __name__ == '__main__':
    main()
