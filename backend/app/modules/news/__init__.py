from app.modules.news.router import router
from app.registry import Module

# Reading progress intentionally earns no points and does not affect streaks.
module = Module("news", router)
