"""Command-line entry point for BibleAI automatic audio monitoring."""

import argparse
import ctypes
import os
import sys

from modules.audio_watcher import (
    AudioFolderWatcher,
    configure_watcher_logging,
    lower_process_priority,
    request_stop,
    settings_from_environment,
)


def _single_instance_mutex():
    if os.name != "nt":
        return None
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(
        None,
        False,
        "Local\\BibleAI_AudioWatcher",
    )
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return False
    return handle


def main():
    parser = argparse.ArgumentParser(description="Automatically process new BibleAI audio files.")
    parser.add_argument("--mark-existing", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    settings = settings_from_environment()

    if args.stop:
        request_stop(settings)
        print("Stop requested.")
        return 0

    configure_watcher_logging()
    watcher = AudioFolderWatcher(settings)
    if args.mark_existing:
        print(f"Marked {watcher.mark_existing()} existing audio file(s).")
        return 0

    mutex = _single_instance_mutex()
    if mutex is False:
        print("BibleAI audio watcher is already running.")
        return 1

    lower_process_priority()
    try:
        watcher.run()
    except KeyboardInterrupt:
        return 0
    finally:
        if mutex:
            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(mutex)
            kernel32.CloseHandle(mutex)
    return 0


if __name__ == "__main__":
    sys.exit(main())
