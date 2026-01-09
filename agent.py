# agent.py
import httpx
from typing import Dict, List, Tuple

from knowledge import load_local_knowledge
from scraper import scrape_epitech_page  # scraping HTTP simple

# Chargement des fichiers .txt du dossier data/epitech
LOCAL_KNOWLEDGE = load_local_knowledge()


def select_docs_for_question(question: str) -> str:
    """
    Sélection simple des documents locaux en fonction des mots-clés de la question.
    On combine plusieurs fichiers si nécessaire.
    """
    q = question.lower()
    selected: List[str] = []

    # Formations / programmes / Pré-MSc / MSc / MBA / Bachelors / PGE
    if any(w in q for w in [
        "formation",
        "programme",
        "bachelor",
        "programme grande école",
        "pge",
        "pré-msc",
        "pre-msc",
        "msc",
        "mba",
    ]):
        if "formations_paris" in LOCAL_KNOWLEDGE and "paris" in q:
            selected.append(LOCAL_KNOWLEDGE["formations_paris"])
        if "formations" in LOCAL_KNOWLEDGE:
            selected.append(LOCAL_KNOWLEDGE["formations"])

    # Admissions / inscription / candidature
    if any(w in q for w in ["admission", "inscription", "candidature", "concours", "parcoursup"]):
        if "admissions" in LOCAL_KNOWLEDGE:
            selected.append(LOCAL_KNOWLEDGE["admissions"])

    # Alternance / stage
    if any(w in q for w in ["alternance", "apprentissage", "stage", "rythme"]):
        if "alternance" in LOCAL_KNOWLEDGE:
            selected.append(LOCAL_KNOWLEDGE["alternance"])

    # Campus / villes
    if any(w in q for w in ["campus", "ville", "villes", "où se trouve", "où est situé"]):
        if "campus" in LOCAL_KNOWLEDGE:
            selected.append(LOCAL_KNOWLEDGE["campus"])

    # Partenaires / entreprises / réseau
    if any(w in q for w in ["partenaire", "partenaires", "entreprise", "entreprises", "réseau"]):
        if "partenaires" in LOCAL_KNOWLEDGE:
            selected.append(LOCAL_KNOWLEDGE["partenaires"])

    # Contexte global minimal si rien n'est matché
    if not selected:
        if "formations" in LOCAL_KNOWLEDGE:
            selected.append(LOCAL_KNOWLEDGE["formations"])
        if "campus" in LOCAL_KNOWLEDGE:
            selected.append(LOCAL_KNOWLEDGE["campus"])

    return "\n\n".join(selected)


# Petite FAQ EPITECH codée en dur (contexte supplémentaire)
EPITECH_FAQ = [
    {
        "question": "formations epitech paris",
        "answer": (
            "À EPITECH Paris, les principales formations sont : "
            "le Programme Grande École en 5 ans, "
            "les Bachelors spécialisés en 3 ans, "
            "des MSc Pro dans 7 spécialités (IA, Big Data, Cybersécurité, Cloud, IoT, "
            "Réalité virtuelle, Business Technology Management) "
            "et plusieurs MSc/MBA orientés data, innovation et management des SI."
        ),
    },
    {
        "question": "admission epitech",
        "answer": (
            "L'admission à EPITECH repose sur l'étude du dossier et un entretien de motivation. "
            "Selon le programme, la candidature se fait via Parcoursup (Programme Grande École) "
            "ou hors Parcoursup (Bachelors, Pré‑MSc, MSc, MBA)."
        ),
    },
    {
        "question": "alternance epitech",
        "answer": (
            "De nombreux cursus EPITECH intègrent des stages longs et de l'alternance, "
            "notamment en 3e année de Bachelor, en MSc Pro et en MBA Data Science & BI, "
            "avec un fort lien au réseau d'entreprises partenaires."
        ),
    },
]


