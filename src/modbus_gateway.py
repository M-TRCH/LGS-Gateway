"""
LGS Smart Gateway v2.0 (Industrial-Grade)
==========================================
Architecture: AsyncIO TCP Server -> Bounded Queue -> Single Serial Worker

Improvements over v1.0:
  - YAML configuration with environment variable overrides
  - Graceful shutdown (SIGTERM / SIGINT)
  - Categorised exception handling (connection vs device vs protocol)
  - Bounded queue with back-pressure (GATEWAY_BUSY)
  - Configurable write deduplication (opt-in, default OFF)
  - Exponential back-off for serial reconnection
  - Adaptive inter-frame delay (baudrate-aware)
  - Lazy device context creation (memory efficient)
  - Read-after-write cache (eliminates redundant serial reads)
  - Proper Modbus exception codes
  - Watchdog task for worker health monitoring
  - HTTP health-check endpoint (/health)
  - Structured logging (text / JSON)
  - Request tracing with sequential IDs

Author: LGS Project
"""

# ==============================================================
# Imports
# ==============================================================
import asyncio
import copy
import json
import logging
import logging.handlers
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Thread
from typing import Any, Dict, List, Optional

import yaml
from pymodbus.client import ModbusSerialClient
from pymodbus.constants import ExcCodes
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusServerContext,
    ModbusSparseDataBlock,
)
from pymodbus.exceptions import ModbusException, ModbusIOException
from pymodbus.server import StartAsyncTcpServer

# ==============================================================
# Version
# ==============================================================
VERSION = "2.0.0"

# ==============================================================
# Robust Modbus Exception-Code Resolution
# ==============================================================
EXC_GATEWAY_NO_RESPONSE = getattr(
    ExcCodes, "GATEWAY_NO_RESPONSE",
    getattr(ExcCodes, "GatewayNoResponse", 0x0B),
)
EXC_GATEWAY_PATH_UNAVAIL = getattr(
    ExcCodes, "GATEWAY_PATH_UNAVAILABLE",
    getattr(ExcCodes, "GatewayPathUnavailable", 0x0A),
)
EXC_SERVER_BUSY = getattr(
    ExcCodes, "SLAVE_BUSY",
    getattr(ExcCodes, "SlaveBusy",
            getattr(ExcCodes, "ServerDeviceBusy", 0x06)),
)
EXC_SLAVE_FAILURE = getattr(
    ExcCodes, "SLAVE_FAILURE",
    getattr(ExcCodes, "SlaveFailure",
            getattr(ExcCodes, "ServerDeviceFailure", 0x04)),
)

# ==============================================================
# Configuration
# ==============================================================
DEFAULT_CONFIG: Dict[str, Any] = {
    "gateway": {
        "tcp_host": "0.0.0.0",
        "tcp_port": 502,
        "server_timeout": 5.0,
    },
    "serial": {
        "port": "/dev/ttyUSB0",
        "baudrate": 9600,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout": 0.5,
        "connect_retries": 3,
        "reconnect_delay_min": 0.5,
        "reconnect_delay_max": 30.0,
        "executor_workers": 2,
    },
    "queue": {"maxsize": 100},
    "deduplication": {
        "enabled": False,
        "cache_ttl": 0.5,
        "history_ttl": 5.0,
    },
    "logging": {"level": "INFO", "format": "text"},
    "health": {"enabled": True, "host": "0.0.0.0", "port": 8080},
    "watchdog": {
        "enabled": True,
        "interval": 10.0,
        "queue_warn_threshold": 50,
    },
}

