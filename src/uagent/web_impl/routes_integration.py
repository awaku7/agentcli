"""Versioned, read-only integration API for external UAG management services."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi.responses import JSONResponse

from ..runtime.instance_identity import get_instance_id, get_instance_name
from .app import app

INTEGRATION_API_VERSION = "1"
SUPPORTED_ENTRYPOINTS = ("cli", "web", "gui", "a2a")


def _uag_version() -> str:
    try:
        return version("uag")
    except PackageNotFoundError:
        return "unknown"


@app.get("/api/admin/integration/v1/manifest", include_in_schema=False)
async def get_integration_manifest():
    """Describe this UAG installation to an authorized management client.

    The application middleware protects this path with the configured global
    administrator policy. The instance ID is an identifier, not a credential.
    """
    try:
        instance_id = get_instance_id()
        instance_name = get_instance_name(instance_id)
    except (OSError, RuntimeError, ValueError):
        return JSONResponse(
            status_code=503,
            content={"error": "UAG integration identity is unavailable"},
        )

    return {
        "api_version": INTEGRATION_API_VERSION,
        "instance": {
            "id": instance_id,
            "name": instance_name,
        },
        "software": {
            "name": "uag",
            "version": _uag_version(),
        },
        "supported_entrypoints": list(SUPPORTED_ENTRYPOINTS),
        "capabilities": ["instance.identity.read"],
    }
