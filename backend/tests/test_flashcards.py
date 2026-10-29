from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.db import utcnow
from app.modules.core.models import ActivityCompletion, User
from app.modules.core.service import today_summary
from app.modules.flashcards.models import CardState, Review


def test_deck_subject_assignment_reassignment_and_ownership(client, owner, other, deck):
    path = f"/api/flashcards/decks/{deck['id']}"
    assert client.get(path, headers=owner).json()["subject"] == ""
    payload = {"name": deck["name"], "subject": "  BIO101 · Biology  "}
    assert client.put(path, headers=other, json=payload).status_code == 404
    response = client.put(path, headers=owner, json=payload)
    assert response.status_code == 200
    assert response.json()["subject"] == "BIO101 · Biology"
    assert client.get("/api/flashcards/decks", headers=owner).json()[0]["subject"] == "BIO101 · Biology"
    created = client.post("/api/flashcards/decks", headers=owner,
        json={"name": "Week 2", "subject": "BIO101 · Biology"})
    assert created.status_code == 201 and created.json()["subject"] == "BIO101 · Biology"
    assert client.put(path, headers=owner, json={**payload, "subject": "Calculus"}).json()["subject"] == "Calculus"
    assert client.put(path, headers=owner, json={**payload, "subject": "  "}).json()["subject"] == ""
    assert client.put(path, headers=owner, json={**payload, "subject": "x" * 121}).status_code == 422


def test_ownership(client, owner, other, deck, card):
    d, c = deck["id"], card["id"]
    for method, path, kwargs in [
        ("get", f"/decks/{d}", {}), ("get", f"/decks/{d}/cards", {}),
        ("put", f"/decks/{d}", {"json": {"name": "stolen"}}), ("delete", f"/decks/{d}", {}),
        ("post", f"/decks/{d}/cards", {"json": {"front": "x", "back": "y"}}),
        ("get", f"/cards/{c}", {}), ("put", f"/cards/{c}", {"json": {"front": "x", "back": "y"}}),
        ("delete", f"/cards/{c}", {}), ("post", f"/decks/{d}/sessions", {}),
        ("post", f"/decks/{d}/import", {"files": {"file": ("cards.csv", b"front,back\nx,y")}}),
    ]:
        assert getattr(client, method)(f"/api/flashcards{path}", headers=other, **kwargs).status_code == 404
    assert client.get("/api/flashcards/decks", headers=other).json() == []
    assert client.get(f"/api/flashcards/cards/{c}", headers=owner).json()["front"] == "Question?"


def test_crud_and_csv(client, owner, deck, card):
    d, c = deck["id"], card["id"]
    assert client.put(f"/api/flashcards/decks/{d}", headers=owner, json={"name": "Renamed"}).json()["name"] == "Renamed"
    assert client.put(f"/api/flashcards/cards/{c}", headers=owner, json={"front": "Edited", "back": "Answer"}).status_code == 200
    response = client.post(f"/api/flashcards/decks/{d}/import", headers=owner,
        files={"file": ("cards.csv", b'front,back\nHello,World\n,Empty\n"Comma, here",OK\nshort\n')})
    assert response.status_code == 200
    assert response.json()["imported"] == 2
    assert response.json()["skipped"] == 2
    assert client.post(f"/api/flashcards/decks/{d}/import", headers=owner,
        files={"file": ("bad.csv", b"bad,headers\nx,y")}).status_code == 422
    assert len(client.get(f"/api/flashcards/decks/{d}/cards", headers=owner).json()) == 3
    assert client.delete(f"/api/flashcards/cards/{c}", headers=owner).status_code == 200
    assert client.get(f"/api/flashcards/cards/{c}", headers=owner).status_code == 404
    assert client.delete(f"/api/flashcards/decks/{d}", headers=owner).status_code == 200


def test_review_idempotency_completion_and_conflict(client, owner, other, deck, card, db):
    session = client.post(f"/api/flashcards/decks/{deck['id']}/sessions", headers=owner).json()
    sid = session["id"]
    complete = f"/api/flashcards/sessions/{sid}/complete"
    assert client.post(complete, headers=other).status_code == 404
    assert client.post(complete, headers=owner).status_code == 409
    payload = {"id": str(uuid4()), "card_id": card["id"], "session_id": sid,
               "rating": "good", "version": 0, "reviewed_at": utcnow().isoformat()}
    assert client.post("/api/flashcards/reviews", headers=other, json=payload).status_code == 404
    assert client.post("/api/flashcards/reviews", headers=owner, json=payload).json()["duplicate"] is False
    assert client.post("/api/flashcards/reviews", headers=owner, json=payload).json()["duplicate"] is True
    assert client.post("/api/flashcards/reviews", headers=owner, json={**payload, "rating": "easy"}).status_code == 409
    assert client.post(complete, headers=owner).status_code == 200
    assert client.post(complete, headers=owner).status_code == 200
    assert db.scalar(select(func.count()).select_from(Review)) == 1
    assert db.scalar(select(func.count()).select_from(ActivityCompletion)) == 1
    today = client.get("/api/core/today", headers=owner).json()
    assert today["streak"] == 1 and next(item for item in today["activities"] if item["type"] == "flashcards")["completions"] == 1
    assert client.get(f"/api/flashcards/decks/{deck['id']}/cards?due=true", headers=owner).json() == []
    summary = client.get(f"/api/flashcards/decks/{deck['id']}", headers=owner).json()
    assert summary["ready_count"] == 0
    assert db.get(CardState, UUID(card["id"])).stability is not None
    assert db.scalar(select(Review)).scheduler == "fsrs6"
    # Real foreign-key databases must support deleting already-reviewed decks too.
    assert client.delete(f"/api/flashcards/decks/{deck['id']}", headers=owner).status_code == 200
    assert db.scalar(select(func.count()).select_from(ActivityCompletion)) == 1


def test_quick_session_default_limit_and_stale_version(client, owner, deck, card, db):
    for i in range(12):
        client.post(f"/api/flashcards/decks/{deck['id']}/cards", headers=owner,
                    json={"front": f"Question {i}", "back": "Answer"})
    session = client.post(f"/api/flashcards/decks/{deck['id']}/sessions", headers=owner).json()
    assert len(session["cards"]) == 10
    card = session["cards"][0]
    state = db.get(CardState, UUID(card["id"]))
    state.version = 1
    db.commit()
    assert client.post("/api/flashcards/reviews", headers=owner, json={
        "id": str(uuid4()), "card_id": card["id"], "session_id": session["id"], "rating": "easy",
        "version": 0, "reviewed_at": utcnow().isoformat()}).status_code == 409


def test_streak_uses_all_activity_types_and_utc_days(db, client, owner):
    user = db.scalar(select(User))
    now = utcnow()
    for days in [0, 0, 1, 2, 4]:
        db.add(ActivityCompletion(user_id=user.id, activity_type="future-module", activity_ref=uuid4(),
                                   completed_at=now - timedelta(days=days), points=3))
    db.commit()
    assert today_summary(db, user.id) == {"streak": 3, "points": 6}
