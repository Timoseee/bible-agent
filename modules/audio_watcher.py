"""Low-overhead background monitoring for automatic audio processing."""

import ctypes
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from modules.resource_path import writable_path


AUDIO_EXTENSIONS = {".mp3", ".m4a"}
LOGGER = logging.getLogger("bibleai.audio_watcher")
WORKER_RESULT_PREFIX = "__BIBLEAI_WATCH_RESULT__="


@dataclass(frozen=True)
class WatcherSettings:
    input_dir: Path
    state_path: Path
    stop_path: Path
    scan_interval_seconds: float = 3.0
    stable_seconds: float = 15.0
    idle_seconds: float = 120.0
    retry_seconds: float = 600.0
    require_ac_power: bool = True
    notify_on_success: bool = True


def _bool_setting(value, default):
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


def settings_from_environment():
    """Build watcher settings from optional environment variables."""
    return WatcherSettings(
        input_dir=writable_path("input/audio"),
        state_path=writable_path("output/audio_watcher_state.json"),
        stop_path=writable_path("output/stop_audio_watcher.flag"),
        scan_interval_seconds=float(os.getenv("WATCH_SCAN_INTERVAL_SECONDS", "3")),
        stable_seconds=float(os.getenv("WATCH_FILE_STABLE_SECONDS", "15")),
        idle_seconds=float(os.getenv("WATCH_IDLE_SECONDS", "120")),
        retry_seconds=float(os.getenv("WATCH_RETRY_SECONDS", "600")),
        require_ac_power=_bool_setting(os.getenv("WATCH_REQUIRE_AC_POWER"), True),
        notify_on_success=_bool_setting(os.getenv("WATCH_NOTIFY_ON_SUCCESS"), True),
    )


def configure_watcher_logging():
    """Write watcher activity to a small rotating log file."""
    if LOGGER.handlers:
        return
    log_path = writable_path("logs/audio_watcher.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)


def lower_process_priority():
    """Run below normal priority on Windows so interactive apps stay responsive."""
    if os.name != "nt":
        return
    try:
        below_normal_priority_class = 0x00004000
        kernel32 = ctypes.windll.kernel32
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), below_normal_priority_class)
    except (AttributeError, OSError):
        LOGGER.warning("Could not lower watcher process priority")


def user_idle_seconds():
    """Return seconds since the last keyboard or mouse input on Windows."""
    if os.name != "nt":
        return float("inf")

    class LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    try:
        info = LastInputInfo()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        elapsed_ms = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
        return elapsed_ms / 1000.0
    except (AttributeError, OSError):
        return 0.0


def is_on_ac_power():
    """Return False only when Windows explicitly reports battery power."""
    if os.name != "nt":
        return True

    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_byte),
            ("BatteryFlag", ctypes.c_byte),
            ("BatteryLifePercent", ctypes.c_byte),
            ("SystemStatusFlag", ctypes.c_byte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]

    try:
        status = SystemPowerStatus()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return True
        return status.ACLineStatus != 0
    except (AttributeError, OSError):
        return True


