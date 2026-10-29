import base64
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.modules.core.models import ActivityCompletion, User
from app.modules.exercise import notifications, service
from app.modules.exercise.models import ExerciseCompletion, ExercisePlan, PushSubscription

TUESDAY = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)  # 20:00 Malaysia


def test_defaults_missed_days_and_walks(client, owner, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: TUESDAY)
    plan = client.get("/api/exercise/plan", headers=owner).json()
    assert plan["current_day"] == 1 and plan["weekdays"] == [1, 4, 6]
    assert plan["reminder_time"] == "20:00" and plan["today_kind"] == "strength"
    for days in [1, 3, 20]:
        monkeypatch.setattr(service, "utcnow", lambda days=days: TUESDAY + timedelta(days=days))
        next_plan = client.get("/api/exercise/plan", headers=owner).json()
        assert next_plan["current_day"] == 1  # No calendar-driven advancement.
    monkeypatch.setattr(service, "utcnow", lambda: TUESDAY + timedelta(days=1))
    plan = client.get("/api/exercise/plan", headers=owner).json()
    assert plan["today_kind"] == "walk"
    result = client.post("/api/exercise/complete", headers=owner,
        json={"id": str(uuid4()), "kind": "walk", "version": plan["version"]}).json()
    assert result["current_day"] == 1 and result["completed_today"]


def test_strength_progress_idempotency_activity_and_ownership(client, owner, other, db, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: TUESDAY)
    plan = client.get("/api/exercise/plan", headers=owner).json()
    data = {"id": str(uuid4()), "kind": "strength", "day": 1, "version": plan["version"]}
    result = client.post("/api/exercise/complete", headers=owner, json=data)
    assert result.status_code == 200
    assert result.json()["current_day"] == 2 and result.json()["today_day"] == 1
    assert client.post("/api/exercise/complete", headers=owner, json=data).json()["current_day"] == 2
    assert client.post("/api/exercise/complete", headers=other, json=data).status_code == 409
    assert client.get("/api/exercise/plan", headers=other).json()["current_day"] == 1
    assert db.scalar(select(func.count()).select_from(ExerciseCompletion)) == 1
    assert db.scalar(select(func.count()).select_from(ActivityCompletion)) == 1
    data2 = {**data, "id": str(uuid4()), "day": 2, "version": 1}
    assert client.post("/api/exercise/complete", headers=owner, json=data2).json()["current_day"] == 2
    monkeypatch.setattr(service, "utcnow", lambda: TUESDAY + timedelta(days=10))
    assert client.get("/api/exercise/plan", headers=owner).json()["current_day"] == 2
    assert client.post("/api/exercise/complete", headers=owner, json=data2).json()["current_day"] == 3


def test_day_override_schedule_validation_and_finish(client, owner):
    assert client.get("/api/exercise/plan").status_code == 401
    plan = client.get("/api/exercise/plan", headers=owner).json()
    updated = {**plan, "current_day": 30, "weekdays": [0, 2, 4], "reminder_time": "08:15", "reminders": True}
    response = client.put("/api/exercise/plan", headers=owner, json=updated)
    assert response.status_code == 200
    assert response.json()["reminder_time"] == "08:15"
    assert client.put("/api/exercise/plan", headers=owner, json=updated).status_code == 409
    result = client.post("/api/exercise/complete", headers=owner,
        json={"id": str(uuid4()), "kind": "strength", "day": 30, "version": 1})
    assert result.json()["current_day"] == 31
    for bad in [{"current_day": 32}, {"weekdays": [7]}, {"weekdays": [1, 1]}, {"reminder_time": "25:00"}]:
        assert client.put("/api/exercise/plan", headers=owner, json={**updated, **bad}).status_code == 422


def test_timezone_day_boundary(client, owner, monkeypatch):
    # Monday 16:00 UTC is already Tuesday in Malaysia.
    monkeypatch.setattr(service, "utcnow", lambda: datetime(2026, 10, 26, 16, 0, tzinfo=timezone.utc))
    plan = client.get("/api/exercise/plan", headers=owner).json()
    assert plan["today_date"] == "2026-10-27" and plan["today_kind"] == "strength"


def subscription_payload():
    return {"endpoint": "https://fcm.googleapis.com/fcm/send/test-device",
            "keys": {"p256dh": base64.urlsafe_b64encode(b'\x04' + b'x' * 64).decode().rstrip('='),
                     "auth": base64.urlsafe_b64encode(b'x' * 16).decode().rstrip('=')}}


