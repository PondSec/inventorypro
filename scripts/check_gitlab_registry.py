#!/usr/bin/env python3
"""CI-only synthetic registry round trip; no app image, release or deployment."""
import hashlib
import json
import os
import re
from urllib.parse import urlsplit

import requests


def check_registry():
    registry = os.environ.get('CI_REGISTRY', '')
    image = os.environ.get('CI_REGISTRY_IMAGE', '')
    password = os.environ.get('CI_REGISTRY_PASSWORD', '')
    username = os.environ.get('CI_REGISTRY_USER', '')
    revision = os.environ.get('CI_COMMIT_SHA', '')
    if registry != 'gitlab.pondsec.com' or image.lower() != 'gitlab.pondsec.com/pondsec/inventorypro':
        raise ValueError('Expected Inventory Pro GitLab registry configuration is unavailable.')
    if not password or not username or not re.fullmatch('[a-f0-9]{40}', revision):
        raise ValueError('This registry check requires an authenticated GitLab CI job.')
    repository = 'pondsec/inventorypro/qa-registry'
    root = 'https://' + registry
    session = requests.Session()
    def send(method, url, *, expected, **kwargs):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != registry:
            raise ValueError('Registry redirected outside the approved HTTPS host.')
        response = session.request(method, url, timeout=30, allow_redirects=False, **kwargs)
        if response.status_code not in expected:
            raise RuntimeError(f'Registry {method} check failed with HTTP {response.status_code}.')
        return response
    scope = f'repository:{repository}:pull,push'
    authorization = send('GET', root + '/jwt/auth', expected={200},
        params={'service':'container_registry', 'scope':scope}, auth=(username,password)).json()
    token = authorization.get('token') or authorization.get('access_token')
    if not token:
        raise RuntimeError('Registry authentication did not return a token.')
    headers = {'Authorization':'Bearer ' + token}
    config = json.dumps({'architecture':'amd64', 'os':'linux', 'config':{},
        'rootfs':{'type':'layers','diff_ids':[]},
        'history':[{'created_by':'Inventory Pro synthetic connectivity check','empty_layer':True}]},
        separators=(',',':')).encode()
    digest = 'sha256:' + hashlib.sha256(config).hexdigest()
    upload = send('POST', root + f'/v2/{repository}/blobs/uploads/', expected={202}, headers=headers)
    location = upload.headers['Location']
    if location.startswith('/'):
        location = root + location
    send('PUT', location + ('&' if '?' in location else '?') + 'digest=' + digest,
        expected={201}, headers={**headers,'Content-Type':'application/octet-stream'}, data=config)
    manifest = json.dumps({'schemaVersion':2,'mediaType':'application/vnd.oci.image.manifest.v1+json',
        'config':{'mediaType':'application/vnd.oci.image.config.v1+json','digest':digest,'size':len(config)},
        'layers':[]}, separators=(',',':')).encode()
    manifest_digest = 'sha256:' + hashlib.sha256(manifest).hexdigest()
    endpoint = root + f'/v2/{repository}/manifests/qa-{revision[:12]}'
    send('PUT', endpoint, expected={201}, headers={**headers,
        'Content-Type':'application/vnd.oci.image.manifest.v1+json'}, data=manifest)
    # The public project must be readable without CI credentials by real updaters.
    anonymous = send('GET', root + '/jwt/auth', expected={200},
        params={'service':'container_registry','scope':f'repository:{repository}:pull'}).json()
    public_headers = {'Authorization':'Bearer ' + (anonymous.get('token') or anonymous.get('access_token'))}
    downloaded = send('GET', root + f'/v2/{repository}/manifests/{manifest_digest}',
        expected={200}, headers={**public_headers,'Accept':'application/vnd.oci.image.manifest.v1+json'})
    if downloaded.content != manifest:
        raise RuntimeError('Registry manifest digest round trip failed.')
    downloaded_config = send('GET', root + f'/v2/{repository}/blobs/{digest}', expected={200}, headers=public_headers)
    if downloaded_config.content != config:
        raise RuntimeError('Registry blob round trip failed.')
    print('GitLab registry: authenticated synthetic upload and anonymous digest download passed.')


if __name__ == '__main__':
    check_registry()
