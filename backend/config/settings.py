from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
FRONTEND = WORKSPACE / 'frontend'
load_dotenv(ROOT / '.env', override=False)
DATA = ROOT / 'data'
ASSETS = DATA / 'assets'
RELEASES = DATA / 'releases'
SAMPLES = DATA / 'samples'
for directory in (DATA, ASSETS, RELEASES):
    directory.mkdir(parents=True, exist_ok=True)

SERVER_URL = os.getenv('AGENT_SERVER_URL', 'http://127.0.0.1:2024')
OCR_URL = os.getenv('OCR_URL', os.getenv('OCR_API_URL', 'http://36.103.199.11:5002/process'))


def office_converter():
    value = os.getenv('DOC_CONVERTER', '')
    if not value:
        return None
    path = Path(value)
    return str((ROOT / path).resolve() if not path.is_absolute() else path)


def database_options():
    return dict(host=os.environ['GAUSSDB_HOST'], port=int(os.environ['GAUSSDB_PORT']),
                user=os.environ['GAUSSDB_USER'], password=os.environ['GAUSSDB_PASSWORD'],
                dbname=os.environ['GAUSSDB_DATABASE'], connect_timeout=8)
