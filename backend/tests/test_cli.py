from contextlib import nullcontext

from sqlalchemy import select

from app import cli
from app.modules.core.models import User
from app.modules.core.service import password_matches


def configure(monkeypatch, db, passwords):
    answers = iter(passwords)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "getpass", lambda prompt: next(answers))
    monkeypatch.setattr(cli, "SessionLocal", lambda: nullcontext(db))


def test_cli_creates_account_that_can_sign_in(monkeypatch, db, client, capsys):
    password = "local-account-password"
    configure(monkeypatch, db, [password, password])
    assert cli.main(["create-user", "--email", "OWNER@example.com"]) == 0
    user = db.scalar(select(User))
    assert user.email == "owner@example.com"
    assert password_matches(password, user.password_hash)
    output = capsys.readouterr()
    assert password not in output.out + output.err
    assert client.post("/api/core/auth/login", json={"email": user.email, "password": password}).status_code == 200
    configure(monkeypatch, db, [password, password])
    assert cli.main(["create-user", "--email", "OWNER@example.com"]) == 1
    assert "already registered" in capsys.readouterr().err


def test_cli_rejects_mismatched_and_weak_password_without_echo(monkeypatch, db, capsys):
    for passwords in (["first-secret", "second-secret"], ["short", "short"]):
        configure(monkeypatch, db, passwords)
        assert cli.main(["create-user", "--email", "owner@example.com"]) == 1
        output = capsys.readouterr()
        assert passwords[0] not in output.out + output.err
        assert db.scalar(select(User)) is None


def test_cli_requires_interactive_terminal(monkeypatch, db, capsys):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    assert cli.main(["create-user", "--email", "owner@example.com"]) == 1
    assert "interactive terminal" in capsys.readouterr().err
