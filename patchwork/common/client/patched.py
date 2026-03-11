from __future__ import annotations

import contextlib
from typing_extensions import Any, Dict, Optional


class PatchedClient:
    """
    Client for the patched.codes managed service.
    Handles telemetry and API key management.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def send_public_telemetry(self, patchflow_name: str, inputs: Dict[str, Any]) -> None:
        """Send anonymous telemetry about patchflow usage."""
        # Telemetry is best-effort; never raise on failure
        try:
            import requests

            safe_inputs = {k: v for k, v in inputs.items() if "api_key" not in k.lower()}
            requests.post(
                "https://app.patched.codes/api/v1/telemetry",
                json={"patchflow": patchflow_name, "inputs": safe_inputs},
                timeout=2,
            )
        except Exception:
            pass

    @contextlib.contextmanager
    def patched_telemetry(self, patchflow_name: str, output_dict: Dict[str, Any]):
        """Context manager that captures patchflow output for telemetry."""
        try:
            yield output_dict
        finally:
            pass
