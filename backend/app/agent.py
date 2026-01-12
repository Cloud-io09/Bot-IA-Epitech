# agent.py
import os
import re
from urllib.parse import urlparse
from urllib.parse import urlparse
from pathlib import Path
from typing import Dict, List, Tuple

import httpx

from .rag import load_index, search_index, shorten, rerank_results


# session_id -> liste de (role, content)
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
INDEX_PATH = Path(os.getenv("RAG_INDEX_PATH", "rag_index.jsonl"))
DIFFICULTY_THRESHOLD = int(os.getenv("DIFFICULTY_THRESHOLD", "2"))
RERANK_ENABLED = os.getenv("RAG_RERANK", "1") != "0"

SMALLTALK_PATTERNS = [
    "bonjour",
    "salut",
    "coucou",
    "hello",
    "hi",
    "hey",
    "bonsoir",
    "ca va",
    "ça va",
    "merci",
    "merci beaucoup",
    "au revoir",
    "bye",
]

EPITECH_KEYWORDS = [
    "epitech",
    "campus",
    "admission",
    "inscription",
    "candidature",
    "programme",
    "pge",
    "bachelor",
    "msc",
    "mba",
    "alternance",
    "frais",
    "scolarite",
    "formation",
    "ecole",
    "etapes d'admission",
    "master",
    "masters",
]
PGE_BASE_URL = "https://www.epitech.eu/programme-grande-ecole-informatique"
_INDEX_CACHE: List[Dict[str, object]] | None = None
_INDEX_MTIME = 0.0

# session_id -> liste de (role, content)
conversations: Dict[str, List[Tuple[str, str]]] = {}


def get_index() -> List[Dict[str, object]]:
    global _INDEX_CACHE, _INDEX_MTIME
    if not INDEX_PATH.exists():
        return []
    mtime = INDEX_PATH.stat().st_mtime
    if _INDEX_CACHE is None or mtime != _INDEX_MTIME:
        _INDEX_CACHE = load_index(INDEX_PATH)
        _INDEX_MTIME = mtime
    return _INDEX_CACHE or []


def build_sources(hits: List[Dict[str, object]]) -> Tuple[str, List[Dict[str, str]]]:
    blocks: List[str] = []
    sources: List[Dict[str, str]] = []
    for idx, hit in enumerate(hits, start=1):
        score = hit.get("rerank_score", hit.get("score"))
        if isinstance(score, (int, float)):
            if "rerank_score" in hit and score < 1:
                continue
            if "rerank_score" not in hit and score < 0.15:
                continue
        url = str(hit.get("url", "")).strip()
        text = str(hit.get("text", "")).strip()
        title = str(hit.get("title", "")).strip()
        if not url or not text:
            continue
        header = f"[{idx}] {title} - {url}" if title else f"[{idx}] {url}"
        blocks.append(f"{header}\n{text}")
        sources.append({"url": url, "snippet": shorten(text)})
    return "\n\n".join(blocks), sources


def detect_smalltalk(message: str) -> str | None:
    cleaned = message.lower().strip()
    cleaned = re.sub(r"[^\w\s']", " ", cleaned)
    cleaned = " ".join(cleaned.split())
    for pattern in SMALLTALK_PATTERNS:
        if pattern in cleaned:
            if "merci" in cleaned:
                return "Avec plaisir. Si tu as une question sur EPITECH, je suis la."
            if "au revoir" in cleaned or "bye" in cleaned:
                return "A bientot. Je reste dispo pour toute question sur EPITECH."
            if "ca va" in cleaned or "ça va" in cleaned:
                return "Ca va bien, merci. Tu veux des infos sur EPITECH ?"
            return "Bonjour ! Pose-moi une question sur EPITECH."
    return None


def is_epitech_related(message: str) -> bool:
    cleaned = message.lower()
    return any(keyword in cleaned for keyword in EPITECH_KEYWORDS)


def contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def difficulty_score(message: str) -> int:
    tokens = re.findall(r"\w+", message.lower())
    token_set = set(tokens)
    score = 0
    if is_epitech_related(message):
        score += 3
    if any(word in token_set for word in ["quoi", "comment", "ou", "où", "quand", "pourquoi"]):
        score += 1
    if len(tokens) >= 6:
        score += 1
    if len(tokens) >= 12:
        score += 1
    return score


def is_post_url(url: str) -> bool:
    path = urlparse(url).path
    return bool(re.search(r"/\d{4}/\d{2}/\d{2}/", path))


def is_campus_question(message: str) -> bool:
    return "campus" in message.lower()


def is_program_question(message: str) -> bool:
    q = message.lower()
    return contains_any(
        q,
        [
            "msc",
            "mba",
            "master",
            "masters",
            "master of science",
            "master of business",
            "bachelor",
            "programme grande ecole",
            "programme grande école",
            "pge",
        ],
    )