def test_push_keys_subscription_security_and_reminder_dispatch(client, owner, other, db, monkeypatch):
    key = client.get("/api/exercise/push/key", headers=owner).json()["public_key"]
    assert len(base64.urlsafe_b64decode(key + "==")) == 65
    assert client.get("/api/exercise/push/key", headers=owner).json()["public_key"] == key
    payload = subscription_payload()
    assert client.post("/api/exercise/push/subscribe", headers=owner, json=payload).status_code == 200
    assert client.post("/api/exercise/push/subscribe", headers=other, json=payload).status_code == 409
    assert client.post("/api/exercise/push/subscribe", headers=owner,
        json={**payload, "endpoint": "https://127.0.0.1/private"}).status_code == 422
    plan = client.get("/api/exercise/plan", headers=owner).json()
    client.put("/api/exercise/plan", headers=owner, json={**plan, "reminders": True})
    monkeypatch.setattr(notifications, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(notifications, "utcnow", lambda: TUESDAY)
    calls = []
    monkeypatch.setattr(notifications, "deliver", lambda subscription, title: calls.append(title))
    notifications.reminder_tick()
    notifications.reminder_tick()
    assert calls == ["Day 1 · Strength"]
    monkeypatch.setattr(notifications, "utcnow", lambda: TUESDAY + timedelta(days=1))
    notifications.reminder_tick()
    assert calls[-1] == "Time for a walk"
    assert client.post("/api/exercise/push/unsubscribe", headers=other, json=payload).status_code == 200
    assert db.scalar(select(func.count()).select_from(PushSubscription)) == 1
    client.post("/api/exercise/push/unsubscribe", headers=owner, json=payload)
    assert db.scalar(select(func.count()).select_from(PushSubscription)) == 0


def test_push_key_can_sign_without_external_network(tmp_path, monkeypatch):
    from py_vapid import Vapid
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "push_keys_file", tmp_path / "vapid.json")
    keys = notifications.push_keys()
    signer = Vapid.from_string(keys["private"])
    assert signer.public_key is not None


def test_reminder_window_and_completed_activity_suppress_delivery(client, owner, db, monkeypatch):
    plan = client.get("/api/exercise/plan", headers=owner).json()
    client.put("/api/exercise/plan", headers=owner, json={**plan, "reminders": True})
    client.post("/api/exercise/push/subscribe", headers=owner, json=subscription_payload())
    monkeypatch.setattr(notifications, "SessionLocal", lambda: nullcontext(db))
    calls = []
    monkeypatch.setattr(notifications, "deliver", lambda subscription, title: calls.append(title))
    for now in [TUESDAY - timedelta(minutes=1), TUESDAY + timedelta(minutes=30)]:
        monkeypatch.setattr(notifications, "utcnow", lambda now=now: now)
        notifications.reminder_tick()
    assert calls == []
    monkeypatch.setattr(service, "utcnow", lambda: TUESDAY)
    client.post("/api/exercise/complete", headers=owner,
        json={"id": str(uuid4()), "kind": "strength", "day": 1, "version": 1})
    monkeypatch.setattr(notifications, "utcnow", lambda: TUESDAY)
    notifications.reminder_tick()
    assert calls == []


def test_custom_plan_links_and_strength_only_progress(client, owner, monkeypatch):
    monkeypatch.setattr(service, "utcnow", lambda: TUESDAY)
    plan = client.get("/api/exercise/plan", headers=owner).json()
    plan.update(name="My strength plan", total_days=2, workout_links=["https://youtu.be/first", "https://youtu.be/second"])
    saved = client.put("/api/exercise/plan", headers=owner, json=plan)
    assert saved.status_code == 200
    plan = saved.json()
    assert plan["workout_url"] == "https://youtu.be/first"
    result = client.post("/api/exercise/complete", headers=owner, json={"id": str(uuid4()), "kind": "strength", "day": 1, "version": plan["version"]}).json()
    assert result["progress_percent"] == 50 and result["completed_count"] == 1
    monkeypatch.setattr(service, "utcnow", lambda: TUESDAY + timedelta(days=1))
    result = client.post("/api/exercise/complete", headers=owner, json={"id": str(uuid4()), "kind": "walk", "version": result["version"]}).json()
    assert result["current_day"] == 2 and result["progress_percent"] == 50
    assert result["workout_url"] == "https://youtu.be/second"
    for bad in [{"playlist_url": "javascript:alert(1)"}, {"workout_links": ["https://example.com/video"]}, {"total_days": 0}, {"current_day": 4}]:
        assert client.put("/api/exercise/plan", headers=owner, json={**result, **bad}).status_code == 422
    # Manually moving ahead does not invent completed sessions.
    result = client.put("/api/exercise/plan", headers=owner, json={**result, "current_day": 3}).json()
    assert result["progress_percent"] == 50
