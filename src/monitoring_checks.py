"""Collection retries and data checks; standard library only, no login side effects."""

import csv
import json
import math
import os
import signal
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BEIJING = timezone(timedelta(hours=8))


def run_attempt(command, stdout, stderr, timeout):
    """On Linux runners, also stop Chromium children when an attempt times out."""
    process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=(os.name == "posix"))
    try:
        return subprocess.CompletedProcess(command, process.wait(timeout=timeout))
    except subprocess.TimeoutExpired:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait()
        raise


def parse_timestamp(value):
    """Historical timestamps without an offset were recorded in Beijing time."""
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=BEIJING) if parsed.tzinfo is None else parsed


def validate_collection(before, after, csv_text, started_at, now=None):
    """Require one fresh, finite record, preserved history and matching CSV."""
    if not after.startswith(before):
        raise ValueError("Collection overwrote existing JSON history")
    if before and not before.endswith(b"\n"):
        raise ValueError("Existing JSON history must end with a newline")
    added = [line for line in after[len(before):].splitlines() if line.strip()]
    if len(added) != 1:
        raise ValueError("Collection must append exactly one record")
    rows = [json.loads(line) for line in after.splitlines() if line.strip()]
    latest = rows[-1]
    value = latest["remaining_electricity"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Electricity must be a finite number")
    if latest.get("unit") != "度":
        raise ValueError("Unexpected electricity unit")
    recorded_at = parse_timestamp(latest["timestamp"])
    now = now or datetime.now(BEIJING)
    if not started_at - timedelta(seconds=5) <= recorded_at <= now + timedelta(minutes=5):
        raise ValueError("New record timestamp is stale or in the future")
    csv_rows = list(csv.DictReader(csv_text.splitlines()))
    if len(csv_rows) != len(rows):
        raise ValueError("CSV and JSON record counts differ")
    for json_row, csv_row in zip(rows, csv_rows):
        if (parse_timestamp(csv_row["time"]) != parse_timestamp(json_row["timestamp"])
                or float(csv_row["num"]) != float(json_row["remaining_electricity"])
                or csv_row["unit"] != json_row["unit"]):
            raise ValueError("CSV and JSON records differ")
    return latest


def run_collection(command, data_dir, log, attempts=3, timeout=240,
                   runner=run_attempt, sleep=time.sleep):
    data_dir = Path(data_dir)
    json_path = data_dir / "electricity_data.json"
    csv_path = data_dir / "electricity_data.csv"
    before = json_path.read_bytes() if json_path.exists() else b""
    started_at = datetime.now(BEIJING)
    for attempt in range(1, attempts + 1):
        log.write(f"Collection attempt {attempt}/{attempts}; timeout={timeout}s\n")
        log.flush()
        try:
            result = runner(command, stdout=log, stderr=log, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
            log.write("Collection attempt timed out\n")
        after = json_path.read_bytes() if json_path.exists() else b""
        if code == 0:
            latest = validate_collection(before, after, csv_path.read_text(encoding="utf-8"), started_at)
            log.write(f"Verified new record: {latest['timestamp']}\n")
            log.flush()
            return latest
        if after != before:
            raise RuntimeError("Collection failed after modifying data; refusing a duplicate retry")
        log.write(f"Workflow script exited with code {code}\n")
        log.flush()
        if attempt == attempts:
            raise RuntimeError(f"Collection failed after {attempts} attempts (exit {code})")
        sleep(15 * attempt)
