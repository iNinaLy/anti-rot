from app.modules.rewards.router import router
from app.registry import Module

module = Module("rewards", router)
