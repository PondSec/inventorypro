#!/usr/bin/env python3
"""Upload signed preparation artifacts; do not create a release or change latest."""
import os
from pathlib import Path
import urllib.request
from validate_release_request import validate_request


def main():
    version = validate_request({'version': os.environ['RELEASE_VERSION']})
    token = os.environ['INVENTORY_GITLAB_DEPLOY_TOKEN']
    base = f'https://gitlab.pondsec.com/api/v4/projects/21/packages/generic/inventorypro/{version}'
    for name, target in [('gitlab-update-manifest.json', 'update-manifest.json'),
                         (f'inventorypro-{version}.tar.gz', f'inventorypro-{version}.tar.gz')]:
        content = (Path('release-artifacts') / name).read_bytes()
        request = urllib.request.Request(f'{base}/{target}', data=content, method='PUT',
                                         headers={'Deploy-Token': token, 'Content-Type': 'application/octet-stream'})
        with urllib.request.urlopen(request, timeout=120) as response:
            if response.status != 201:
                raise RuntimeError(f'Unexpected package upload status: {response.status}')
        print(f'Prepared GitLab package artifact {target}. Live feed unchanged.')


if __name__ == '__main__':
    main()
