from app.modules.core.router import router
from app.registry import Module

module = Module("core", router)
