"""JSON response serialization shared by the HTTP adapters."""
from fastapi.responses import Response

from backend.infrastructure.repository import dumps


def response(value, status=200, **headers):
    return Response(dumps(value), status_code=status, media_type='application/json', headers=headers)
