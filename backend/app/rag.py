from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from typing import Iterable, List, Dict, Any

import httpx


DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
DEFAULT_RERANK_MODEL = os.getenv("OLLAMA_RERANK_MODEL", os.getenv("OLLAMA_CHAT_MODEL", "llama3.2"))


@dataclass
class IndexChunk:
    url: str
    title: str
    text: str
    embedding: List[float]


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> Iterable[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    step = max(1, chunk_size - overlap)
    return [cleaned[i : i + chunk_size] for i in range(0, len(cleaned), step)]


def embed_text(text: str, model: str = DEFAULT_EMBED_MODEL) -> List[float]:
    resp = httpx.post(
        f"{DEFAULT_OLLAMA_URL}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("embedding", [])


def build_index(
    pages: Iterable[Dict[str, str]],
    chunk_size: int = 1200,
    overlap: int = 200,
    max_chunks_per_page: int = 8,
    embed_model: str = DEFAULT_EMBED_MODEL,
) -> List[IndexChunk]:
    chunks: List[IndexChunk] = []
    for page in pages:
        url = page.get("url", "")
        title = page.get("title", "")
        text = page.get("text", "")
        if not text:
            continue
        for chunk in chunk_text(text, chunk_size=chunk_size, overlap=overlap)[:max_chunks_per_page]:
            embedding = embed_text(chunk, model=embed_model)
            if not embedding:
                continue
            chunks.append(IndexChunk(url=url, title=title, text=chunk, embedding=embedding))
    return chunks


def save_index(chunks: Iterable[IndexChunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            payload = {
                "url": chunk.url,
                "title": chunk.title,
                "text": chunk.text,
                "embedding": chunk.embedding,
            }
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def load_index(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_index(
    index: List[Dict[str, Any]],
    query: str,
    top_k: int = 4,
    embed_model: str = DEFAULT_EMBED_MODEL,
) -> List[Dict[str, Any]]:
    try:
        query_embedding = embed_text(query, model=embed_model)
    except httpx.HTTPError:
        return []
    if not query_embedding:
        return []
    scored: List[Dict[str, Any]] = []
    for entry in index:
        score = cosine_similarity(query_embedding, entry.get("embedding", []))
        scored.append({**entry, "score": score})
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def rerank_results(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 4,
    model: str = DEFAULT_RERANK_MODEL,
) -> List[Dict[str, Any]]:
    if not candidates:
        return []
    prompt = build_rerank_prompt(query, candidates)
    try:
        resp = httpx.post(
            f"{DEFAULT_OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("response", "").strip()
    except (httpx.HTTPError, ValueError):
        return candidates[:top_k]

    scores = parse_score_list(raw, expected_len=len(candidates))
    if scores is None:
        return candidates[:top_k]

    rescored = []
    for entry, score in zip(candidates, scores):
        rescored.append({**entry, "rerank_score": score})
    rescored.sort(key=lambda item: item.get("rerank_score", 0), reverse=True)
    return rescored[:top_k]


def build_rerank_prompt(query: str, candidates: List[Dict[str, Any]]) -> str:
    lines = [
        "Tu es un reranker. Donne un score de pertinence entre 0 et 3 pour chaque passage.",
        "Reponds uniquement avec un tableau JSON de nombres, dans le meme ordre.",
        "0 = pas pertinent, 3 = repond clairement a la question.",
        "Si un passage est un menu, une navigation, ou du contenu general sans reponse, donne 0.",
        f"Question: {query}",
        "Passages:",
    ]
    for idx, entry in enumerate(candidates):
        title = entry.get("title", "")
        url = entry.get("url", "")
        text = truncate(entry.get("text", ""))
        header = f"[{idx}] {title} - {url}" if title else f"[{idx}] {url}"
        lines.append(header)
        lines.append(text)
    return "\n".join(lines)


def parse_score_list(raw: str, expected_len: int) -> List[int] | None:
    payload = raw
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        start = payload.find("[")
        end = payload.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(payload[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(data, list) or len(data) != expected_len:
        return None
    scores: List[int] = []
    for item in data:
        try:
            score = int(item)
        except (TypeError, ValueError):
            score = 0
        scores.append(max(0, min(score, 3)))
    return scores


def shorten(text: str, max_len: int = 240) -> str:
    cleaned = normalize_text(text)
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "..."


def truncate(text: str, max_len: int = 900) -> str:
    cleaned = normalize_text(text)
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "..."
