from fastapi import APIRouter

from app.api.routes import linkedin

api_router = APIRouter()
api_router.include_router(linkedin.router)
