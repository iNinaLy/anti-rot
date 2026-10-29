import base64
import json
import logging
import os
from threading import Lock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import webpush, WebPushException
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.modules.exercise.models import ExercisePlan, PushSubscription
from app.modules.exercise.service import snapshot, ZONE

key_lock = Lock()
log = logging.getLogger(__name__)


def push_keys() -> dict[str, str]:
    path = get_settings().push_keys_file
    with key_lock:
        if path.exists():
            return json.loads(path.read_text())
        path.parent.mkdir(parents=True, exist_ok=True)
        key = ec.generate_private_key(ec.SECP256R1())
        private = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
        public = key.public_key().public_bytes(serialization.Encoding.X962,
                                               serialization.PublicFormat.UncompressedPoint)
        result = {"private": base64.urlsafe_b64encode(private).decode().rstrip("="),
                  "public": base64.urlsafe_b64encode(public).decode().rstrip("=")}
        # Exclusive creation keeps one persistent identity across app restarts.
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(result, stream)
        except FileExistsError:
            return json.loads(path.read_text())
        return result


def deliver(subscription: PushSubscription, title: str) -> None:
    webpush(subscription_info=json.loads(subscription.subscription),
            data=json.dumps({"title": "Anti-Rot", "body": title, "url": "/?view=exercise"}),
            vapid_private_key=push_keys()["private"],
            vapid_claims={"sub": get_settings().push_contact}, ttl=1800, timeout=10)


def reminder_tick() -> None:
    if not get_settings().reminders_enabled:
        return
    now = utcnow()
    local = now.astimezone(ZONE)
    with SessionLocal() as db:
        for subscription in db.scalars(select(PushSubscription)).all():
            plan = db.get(ExercisePlan, subscription.user_id)
            if not plan or not plan.reminders or subscription.last_sent_date == local.date():
                continue
            hour, minute = map(int, plan.reminder_time.split(":"))
            scheduled = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # A short catch-up window avoids stale reminders after a long outage.
            if not 0 <= (local - scheduled).total_seconds() < 1800:
                continue
            state = snapshot(db, subscription.user_id, now)
            if state["completed_today"] or (state["today_kind"] == "strength" and state["current_day"] > state["total_days"]):
                continue
            title = f"Day {state['current_day']} · Strength" if state["today_kind"] == "strength" else "Time for a walk"
            try:
                deliver(subscription, title)
                subscription.last_sent_date = local.date()
                db.commit()
            except WebPushException as error:
                if error.response is not None and error.response.status_code in (404, 410):
                    db.delete(subscription)
                    db.commit()
                else:
                    log.warning("Push delivery failed for subscription %s", subscription.id)
            except Exception:
                log.warning("Push delivery unavailable for subscription %s", subscription.id)
