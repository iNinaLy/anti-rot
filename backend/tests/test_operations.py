from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import tarfile
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base
from app.modules.core.models import User
from app.modules.operations import service
from app.transfer import export_database, import_database


def test_nightly_backup_includes_media_keys_and_retains_only_configured_count(tmp_path,monkeypatch):
    engine=create_engine(f"sqlite:///{(tmp_path/'source.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(email='backup@example.com',password_hash='hash'));db.commit()
    settings=get_settings()
    monkeypatch.setattr(settings,'backup_dir',tmp_path/'backups')
    monkeypatch.setattr(settings,'backup_keep',2)
    monkeypatch.setattr(settings,'media_dir',tmp_path/'media')
    monkeypatch.setattr(settings,'push_keys_file',tmp_path/'keys.json')
    settings.media_dir.mkdir();(settings.media_dir/'sample').write_bytes(b'image')
    settings.push_keys_file.write_text('private-test-key')
    monkeypatch.setattr(service,'engine',engine)
    now=datetime(2026,10,29,4,tzinfo=timezone.utc)
    for day in range(3): path=service.create_backup(now+timedelta(days=day))
    assert len(list(settings.backup_dir.glob('*.tar.gz')))==2
    with tarfile.open(path) as archive:
        assert {'database/app.db','manifest.json','media/sample','push-keys.json'}.issubset(archive.getnames())
        restored=tmp_path/'restored.db';restored.write_bytes(archive.extractfile('database/app.db').read())
    with sqlite3.connect(restored) as connection:
        assert connection.execute('select count(*) from users').fetchone()[0]==1
    engine.dispose()


def test_restore_rejects_path_traversal(tmp_path):
    import io
    from app.restore import restore
    archive=tmp_path/'unsafe.tar.gz'
    with tarfile.open(archive,'w:gz') as stream:
        member=tarfile.TarInfo('../../escape');member.size=4;stream.addfile(member,io.BytesIO(b'bad!'))
    with pytest.raises(ValueError,match='unsafe'):
        restore(archive)


def test_portable_transfer_roundtrip_refuses_overwrite(tmp_path):
    source=create_engine(f"sqlite:///{(tmp_path/'source.db').as_posix()}")
    target=create_engine(os.environ.get('TEST_DATABASE_URL') or f"sqlite:///{(tmp_path/'target.db').as_posix()}")
    Base.metadata.create_all(source);Base.metadata.create_all(target)
    user_id=uuid4()
    with Session(source) as db:
        db.add(User(id=user_id,email='move@example.com',password_hash='private'));db.commit()
        from app.modules.flashcards.models import Deck,Card,CardState
        deck=Deck(user_id=user_id,name='Transferred',description='',subject='Security')
        db.add(deck);db.flush()
        db.add(Card(deck_id=deck.id,front='Protocol?',back='TLS',tags=['security'],choices=['TLS','FTP'],state=CardState()));db.commit()
    snapshot=tmp_path/'snapshot.json';export_database(source,snapshot);import_database(target,snapshot)
    with Session(target) as db:
        assert db.get(User,user_id).email=='move@example.com'
        card=db.scalar(select(Card))
        assert card.tags==['security'] and card.choices==['TLS','FTP'] and card.state.due_at.tzinfo is not None
    with pytest.raises(ValueError,match='empty'):import_database(target,snapshot)
    if os.environ.get('TEST_DATABASE_URL'):
        Base.metadata.drop_all(target)
    source.dispose();target.dispose()