# env-var name -> (section, key [, converter])
_ENV_OVERRIDES: Dict[str, tuple] = {
    "LGS_TCP_HOST": ("gateway", "tcp_host"),
    "LGS_TCP_PORT": ("gateway", "tcp_port", int),
    "LGS_SERVER_TIMEOUT": ("gateway", "server_timeout", float),
    "LGS_SERIAL_PORT": ("serial", "port"),
    "LGS_SERIAL_BAUDRATE": ("serial", "baudrate", int),
    "LGS_SERIAL_TIMEOUT": ("serial", "timeout", float),
    "LGS_QUEUE_MAXSIZE": ("queue", "maxsize", int),
    "LGS_DEDUPE_ENABLED": ("deduplication", "enabled",
                           lambda x: x.lower() in ("true", "1", "yes")),
    "LGS_DEDUPE_TTL": ("deduplication", "cache_ttl", float),
    "LGS_LOG_LEVEL": ("logging", "level"),
    "LGS_LOG_FORMAT": ("logging", "format"),
    "LGS_HEALTH_ENABLED": ("health", "enabled",
                           lambda x: x.lower() in ("true", "1", "yes")),
    "LGS_HEALTH_PORT": ("health", "port", int),
    "LGS_WATCHDOG_ENABLED": ("watchdog", "enabled",
                             lambda x: x.lower() in ("true", "1", "yes")),
    "LGS_WATCHDOG_INTERVAL": ("watchdog", "interval", float),
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_path: Optional[str] = None) -> dict:
    """Load config: defaults -> YAML file -> environment variables."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)

    # Resolve config file path
    if config_path is None:
        config_path = os.environ.get("LGS_CONFIG_FILE")
    if config_path is None:
        for candidate in (
            Path(__file__).resolve().parent.parent / "config.yaml",
            Path("/etc/lgs_gateway/config.yaml"),
            Path("config.yaml"),
        ):
            if candidate.exists():
                config_path = str(candidate)
                break

    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as fh:
            file_cfg = yaml.safe_load(fh) or {}
        cfg = _deep_merge(cfg, file_cfg)

    # Apply environment-variable overrides
    for env_var, spec in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None:
            continue
        section, key = spec[0], spec[1]
        converter = spec[2] if len(spec) == 3 else str
        cfg.setdefault(section, {})[key] = converter(raw)

    return cfg


# ==============================================================
# Logging
# ==============================================================
class _JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(config: dict) -> logging.Logger:
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    fmt = log_cfg.get("format", "text")

    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(_JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
    root.addHandler(handler)
    root.setLevel(level)

    gw_log = logging.getLogger("LGS-GW")
    gw_log.setLevel(level)

    pymodbus_level = logging.WARNING if level > logging.DEBUG else logging.INFO
    logging.getLogger("pymodbus").setLevel(pymodbus_level)

    return gw_log


# ==============================================================
# Utility helpers
# ==============================================================
def _norm_coils(value) -> List[int]:
    """Normalise coil value(s) to list of int 0/1."""
    if isinstance(value, (list, tuple)):
        return [1 if v else 0 for v in value]
    return [1 if value else 0]


def _norm_regs(value) -> List[int]:
    """Normalise register value(s) to list of int."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _inter_frame_delay(baudrate: int) -> float:
    """Modbus RTU inter-frame silence per spec.

    3.5 character times for baudrate <= 19200,
    fixed 1.75 ms for > 19200.  A 0.5 ms safety margin is added.
    """
    if baudrate <= 19200:
        return 3.5 * (11.0 / baudrate) + 0.0005
    return 0.00225  # 1.75 ms + 0.5 ms


def _is_write_fc(fc: int) -> bool:
    return fc in (5, 6, 15, 16)


def _is_coil_fc(fc: int) -> bool:
    return fc in (1, 5, 15)


def _map_write_to_read(fc: int) -> int:
    """Map write FC to corresponding read FC for read-after-write."""
    return {5: 1, 6: 3, 15: 1, 16: 3}.get(fc, fc)


# ==============================================================
# Custom exceptions (error categorisation)
# ==============================================================
class SerialConnectionError(Exception):
    """Serial port connection failure -- reconnect required."""


class DeviceNoResponseError(Exception):
    """RTU device did not respond within timeout."""


class DeviceError(Exception):
    """RTU device responded with an error frame."""
    def __init__(self, message: str, exc_code: Optional[int] = None):
        super().__init__(message)
        self.exc_code = exc_code


class QueueFullError(Exception):
    """Request queue capacity exceeded."""


# ==============================================================
# RtuRequest
# ==============================================================
_req_counter = 0


