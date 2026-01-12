# EPITECH Web RAG Chat

Chatbot local pour repondre aux questions sur EPITECH a partir du site officiel (epitech.eu), via un pipeline RAG.

## Description

Ce projet de cours combine :
- un backend Python (FastAPI) qui gere le RAG et Ollama,
- un frontend statique integre au site,
- une indexation dynamique du site EPITECH pour generer des reponses sourcées.

## Fonctionnalites

- Chat web avec sources cliquables.
- Indexation dynamique du site EPITECH (sitemap + crawl).
- Reranking local pour filtrer les passages peu pertinents.
- Garde-fous (petites phrases, campus, programmes, PGE, etc.).

## Pre-requis

- Python 3
- Ollama installe et lance localement

## Installation

```bash
pip install -r backend/requirements.txt
ollama pull llama3.2
ollama pull nomic-embed-text
```

## Indexation (scraping dynamique)

```bash
python -m backend.app.indexer --base-url https://www.epitech.eu --max-pages 80 --max-depth 2
```

Options utiles :
- `--max-pages` : nombre de pages max.
- `--max-depth` : profondeur de crawl.
- `--rate-limit` : delai entre requetes.
- `--no-sitemap` : desactive l'utilisation du sitemap.

## Lancer l application

```bash
uvicorn backend.app.main:app --reload
```

Puis ouvrir :
- `http://localhost:8000/` (site + chatbot)
- `http://localhost:8000/tech-doc.html` (doc technique)

## Structure

- `backend/app/main.py` : API `/chat` + serveur statique.
- `backend/app/agent.py` : logique RAG + guardrails.
- `backend/app/crawler.py` : crawl du site EPITECH.
- `backend/app/rag.py` : embeddings, index, recherche, rerank.
- `backend/app/indexer.py` : construction de l index.
- `frontend/site/` : site web + chatbot integre.

## Configuration

Variables d'environnement utiles :

- `OLLAMA_BASE_URL` (defaut `http://127.0.0.1:11434`)
- `OLLAMA_CHAT_MODEL` (defaut `llama3.2`)
- `OLLAMA_EMBED_MODEL` (defaut `nomic-embed-text`)
- `OLLAMA_RERANK_MODEL` (defaut `llama3.2`)
- `RAG_INDEX_PATH` (defaut `rag_index.jsonl`)
- `RAG_RERANK` (defaut `1`, mettre `0` pour desactiver)

## Notes

- Le crawl est limite au domaine `epitech.eu` et respecte un rate limit.
- Certaines pages peuvent etre partiellement rendues en JavaScript.
- L index (`rag_index.jsonl`) est genere localement et ignore par git.

## Scraping responsable

Ce projet est prevu pour un usage scolaire/perso. Avant de lancer un crawl :

- Verifier les CGU et le robots.txt du site cible.
- Ne pas collecter de donnees personnelles.
- Citer les sources dans les reponses.
- Limiter la charge (1 requete/seconde max).

Si le site interdit le scraping (CGU ou robots.txt), n'effectuez pas le crawl sans accord ecrit.
Si certaines regles ne peuvent pas etre respectees, indiquez-le clairement dans votre documentation
et expliquez ce qui n'a pas ete possible.

## Support

Projet scolaire. Pour toute question : contactez l equipe du groupe.
