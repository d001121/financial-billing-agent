"""Local stdio fixture with a receipt proving each real MCP tool execution."""
import json
from pathlib import Path
import sys

from fastmcp import FastMCP

server = FastMCP('host-integration-probe')


@server.tool()
def calculate(a: int, b: int) -> int:
    """Add two integers and write one execution receipt for the integration test."""
    result = a + b
    with Path(sys.argv[1]).open('a', encoding='utf-8') as receipt:
        receipt.write(json.dumps(dict(a=a, b=b, result=result)) + '\n')
    return result


if __name__ == '__main__':
    server.run(transport='stdio', show_banner=False, log_level='ERROR')
