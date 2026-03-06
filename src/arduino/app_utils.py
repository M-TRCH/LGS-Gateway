"""
Stub implementation of arduino.app_utils for local testing.
Provides `App` and `Bridge` minimal interfaces used by the Python scripts.
"""

import random
import signal
import sys
import time
from typing import Any, Callable


class _Bridge:
    def __init__(self):
        # functions provided by Python for MCU to call
        self._provided: dict[str, Callable[..., Any]] = {}
        # functions provided by MCU (simulated here)
        self._remote_handlers: dict[str, Callable[..., Any]] = {
            "add_numbers": lambda a, b: a + b,
            "send_modbus": lambda tx_hex: tx_hex if tx_hex else "",
            # --- Modbus FC stubs (simulate success) ---
            # FC01: Read Coils → return 1 byte of random coil statuses
            "read_coils": lambda sid, addr, qty: format(random.randint(0, 255), '02X'),
            # FC02: Read Discrete Inputs → same format as FC01
            "read_discrete_inputs": lambda sid, addr, qty: format(random.randint(0, 255), '02X'),
            # FC03: Read Holding Registers → return qty registers as hex (dummy)
            "read_holding_registers": lambda sid, addr, qty: ''.join(
                format(random.randint(0, 65535), '04X') for _ in range(qty)
            ),
            # FC04: Read Input Registers → same format as FC03
            "read_input_registers": lambda sid, addr, qty: ''.join(
                format(random.randint(0, 65535), '04X') for _ in range(qty)
            ),
            # FC05: Write Single Coil → 1=success
            "write_coil": lambda sid, addr, val: 1,
            # FC06: Write Single Register → 1=success
            "write_register": lambda sid, addr, val: 1,
            # FC15: Write Multiple Coils → 1=success
            "write_coils": lambda sid, addr, qty, data: 1,
            # FC16: Write Multiple Registers → 1=success
            "write_registers": lambda sid, addr, qty, data: 1,
            # Arduino test: random int
            "test": lambda: random.randint(0, 99),
        }

    def provide(self, name: str, func: Callable[..., Any]):
        self._provided[name] = func

    def provide_safe(self, name: str, func: Callable[..., Any]):
        # alias for compatibility with MCU stub
        self.provide(name, func)

    def call(self, name: str, *args, **kwargs) -> Any:
        handler = self._remote_handlers.get(name)
        if handler is None:
            raise RuntimeError(f"Remote function '{name}' not found (stub mode)")
        return handler(*args, **kwargs)


class _App:
    def run(self, user_loop: Callable[[], None] | None = None):
        # If user_loop is provided, call it repeatedly until interrupted.
        def _signal_handler(_sig, _frame):
            print("\nStopping...")
            sys.exit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        if user_loop is None:
            # Block indefinitely (simulate MCU main loop)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return

        while True:
            user_loop()


App = _App()
Bridge = _Bridge()