def is_pge_question(message: str) -> bool:
    q = message.lower()
    return "pge" in q or "programme grande ecole" in q or "programme grande école" in q


def is_master_specialty_question(message: str) -> bool:
    q = message.lower()
    return "specialit" in q and contains_any(q, ["master", "masters", "msc", "mba"])


def is_campus_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    if "ecole-informatique-" in path and "ecole-informatique-apres-bac" not in path:
        return True
    if "campus-epitech-" in path:
        return True
    return False


def is_program_url(url: str, question: str) -> bool:
    path = urlparse(url).path.lower()
    q = question.lower()
    if "mba" in q:
        if contains_any(path, ["mba", "master-of-business"]):
            return True
    if "msc" in q:
        if contains_any(path, ["msc", "master-of-science", "msc-pro"]):
            return True
    if "bachelor" in q:
        if "bachelor" in path:
            return True
    if "pge" in q or "programme grande ecole" in q or "programme grande école" in q:
        if contains_any(path, ["programme-grande-ecole", "diplome-expert-informatique"]):
            return True
    return False


def is_pge_url(url: str) -> bool:
    return url.rstrip("/") == PGE_BASE_URL


def select_campus_candidates(index: List[Dict[str, object]]) -> List[Dict[str, object]]:
    candidates = [entry for entry in index if is_campus_url(str(entry.get("url", "")))]
    if candidates:
        candidates.sort(key=lambda entry: str(entry.get("url", "")))
        return candidates
    fallback = [entry for entry in index if not is_post_url(str(entry.get("url", "")))]
    fallback.sort(key=lambda entry: str(entry.get("url", "")))
    return fallback


def select_program_candidates(index: List[Dict[str, object]], question: str) -> List[Dict[str, object]]:
    candidates = [
        entry for entry in index if is_program_url(str(entry.get("url", "")), question)
    ]
    if candidates:
        candidates.sort(key=lambda entry: str(entry.get("url", "")))
        return candidates
    fallback = [entry for entry in index if not is_post_url(str(entry.get("url", "")))]
    fallback.sort(key=lambda entry: str(entry.get("url", "")))
    return fallback


def select_pge_candidates(index: List[Dict[str, object]]) -> List[Dict[str, object]]:
    candidates = [entry for entry in index if is_pge_url(str(entry.get("url", "")))]
    if candidates:
        candidates.sort(key=lambda entry: str(entry.get("url", "")))
        return candidates
    fallback = [entry for entry in index if not is_post_url(str(entry.get("url", "")))]
    fallback.sort(key=lambda entry: str(entry.get("url", "")))
    return fallback


def is_msc_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return "master-of-science" in path or "/msc-" in path or "/msc" in path


def is_mba_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return "/mba" in path or "master-of-business" in path


def clean_title(title: str) -> str:
    cleaned = title.replace(" - Epitech", "")
    cleaned = cleaned.replace(" - Ecole informatique Epitech", "")
    cleaned = cleaned.replace("Epitech", "").strip(" -")
    return cleaned.strip()


def slug_to_title(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("-", " ").split())


