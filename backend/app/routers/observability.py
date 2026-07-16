"""Authenticated operational status for clinic and read-only staff."""
from fastapi import APIRouter, Depends

from app.dependencies import require_roles
from app.models import User
from app.services.observability import dependency_status

router = APIRouter(prefix='/observability', tags=['observability'])


@router.get('/status')
def status(_: User = Depends(require_roles('technical'))) -> dict:
    """Expose dependency state without returning secrets or connection strings."""
    return dependency_status()
