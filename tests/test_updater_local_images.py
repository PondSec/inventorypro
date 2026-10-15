import http.client
import os
import pytest
import updater


def test_local_running_image_is_immutable_rollback_target(monkeypatch):
    image = 'sha256:' + 'a' * 64
    values = iter(['container', image, ''])
    monkeypatch.setattr(updater, 'command', lambda *args: next(values))
    assert updater.active_image_reference() == image


def test_local_rollback_skips_registry_pull(monkeypatch):
    calls = []
    monkeypatch.setattr(updater, 'command', lambda *args: calls.append(args))
    updater.deploy_image('sha256:' + 'a' * 64)
    assert len(calls) == 1
    assert '--no-build' in calls[0][0]
    assert calls[0][1]['INVENTORY_IMAGE'] == 'sha256:' + 'a' * 64


def test_signed_manifest_cannot_select_local_image(monkeypatch):
    with pytest.raises(updater.UpdateError):
        updater.validate_manifest({'schemaVersion': 1, 'version': '1.2.3',
            'image': 'sha256:' + 'a' * 64, 'signatureAlgorithm': 'ed25519', 'signature': ''})


def test_compose_project_comes_from_actual_sidecar_label(monkeypatch):
    monkeypatch.delenv('COMPOSE_PROJECT_NAME', raising=False)
    monkeypatch.setenv('HOSTNAME', 'a' * 12)
    monkeypatch.setattr(updater, 'command', lambda *args: 'inventar-system')
    updater.configure_compose_project()
    assert os.environ['COMPOSE_PROJECT_NAME'] == 'inventar-system'


def test_explicit_compose_project_is_preserved(monkeypatch):
    monkeypatch.setenv('COMPOSE_PROJECT_NAME', 'customer-project')
    monkeypatch.setattr(updater, 'command', lambda *args: pytest.fail('No Docker inspection required'))
    updater.configure_compose_project()
    assert os.environ['COMPOSE_PROJECT_NAME'] == 'customer-project'


def test_missing_or_invalid_compose_project_fails_closed(monkeypatch):
    monkeypatch.delenv('COMPOSE_PROJECT_NAME', raising=False)
    monkeypatch.setenv('HOSTNAME', 'not-a-container')
    with pytest.raises(updater.UpdateError):
        updater.configure_compose_project()


@pytest.mark.parametrize('error', [ConnectionResetError(), http.client.RemoteDisconnected()])
def test_health_retries_transient_container_startup_disconnects(monkeypatch, error):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    outcomes = iter([error, Response()])
    def open_url(*args, **kwargs):
        value = next(outcomes)
        if isinstance(value, Exception): raise value
        return value
    monkeypatch.setattr(updater.urllib.request, 'urlopen', open_url)
    monkeypatch.setattr(updater.time, 'sleep', lambda _: None)
    assert updater.wait_for_health()
