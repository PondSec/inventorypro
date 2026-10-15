"""Guard the source archive and Docker image against missing runtime modules."""
import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_clean_tracked_source_imports_without_untracked_workspace_files(tmp_path):
    subprocess.run(['git', 'checkout-index', '--all', '--prefix=' + str(tmp_path) + '/'],
                   cwd=ROOT, check=True, capture_output=True)
    result = subprocess.run([sys.executable, '-c',
        'import app; from pathlib import Path; assert Path(app.__file__).parent == Path.cwd()'],
        cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_every_application_package_import_is_distributed():
    tree = ast.parse((ROOT / 'app.py').read_text())
    modules = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        and node.module.startswith('inventorypro')
    }
    assert modules
    tracked = set(subprocess.check_output(
        ['git', 'ls-files', '--cached'], cwd=ROOT, text=True,
    ).splitlines())
    for module in modules:
        assert importlib.util.find_spec(module) is not None, module
        path = module.replace('.', '/')
        assert path + '.py' in tracked or path + '/__init__.py' in tracked, module
    assert 'inventorypro/domains/customization/defaults.json' in tracked


def test_docker_distributes_package_and_migrations():
    dockerfile = (ROOT / 'Dockerfile').read_text()
    assert 'COPY inventorypro ./inventorypro' in dockerfile
    assert 'COPY migrations ./migrations' in dockerfile
    assert list((ROOT / 'migrations').glob('[0-9][0-9][0-9]_*.sql'))
    assert 'requirements.lock' in dockerfile
