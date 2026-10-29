from sqlalchemy import func, select

from app.modules.flashcards.models import Subject
from app.modules.flashcards.subjects import DEFAULT_SUBJECTS


def test_default_subjects_and_private_persistent_additions(client, owner, other, db):
    path = "/api/flashcards/subjects"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=owner).json() == list(DEFAULT_SUBJECTS)
    response = client.post(path, headers=owner, json={"name": "  ITT700 – Advanced Networking  "})
    assert response.status_code == 201
    assert response.json()["name"] == "ITT700 – Advanced Networking"
    assert "ITT700 – Advanced Networking" in client.get(path, headers=owner).json()
    assert client.get(path, headers=other).json() == list(DEFAULT_SUBJECTS)
    assert client.post(path, headers=owner, json={"name": "itt700 – advanced networking"}).json()["name"] == response.json()["name"]
    assert db.scalar(select(func.count()).select_from(Subject)) == 1
    assert client.post(path, headers=owner, json={"name": "   "}).status_code == 422
    assert client.post(path, headers=owner, json={"name": "x" * 121}).status_code == 422


def test_legacy_deck_subjects_stay_selectable_and_can_be_saved(client, owner, other, deck):
    path = "/api/flashcards/subjects"
    client.put(f"/api/flashcards/decks/{deck['id']}", headers=owner,
        json={"name": deck["name"], "subject": "Legacy subject"})
    assert "Legacy subject" in client.get(path, headers=owner).json()
    assert "Legacy subject" not in client.get(path, headers=other).json()
    assert client.post(path, headers=owner, json={"name": "legacy subject"}).json()["name"] == "Legacy subject"
    client.delete(f"/api/flashcards/decks/{deck['id']}", headers=owner)
    assert "Legacy subject" in client.get(path, headers=owner).json()
