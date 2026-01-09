# main.py
from fastapi import FastAPI
from pydantic import BaseModel
from agent import run_agent  # logique IA dans agent.py


app = FastAPI()


class ChatRequest(BaseModel):
    message: str
    session_id: str  # identifiant de conversation (fourni par le front)


class ChatResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # Appel à la logique d'agent qui utilise Ollama
    answer = await run_agent(req.message, req.session_id)
    return ChatResponse(answer=answer)
