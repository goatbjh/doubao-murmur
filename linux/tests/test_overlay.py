"""Regression tests for bounded overlay animation scheduling."""

from types import SimpleNamespace

import doubao_murmur.ui.overlay as overlay_module
from doubao_murmur.app_state import RecordingState
from doubao_murmur.ui.overlay import Overlay


class _FakeArea:
    def __init__(self):
        self.draw_requests = 0

    def queue_draw(self):
        self.draw_requests += 1


class _FakeCairoContext:
    def __getattr__(self, name):
        return lambda *args: None


def test_recording_animation_uses_one_bounded_timer(monkeypatch):
    """Drawing must not recursively enqueue frames at idle-loop speed."""
    state = SimpleNamespace(
        recording_state=RecordingState.RECORDING,
        transcription_text="",
        error_message=None,
    )
    overlay = Overlay(state)
    overlay._window = object()
    overlay._indicator = _FakeArea()

    timers = []
    idle_callbacks = []
    monkeypatch.setattr(
        overlay_module.GLib,
        "timeout_add",
        lambda interval, callback: timers.append((interval, callback)) or 41,
    )
    monkeypatch.setattr(
        overlay_module.GLib,
        "idle_add",
        lambda callback: idle_callbacks.append(callback) or 42,
    )
    monkeypatch.setattr(overlay_module, "present_overlay", lambda *args: None)

    overlay.show()
    overlay.show()
    overlay._draw_indicator(
        overlay._indicator, _FakeCairoContext(), 14, 14
    )

    assert len(timers) == 1
    assert 16 <= timers[0][0] <= 100
    assert idle_callbacks == []
