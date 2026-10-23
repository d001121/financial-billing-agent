"""Run the isolated native UI fixture with its own persisted server directory."""
from pathlib import Path
import json,os,sys
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root))
runtime=root/'backend/tests/reports/conversation-runtime'
runtime.mkdir(exist_ok=True)
config=runtime/'langgraph.json'
config.write_text(json.dumps({'dependencies':[str(root/'backend')],
    'graphs':{'workorder-agent':'backend.tests.fixtures.conversation_ui:make_graph'},
    'env':str(root/'backend/.env'), 'http':{'app':'backend.tests.fixtures.conversation_ui:app'}}),encoding='utf-8')
os.chdir(runtime)
sys.argv=['langgraph','dev','--config',str(config),'--no-browser','--no-reload','--allow-blocking','--host','127.0.0.1','--port','2025']
from langgraph_cli.cli import cli
cli()
