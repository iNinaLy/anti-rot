"""Portable logical snapshots. Import only into an empty, migrated database."""
from datetime import date, datetime
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import Date, DateTime, Uuid, create_engine, func, select

from app.db import Base, UTCDateTime


def export_database(engine, path: Path) -> None:
    options = {"isolation_level": "REPEATABLE READ"} if engine.dialect.name == "postgresql" else {}
    with engine.connect().execution_options(**options) as connection, connection.begin():
        tables = {table.name: [dict(row) for row in connection.execute(select(table)).mappings()]
                  for table in Base.metadata.sorted_tables}
    path.write_text(json.dumps({"format": 1, "tables": tables}, default=lambda value:
        value.isoformat() if isinstance(value, (date, datetime)) else str(value)), encoding="utf-8")


def import_database(engine, path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != 1 or set(data.get("tables", {})) != set(Base.metadata.tables):
        raise ValueError("Snapshot schema differs; use the matching app version and migrations")
    with engine.begin() as connection:
        if any(connection.scalar(select(func.count()).select_from(table)) for table in Base.metadata.sorted_tables):
            raise ValueError("Target database must be empty; existing data will never be overwritten")
        for table in Base.metadata.sorted_tables:
            rows = data["tables"][table.name]
            for row in rows:
                for column in table.columns:
                    value = row.get(column.name)
                    if value is None:
                        continue
                    if isinstance(column.type, Uuid):
                        row[column.name] = UUID(value)
                    elif isinstance(column.type, (DateTime, UTCDateTime)):
                        row[column.name] = datetime.fromisoformat(value)
                    elif isinstance(column.type, Date):
                        row[column.name] = date.fromisoformat(value)
            if rows:
                connection.execute(table.insert(), rows)


if __name__ == "__main__":
    import argparse
    from app.registry import discover_modules
    discover_modules()
    parser = argparse.ArgumentParser(description="Anti-Rot database transfer; URLs come from environment variables")
    parser.add_argument("action", choices=("export", "import"))
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    key = "SOURCE_DATABASE_URL" if args.action == "export" else "TARGET_DATABASE_URL"
    if not os.environ.get(key):
        parser.error(f"Set {key} in the environment")
    try:
        transfer_engine = create_engine(os.environ[key])
        (export_database if args.action == "export" else import_database)(transfer_engine, args.file)
        transfer_engine.dispose()
        print("Database transfer complete.")
    except Exception as error:
        # Driver errors can include credentials or row values; do not print them.
        raise SystemExit(f"Transfer failed ({type(error).__name__}). Check schema, permissions and an empty target database.")
