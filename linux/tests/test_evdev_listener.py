"""Regression tests for evdev hot-plug and device failure handling."""

import os
import struct
import threading
import time

import doubao_murmur.hotkey.evdev_listener as evdev_module
from doubao_murmur.hotkey.evdev_listener import (
    EVENT_FORMAT,
    EV_KEY,
    KEY_RIGHTALT,
    EvdevListener,
)


def test_listener_drops_device_after_eof(monkeypatch):
    """A removed input device must not turn into a full-core read loop."""
    read_fd, write_fd = os.pipe()
    os.close(write_fd)
    device_path = f"/proc/self/fd/{read_fd}"

    listener = EvdevListener(lambda: None, lambda: None)
    monkeypatch.setattr(
        listener, "_find_keyboard_devices", lambda: [device_path]
    )

    read_calls = 0
    real_read = os.read

    def counted_read(fd, size):
        nonlocal read_calls
        read_calls += 1
        return real_read(fd, size)

    monkeypatch.setattr(evdev_module.os, "read", counted_read)

    try:
        assert listener.start()
        time.sleep(0.05)
        listener.stop()
    finally:
        os.close(read_fd)

    assert read_calls <= 2


def test_listener_recovers_after_device_replacement(monkeypatch):
    """Hot-plugging a replacement keyboard must restore the global hotkey."""
    dead_read_fd, dead_write_fd = os.pipe()
    os.close(dead_write_fd)
    dead_path = f"/proc/self/fd/{dead_read_fd}"

    live_read_fd, live_write_fd = os.pipe()
    live_path = f"/proc/self/fd/{live_read_fd}"
    os.write(
        live_write_fd,
        struct.pack(EVENT_FORMAT, 0, 0, EV_KEY, KEY_RIGHTALT, 1)
        + struct.pack(EVENT_FORMAT, 0, 0, EV_KEY, KEY_RIGHTALT, 0),
    )

    toggled = threading.Event()
    listener = EvdevListener(toggled.set, lambda: None)
    scans = 0

    def devices():
        nonlocal scans
        scans += 1
        return [dead_path] if scans == 1 else [live_path]

    monkeypatch.setattr(listener, "_find_keyboard_devices", devices)
    monkeypatch.setattr(evdev_module, "RESCAN_INTERVAL", 0.01, raising=False)

    try:
        assert listener.start()
        assert toggled.wait(timeout=0.25)
        listener.stop()
    finally:
        os.close(dead_read_fd)
        os.close(live_read_fd)
        os.close(live_write_fd)
