import os
from pathlib import Path

os.environ["SECRET_KEY"] = "test-only-secret-key-at-least-32-characters"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["COOKIE_SECURE"] = "false"
os.environ["LOGIN_ATTEMPTS"] = "100"
os.environ["NEWS_FETCH_ENABLED"] = "false"
os.environ["BACKUPS_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_db
from app.main import app
from app.modules.core.schemas import Credentials
from app.modules.core.service import create_user


@pytest.fixture
def db(tmp_path: Path):
    test_url = os.environ.get("TEST_DATABASE_URL")
    engine = (create_engine(test_url) if test_url else
              create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    settings = get_settings()
    previous = settings.media_dir
    previous_keys = settings.push_keys_file
    settings.push_keys_file = tmp_path / "push-keys.json"
    settings.media_dir = tmp_path / "media"
    with factory() as session:
        app.dependency_overrides[get_db] = lambda: session
        yield session
    settings.media_dir = previous
    settings.push_keys_file = previous_keys
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def owner(client, db):
    credentials = {"email": "owner@example.com", "password": "a-long-test-password"}
    create_user(db, Credentials(**credentials))
    data = client.post("/api/core/auth/login", json=credentials).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
def other(client, db):
    credentials = {"email": "other@example.com", "password": "another-long-password"}
    create_user(db, Credentials(**credentials))
    data = client.post("/api/core/auth/login", json=credentials).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


@pytest.fixture
def deck(client, owner):
    return client.post("/api/flashcards/decks", headers=owner, json={"name": "Test deck"}).json()


@pytest.fixture
def card(client, owner, deck):
    return client.post(f"/api/flashcards/decks/{deck['id']}/cards", headers=owner,
                       json={"front": "Question?", "back": "Answer."}).json()
