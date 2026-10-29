from fastapi import APIRouter

# Backups contain all account data and secrets; there is deliberately no public download endpoint.
router = APIRouter()
