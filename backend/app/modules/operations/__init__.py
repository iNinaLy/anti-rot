from app.modules.operations.router import router
from app.modules.operations.service import backup_tick
from app.registry import Module

module = Module("operations", router, background_tick=backup_tick)
