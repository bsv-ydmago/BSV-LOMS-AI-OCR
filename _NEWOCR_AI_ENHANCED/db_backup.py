"""
db_backup.py — Automated Daily PostgreSQL Backup
=================================================
Schedules a pg_dump every day at 4:00 PM local time.
Runs in a background daemon thread — safe to import from app.py.

Usage (in app.py):
    from db_backup import start_backup_scheduler
    start_backup_scheduler()

Backup files are written to:
    <SCRIPT_DIR>/backups/YYYY-MM-DD/backup_HH-MM-SS.sql

Each day gets its own folder. Only the most recent MAX_DAYS
dated folders are kept (default: 30).
"""

import os
import subprocess
import threading
import time
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

BACKUP_HOUR   = 13   # 11 AM
BACKUP_MINUTE = 35   # :50
CHECK_INTERVAL = 60          # seconds between clock checks
MAX_DAYS       = 30          # how many dated folders to keep

# Backups are stored in the current Windows user's Documents folder.
# This works whether running from source or as a PyInstaller .exe,
# and survives app reinstalls or moving the .exe.
#
# Final structure:
#   C:/Users/<you>/Documents/
#     └── DocExtractPro Backups/
#           └── 2025-05-05/
#                 └── backup_16-00-12.sql
#
# Path.home() always returns the current user's home directory
# (e.g. C:/Users/Juan) on Windows, macOS, and Linux.
BACKUP_DIR = Path.home() / "Documents" / "DocExtractPro Backups"

log = logging.getLogger("db_backup")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _pg_dump_path() -> str:
    """
    Return the full path to pg_dump.
    Checks common PostgreSQL installation paths on Windows first,
    then falls back to assuming pg_dump is on PATH.
    """
    candidates = [
        r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\14\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\13\bin\pg_dump.exe",
        r"C:\Program Files (x86)\PostgreSQL\17\bin\pg_dump.exe",
        r"C:\Program Files (x86)\PostgreSQL\16\bin\pg_dump.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return "pg_dump"   # assume it's on PATH (Linux / macOS / custom Windows install)


def _prune_old_day_folders():
    """
    Remove the oldest dated subfolders under BACKUP_DIR if the
    total count exceeds MAX_DAYS.

    Only removes folders whose names look like YYYY-MM-DD.
    """
    if not BACKUP_DIR.exists():
        return
    dated = sorted(
        [d for d in BACKUP_DIR.iterdir() if d.is_dir() and _is_date_folder(d.name)],
        key=lambda d: d.name,   # lexicographic == chronological for YYYY-MM-DD
    )
    excess = len(dated) - MAX_DAYS
    for folder in dated[:excess]:
        try:
            import shutil
            shutil.rmtree(folder)
            log.info("Pruned old backup folder: %s", folder.name)
        except Exception as exc:
            log.warning("Could not prune folder %s: %s", folder.name, exc)


def _is_date_folder(name: str) -> bool:
    """Return True if name looks like YYYY-MM-DD."""
    try:
        datetime.strptime(name, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def run_backup() -> bool:
    """
    Execute pg_dump and save into a dated subfolder.

    Final path example:
        backups/
          2025-05-05/
            backup_16-00-12.sql

    Returns True on success, False on failure.
    """
    now         = datetime.now()
    date_str    = now.strftime("%Y-%m-%d")          # folder name  e.g. 2025-05-05
    time_str    = now.strftime("%H-%M-%S")          # file suffix  e.g. 16-00-12

    today_dir   = BACKUP_DIR / date_str
    today_dir.mkdir(parents=True, exist_ok=True)

    output_file = today_dir / f"backup_{time_str}.sql"

    host     = os.getenv("DB_HOST",     "localhost")
    port     = os.getenv("DB_PORT",     "5432")
    dbname   = os.getenv("DB_NAME",     "")
    user     = os.getenv("DB_USER",     "")
    password = os.getenv("DB_PASSWORD", "")

    if not dbname or not user:
        log.error("DB_NAME or DB_USER missing from .env — backup aborted.")
        return False

    env = os.environ.copy()
    env["PGPASSWORD"] = password          # avoids interactive password prompt

    cmd = [
        _pg_dump_path(),
        "-h", host,
        "-p", port,
        "-U", user,
        "-d", dbname,
        "-F", "p",                        # plain-text SQL (human-readable)
        "-f", str(output_file),
    ]

    log.info("Starting backup → backups/%s/%s", date_str, output_file.name)
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,                  # 10-minute hard limit
        )
        if result.returncode == 0:
            size_kb = output_file.stat().st_size // 1024
            log.info(
                "Backup complete (%d KB): backups/%s/%s",
                size_kb, date_str, output_file.name,
            )
            _prune_old_day_folders()
            return True
        else:
            log.error("pg_dump failed (exit %d):\n%s", result.returncode, result.stderr)
            if output_file.exists():
                output_file.unlink(missing_ok=True)
            return False

    except FileNotFoundError:
        log.error(
            "pg_dump not found. Install PostgreSQL client tools or add pg_dump to PATH.\n"
            "Download: https://www.postgresql.org/download/"
        )
        return False
    except subprocess.TimeoutExpired:
        log.error("pg_dump timed out after 10 minutes.")
        return False
    except Exception as exc:
        log.error("Unexpected backup error: %s", exc)
        return False


# ── Scheduler ─────────────────────────────────────────────────────────────────

_scheduler_started = False   # guard against double-start
_backup_done_today: str = "" # tracks the date of the last successful run


def _scheduler_loop():
    global _backup_done_today
    log.info(
        "Backup scheduler started — daily backup at %02d:%02d.",
        BACKUP_HOUR, BACKUP_MINUTE,
    )
    while True:
        time.sleep(CHECK_INTERVAL)
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        if (
            now.hour   == BACKUP_HOUR
            and now.minute == BACKUP_MINUTE
            and _backup_done_today != today   # run only once per day
        ):
            log.info("4 PM reached — running scheduled backup.")
            success = run_backup()
            if success:
                _backup_done_today = today


def start_backup_scheduler():
    """
    Start the background scheduler thread.
    Safe to call multiple times — only one thread is ever created.
    """
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    t = threading.Thread(target=_scheduler_loop, name="db-backup-scheduler", daemon=True)
    t.start()
    log.info("db_backup: scheduler thread launched.")