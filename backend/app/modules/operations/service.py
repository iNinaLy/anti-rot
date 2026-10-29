from datetime import datetime
from contextlib import closing
import json
import logging
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db import engine, utcnow
from app.transfer import export_database
from sqlalchemy import inspect, text


def create_backup(now: datetime | None = None) -> Path:
    settings = get_settings()
    now = now or utcnow()
    directory = settings.backup_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    date = now.astimezone(ZoneInfo("Asia/Kuala_Lumpur")).date().isoformat()
    destination = directory / f"anti-rot-{date}.tar.gz"
    partial = directory / f"anti-rot-{date}.partial"
    try:
        with tempfile.TemporaryDirectory(prefix="anti-rot-backup-") as temporary:
            staging = Path(temporary)
            database = staging / ("app.db" if engine.dialect.name == "sqlite" else "database.json")
            if engine.dialect.name == "sqlite":
                if not engine.url.database or engine.url.database == ":memory:":
                    raise ValueError("Nightly snapshots require a file-backed database")
                with closing(sqlite3.connect(engine.url.database)) as source, closing(sqlite3.connect(database)) as target:
                    source.backup(target)
            else:
                export_database(engine, database)
            manifest = staging / "manifest.json"
            with engine.connect() as connection:
                schema = connection.scalar(text("SELECT version_num FROM alembic_version")) if inspect(connection).has_table("alembic_version") else "unversioned"
            manifest.write_text(json.dumps({"format": 1, "database": engine.dialect.name,
                "created_at": now.isoformat(), "schema": schema}), encoding="utf-8")
            with tarfile.open(partial, "w:gz") as archive:
                archive.add(database, arcname="database/" + database.name)
                archive.add(manifest, arcname="manifest.json")
                if settings.media_dir.exists():
                    archive.add(settings.media_dir, arcname="media")
                if settings.push_keys_file.exists():
                    archive.add(settings.push_keys_file, arcname="push-keys.json")
            os.chmod(partial, 0o600)
            os.replace(partial, destination)
        backups = sorted(directory.glob("anti-rot-????-??-??.tar.gz"), reverse=True)
        for old in backups[settings.backup_keep:]:
            if old.resolve().parent == directory:
                old.unlink()
        return destination
    finally:
        partial.unlink(missing_ok=True)


def backup_tick() -> None:
    settings = get_settings()
    if not settings.backups_enabled:
        return
    now = utcnow().astimezone(ZoneInfo("Asia/Kuala_Lumpur"))
    hour, minute = map(int, settings.backup_time.split(":"))
    if (now.hour, now.minute) < (hour, minute):
        return
    if not (settings.backup_dir / f"anti-rot-{now.date().isoformat()}.tar.gz").exists():
        path = create_backup(now)
        logging.getLogger(__name__).info("Nightly backup completed: %s", path.name)
