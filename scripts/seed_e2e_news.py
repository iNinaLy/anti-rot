"""Synthetic RSS-like stories for isolated browser tests only."""
import hashlib

from app.db import SessionLocal, utcnow
from app.registry import discover_modules
from app.modules.news.models import NewsArticle

discover_modules()
stories = [
    ("malaysia", "BERNAMA", "Parliament debates rural broadband investment"),
    ("malaysia", "Malay Mail", "Ringgit gains as consumer inflation eases"),
    ("malaysia", "Malaysiakini", "New education policy supports student research"),
    ("world", "BBC", "Diplomats begin regional trade negotiations"),
    ("world", "The Guardian", "Global shipping agreement sets new standards"),
    ("world", "BBC", "Voters prepare for an important election"),
    ("discovery", "Malay Mail", "Engineers develop faster battery charging"),
    ("discovery", "BBC", "Astronomers discover distant planetary system"),
    ("discovery", "The Guardian", "Museum opens interactive history exhibition"),
    ("malaysia", "BERNAMA", "Public transport services extend into new districts"),
]
with SessionLocal() as db:
    for index, (category, source, title) in enumerate(stories):
        url = f"https://example.com/synthetic-story/{index}"
        db.add(NewsArticle(url_hash=hashlib.sha256(url.encode()).hexdigest(), url=url,
            title=title, excerpt="Synthetic story for browser verification; not real news.",
            source=source, category=category, tags="", published_at=utcnow()))
    db.commit()
