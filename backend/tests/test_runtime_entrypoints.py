"""The portable runtime resolves configured server entries outside the project.

Docs MCP: /langsmith/monorepo-support and /langsmith/custom-checkpointer.
Reference MCP: AsyncSqliteSaver (langgraph.checkpoint.sqlite), installed 3.1.2.
Only import locations change; the official Server keeps lifecycle ownership.
"""
import json
from pathlib import Path
import subprocess
import sys


BACKEND = Path(__file__).resolve().parents[1]


def test_configured_server_entries_import_from_external_working_directory(tmp_path):
    code = '''
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

root = Path(sys.argv[1]).resolve()
with patch('dotenv.load_dotenv', return_value=False):
    import backend
    config = json.loads((root / 'langgraph.json').read_text(encoding='utf-8'))
    graph_module, graph_name = config['graphs']['workorder-agent'].split(':')
    graph = getattr(importlib.import_module(graph_module), graph_name)
    http_module, http_name = config['http']['app'].split(':')
    app = getattr(importlib.import_module(http_module), http_name)
    checkpoint_path, checkpoint_name = config['checkpointer']['path'].split(':')
    spec = importlib.util.spec_from_file_location('_entry_checkpointer', root / checkpoint_path)
    checkpoint_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checkpoint_module)

assert Path(backend.__file__).resolve() == root / '__init__.py'
assert root / 'src' not in [Path(path).resolve() for path in sys.path]
assert callable(graph) and callable(getattr(checkpoint_module, checkpoint_name))
paths = app.openapi()['paths']
assert '/api/tasks' in paths and '/api/tasks/{task_id}/export' in paths
print(json.dumps({'backend': str(Path(backend.__file__).resolve()), 'routes': len(paths)}))
'''
    result = subprocess.run([sys.executable, '-B', '-c', code, str(BACKEND)],
                            cwd=tmp_path, capture_output=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    imported = json.loads(result.stdout)
    assert Path(imported['backend']) == BACKEND / '__init__.py'
    assert imported['routes'] >= 19
