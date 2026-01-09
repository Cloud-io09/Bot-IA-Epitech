# scraper.py
import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.epitech.eu"

def scrape_epitech_page(path: str) -> str:
    """
    Récupère le texte principal d'une page EPITECH (path commençant par /fr/...)
    """
    url = BASE_URL + path
    resp = httpx.get(url, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main") or soup.body
    text = " ".join(main.stripped_strings) if main else ""
    return text
