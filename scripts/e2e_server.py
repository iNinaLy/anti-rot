"""Serve a production build against temporary data for browser tests."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="daymark-e2e-") as temporary:
    directory = Path(temporary)
    environment = {**os.environ, "SECRET_KEY": secrets.token_urlsafe(48),
        "DATABASE_URL": "sqlite:///" + (directory / "app.db").as_posix(),
        "MEDIA_DIR": str(directory / "media"), "COOKIE_SECURE": "false",
        "NEWS_FETCH_ENABLED": "false",
        "BACKUPS_ENABLED": "false",
        "STATIC_DIR": str(root / "frontend" / "dist")}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=root / "backend", env=environment, check=True)
    # Provision a test account through the same local service as the CLI.
    subprocess.run([sys.executable, "-c",
        "from app.registry import discover_modules; discover_modules(); "
        "from app.db import SessionLocal; from app.modules.core.schemas import Credentials; "
        "from app.modules.core.service import create_user; "
        "db=SessionLocal(); create_user(db, Credentials(email='browser@example.com', "
        "password='browser-test-long-password')); db.close()"],
        cwd=root / "backend", env=environment, check=True)
    subprocess.run([sys.executable, "-c", (root / "scripts" / "seed_e2e_news.py").read_text()],
                   cwd=root / "backend", env=environment, check=True)
    subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                   cwd=root / "backend", env=environment, check=True)
