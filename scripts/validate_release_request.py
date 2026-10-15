#!/usr/bin/env python3
"""Gate an explicit dev release against the exact authoritative GitLab commit."""
import json
import os
import re
import subprocess
from pathlib import Path


def validate_request(request):
    if not isinstance(request, dict) or set(request) != {'version'}:
        raise ValueError('Release request must contain exactly a version.')
    version = request['version']
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('A stable numeric semantic version is required.')
    return version


def main():
    version = validate_request(json.loads(Path('.release/request.json').read_text()))
    if os.environ.get('GITHUB_REF') != 'refs/heads/dev':
        raise ValueError('Only dev release requests are allowed.')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if source != os.environ.get('GITHUB_SHA'):
        raise ValueError('Checkout differs from triggering commit.')
    subprocess.run(['git', 'fetch', '--no-tags', 'https://gitlab.pondsec.com/PondSec/inventorypro.git', 'dev'], check=True)
    authoritative = subprocess.check_output(['git', 'rev-parse', 'FETCH_HEAD'], text=True).strip()
    # Allow later dev documentation fixes, but never a source absent from GitLab dev.
    subprocess.run(['git', 'merge-base', '--is-ancestor', source, authoritative], check=True)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'version={version}\n')
    print(f'Verified GitLab dev source {source}; preparing {version}, no live feed publication.')


if __name__ == '__main__':
    main()
