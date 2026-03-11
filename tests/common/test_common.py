"""
Tests for patchwork.common utilities.
"""
from __future__ import annotations


class TestPatchedClient:
    def test_no_key_is_disabled(self):
        from patchwork.common.client.patched import PatchedClient

        client = PatchedClient(api_key=None)
        assert not client._enabled

    def test_with_key_is_enabled(self):
        from patchwork.common.client.patched import PatchedClient

        client = PatchedClient(api_key="tok_abc")
        assert client._enabled

    def test_send_telemetry_no_key_does_not_raise(self):
        from patchwork.common.client.patched import PatchedClient

        client = PatchedClient(api_key=None)
        # Should not raise even without a network
        client.send_public_telemetry("NullShift", {})

    def test_context_manager_yields_dict(self):
        from patchwork.common.client.patched import PatchedClient

        client = PatchedClient(api_key=None)
        result = {}
        with client.patched_telemetry("NullShift", result) as d:
            d["key"] = "value"
        assert result["key"] == "value"


class TestStepBase:
    def test_missing_input_raises_value_error(self):
        from patchwork.steps.DetectUntestedFunctions.DetectUntestedFunctions import DetectUntestedFunctions

        import pytest
        with pytest.raises((ValueError, KeyError)):
            DetectUntestedFunctions({})

    def test_step_status_default_completed(self):
        from patchwork.steps.DetectUntestedFunctions.DetectUntestedFunctions import DetectUntestedFunctions
        from patchwork.step import StepStatus

        step = DetectUntestedFunctions({"pr_diff": ""})
        # Run it so status is updated
        step.run()
        assert step.status == StepStatus.COMPLETED
