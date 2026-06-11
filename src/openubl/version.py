"""Runtime version sync check."""

import json
import urllib.request

from . import __version__


def check_api_version(base_url: str = "http://localhost:8000") -> dict:
    """Fetch /api/v1/version and compare with the local SDK version."""
    req = urllib.request.Request(f"{base_url}/api/v1/version")
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
    api_version = data["version"]
    return {
        "ok": api_version == __version__,
        "sdk_version": __version__,
        "api_version": api_version,
    }
