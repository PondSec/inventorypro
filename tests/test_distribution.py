"""Guard the source archive and Docker image against missing runtime modules."""
import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_application_package_import_is_distributed():
    tree = ast.parse((ROOT / 'app.py').read_text())
    modules = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        and node.module.startswith('inventorypro')
    }
    assert modules
    for module in modules:
        assert importlib.util.find_spec(module) is not None, module


def test_docker_distributes_package_and_migrations():
    dockerfile = (ROOT / 'Dockerfile').read_text()
    assert 'COPY inventorypro ./inventorypro' in dockerfile
    assert 'COPY migrations ./migrations' in dockerfile
    assert list((ROOT / 'migrations').glob('[0-9][0-9][0-9]_*.sql'))
    assert 'requirements.lock' in dockerfile
