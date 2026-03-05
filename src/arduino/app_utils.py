"""
Stub implementation of arduino.app_utils for local testing.
Simulates App and Bridge when no real MCU is connected.
"""

import signal
import sys
import time


class _Bridge:
    """Simulates the Arduino Bridge RPC interface."""

    def __init__(self):
        self._provided = {}
        self._remote_handlers = {
            "add_numbers": lambda a, b: a + b,
        }

    def provide(self, name: str, func):
        """Register a Python function callable from the MCU side."""
        self._provided[name] = func

    def call(self, name: str, *args):
        """Call a function on the MCU side (simulated locally)."""
        handler = self._remote_handlers.get(name)
        if handler is None:
            raise RuntimeError(f"Remote function '{name}' not found (stub mode)")
        return handler(*args)


class _App:
    """Simulates the Arduino App runner."""

    def run(self, user_loop=None):
        """Run the user loop until interrupted."""
        if user_loop is None:
            return

        def _signal_handler(_sig, _frame):
            print("\nStopping...")
            sys.exit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        while True:
            user_loop()


App = _App()
Bridge = _Bridge()
