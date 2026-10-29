from dataclasses import dataclass
from importlib import import_module
from pkgutil import iter_modules
from typing import Callable
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app import modules


@dataclass(frozen=True)
class Module:
    name: str
    router: APIRouter
    activity_provider: Callable[[Session, UUID], dict] | None = None
    background_tick: Callable[[], None] | None = None


def discover_modules() -> list[Module]:
    return [import_module(f"app.modules.{info.name}").module
            for info in iter_modules(modules.__path__) if info.ispkg]
