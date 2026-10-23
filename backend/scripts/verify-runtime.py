"""Check the bundled interpreter, dependency paths, and native extensions offline."""

import json
import ssl
import sqlite3
import sys
import sysconfig
from importlib.metadata import version
from pathlib import Path

import dotenv
import cryptography
import fastmcp
import langchain
import langchain_core
import langchain_openai
import mcp
import obs
import certifi
import pydantic_core
import pythoncom
import pywintypes
import win32api
import backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter


project_root = Path(__file__).resolve().parents[1]
runtime_root = project_root / "bishi1"
workspace_root = project_root.parent
assert Path(backend.__file__).resolve() == project_root / "__init__.py"
assert Path(sys.executable).resolve() == (runtime_root / "python.exe").resolve()
assert Path(sys.prefix).resolve() == runtime_root.resolve()
assert sys.flags.isolated == 1
assert Path(sysconfig.get_path("purelib")).resolve().is_relative_to(runtime_root)

for module in (
    dotenv,
    langchain,
    langchain_core,
    langchain_openai,
    pydantic_core,
    fastmcp,
    mcp,
    obs,
    certifi,
    cryptography,
    pythoncom,
    pywintypes,
    win32api,
):
    assert Path(module.__file__).resolve().is_relative_to(runtime_root)
for entry in sys.path:
    assert entry
    path = Path(entry).resolve()
    assert path == workspace_root or path.is_relative_to(project_root)

with sqlite3.connect(":memory:") as connection:
    assert connection.execute("SELECT 1").fetchone() == (1,)
assert ssl.create_default_context() is not None
assert callable(create_agent)
assert callable(MCPAdapter)
cipher = AESGCM(AESGCM.generate_key(bit_length=128))
nonce = bytes(12)
assert cipher.decrypt(nonce, cipher.encrypt(nonce, b"portable-runtime", None), None) == b"portable-runtime"
obs_client = obs.ObsClient(access_key_id='offline-test', secret_access_key='offline-test',
                           server='https://obs.example.invalid', ssl_verify=certifi.where(),
                           max_retry_count=0)
try:
    # Signing is local; this makes no upload/download or OCR request.
    assert obs_client.createSignedUrl('GET', bucketName='offline-test',
                                      objectKey='sample.pdf', expires=300)['signedUrl'].startswith('https://')
finally:
    obs_client.close()

print(
    json.dumps(
        {
            "runtime": str(runtime_root),
            "backend_package": str(Path(backend.__file__).resolve()),
            "python": sys.version.split()[0],
            "isolated": bool(sys.flags.isolated),
            "dependencies": {
                package: version(package)
                for package in (
                    "langchain",
                    "langchain-core",
                    "langchain-openai",
                    "python-dotenv",
                    "fastmcp",
                    "mcp",
                    "esdk-obs-python",
                    "cryptography",
                    "pywin32",
                )
            },
            "native_extensions": "ok",
            "obs_local_signing": "ok",
            "project_external_workdir": Path.cwd().resolve() != project_root,
        },
        ensure_ascii=True,
    )
)