def _signature(path):
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def process_in_worker(path):
    """Process one file in a child process so model memory is fully released."""
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--watch-worker", str(path)]
    else:
        main_path = Path(__file__).resolve().parent.parent / "main.py"
        command = [sys.executable, str(main_path), "--watch-worker", str(path)]

    options = {
        "cwd": str(writable_path(".")),
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "check": False,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW

    completed = subprocess.run(command, **options)
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(WORKER_RESULT_PREFIX):
            try:
                return json.loads(line[len(WORKER_RESULT_PREFIX) :])
            except ValueError:
                break

    error = completed.stderr.strip() or completed.stdout.strip()
    return {
        "success": False,
        "step": "worker",
        "error": error[-1000:] or f"Worker exited with code {completed.returncode}",
    }


class WatchState:
    """Persistent fingerprints prevent already processed audio from repeating."""

    def __init__(self, path):
        self.path = Path(path)
        self.data = {"version": 1, "files": {}}
        self.load()

    def load(self):
        if not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("files"), dict):
                self.data = loaded
        except (OSError, ValueError):
            LOGGER.warning("Watcher state could not be read; starting with an empty state")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def entry(self, path):
        return self.data["files"].get(Path(path).name, {})

    def mark(self, path, signature, status, **details):
        self.data["files"][Path(path).name] = {
            "signature": signature,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        self.save()


class AudioFolderWatcher:
    """Observe a folder and process one stable, eligible audio file at a time."""

    def __init__(
        self,
        settings,
        processor=None,
        idle_provider=None,
        power_provider=None,
    ):
        self.settings = settings
        self.processor = processor or process_in_worker
        self.idle_provider = idle_provider or user_idle_seconds
        self.power_provider = power_provider or is_on_ac_power
        self.state = WatchState(settings.state_path)
        self.observed = {}

    def audio_paths(self):
        self.settings.input_dir.mkdir(parents=True, exist_ok=True)
        return sorted(
            path
            for path in self.settings.input_dir.iterdir()
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        )

    def mark_existing(self):
        """Mark current files as a processed baseline without running the pipeline."""
        count = 0
        for path in self.audio_paths():
            self.state.mark(path, _signature(path), "success", baseline=True)
            count += 1
        return count

    def _eligible(self, path, signature, now_monotonic, now_time):
        entry = self.state.entry(path)
        if entry.get("signature") == signature:
            if entry.get("status") == "success":
                return False
            if entry.get("status") == "failed" and float(entry.get("retry_at", 0)) > now_time:
                return False

        observation = self.observed.get(path.name)
        if not observation or observation["signature"] != signature:
            self.observed[path.name] = {
                "signature": signature,
                "stable_since": now_monotonic,
            }
            return self.settings.stable_seconds <= 0

        return now_monotonic - observation["stable_since"] >= self.settings.stable_seconds

    def scan_once(self, now_monotonic=None, now_time=None):
        """Process at most one file, returning its pipeline result or None."""
        now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
        now_time = time.time() if now_time is None else now_time

        for path in self.audio_paths():
            try:
                signature = _signature(path)
            except OSError:
                continue
            if not self._eligible(path, signature, now_monotonic, now_time):
                continue
            if self.settings.require_ac_power and not self.power_provider():
                LOGGER.info("Waiting for AC power before processing %s", path.name)
                return None
            if self.idle_provider() < self.settings.idle_seconds:
                return None

            LOGGER.info("Processing started: %s", path.name)
            try:
                result = self.processor(path)
            except Exception as error:
                result = {"success": False, "error": str(error), "step": "watcher"}

            if result.get("success"):
                self.state.mark(
                    path,
                    signature,
                    "success",
                    output=result.get("output", ""),
                )
                LOGGER.info("Processing completed: %s -> %s", path.name, result.get("output", ""))
                if self.settings.notify_on_success and os.name == "nt":
                    try:
                        import winsound

                        winsound.MessageBeep(winsound.MB_OK)
                    except (ImportError, RuntimeError):
                        pass
            else:
                self.state.mark(
                    path,
                    signature,
                    "failed",
                    error=result.get("error", "Unknown processing error"),
                    retry_at=now_time + self.settings.retry_seconds,
                )
                LOGGER.error("Processing failed: %s: %s", path.name, result.get("error", ""))
            return result
        return None

    def run(self):
        """Run until the stop flag appears or the process is interrupted."""
        self.settings.stop_path.unlink(missing_ok=True)
        LOGGER.info("Audio watcher started: %s", self.settings.input_dir)
        while not self.settings.stop_path.exists():
            self.scan_once()
            time.sleep(max(0.5, self.settings.scan_interval_seconds))
        self.settings.stop_path.unlink(missing_ok=True)
        LOGGER.info("Audio watcher stopped")


def request_stop(settings=None):
    settings = settings or settings_from_environment()
    settings.stop_path.parent.mkdir(parents=True, exist_ok=True)
    settings.stop_path.write_text("stop", encoding="utf-8")
