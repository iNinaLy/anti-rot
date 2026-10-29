from datetime import timedelta
import io
import json
from uuid import uuid4

import httpx
from pypdf import PdfWriter
from sqlalchemy import func, select

from app.db import utcnow
from app.modules.core.models import ActivityCompletion, User
from app.modules.flashcards import drafts
from app.modules.flashcards.models import Card


def test_tags_choices_and_tagged_sessions(client, owner, other, deck):
    path = f"/api/flashcards/decks/{deck['id']}/cards"
    created = client.post(path, headers=owner, json={"front":"Protocol?", "back":"TLS", "tags":[" Security ","security","week-1"], "choices":["TLS","FTP","DNS"]})
    assert created.status_code == 201
    assert created.json()["tags"] == ["security","week-1"]
    client.post(path, headers=owner, json={"front":"Other", "back":"Other answer", "tags":["other"]})
    batch = client.post(f"/api/flashcards/decks/{deck['id']}/sessions?tag=security", headers=owner).json()
    assert len(batch["cards"]) == 1 and batch["cards"][0]["choices"] == ["TLS","FTP","DNS"]
    assert client.post(f"/api/flashcards/decks/{deck['id']}/sessions?tag=security", headers=other).status_code == 404
    assert client.post(path, headers=owner, json={"front":"Q", "back":"A", "choices":["B","C"]}).status_code == 422


def test_ai_returns_drafts_only_and_explicit_save_checks_ownership(client, owner, other, deck, db, monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self, url, json):
            return httpx.Response(200, request=httpx.Request('POST',url), json={"response": '{"cards":[{"front":"What does TLS protect?","back":"Data in transit","tags":["security"],"choices":[]}]}'})
    monkeypatch.setattr(drafts.httpx, "Client", FakeClient)
    response = client.post('/api/flashcards/drafts', headers=owner, json={"notes":"TLS encrypts data while it travels between network endpoints.","count":5})
    assert response.status_code == 200
    assert db.scalar(select(func.count()).select_from(Card)) == 0
    assert client.post(f"/api/flashcards/decks/{deck['id']}/drafts/save", headers=other, json=response.json()).status_code == 404
    assert client.post(f"/api/flashcards/decks/{deck['id']}/drafts/save", headers=owner, json=response.json()).json()['imported'] == 1
    assert db.scalar(select(func.count()).select_from(Card)) == 1
    assert client.post('/api/flashcards/drafts/pdf', headers=owner, files={"file":("fake.pdf",b'not a PDF')}).status_code == 422
    writer=PdfWriter();writer.add_blank_page(width=100,height=100);stream=io.BytesIO();writer.write(stream)
    assert client.post('/api/flashcards/drafts/pdf', headers=owner, files={"file":("scan.pdf",stream.getvalue())}).status_code == 422
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    writer=PdfWriter();page=writer.add_blank_page(width=300,height=300)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    contents=DecodedStreamObject();contents.set_data(b'BT /F1 12 Tf 10 100 Td (TLS protects data in transit using encryption and certificates.) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(contents)
    stream=io.BytesIO();writer.write(stream)
    assert client.post('/api/flashcards/drafts/pdf',headers=owner,files={"file":('notes.pdf',stream.getvalue())}).status_code==200


def test_ai_unavailable_never_creates_cards(client, owner, db, monkeypatch):
    class Unavailable:
        def __init__(self, **kwargs): pass
        def __enter__(self): raise httpx.ConnectError('offline')
        def __exit__(self,*args): pass
    monkeypatch.setattr(drafts.httpx, "Client", Unavailable)
    response=client.post('/api/flashcards/drafts',headers=owner,json={"notes":"A long enough paragraph of reference notes.","count":5})
    assert response.status_code == 503
    assert db.scalar(select(func.count()).select_from(Card)) == 0


def test_rewards_balance_ownership_redemption_idempotency_and_history(client, owner, other, db):
    user=db.scalar(select(User).where(User.email=='owner@example.com'))
    db.add(ActivityCompletion(user_id=user.id, activity_type='flashcards',activity_ref=uuid4(),points=10));db.commit()
    reward=client.post('/api/rewards/items',headers=owner,json={"name":"Movie night","cost":7}).json()
    assert client.put(f"/api/rewards/items/{reward['id']}",headers=other,json={"name":"Stolen","cost":1}).status_code == 404
    purchase={"id":str(uuid4()),"reward_id":reward['id']}
    assert client.post('/api/rewards/redeem',headers=other,json=purchase).status_code == 404
    response=client.post('/api/rewards/redeem',headers=owner,json=purchase)
    assert response.json()['balance'] == 3
    assert client.post('/api/rewards/redeem',headers=owner,json=purchase).json()['balance'] == 3
    assert client.post('/api/rewards/redeem',headers=owner,json={**purchase,"id":str(uuid4())}).status_code == 409
    assert client.get('/api/rewards',headers=other).json()['balance'] == 0
    client.delete(f"/api/rewards/items/{reward['id']}",headers=owner)
    result=client.get('/api/rewards',headers=owner).json()
    assert result['rewards'] == [] and result['history'][0]['name'] == 'Movie night'


def test_activity_statistics_are_private_and_have_no_goal(client, owner, other, db):
    user=db.scalar(select(User).where(User.email=='owner@example.com'))
    for days in [0,0,1]:
        db.add(ActivityCompletion(user_id=user.id,activity_type='exercise',activity_ref=uuid4(),points=2,completed_at=utcnow()-timedelta(days=days)))
    db.commit()
    result=client.get('/api/core/stats',headers=owner).json()
    assert result['completions']==3 and result['points']==6 and len(result['days'])==365
    assert result['days'][-1]['completions']==2
    assert client.get('/api/core/stats',headers=other).json()['completions']==0
