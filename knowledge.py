from pathlib import Path
from typing import Dict


DATA_DIR = Path(__file__).parent / "data" / "epitech"


def load_local_knowledge() -> Dict[str, str]:
    """
    Charge tous les fichiers .txt du dossier data/epitech
    et retourne un dict {clé: contenu}.
    """
    knowledge: Dict[str, str] = {}

    if not DATA_DIR.exists():
        return knowledge

    for path in DATA_DIR.glob("*.txt"):
        key = path.stem  # ex: 'formations_paris'
        text = path.read_text(encoding="utf-8")
        knowledge[key] = text.strip()

    return knowledge