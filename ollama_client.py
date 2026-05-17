"""Ollama HTTP reachability (daemon may run without CLI on PATH)."""

import os
import urllib.error
import urllib.request

_DEFAULT_HOST = "http://127.0.0.1:11434"


def ollama_base_url() -> str:
    return (os.environ.get("OLLAMA_HOST") or _DEFAULT_HOST).rstrip("/")


def ollama_server_reachable(timeout: float = 3.0) -> tuple[bool, str | None]:
    """Return (ok, error_message). Uses the same HTTP API the UI stack relies on."""
    base = ollama_base_url()
    url = f"{base}/api/tags"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return True, None
            return False, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, str(e.reason) if e.reason else str(e)
    except OSError as e:
        return False, str(e)
