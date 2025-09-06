from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import prisma
from app.routers import bot, document, chat, integration


@asynccontextmanager
async def lifespan(app: FastAPI):
    await prisma.connect()
    print("Database connected")
    yield
    await prisma.disconnect()
    print("Database disconnected")


app = FastAPI(
    title="RAG Chatbot API",
    description="RAG Chatbot with PostgreSQL + pgvector",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bot.router, prefix="/api/v1/bots", tags=["bots"])
app.include_router(document.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(integration.router, prefix="/api/v1/integrations", tags=["integrations"])


@app.get("/")
async def root():
    return {
        "message": "RAG Chatbot API", 
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    try:
        await prisma.query_raw("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}