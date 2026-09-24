from fastapi import APIRouter

from modules.auth.router import router as auth_router
from modules.conversations.router import router as conversations_router
from modules.documents.router import router as documents_router
from modules.messages.router import router as messages_router
from modules.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(conversations_router)
api_router.include_router(messages_router)
api_router.include_router(documents_router)