class RtuRequest:
    """Request descriptor with lifecycle timestamps."""

    __slots__ = (
        "rid", "unit_id", "func_code", "address", "value", "count",
        "future", "queue_ts", "dequeued_ts", "forward_ts", "resp_ts",
    )

    def __init__(self, unit_id: int, func_code: int, address: int,
                 value=None, count: int = 1):
        global _req_counter
        _req_counter += 1
        self.rid: int = _req_counter
        self.unit_id = unit_id
        self.func_code = func_code
        self.address = address
        self.value = value
        self.count = count
        self.future: Optional[asyncio.Future] = None
        self.queue_ts: Optional[float] = None
        self.dequeued_ts: Optional[float] = None
        self.forward_ts: Optional[float] = None
        self.resp_ts: Optional[float] = None

    def __repr__(self) -> str:
        return (f"Req#{self.rid}(u={self.unit_id} fc={self.func_code} "
                f"a={self.address} c={self.count})")


# ==============================================================
# SerialManager
# ==============================================================
class SerialManager:
    """Manages serial I/O through a bounded async queue.

    ALL coroutine methods run on *serial_loop* (separate thread).
    Internal state is therefore single-threaded -- no locks required
    as long as this invariant is maintained.
    """

    def __init__(self, config: dict):
        ser = config["serial"]
        self._cfg = config
        self._serial_params = {
            k: ser[k] for k in ("port", "baudrate", "bytesize",
                                "parity", "stopbits", "timeout")
        }
        self.client = ModbusSerialClient(**self._serial_params)
        self.executor = ThreadPoolExecutor(
            max_workers=ser.get("executor_workers", 2),
            thread_name_prefix="serial-io",
        )
        self.queue: Optional[asyncio.Queue] = None

        # Connection / reconnect state
        self._connected = False
        self._retries = ser.get("connect_retries", 3)
        self._delay_min = ser.get("reconnect_delay_min", 0.5)
        self._delay_max = ser.get("reconnect_delay_max", 30.0)
        self._delay = self._delay_min

        # Deduplication
        dd = config.get("deduplication", {})
        self._dedupe_on = dd.get("enabled", False)
        self._dedupe_ttl = dd.get("cache_ttl", 0.5)
        self._hist_ttl = dd.get("history_ttl", 5.0)
        self._write_hist: Dict[tuple, tuple] = {}
        self._last_hist_clean = 0.0

        # Bus timing
        self._frame_delay = _inter_frame_delay(ser["baudrate"])

        # Observable metrics (read cross-thread via GIL safety)
        self.metrics: Dict[str, Any] = {
            "requests_total": 0,
            "requests_ok": 0,
            "requests_err": 0,
            "requests_deduped": 0,
            "reconnects": 0,
            "worker_alive": False,
            "queue_depth": 0,
            "last_req_ts": 0.0,
            "avg_rtu_ms": 0.0,
        }
        self._lat_buf: List[float] = []

        self._shutdown = False
        self._log = logging.getLogger("LGS-GW.serial")

    # ---------- deduplication helpers ----------

    def _hist_clean(self):
        now = time.time()
        if now - self._last_hist_clean < 1.0:
            return
        self._last_hist_clean = now
        stale = [k for k, (_, ts) in self._write_hist.items()
                 if now - ts > self._hist_ttl]
        for k in stale:
            self._write_hist.pop(k, None)

    def _dedupe_check(self, req: RtuRequest):
        """Return cached result if write is redundant, else None."""
        coil = _is_coil_fc(req.func_code)
        key = (req.unit_id, req.address, "c" if coil else "r")
        last = self._write_hist.get(key)
        if last is None:
            return None
        last_val, last_ts = last
        if time.time() - last_ts >= self._dedupe_ttl:
            return None
        # normalise for comparison
        v = req.value
        if req.func_code in (5, 6) and isinstance(v, (list, tuple)):
            v = v[0]
        norm = _norm_coils(v) if coil else _norm_regs(v)
        cmp = norm[0] if len(norm) == 1 else norm
        if last_val != cmp:
            return None
        return _norm_coils(req.value) if coil else _norm_regs(req.value)

    def _hist_update(self, req: RtuRequest):
        coil = _is_coil_fc(req.func_code)
        key = (req.unit_id, req.address, "c" if coil else "r")
        v = req.value
        if req.func_code in (5, 6) and isinstance(v, (list, tuple)):
            v = v[0]
        norm = _norm_coils(v) if coil else _norm_regs(v)
        store = norm[0] if len(norm) == 1 else norm
        self._write_hist[key] = (store, time.time())

    # ---------- public coroutine ----------

    async def submit(self, req: RtuRequest):
        """Enqueue request and wait for serial result.

        MUST be awaited from the serial event-loop.
        """
        self.metrics["requests_total"] += 1
        self.metrics["last_req_ts"] = time.time()

        # Write deduplication (opt-in)
        if self._dedupe_on and _is_write_fc(req.func_code):
            self._hist_clean()
            cached = self._dedupe_check(req)
            if cached is not None:
                self.metrics["requests_deduped"] += 1
                self.metrics["requests_ok"] += 1
                return cached

        if self.queue is None:
            raise RuntimeError("Queue not initialised")
        if self.queue.full():
            self.metrics["requests_err"] += 1
            raise QueueFullError(f"Queue full ({self.queue.maxsize})")

        req.queue_ts = time.time()
        req.future = asyncio.get_running_loop().create_future()
        await self.queue.put(req)
        self.metrics["queue_depth"] = self.queue.qsize()

        try:
            result = await req.future
        except Exception:
            self.metrics["requests_err"] += 1
            raise

        # Latency tracking
        if req.resp_ts and req.forward_ts:
            ms = (req.resp_ts - req.forward_ts) * 1000
            self._lat_buf.append(ms)
            if len(self._lat_buf) > 100:
                self._lat_buf.pop(0)
            self.metrics["avg_rtu_ms"] = (
                sum(self._lat_buf) / len(self._lat_buf))

        self.metrics["requests_ok"] += 1

        if self._dedupe_on and _is_write_fc(req.func_code):
            self._hist_update(req)

        return result

    # ---------- worker loop ----------

    async def worker(self):
        """Dequeue and execute serial requests one-by-one."""
        self._log.info(
            "Worker started -- port=%s baud=%s delay=%.2fms",
            self._serial_params["port"],
            self._serial_params["baudrate"],
            self._frame_delay * 1000,
        )
        self.metrics["worker_alive"] = True

        try:
            while not self._shutdown:
                loop = asyncio.get_running_loop()

                # -- ensure connection --
                if not self._connected:
                    await self._connect(loop)
                    if not self._connected:
                        continue

                # -- dequeue (with timeout for shutdown poll) --
                try:
                    req: RtuRequest = await asyncio.wait_for(
                        self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                req.dequeued_ts = time.time()
                self.metrics["queue_depth"] = self.queue.qsize()

                # -- execute --
                try:
                    data = await self._exec(req, loop)
                    req.resp_ts = time.time()
                    if req.future and not req.future.done():
                        req.future.set_result(data)
                    self._delay = self._delay_min  # reset backoff

                except (ConnectionError, OSError) as exc:
                    self._log.warning("Connection error: %s -- %s", req, exc)
                    self._connected = False
                    self.metrics["reconnects"] += 1
                    if req.future and not req.future.done():
                        req.future.set_exception(
                            SerialConnectionError(str(exc)))

                except (ModbusIOException, DeviceNoResponseError) as exc:
                    self._log.warning("Device I/O error: %s -- %s", req, exc)
                    if req.future and not req.future.done():
                        req.future.set_exception(
                            DeviceNoResponseError(str(exc)))

                except DeviceError as exc:
                    self._log.warning("Device error: %s -- %s", req, exc)
                    if req.future and not req.future.done():
                        req.future.set_exception(exc)

                except Exception as exc:
                    self._log.exception("Unexpected error: %s", req)
                    if req.future and not req.future.done():
                        req.future.set_exception(exc)

                finally:
                    await asyncio.sleep(self._frame_delay)
                    try:
                        self.queue.task_done()
                    except ValueError:
                        pass
        finally:
            self.metrics["worker_alive"] = False
            self._log.info("Worker stopped")

    # ---------- serial connection ----------

    async def _connect(self, loop):
        port = self._serial_params["port"]

        # Check device node exists (avoids noisy retries)
        if port.startswith("/dev/") and not Path(port).exists():
            self._log.warning("Port %s absent -- retry in %.1fs",
                              port, self._delay)
            await asyncio.sleep(self._delay)
            self._delay = min(self._delay * 2, self._delay_max)
            return

        for attempt in range(1, self._retries + 1):
            if self._shutdown:
                return
            try:
                ok = await loop.run_in_executor(
                    self.executor, self.client.connect)
            except Exception as exc:
                self._log.debug("Connect %d/%d failed: %s",
                                attempt, self._retries, exc)
                ok = False
            if ok:
                self._connected = True
                self._delay = self._delay_min
                self._log.info("Serial connected on %s", port)
                return
            await asyncio.sleep(0.1)

        self._log.warning(
            "Connect failed (%d attempts) -- retry in %.1fs",
            self._retries, self._delay)
        self.metrics["reconnects"] += 1
        await asyncio.sleep(self._delay)
        self._delay = min(self._delay * 2, self._delay_max)

    # ---------- execute single request ----------

    async def _exec(self, req: RtuRequest, loop) -> list:
        req.forward_ts = time.time()
        try:
            return await self._do_io(req, loop)
        except (ModbusIOException, ModbusException,
                DeviceNoResponseError, DeviceError):
            # Broadcast writes expect no response -- echo back data
            if req.unit_id == 0 and _is_write_fc(req.func_code):
                self._log.debug("Broadcast %s -- no response (expected)", req)
                return self._echo(req)
            raise

    async def _do_io(self, req: RtuRequest, loop) -> list:
        fc, uid, addr, cnt = (req.func_code, req.unit_id,
                              req.address, req.count)
        ex = self.executor
        cl = self.client

        if fc == 1:
            r = await loop.run_in_executor(
                ex, lambda: cl.read_coils(addr, count=cnt, device_id=uid))
            self._chk(r, req)
            return list(getattr(r, "bits", []))[:cnt]

        if fc == 2:
            r = await loop.run_in_executor(
                ex, lambda: cl.read_discrete_inputs(
                    addr, count=cnt, device_id=uid))
            self._chk(r, req)
            return list(getattr(r, "bits", []))[:cnt]

        if fc == 3:
            r = await loop.run_in_executor(
                ex, lambda: cl.read_holding_registers(
                    addr, count=cnt, device_id=uid))
            self._chk(r, req)
            return list(getattr(r, "registers", []))[:cnt]

        if fc == 4:
            r = await loop.run_in_executor(
                ex, lambda: cl.read_input_registers(
                    addr, count=cnt, device_id=uid))
            self._chk(r, req)
            return list(getattr(r, "registers", []))[:cnt]

        if fc == 5:
            r = await loop.run_in_executor(
                ex, lambda: cl.write_coil(addr, req.value, device_id=uid))
            self._chk(r, req)
            return _norm_coils(req.value)

        if fc == 6:
            r = await loop.run_in_executor(
                ex, lambda: cl.write_register(addr, req.value, device_id=uid))
            self._chk(r, req)
            return _norm_regs(req.value)

        if fc == 15:
            r = await loop.run_in_executor(
                ex, lambda: cl.write_coils(addr, req.value, device_id=uid))
            self._chk(r, req)
            return _norm_coils(req.value)[:cnt]

        if fc == 16:
            r = await loop.run_in_executor(
                ex, lambda: cl.write_registers(addr, req.value, device_id=uid))
            self._chk(r, req)
            return _norm_regs(req.value)[:cnt]

        self._log.warning("Unsupported FC %s on %s", fc, req)
        return []

    @staticmethod
    def _chk(resp, req: RtuRequest):
        """Raise if pymodbus response indicates an error."""
        if resp is None:
            raise DeviceNoResponseError(
                f"No response from unit {req.unit_id}")
        if (hasattr(resp, "isError") and callable(resp.isError)
                and resp.isError()):
            raise DeviceError(
                f"Error from unit {req.unit_id}: {resp}",
                exc_code=getattr(resp, "exception_code", None),
            )

    @staticmethod
    def _echo(req: RtuRequest) -> list:
        """Echo expected write data (for broadcast / no-response)."""
        if _is_coil_fc(req.func_code):
            return _norm_coils(req.value)
        return _norm_regs(req.value)

    # ---------- graceful shutdown ----------

    async def shutdown(self):
        self._log.info("Shutting down serial manager ...")
        self._shutdown = True

        # Drain pending requests
        if self.queue:
            while not self.queue.empty():
                try:
                    r = self.queue.get_nowait()
                    if r.future and not r.future.done():
                        r.future.set_exception(
                            RuntimeError("Gateway shutting down"))
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    break

        try:
            self.client.close()
        except Exception:
            pass

        self.executor.shutdown(wait=False, cancel_futures=True)
        self._log.info("Serial manager stopped")


# ==============================================================
# Pass-through Data Block
# ==============================================================
class _PassthroughBlock(ModbusSparseDataBlock):
    """Accepts all address ranges -- actual I/O is in GatewayContext."""

    def validate(self, address, count=1):
        return count > 0

    def getValues(self, address, count=1):
        return [0] * count

    def setValues(self, address, values):
        pass


# ==============================================================
# GatewayContext
# ==============================================================
class GatewayContext(ModbusDeviceContext):
    """Per-unit-ID context that proxies read/write to the serial bus."""

    def __init__(self, unit_id: int, serial_mgr: SerialManager,
                 serial_loop: asyncio.AbstractEventLoop, config: dict):
        self.unit_id = unit_id
        self._mgr = serial_mgr
        self._loop = serial_loop
        self._timeout = config["gateway"]["server_timeout"]
        self._log = logging.getLogger("LGS-GW.ctx")

        # Write-back cache: (fc, address) -> (values_list, timestamp)
        self._wcache: Dict[tuple, tuple] = {}
        self._wcache_ttl = 2.0

        super().__init__(
            _PassthroughBlock({0: 0}), _PassthroughBlock({0: 0}),
            _PassthroughBlock({0: 0}), _PassthroughBlock({0: 0}),
        )

    # --- write-back cache for read-after-write ---

    def _cache_set(self, fc: int, addr: int, vals: list):
        self._wcache[(fc, addr)] = (vals, time.time())

    def _cache_get(self, fc: int, addr: int, count: int):
        entry = self._wcache.pop((fc, addr), None)
        if entry is None:
            return None
        vals, ts = entry
        if time.time() - ts > self._wcache_ttl:
            return None
        return vals[:count] if len(vals) >= count else vals

    # --- error -> Modbus exception code mapping ---

    def _exc_to_code(self, exc: Exception):
        if isinstance(exc, QueueFullError):
            return EXC_SERVER_BUSY
        if isinstance(exc, SerialConnectionError):
            return EXC_GATEWAY_PATH_UNAVAIL
        if isinstance(exc, DeviceNoResponseError):
            return EXC_GATEWAY_NO_RESPONSE
        if isinstance(exc, DeviceError):
            return exc.exc_code or EXC_SLAVE_FAILURE
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return EXC_GATEWAY_NO_RESPONSE
        return EXC_GATEWAY_NO_RESPONSE

    # --- sync bridge (fallback for pymodbus sync code-path) ---

    def _sync_submit(self, req: RtuRequest):
        try:
            cf = asyncio.run_coroutine_threadsafe(
                self._mgr.submit(req), self._loop)
            return cf.result(timeout=self._timeout)
        except Exception as exc:
            self._log.debug("sync error %s: %s", req, exc)
            return self._exc_to_code(exc)

    # --- async bridge (preferred by pymodbus async server) ---

    async def _async_submit(self, req: RtuRequest):
        try:
            cf = asyncio.run_coroutine_threadsafe(
                self._mgr.submit(req), self._loop)
            wrapped = asyncio.wrap_future(cf)
            return await asyncio.wait_for(wrapped, timeout=self._timeout)
        except Exception as exc:
            self._log.debug("async error %s: %s", req, exc)
            return self._exc_to_code(exc)

    # ========== sync getValues / setValues ==========

    def getValues(self, fc, address, count=1):
        # Read-after-write: return cached write result
        if _is_write_fc(fc):
            cached = self._cache_get(fc, address, count)
            if cached is not None:
                return cached
            fc = _map_write_to_read(fc)

        return self._sync_submit(
            RtuRequest(self.unit_id, fc, address, count=count))

    def setValues(self, fc, address, values):
        val = values[0] if len(values) == 1 else values
        cnt = len(values) if isinstance(values, (list, tuple)) else 1
        req = RtuRequest(self.unit_id, fc, address, value=val, count=cnt)

        if self.unit_id == 0:
            # Broadcast: fire-and-forget
            asyncio.run_coroutine_threadsafe(
                self._mgr.submit(req), self._loop)
            return SerialManager._echo(req)

        result = self._sync_submit(req)
        if isinstance(result, list):
            self._cache_set(fc, address, result)
        return result

    # ========== async getValues / setValues ==========

    async def async_getValues(self, fc, address, count=1):
        if _is_write_fc(fc):
            cached = self._cache_get(fc, address, count)
            if cached is not None:
                return cached
            fc = _map_write_to_read(fc)

        return await self._async_submit(
            RtuRequest(self.unit_id, fc, address, count=count))

    async def async_setValues(self, fc, address, values):
        val = values[0] if len(values) == 1 else values
        cnt = len(values) if isinstance(values, (list, tuple)) else 1
        req = RtuRequest(self.unit_id, fc, address, value=val, count=cnt)

        if self.unit_id == 0:
            asyncio.run_coroutine_threadsafe(
                self._mgr.submit(req), self._loop)
            return None

        try:
            result = await self._async_submit(req)
            if isinstance(result, list):
                self._cache_set(fc, address, result)
            return None  # success
        except Exception:
            return EXC_GATEWAY_NO_RESPONSE


# ==============================================================
# Lazy Device Dictionary
# ==============================================================
class _LazyDevices(dict):
    """Creates GatewayContext instances on first access (unit 0-247).

    IMPORTANT: ``__bool__`` always returns True so that pymodbus'
    ``ModbusServerContext.__init__`` (which does ``devices or {}``)
    does not discard this instance when it is still empty.
    """

    def __init__(self, factory):
        super().__init__()
        self._factory = factory

    def __bool__(self) -> bool:
        # Must be truthy even when empty, otherwise
        # ``ModbusServerContext.__init__`` replaces us with a plain dict.
        return True

    def __contains__(self, key):
        if isinstance(key, int) and 0 <= key <= 247:
            return True
        return super().__contains__(key)

    def __missing__(self, key):
        if isinstance(key, int) and 0 <= key <= 247:
            ctx = self._factory(key)
            self[key] = ctx
            return ctx
        raise KeyError(key)


# ==============================================================
# Health-check HTTP endpoint
# ==============================================================
async def _health_server(serial_mgr: SerialManager, config: dict,
                         start_ts: float):
    hcfg = config.get("health", {})
    host = hcfg.get("host", "0.0.0.0")
    port = hcfg.get("port", 8080)
    log = logging.getLogger("LGS-GW.health")

    async def _handle(reader, writer):
        try:
            await asyncio.wait_for(reader.read(4096), timeout=5.0)
        except (asyncio.TimeoutError, ConnectionResetError):
            writer.close()
            return

        m = serial_mgr.metrics
        alive = m["worker_alive"] and serial_mgr._connected
        body = json.dumps({
            "status": "ok" if alive else "degraded",
            "version": VERSION,
            "uptime_s": round(time.time() - start_ts, 1),
            "serial": {
                "connected": serial_mgr._connected,
                "port": serial_mgr._serial_params["port"],
            },
            "worker_alive": m["worker_alive"],
            "queue_depth": m["queue_depth"],
            "counters": {
                "total": m["requests_total"],
                "ok": m["requests_ok"],
                "err": m["requests_err"],
                "deduped": m["requests_deduped"],
                "reconnects": m["reconnects"],
            },
            "avg_rtu_ms": round(m["avg_rtu_ms"], 2),
        }, indent=2)

        code = 200 if alive else 503
        phrase = "OK" if code == 200 else "Service Unavailable"
        resp = (
            f"HTTP/1.1 {code} {phrase}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body.encode())}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{body}"
        )
        try:
            writer.write(resp.encode())
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    srv = await asyncio.start_server(_handle, host, port)
    log.info("Health endpoint at http://%s:%d/", host, port)
    async with srv:
        await srv.serve_forever()


# ==============================================================
# Watchdog
# ==============================================================
async def _watchdog(serial_mgr: SerialManager, config: dict):
    wcfg = config.get("watchdog", {})
    interval = wcfg.get("interval", 10.0)
    q_warn = wcfg.get("queue_warn_threshold", 50)
    log = logging.getLogger("LGS-GW.watchdog")

    while True:
        await asyncio.sleep(interval)
        m = serial_mgr.metrics

        if not m["worker_alive"]:
            log.critical("WATCHDOG: Serial worker is NOT alive!")

        qd = m["queue_depth"]
        if qd > q_warn:
            log.warning("WATCHDOG: Queue depth %d > threshold %d",
                        qd, q_warn)

        if not serial_mgr._connected:
            log.warning("WATCHDOG: Serial port disconnected")

        last = m["last_req_ts"]
        if last > 0 and (time.time() - last) > 300:
            log.info("WATCHDOG: No requests in 5 min (idle)")


# ==============================================================
# Main
# ==============================================================
async def run_gateway(config: dict):
    log = setup_logging(config)
    start_ts = time.time()
    gw_cfg = config["gateway"]

    log.info("=== LGS Smart Gateway v%s starting ===", VERSION)

    # ---- Serial manager + background loop ----
    serial_mgr = SerialManager(config)
    serial_loop = asyncio.new_event_loop()

    def _serial_thread():
        asyncio.set_event_loop(serial_loop)
        serial_mgr.queue = asyncio.Queue(
            maxsize=config["queue"]["maxsize"])
        serial_loop.create_task(serial_mgr.worker())
        serial_loop.run_forever()

    thr = Thread(target=_serial_thread, daemon=True, name="serial-worker")
    thr.start()

    # Give serial loop time to initialise queue
    await asyncio.sleep(0.1)

    # ---- Lazy server context ----
    devices = _LazyDevices(
        lambda uid: GatewayContext(uid, serial_mgr, serial_loop, config))
    context = ModbusServerContext(devices=devices, single=False)

    # ---- Resolve TCP bind address ----
    host = gw_cfg["tcp_host"]
    port = gw_cfg["tcp_port"]
    try:
        if port < 1024 and os.geteuid() != 0:
            log.warning("Need root for port %d -- falling back to 1502",
                        port)
            port = 1502
    except AttributeError:
        pass

    # ---- Shutdown plumbing ----
    shutdown_ev = asyncio.Event()
    main_loop = asyncio.get_running_loop()

    def _on_signal():
        log.info("Shutdown signal received")
        shutdown_ev.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            main_loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            pass  # Windows

    # ---- Background tasks ----
    tasks: List[asyncio.Task] = []

    log.info("TCP server on %s:%d", host, port)
    tasks.append(asyncio.create_task(
        StartAsyncTcpServer(context=context, address=(host, port)),
        name="tcp-server"))

    if config["health"]["enabled"]:
        tasks.append(asyncio.create_task(
            _health_server(serial_mgr, config, start_ts),
            name="health"))

    if config["watchdog"]["enabled"]:
        tasks.append(asyncio.create_task(
            _watchdog(serial_mgr, config),
            name="watchdog"))

    # ---- Wait for shutdown or unexpected task exit ----
    shutdown_task = asyncio.create_task(
        shutdown_ev.wait(), name="shutdown")
    all_tasks = [shutdown_task] + tasks
    done, _ = await asyncio.wait(
        all_tasks, return_when=asyncio.FIRST_COMPLETED)

    # If a non-shutdown task finished first, that is unexpected
    for t in done:
        if t is not shutdown_task and t.exception():
            log.error("Task %s crashed: %s", t.get_name(), t.exception())

    # ---- Graceful shutdown ----
    log.info("Initiating graceful shutdown ...")

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    # Stop serial manager (on its loop)
    try:
        cf = asyncio.run_coroutine_threadsafe(
            serial_mgr.shutdown(), serial_loop)
        cf.result(timeout=5.0)
    except Exception as exc:
        log.warning("Serial shutdown issue: %s", exc)

    serial_loop.call_soon_threadsafe(serial_loop.stop)
    thr.join(timeout=5.0)

    log.info("=== LGS Smart Gateway stopped ===")


# ==============================================================
# Entry point
# ==============================================================
def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)
    try:
        asyncio.run(run_gateway(config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
