import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('validate_release_request', Path(__file__).resolve().parents[1] / 'scripts/validate_release_request.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_explicit_stable_release_request():
    assert module.validate_request({'version': '0.2.0'}) == '0.2.0'
    assert module.validate_request({'version': '0.3.0'}) == '0.3.0'


@pytest.mark.parametrize('payload', [None, [], {}, {'version': '0.2.0', 'deploy': True},
                                    {'version': 'v0.2.0'}, {'version': '0.2.0\nfoo=bar'},
                                    {'version': '$(whoami)'}, {'version': 2}, {'version': '0.2.0-beta'}])
def test_invalid_release_requests_cannot_inject_workflow_outputs(payload):
    with pytest.raises(ValueError):
        module.validate_request(payload)
