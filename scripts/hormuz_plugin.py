#!/usr/bin/env python3
"""Omarchy bridge to the existing Hormuz CLI. No HTTP or credential storage."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time

MAX_OUTPUT = 256 * 1024
COMMAND_TIMEOUT = 8.0
STATUS_SCHEMA = "hormuz.omarchy-status.v1"
MESSAGES = {
    "invalid_settings": "Check the profile name, executable, and absolute private state directory in the widget settings.",
    "cli_unavailable": "Hormuz is not installed or not on the shell PATH. Set its absolute executable path in the widget settings.",
    "cli_failed": "Cannot read or update this profile. Check the Hormuz CLI version, saved profile, and private state directory. See the plugin README for setup.",
    "timeout": "Hormuz did not respond in time. Refresh to try again.",
    "output_too_large": "The local report exceeded the plugin's size limit.",
    "invalid_report": "This Hormuz benefit report is incompatible. Use a CLI with the personal-benefit v1 contract.",
    "already_running": "This profile already has an agent session launched by the Omarchy plugin. Use that terminal or close its session first.",
    "runtime_unavailable": "An owned, private XDG_RUNTIME_DIR is required to launch an agent.",
    "interrupted": "The local operation was interrupted.",
}


class PluginError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def settings(cli: str, profile: str, state: str) -> tuple[str, str]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", profile):
        raise PluginError("invalid_settings")
    if not cli or any(ord(c) < 32 for c in cli + state):
        raise PluginError("invalid_settings")
    if "/" in cli and not Path(cli).is_absolute():
        raise PluginError("invalid_settings")
    executable = shutil.which(cli)
    if executable is None:
        raise PluginError("cli_unavailable")
    if state:
        expanded = Path(state).expanduser()
        if not expanded.is_absolute():
            raise PluginError("invalid_settings")
        state = str(expanded)
    return executable, state


def cli_arguments(executable: str, profile: str, state: str, action: str) -> list[str]:
    args = [executable, "personal", action, "--profile", profile]
    if state:
        args.extend(["--state-directory", state])
    if action == "benefit":
        args.append("--json")
    return args


def _signal_group(child: subprocess.Popen[bytes], signum: int) -> None:
    try:
        os.killpg(child.pid, signum)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin reports EPERM for a group containing only unreaped zombies.
        # Confirm our leader exited without reaping it; never ignore refusal
        # for a live leader or on the Linux deployment platform.
        exited = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if sys.platform != "darwin" or exited is None:
            raise


def _stop_group(child: subprocess.Popen[bytes]) -> None:
    # The unreaped group leader keeps this group identity owned by this call.
    _signal_group(child, signal.SIGTERM)
    # Do not reap the leader before the final group signal: it pins the owned
    # group identity even if a descendant ignores graceful termination.
    time.sleep(0.1)
    _signal_group(child, signal.SIGKILL)
    child.wait(timeout=1)


def capture(args: list[str], *, timeout: float = COMMAND_TIMEOUT) -> bytes:
    """Bound both output and wall time; close pipes and reap owned subprocesses."""
    child = subprocess.Popen(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )
    assert child.stdout is not None
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise PluginError("timeout")
                for key, _ in selector.select(min(remaining, 0.2)):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(chunk)
                        if len(output) > MAX_OUTPUT:
                            raise PluginError("output_too_large")
            try:
                return_code = child.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise PluginError("timeout") from None
            if return_code != 0:
                raise PluginError("cli_failed")
        return bytes(output)
    finally:
        try:
            if child.returncode is None:
                _stop_group(child)
        finally:
            child.stdout.close()


def _count(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 10**18:
        raise PluginError("invalid_report")
    return value


def _optional_number(value: object) -> int | float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 10**18:
        raise PluginError("invalid_report")
    return value


def _reduction(value: object, unit: str) -> tuple[int | float | None, int | float | None]:
    if not isinstance(value, dict) or type(value.get("complete")) is not bool:
        raise PluginError("invalid_report")
    if not value["complete"]:
        return None, None
    amount, percentage = _optional_number(value.get(unit)), _optional_number(value.get("percent"))
    if amount is None or percentage is None or percentage > 100:
        raise PluginError("invalid_report")
    return amount, percentage


def project_report(raw: bytes, profile: str) -> dict[str, object]:
    """Forward only approved scalars, never arbitrary CLI text or extra fields."""
    try:
        report = json.loads(raw)
        if (
            report["schema_id"] != "hormuz.personal-benefit"
            or type(report["schema_version"]) is not int or report["schema_version"] != 1
            or report["profile"] != profile
            or type(report["optimization_enabled"]) is not bool
            or report["content_retained"] is not False
        ):
            raise PluginError("invalid_report")
        traffic = report["traffic"]
        requests = _count(traffic["total_requests"])
        eligible = _count(traffic["eligible_requests"])
        transformed = _count(traffic["transformed_requests"])
        if not transformed <= eligible <= requests:
            raise PluginError("invalid_report")
        tokens, token_percent = _reduction(
            report["estimated_token_reduction"]["all_captured_traffic"], "tokens"
        )
        saved_bytes, byte_percent = _reduction(
            report["request_byte_reduction"]["all_captured_traffic"], "bytes"
        )
        cache = report["provider_reported"]["cache_read_tokens"]
        cache_read = _optional_number(cache["total"]) if _count(cache["observed"]) else None
        return {
            "schema": STATUS_SCHEMA, "ok": True, "profile": profile,
            "enabled": report["optimization_enabled"],
            "requests": requests, "eligible": eligible, "transformed": transformed,
            "tokensSaved": tokens, "tokenPercent": token_percent,
            "bytesSaved": saved_bytes, "bytePercent": byte_percent,
            "cacheReadTokens": cache_read,
        }
    except (KeyError, TypeError, ValueError, OverflowError):
        raise PluginError("invalid_report") from None


def status(executable: str, profile: str, state: str, action: str) -> dict[str, object]:
    if action in {"on", "off"}:
        capture(cli_arguments(executable, profile, state, action))
    return project_report(capture(cli_arguments(executable, profile, state, "benefit")), profile)


def _private_directory(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise PluginError("runtime_unavailable")


def launch(executable: str, profile: str, state: str) -> None:
    """Replace this wrapper with the CLI, retaining a per-profile session lock."""
    import fcntl

    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if not runtime or not Path(runtime).is_absolute():
        raise PluginError("runtime_unavailable")
    try:
        root = Path(runtime)
        _private_directory(root)
        lock_dir = root / "hormuz-omarchy"
        lock_dir.mkdir(mode=0o700, exist_ok=True)
        _private_directory(lock_dir)
        # Include effective state so two separate profile stores do not collide.
        effective_state = state or os.environ.get("HORMUZ_CLIENT_STATE_DIRECTORY") or str(
            Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "hormuz"
        )
        key = hashlib.sha256((os.path.abspath(os.path.expanduser(effective_state)) + "\0" + profile).encode()).hexdigest()
        descriptor = os.open(lock_dir / (key + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1:
                raise PluginError("runtime_unavailable")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise PluginError("already_running") from None
            # exec preserves terminal interaction. OS closes the lock on CLI exit.
            os.set_inheritable(descriptor, True)
            os.execvpe(executable, cli_arguments(executable, profile, state, "run"), os.environ.copy())
        finally:
            os.close(descriptor)
    except OSError:
        raise PluginError("runtime_unavailable") from None


def _interrupted(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "on", "off", "launch"])
    parser.add_argument("--cli", default="hormuz")
    parser.add_argument("--profile", default="personal-codex")
    parser.add_argument("--state-directory", default="")
    options = parser.parse_args(argv)
    try:
        executable, state = settings(options.cli, options.profile, options.state_directory)
        if options.action == "launch":
            launch(executable, options.profile, state)
            return 0
        result = status(executable, options.profile, state, options.action)
    except KeyboardInterrupt:
        result = {"ok": False, "error": "interrupted", "message": MESSAGES["interrupted"]}
    except (PluginError, OSError) as error:
        code = error.code if isinstance(error, PluginError) else "cli_failed"
        result = {"ok": False, "error": code, "message": MESSAGES[code]}
    if options.action == "launch":
        print(result["message"], file=sys.stderr)
        return 1
    result.update(schema=STATUS_SCHEMA, profile=options.profile)
    print(json.dumps(result, allow_nan=False, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _interrupted)
    raise SystemExit(main())
