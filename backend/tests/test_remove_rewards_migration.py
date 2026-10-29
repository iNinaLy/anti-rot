from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, func, inspect, select

from app.config import get_settings


def test_remove_rewards_preserves_shared_activity(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'remove-rewards.db').as_posix()}"
    monkeypatch.setattr(get_settings(), 'database_url', url)
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / 'alembic.ini'))
    config.set_main_option('script_location', str(backend / 'migrations'))
    command.upgrade(config, '0007')
    engine = create_engine(url)
    metadata = MetaData(); metadata.reflect(engine)
    user, reward = uuid4().hex, uuid4().hex
    now = datetime.now(timezone.utc)
    with engine.begin() as db:
        db.execute(metadata.tables['users'].insert(), {'id': user, 'email': 'legacy@example.com', 'password_hash': 'unused', 'created_at': now})
        db.execute(metadata.tables['rewards'].insert(), {'id': reward, 'user_id': user, 'name': 'Old reward', 'cost': 1, 'active': True})
        db.execute(metadata.tables['reward_wallets'].insert(), {'user_id': user, 'version': 1})
        db.execute(metadata.tables['redemptions'].insert(), {'id': uuid4().hex, 'user_id': user, 'reward_id': reward, 'name': 'Old reward', 'cost': 1, 'redeemed_at': now})
        db.execute(metadata.tables['activity_completions'].insert(), {'id': uuid4().hex, 'user_id': user, 'activity_type': 'exercise', 'activity_ref': uuid4().hex, 'completed_at': now, 'points': 1})
    command.upgrade(config, 'head')
    assert not {'rewards', 'reward_wallets', 'redemptions'} & set(inspect(engine).get_table_names())
    with engine.connect() as db:
        assert db.scalar(select(func.count()).select_from(metadata.tables['activity_completions'])) == 1
        assert db.scalar(select(func.count()).select_from(metadata.tables['users'])) == 1
    command.check(config)
    engine.dispose()
