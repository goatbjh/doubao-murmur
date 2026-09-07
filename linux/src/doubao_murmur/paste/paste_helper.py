"""Copy text to clipboard and simulate Shift+Insert paste.

Mirrors PasteHelper.swift.

Methods (in priority order):
1. wl-copy (Wayland clipboard) + ydotool (paste simulation)
2. xclip/xsel (X11 clipboard) + xdotool (X11 paste simulation)
3. GTK clipboard API as last resort
"""

from __future__ import annotations

import logging
import subprocess
import time

from doubao_murmur.config import PASTE_DELAY
from doubao_murmur.host_tools import command_candidates

logger = logging.getLogger(__name__)

class PasteHelper:
    """Copy text to clipboard and simulate paste keystroke."""

    @staticmethod
    def copy_and_paste(text: str) -> None:
        if not text:
            return
        PasteHelper._copy_to_clipboard(text)
        time.sleep(PASTE_DELAY)
        PasteHelper._simulate_paste()

    @staticmethod
    def copy_only(text: str) -> None:
        if not text:
            return
        PasteHelper._copy_to_clipboard(text)

    @staticmethod
    def _copy_to_clipboard(text: str) -> None:
        """Copy text to system clipboard."""
        # Try Wayland first
        for command in command_candidates("wl-copy"):
            try:
                subprocess.run(
                    command,
                    input=text.encode(),
                    check=True,
                    timeout=3,
                )
                logger.info("Copied to clipboard via wl-copy")
                return
            except Exception as e:
                logger.warning("wl-copy failed: %s", e)

        # Try X11
        for command in command_candidates("xclip"):
            try:
                subprocess.run(
                    command + ["-selection", "clipboard"],
                    input=text.encode(),
                    check=True,
                    timeout=3,
                )
                logger.info("Copied to clipboard via xclip")
                return
            except Exception as e:
                logger.warning("xclip failed: %s", e)

        # Try xsel
        for command in command_candidates("xsel"):
            try:
                subprocess.run(
                    command + ["--clipboard", "--input"],
                    input=text.encode(),
                    check=True,
                    timeout=3,
                )
                logger.info("Copied to clipboard via xsel")
                return
            except Exception as e:
                logger.warning("xsel failed: %s", e)

        # GTK clipboard as last resort
        try:
            from gi.repository import Gdk

            display = Gdk.Display.get_default()
            if display:
                clipboard = display.get_clipboard()
                clipboard.set(text)
                logger.info("Copied to clipboard via GTK")
        except Exception as e:
            logger.error("All clipboard methods failed: %s", e)

    @staticmethod
    def _simulate_paste() -> None:
        """Simulate Shift+Insert for the focused window."""
        # Try ydotool (works on both Wayland and X11)
        # Linux input keycodes: 42=LEFTSHIFT, 110=INSERT
        ydotool_keys = ["42:1", "110:1", "110:0", "42:0"]
        for command in command_candidates("ydotool"):
            try:
                subprocess.run(
                    command + ["key"] + ydotool_keys,
                    check=True,
                    timeout=3,
                )
                logger.info("Paste simulated via ydotool (Shift+Insert)")
                return
            except Exception as e:
                logger.warning("ydotool failed: %s", e)

        # Try wtype (Wayland virtual keyboard)
        wtype_args = ["-M", "shift", "-k", "Insert", "-m", "shift"]
        for command in command_candidates("wtype"):
            try:
                subprocess.run(
                    command + wtype_args,
                    check=True,
                    timeout=3,
                )
                logger.info("Paste simulated via wtype (Shift+Insert)")
                return
            except Exception as e:
                logger.warning("wtype failed: %s", e)

        # Try xdotool (X11 only)
        for command in command_candidates("xdotool"):
            try:
                subprocess.run(
                    command + ["key", "shift+Insert"],
                    check=True,
                    timeout=3,
                )
                logger.info("Paste simulated via xdotool (Shift+Insert)")
                return
            except Exception as e:
                logger.warning("xdotool failed: %s", e)

        logger.error("No paste simulation method available")
        logger.info(
            "Text was copied to clipboard but could not auto-paste. "
            "Install ydotool or wtype for auto-paste."
        )