def collect_master_specialties(index: List[Dict[str, object]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    msc_entries: Dict[str, Dict[str, str]] = {}
    mba_entries: Dict[str, Dict[str, str]] = {}
    for entry in index:
        url = str(entry.get("url", ""))
        if not url or is_post_url(url):
            continue
        title = clean_title(str(entry.get("title", "")))
        if is_msc_url(url):
            if url not in msc_entries:
                label = title or slug_to_title(urlparse(url).path.rsplit("/", 1)[-1])
                msc_entries[url] = {"label": label, "url": url, "snippet": shorten(str(entry.get("text", "")))}
        if is_mba_url(url):
            if url not in mba_entries:
                label = title or slug_to_title(urlparse(url).path.rsplit("/", 1)[-1])
                mba_entries[url] = {"label": label, "url": url, "snippet": shorten(str(entry.get("text", "")))}
    return list(msc_entries.values()), list(mba_entries.values())


def build_master_specialties_answer(msc: List[Dict[str, str]], mba: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    sources: List[Dict[str, str]] = []
    lines: List[str] = []

    def add_section(title: str, entries: List[Dict[str, str]]) -> None:
        nonlocal sources, lines
        if not entries:
            return
        lines.append(title)
        for entry in entries:
            sources.append({"url": entry["url"], "snippet": entry["snippet"]})
            idx = len(sources)
            lines.append(f"- {entry['label']} [{idx}]")
        lines.append("")

    msc_sorted = sorted(msc, key=lambda item: item["label"])[:12]
    mba_sorted = sorted(mba, key=lambda item: item["label"])[:12]
    add_section("MSc (Master of Science) chez EPITECH :", msc_sorted)
    add_section("MBA chez EPITECH :", mba_sorted)

    if not lines:
        return "", []

    if len(msc) > len(msc_sorted) or len(mba) > len(mba_sorted):
        lines.append(
            "Liste partielle basee sur les pages indexees. Consulte le site EPITECH pour la liste complete."
        )
    return "\n".join(line for line in lines if line is not None).strip(), sources


def should_include_history(message: str) -> bool:
    lowered = message.lower()
    triggers = [
        "comme tu",
        "tu as dit",
        "par rapport",
        "et pour",
        "et aussi",
        "peux-tu preciser",
        "peux-tu préciser",
        "suite",
        "continue",
        "plus de details",
        "plus de détails",
    ]
    return any(trigger in lowered for trigger in triggers)


def required_term_groups(message: str) -> List[List[str]]:
    q = message.lower()
    groups: List[List[str]] = []
    if "mba" in q:
        groups.append(["mba", "master of business", "master-of-business"])
    if "msc" in q:
        groups.append(["msc", "master of science", "master-of-science"])
    if "bachelor" in q:
        groups.append(["bachelor"])
    if "pge" in q or "programme grande ecole" in q or "programme grande école" in q:
        groups.append(["programme grande ecole", "programme grande école", "pge"])
    return groups


def sources_cover_terms(hits: List[Dict[str, object]], term_groups: List[List[str]]) -> bool:
    if not term_groups:
        return True
    combined = " ".join(str(hit.get("text", "")).lower() for hit in hits)
    for group in term_groups:
        if not any(term in combined for term in group):
            return False
    return True


def extract_snippet(text: str, start: int, end: int, window: int = 200) -> str:
    left = max(0, start - 80)
    right = min(len(text), end + window)
    snippet = text[left:right].strip()
    rel_start = start - left
    rel_end = end - left

    for sep in [". ", "! ", "? "]:
        pos = snippet.rfind(sep, 0, rel_start)
        if pos != -1:
            snippet = snippet[pos + 2 :]
            rel_end -= pos + 2
            break

    end_positions = [snippet.find(sep, rel_end) for sep in [". ", "! ", "? "]]
    end_positions = [pos for pos in end_positions if pos != -1]
    if end_positions:
        snippet = snippet[: min(end_positions) + 1]

    return " ".join(snippet.split())


def extract_pge_answer(hits: List[Dict[str, object]]) -> str | None:
    patterns = [
        r"programme en 5 ans",
        r"5 ans apr[eè]s",
        r"bac\+5",
        r"dipl[oô]me d",
        r"titre d",
        r"rncp",
        r"parcoursup",
    ]
    quotes: List[str] = []
    seen = set()
    for idx, hit in enumerate(hits, start=1):
        url = str(hit.get("url", ""))
        if not is_pge_url(url):
            continue
        text = str(hit.get("text", ""))
        lowered = text.lower()
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            snippet = extract_snippet(text, match.start(), match.end())
            if "international" in snippet.lower() or "etranger" in snippet.lower():
                continue
            if snippet and snippet not in seen:
                quotes.append(f"{snippet} [{idx}]")
                seen.add(snippet)
        if len(quotes) >= 3:
            break
    if not quotes:
        return None
    return "Voici ce que le site EPITECH indique sur le Programme Grande Ecole :\n" + "\n".join(
        f"- {quote}" for quote in quotes
    )


async def run_agent(user_message: str, session_id: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Gère une conversation par session_id et répond uniquement sur la base
    des informations EPITECH (locales + scraping HTTP).
    """
    # Historique
    history = conversations.get(session_id, [])
    history.append(("user", user_message))
    history = history[-6:]
    conversations[session_id] = history

    smalltalk = detect_smalltalk(user_message)
    if smalltalk:
        history.append(("assistant", smalltalk))
        conversations[session_id] = history
        return smalltalk, []

    score = difficulty_score(user_message)
    if score < DIFFICULTY_THRESHOLD:
        answer = (
            "Je peux aider sur EPITECH (campus, admissions, programmes, alternance). "
            "Peux-tu preciser ta question ?"
        )
        history.append(("assistant", answer))
        conversations[session_id] = history
        return answer, []

    campus_question = is_campus_question(user_message)
    pge_question = is_pge_question(user_message)
    master_specialty_question = is_master_specialty_question(user_message)
    program_question = is_program_question(user_message)

    # Rôle système : réponses sourcées et structurées
    system_context = (
        "Tu es un conseiller EPITECH, l'école d'informatique.\n"
        "Tu dois répondre en français, de manière claire, structurée et concise.\n"
        "Tu réponds UNIQUEMENT aux questions sur EPITECH : "
        "formations, campus, modalités d'admission, alternance, frais, vie étudiante, débouchés.\n"
        "Tu ne dois pas inventer d'informations. Utilise uniquement les sources fournies.\n"
        "Si tu ne trouves pas la réponse dans les sources, dis-le honnêtement.\n"
        "Quand tu mentionnes un fait, cite la source correspondante avec [1], [2], etc.\n"
        "Ne fais pas de recapitulatif de questions precedentes. Repond uniquement a la question courante.\n"
        "Structure ta réponse avec des paragraphes courts et, si utile, des puces.\n\n"
    )
    if campus_question:
        system_context += (
            "Si la question porte sur les campus, liste uniquement les villes presentes dans les sources "
            "et indique si la liste semble partielle.\n\n"
        )
    if program_question:
        system_context += (
            "Si la question porte sur des programmes (MSc, MBA, Bachelor, PGE), "
            "ne donne pas de definitions generales hors sources et n'invente rien.\n\n"
        )

    # Historique texte (sans le dernier message)
    history_text = ""
    if should_include_history(user_message):
        for role, content in history[:-1]:
            prefix = "Utilisateur" if role == "user" else "Assistant"
            history_text += f"{prefix} : {content}\n"

    index = get_index()
    if not index:
        return (
            "Aucune base de connaissances n'est disponible. Lance l'indexation du site EPITECH "
            "pour que je puisse répondre avec des sources.",
            [],
        )

    if master_specialty_question:
        msc_entries, mba_entries = collect_master_specialties(index)
        answer, sources = build_master_specialties_answer(msc_entries, mba_entries)
        if answer:
            history.append(("assistant", answer))
            conversations[session_id] = history
            return answer, sources
    if campus_question:
        candidate_pool = select_campus_candidates(index)
        if len(candidate_pool) > 200:
            candidate_pool = candidate_pool[:200]
        candidates = search_index(candidate_pool, user_message, top_k=12)
        hits = (
            rerank_results(user_message, candidates, top_k=8)
            if RERANK_ENABLED
            else candidates[:8]
        )
    elif pge_question:
        candidate_pool = select_pge_candidates(index)
        if len(candidate_pool) > 80:
            candidate_pool = candidate_pool[:80]
        candidates = search_index(candidate_pool, user_message, top_k=8)
        hits = (
            rerank_results(user_message, candidates, top_k=6)
            if RERANK_ENABLED
            else candidates[:6]
        )
    elif program_question:
        candidate_pool = select_program_candidates(index, user_message)
        if len(candidate_pool) > 200:
            candidate_pool = candidate_pool[:200]
        candidates = search_index(candidate_pool, user_message, top_k=12)
        hits = (
            rerank_results(user_message, candidates, top_k=6)
            if RERANK_ENABLED
            else candidates[:6]
        )
    else:
        candidates = search_index(index, user_message, top_k=8)
        hits = rerank_results(user_message, candidates, top_k=4) if RERANK_ENABLED else candidates[:4]

    required_groups = required_term_groups(user_message)
    if required_groups and not sources_cover_terms(hits, required_groups):
        return (
            "Je n'ai pas trouvé de sources EPITECH qui mentionnent clairement ces termes. "
            "Peux-tu préciser ou reformuler ?",
            [],
        )
    sources_block, sources = build_sources(hits)
    if not sources:
        return (
            "Je n'ai pas trouvé de sources pertinentes sur le site EPITECH pour cette question. "
            "Peux-tu reformuler ou préciser ?",
            [],
        )
    sources_context = "SOURCES EPITECH (extraits):\n" + sources_block + "\n\n"

    if pge_question:
        pge_answer = extract_pge_answer(hits)
        if pge_answer:
            history.append(("assistant", pge_answer))
            conversations[session_id] = history
            return pge_answer, sources

    # Prompt final
    prompt = (
        system_context
        + sources_context
        + history_text
        + f"Utilisateur : {user_message}\n"
        + "Réponds uniquement avec les sources ci-dessus et cite-les avec [1], [2], etc.\n"
        + "Si les sources ne suffisent pas, dis-le clairement.\n"
        + "Assistant :"
    )

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                "model": OLLAMA_CHAT_MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("response", "").strip()
    except (httpx.HTTPError, ValueError):
        answer = ""
    if not answer:
        answer = (
            "Je n'ai pas trouvé d'information fiable dans les sources EPITECH indexées. "
            "Peux-tu préciser ta question ?"
        )

    # Ajout à l'historique
    history.append(("assistant", answer))
    conversations[session_id] = history

    return answer, sources
