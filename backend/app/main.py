# main.py
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import run_agent  # logique IA dans agent.py


app = FastAPI()


class ChatRequest(BaseModel):
    message: str
    session_id: str  # identifiant de conversation (fourni par le front)


class Source(BaseModel):
    url: str
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # Appel à la logique d'agent qui utilise Ollama
    answer, sources = await run_agent(req.message, req.session_id)
    return ChatResponse(answer=answer, sources=[Source(**s) for s in sources])


ROOT_DIR = Path(__file__).resolve().parents[2]
SITE_DIR = ROOT_DIR / "frontend" / "site"

app.mount("/", StaticFiles(directory=SITE_DIR, html=True), name="site")
