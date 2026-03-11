"""
PatchedClient
=============
Lightweight telemetry/no-op client used by the CLI runner.
When no ``patched_api_key`` is provided all methods are no-ops so NullShift
continues to work fully offline.
"""
from __future__ import annotations

import contextlib
from typing import Any, Optional


class PatchedClient:
    """Minimal telemetry client.  All methods are safe no-ops when key is absent."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self._enabled = bool(api_key)

    def send_public_telemetry(self, patchflow_name: str, inputs: dict) -> None:
        if not self._enabled:
            return
        # Fire-and-forget; swallow any network error
        try:
            import requests

            requests.post(
                "https://api.patched.codes/v1/telemetry",
                json={"patchflow": patchflow_name, "inputs_keys": list(inputs.keys())},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=3,
            )
        except Exception:  # noqa: BLE001
            pass

    @contextlib.contextmanager
    def patched_telemetry(self, patchflow_name: str, output_dict: dict):
        """Context manager that yields output_dict; sends telemetry on exit."""
        try:
            yield output_dict
        finally:
            if self._enabled:
                self.send_public_telemetry(patchflow_name, output_dict)