def build_knowledge_context() -> str:
    lines = []
    for item in EPITECH_FAQ:
        lines.append(f"Q: {item['question']}\nR: {item['answer']}")
    return "\n\n".join(lines) + "\n\n"


# session_id -> liste de (role, content)
conversations: Dict[str, List[Tuple[str, str]]] = {}


def choose_scraping_path(question: str) -> str | None:
    """
    Choix de la page EPITECH à scraper en fonction de la question.
    Facile à faire évoluer en ajoutant des règles.
    """
    q = question.lower()

    # Formations / programmes
    if "paris" in q and any(w in q for w in ["formation", "programme", "pge", "bachelor", "msc", "mba"]):
        return "/fr/epitech-diplome-expert-informatique/"

    # Admissions
    if any(w in q for w in ["admission", "inscription", "candidature", "parcoursup", "concours"]):
        return "/fr/admissions/"

    # Alternance / MSc & MBA
    if any(w in q for w in ["alternance", "apprentissage", "rythme", "mba"]):
        return "/fr/formation-alternance/master-of-science-post-bac3/"

    # Par défaut : pas de scraping
    return None


async def run_agent(user_message: str, session_id: str) -> str:
    """
    Gère une conversation par session_id et répond uniquement sur la base
    des informations EPITECH (locales + scraping HTTP).
    """
    # Historique
    history = conversations.get(session_id, [])
    history.append(("user", user_message))
    history = history[-6:]
    conversations[session_id] = history

    # Rôle système : on insiste sur "réponds de manière structurée et pédagogique"
    system_context = (
        "Tu es un conseiller EPITECH, l'école d'informatique.\n"
        "Tu dois répondre en français, de manière claire, structurée et concise.\n"
        "Tu réponds UNIQUEMENT aux questions sur EPITECH : "
        "formations, campus, modalités d'admission, alternance, frais, vie étudiante, débouchés.\n"
        "Tu NE DOIS PAS inventer de nouvelles questions, ni faire des exercices de mathématiques, "
        "de logique ou de culture générale qui ne concernent pas EPITECH.\n"
        "Tu dois répondre directement à la question de l'utilisateur en utilisant les informations "
        "fournies ci-dessous (base de connaissances locale, FAQ et extraits du site d'EPITECH).\n"
        "Si tu ne trouves pas la réponse dans ces informations, dis-le honnêtement "
        "et propose à l'utilisateur une autre question en lien avec EPITECH.\n\n"
        "Structure ta réponse avec des paragraphes courts et, si utile, des puces pour comparer les options.\n\n"
    )

    # Historique texte (sans le dernier message)
    history_text = ""
    for role, content in history[:-1]:
        prefix = "Utilisateur" if role == "user" else "Assistant"
        history_text += f"{prefix} : {content}\n"

    # Scraping : logique centralisée
    scraped_text = ""
    path = choose_scraping_path(user_message)
    if path is not None:
        try:
            scraped_text = scrape_epitech_page(path)
        except Exception:
            scraped_text = ""

    external_knowledge = ""
    if scraped_text:
        external_knowledge = (
            "Voici un extrait d'informations officielles provenant du site d'EPITECH :\n"
            + scraped_text[:2000]
            + "\n\n"
        )

    # FAQ + docs locaux
    knowledge_context = build_knowledge_context()
    local_docs_text = select_docs_for_question(user_message)
    local_docs_context = (
        "Voici des informations provenant de la base de connaissances locale EPITECH :\n"
        + local_docs_text[:4000]
        + "\n\n"
        if local_docs_text
        else ""
    )

    # Prompt final
    prompt = (
        system_context
        + "Voici quelques informations de référence sur EPITECH :\n"
        + knowledge_context
        + local_docs_context
        + external_knowledge
        + history_text
        + f"Utilisateur : {user_message}\n"
        + "En t'appuyant uniquement sur les informations ci-dessus, réponds précisément à la question.\n"
        + "Si certaines informations manquent, dis-le clairement et reste factuel.\n"
        + "Assistant :"
    )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "llama3.2",  # adapte si tu changes de modèle dans Ollama
                "prompt": prompt,
                "stream": False,
            },
            timeout=120,
        )

    data = resp.json()
    answer = data.get("response", "").strip()

    # === GARDE-FOUS POSITIFS (ciblés) ===
    la = answer.lower()
    ql = user_message.lower()

    # 1) Questions sur le Pré-MSc
    if any(w in ql for w in ["pré-msc", "pre-msc"]):
        if "pré" not in la and "msc" not in la:
            answer = (
                "Le Pré‑MSc à EPITECH sert à consolider les fondamentaux techniques "
                "après un bac+2 ou un bac+3 avant d’entrer en MSc Pro ou en alternance. "
                "Pendant cette année, les étudiants renforcent leurs bases en administration "
                "système et réseaux, programmation orientée objet, développement web, "
                "DevOps, sécurité et méthodologie de projet, afin d’aborder sereinement "
                "les spécialisations avancées en MSc."
            )

    # 2) Questions PGE vs Bachelors
    elif any(w in ql for w in ["bachelor", "programme grande école", "pge"]):
        if "bachelor" not in la or "programme grande école" not in la:
            answer = (
                "Le Programme Grande École (PGE) d’EPITECH est un cursus en 5 ans "
                "qui mène à un niveau Bac+5 d’experte en technologies de l’information, "
                "avec une forte spécialisation et un passage à l’international.\n\n"
                "Les Bachelors sont des formations en 3 ans, plus courtes et très orientées "
                "métiers opérationnels (développeur full stack, data/IA, cybersécurité, "
                "cloud Web3, tech & business management). Ils permettent d’entrer rapidement "
                "sur le marché du travail, avec la possibilité de poursuivre ensuite en Bac+5."
            )

    # 3) Questions sur l’alternance
    elif "alternance" in ql or "apprentissage" in ql:
        if "alternance" not in la and "entreprise" not in la:
            answer = (
                "L’alternance à EPITECH permet de combiner cours et expérience en entreprise. "
                "Elle est particulièrement présente en 3e année de Bachelor, en MSc Pro et en MBA, "
                "avec des rythmes de type 3 jours en entreprise / 2 jours en cours, "
                "ou 4 jours en entreprise / 1 jour en cours pour certains MBA."
            )

    # 4) Questions sur les campus
    elif any(w in ql for w in ["campus", "ville", "villes"]):
        if not any(city in la for city in ["paris", "bordeaux", "lille", "lyon", "marseille"]):
            answer = (
                "EPITECH dispose d’un réseau d’environ 15 campus en France "
                "(Paris, Bordeaux, Lille, Lyon, Marseille, Montpellier, Nancy, Nantes, "
                "Nice, Rennes, Strasbourg, Toulouse, Mulhouse, Moulins, La Réunion) "
                "et de plusieurs implantations en Europe."
            )

    # 5) Questions sur les admissions
    elif any(w in ql for w in ["admission", "inscription", "candidature", "concours"]):
        if "entretien" not in la and "dossier" not in la:
            answer = (
                "Les admissions à EPITECH reposent sur l’étude du dossier et un entretien "
                "de motivation. Le Programme Grande École se fait via Parcoursup, tandis "
                "que les Bachelors, Pré‑MSc, MSc Pro et MBA recrutent hors Parcoursup, "
                "sur candidature en ligne puis entretien."
            )

    # ⚠️ SUPPRESSION du garde-fou global bloquant
    # À la place, si la réponse ne mentionne pas EPITECH, on renvoie quelque chose de neutre.
    la = answer.lower()
    if "epitech" not in la:
        answer = (
            "Je ne suis pas certain d’avoir bien répondu à ta question sur EPITECH. "
            "Peux-tu préciser si tu veux parler des formations, des admissions, de l’alternance "
            "ou des campus EPITECH ?"
        )

    # Ajout à l'historique
    history.append(("assistant", answer))
    conversations[session_id] = history

    return answer
