"""Restore a nightly archive with the app stopped. Never extract arbitrary paths."""
import argparse
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

from app.config import get_settings
from app.db import engine
from app.registry import discover_modules
from app.transfer import import_database


def restore(archive_path: Path, replace: bool = False) -> None:
    settings = get_settings()
    with tempfile.TemporaryDirectory(prefix="anti-rot-restore-") as temporary:
        staging = Path(temporary).resolve()
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                target = (staging / member.name).resolve()
                if (not target.is_relative_to(staging) or member.issym() or member.islnk()
                    or not (member.isfile() or member.isdir())
                    or not (member.name in ("manifest.json", "push-keys.json", "database/app.db", "database/database.json", "database", "media") or member.name.startswith("media/"))):
                    raise ValueError("Archive contains an unexpected or unsafe path")
            archive.extractall(staging, filter="data")
        manifest = json.loads((staging / "manifest.json").read_text())
        if manifest.get("format") != 1:
            raise ValueError("Unsupported backup format")
        sqlite = staging / "database" / "app.db"
        logical = staging / "database" / "database.json"
        if sqlite.exists():
            if engine.dialect.name != "sqlite" or not engine.url.database:
                raise ValueError("Use database transfer to change database types")
            target = Path(engine.url.database).resolve()
            if target.exists() and not replace:
                raise ValueError("Database already exists. Stop the app and use --replace only if intentional")
            engine.dispose()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sqlite, target)
            # The snapshot is self-contained; stale journals must not be replayed.
            for suffix in ("-wal", "-shm", "-journal"):
                Path(str(target) + suffix).unlink(missing_ok=True)
        elif logical.exists():
            discover_modules()
            import_database(engine, logical)  # Explicitly refuses any non-empty target.
        else:
            raise ValueError("Archive has no supported database snapshot")
        media = staging / "media"
        if media.exists():
            settings.media_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(media, settings.media_dir, dirs_exist_ok=True)
        key = staging / "push-keys.json"
        if key.exists():
            settings.push_keys_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(key, settings.push_keys_file)
            settings.push_keys_file.chmod(0o600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore a nightly Anti-Rot archive. Stop the app first.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--replace", action="store_true", help="Explicitly replace an existing SQLite database")
    args = parser.parse_args()
    try:
        restore(args.archive, args.replace)
        print("Restore complete. Start the app to apply pending migrations.")
    except Exception as error:
        raise SystemExit(f"Restore failed: {type(error).__name__}. Check the archive, database type, permissions and an empty target.")
