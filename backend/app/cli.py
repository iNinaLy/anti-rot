"""Local account administration. Passwords are prompted without terminal echo."""
import argparse
from getpass import getpass
import sys

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.db import SessionLocal
from app.modules.core.schemas import Credentials
from app.modules.core.service import create_user
from app.registry import discover_modules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Anti-Rot local administration")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="Create an account; public sign-up is disabled")
    create.add_argument("--email", help="Email used to sign in (prompted if omitted)")
    args = parser.parse_args(argv)
    if not sys.stdin.isatty():
        print("Run this command in an interactive terminal to enter a hidden password.", file=sys.stderr)
        return 1
    try:
        email = args.email or input("Email: ").strip()
        password = getpass("Password (at least 10 characters): ")
        if password != getpass("Confirm password: "):
            raise ValueError("Passwords do not match")
        credentials = Credentials(email=email, password=password)
        discover_modules()  # Load all table mappings before issuing queries.
        with SessionLocal() as db:
            user = create_user(db, credentials)
            print(f"Account created for {user.email}. You can now sign in.")
        return 0
    except ValidationError as error:
        # Validation errors can include the rejected input; never echo passwords.
        for problem in error.errors(include_input=False, include_url=False):
            print(f"{problem['loc'][0]}: {problem['msg']}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except OperationalError:
        print("Cannot access the database. Check configuration and run Alembic migrations first.", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("\nAccount creation cancelled.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
