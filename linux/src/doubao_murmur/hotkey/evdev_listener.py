"""evdev listener for global hotkeys via /dev/input.

OPTIONAL input method. Requires user to be in the 'input' group.
Listens for:
- Right Alt (KEY_RIGHTALT=100) press-and-release -> toggle
- ESC (KEY_ESC=1) -> cancel
"""

from __future__ import annotations

import glob
import logging
import os
import select
import struct
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# evdev constants
EV_KEY = 0x01
KEY_ESC = 1
KEY_RIGHTALT = 100

# sizeof(struct input_event) on 64-bit Linux
EVENT_SIZE = 24
EVENT_FORMAT = "llHHi"
POLL_TIMEOUT = 0.5
RESCAN_INTERVAL = 2.0


class EvdevListener:
    """Reads /dev/input/event* devices for global hotkeys."""

    def __init__(self, on_toggle, on_escape) -> None:
        self.on_toggle = on_toggle
        self.on_escape = on_escape
        self._thread: threading.Thread | None = None
        self._running = False
        self._right_alt_down = False
        self._other_key_pressed = False

    @staticmethod
    def is_available() -> bool:
        """Check if any key-capable evdev device is accessible."""
        for path in sorted(glob.glob("/dev/input/event*")):
            if not EvdevListener._supports_key_events(path):
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                os.close(fd)
                return True
            except OSError:
                continue
        return False

    @staticmethod
    def _supports_key_events(path: str) -> bool:
        """Return whether sysfs reports EV_KEY support for an event node.

        If sysfs is unavailable (for example in a restricted container), keep
        the device as a compatibility fallback rather than disabling hotkeys.
        """
        capability_path = (
            Path("/sys/class/input")
            / Path(path).name
            / "device/capabilities/ev"
        )
        try:
            event_types = int(
                capability_path.read_text().strip().replace(" ", ""), 16
            )
        except (OSError, ValueError):
            return True
        return bool(event_types & (1 << EV_KEY))

    def start(self) -> bool:
        """Start listening. Returns False if no accessible devices."""
        devices = self._find_keyboard_devices()
        if not devices:
            logger.warning("No accessible evdev input devices found")
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop, args=(devices,), daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _find_keyboard_devices(self) -> list[str]:
        """Find /dev/input/event* files that are readable."""
        accessible = []
        for path in sorted(glob.glob("/dev/input/event*")):
            if not self._supports_key_events(path):
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                os.close(fd)
                accessible.append(path)
            except OSError:
                continue
        return accessible

    def _listen_loop(self, devices: list[str]) -> None:
        """Main read loop using select() for multiplexing."""
        fds: dict[int, str] = {}

        def add_devices(paths: list[str]) -> None:
            open_paths = set(fds.values())
            for path in paths:
                if path in open_paths:
                    continue
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                    fds[fd] = path
                    open_paths.add(path)
                except Exception as error:
                    logger.warning("Cannot open %s: %s", path, error)

        add_devices(devices)

        buf_size = EVENT_SIZE * 16
        next_rescan = time.monotonic() + RESCAN_INTERVAL

        try:
            while self._running:
                now = time.monotonic()
                if now >= next_rescan:
                    add_devices(self._find_keyboard_devices())
                    next_rescan = now + RESCAN_INTERVAL
                timeout = min(
                    POLL_TIMEOUT, max(0.0, next_rescan - time.monotonic())
                )
                readable, _, _ = select.select(
                    list(fds.keys()), [], [], timeout
                )
                for fd in readable:
                    try:
                        data = os.read(fd, buf_size)
                    except (BlockingIOError, InterruptedError):
                        continue
                    except OSError as error:
                        path = fds.pop(fd, "unknown device")
                        logger.warning(
                            "evdev device unavailable, removing %s: %s",
                            path,
                            error,
                        )
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                        continue
                    if not data:
                        path = fds.pop(fd, "unknown device")
                        logger.info("evdev device closed, removing %s", path)
                        try:
                            os.close(fd)
                        except OSError:
                            pass
                        continue
                    for i in range(0, len(data), EVENT_SIZE):
                        if i + EVENT_SIZE > len(data):
                            break
                        event = struct.unpack(
                            EVENT_FORMAT, data[i : i + EVENT_SIZE]
                        )
                        ev_type = event[2]
                        ev_code = event[3]
                        ev_value = event[4]

                        if ev_type != EV_KEY:
                            continue

                        if ev_code == KEY_RIGHTALT:
                            if ev_value == 1:  # press
                                self._right_alt_down = True
                                self._other_key_pressed = False
                            elif ev_value == 0:  # release
                                if (
                                    self._right_alt_down
                                    and not self._other_key_pressed
                                ):
                                    self.on_toggle()
                                self._right_alt_down = False
                        elif ev_code != KEY_RIGHTALT and ev_value == 1:
                            if self._right_alt_down:
                                self._other_key_pressed = True
                            if ev_code == KEY_ESC:
                                self.on_escape()
        finally:
            for fd in fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
