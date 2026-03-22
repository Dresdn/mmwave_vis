"""
Tests for ZHA binding-timeout detection logic.

When a ZHA device is selected, the backend starts a timer. If no
zha_event arrives from that device within BINDING_TIMEOUT_S seconds,
a ``zha_binding_warning`` socket.io event is emitted to alert the user
that the 0xFC32 cluster binding may be missing.

These tests verify:
  - The timer starts when a device is selected.
  - The timer is cancelled when data arrives from the monitored device.
  - The warning fires when the timer expires.
  - Switching devices resets the timer.
  - Events from *other* devices do not cancel the timer.
"""

import threading
import time
from unittest.mock import MagicMock, call


# ---------------------------------------------------------------------------
# Minimal stub of ZHAClient binding-timer logic
# ---------------------------------------------------------------------------

class _BindingTimerStub:
    """
    Extracts only the binding-timer state machine from ZHAClient so we can
    test it without MQTT, Flask-SocketIO, or a real HA WebSocket.
    """

    def __init__(self, timeout: float = 0.3):
        self.BINDING_TIMEOUT_S = timeout
        self._binding_timer: threading.Timer | None = None
        self._ieee: str | None = None
        self._topic: str | None = None
        self.socketio = MagicMock()

    # -- mirrors ZHAClient._start_binding_timer --
    def _start_binding_timer(self):
        self._cancel_binding_timer()
        self._binding_timer = threading.Timer(
            self.BINDING_TIMEOUT_S, self._emit_binding_warning
        )
        self._binding_timer.daemon = True
        self._binding_timer.start()

    # -- mirrors ZHAClient._cancel_binding_timer --
    def _cancel_binding_timer(self):
        if self._binding_timer is not None:
            self._binding_timer.cancel()
            self._binding_timer = None

    # -- mirrors ZHAClient._emit_binding_warning --
    def _emit_binding_warning(self):
        ieee = self._ieee
        if not ieee:
            return
        self.socketio.emit("zha_binding_warning", {"ieee": ieee, "show": True})

    # -- mirrors ZHAClient._clear_binding_warning --
    def _clear_binding_warning(self):
        self._cancel_binding_timer()
        self.socketio.emit("zha_binding_warning", {"show": False})

    # -- simplified set_device --
    def set_device(self, ieee: str):
        self._ieee = ieee
        self._topic = f"zha/{ieee}"
        self._start_binding_timer()

    # -- simplified data-arrived path --
    def on_data_received(self, ieee: str):
        if ieee == self._ieee:
            self._clear_binding_warning()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_warning_fires_when_no_data():
    """Timer expires → warning emitted with show=True."""
    stub = _BindingTimerStub(timeout=0.15)
    stub.set_device("aa:bb:cc:dd")
    time.sleep(0.3)
    stub.socketio.emit.assert_any_call(
        "zha_binding_warning", {"ieee": "aa:bb:cc:dd", "show": True}
    )


def test_warning_cancelled_when_data_arrives():
    """Data arrives before timeout → no warning, only show=False dismiss."""
    stub = _BindingTimerStub(timeout=0.4)
    stub.set_device("aa:bb:cc:dd")
    time.sleep(0.05)
    stub.on_data_received("aa:bb:cc:dd")
    time.sleep(0.5)

    # Should have emitted show=False (dismiss), but never show=True (warning)
    calls = stub.socketio.emit.call_args_list
    warning_calls = [c for c in calls if c == call("zha_binding_warning", {"ieee": "aa:bb:cc:dd", "show": True})]
    dismiss_calls = [c for c in calls if c == call("zha_binding_warning", {"show": False})]
    assert len(warning_calls) == 0
    assert len(dismiss_calls) == 1


def test_switching_devices_resets_timer():
    """Selecting a new device cancels the old timer and starts a fresh one."""
    stub = _BindingTimerStub(timeout=0.15)
    stub.set_device("device_A")
    time.sleep(0.05)
    # Switch before first timer fires
    stub.set_device("device_B")
    time.sleep(0.25)

    calls = stub.socketio.emit.call_args_list
    # Should warn about device_B (timer expired), NOT device_A
    warning_calls_a = [c for c in calls if c == call("zha_binding_warning", {"ieee": "device_A", "show": True})]
    warning_calls_b = [c for c in calls if c == call("zha_binding_warning", {"ieee": "device_B", "show": True})]
    assert len(warning_calls_a) == 0
    assert len(warning_calls_b) == 1


def test_other_device_data_does_not_cancel_timer():
    """Data from a different device should not cancel the timer."""
    stub = _BindingTimerStub(timeout=0.15)
    stub.set_device("target_device")
    time.sleep(0.05)
    stub.on_data_received("other_device")  # wrong device
    time.sleep(0.25)

    calls = stub.socketio.emit.call_args_list
    warning_calls = [c for c in calls if c == call("zha_binding_warning", {"ieee": "target_device", "show": True})]
    assert len(warning_calls) == 1


def test_no_warning_if_ieee_cleared():
    """If _ieee is None when timer fires, no warning is emitted."""
    stub = _BindingTimerStub(timeout=0.15)
    stub.set_device("aa:bb:cc:dd")
    stub._ieee = None
    time.sleep(0.3)

    calls = stub.socketio.emit.call_args_list
    warning_calls = [c for c in calls if c[0][0] == "zha_binding_warning" and c[0][1].get("show") is True]
    assert len(warning_calls) == 0


def test_cancel_is_idempotent():
    """Calling _cancel_binding_timer when no timer exists does not crash."""
    stub = _BindingTimerStub()
    stub._cancel_binding_timer()  # no timer set — should be a no-op
    stub._cancel_binding_timer()  # again — still fine


def test_data_received_emits_dismiss():
    """on_data_received emits show=False to dismiss any visible banner."""
    stub = _BindingTimerStub(timeout=1.0)
    stub.set_device("aa:bb:cc:dd")
    stub.on_data_received("aa:bb:cc:dd")

    stub.socketio.emit.assert_any_call("zha_binding_warning", {"show": False})


def test_timer_does_not_fire_after_cancel():
    """Explicitly cancelling the timer prevents the warning."""
    stub = _BindingTimerStub(timeout=0.15)
    stub.set_device("aa:bb:cc:dd")
    stub._cancel_binding_timer()
    time.sleep(0.3)

    calls = stub.socketio.emit.call_args_list
    warning_calls = [c for c in calls if c[0][0] == "zha_binding_warning" and c[0][1].get("show") is True]
    assert len(warning_calls) == 0
