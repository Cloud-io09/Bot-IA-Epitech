# scraper_mcp_server.py
from fastmcp import FastMCP, Context
import httpx
from bs4 import BeautifulSoup

# Nom logique du serveur MCP
mcp = FastMCP("EpitechScraperServer")


@mcp.tool
async def scrape_url(url: str, ctx: Context):
    """
    Scrape une page web publique et renvoie le texte principal.
    - url : URL complète (https://...) à scraper.
    """
    await ctx.info(f"Scraping {url}")

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main") or soup.body
    text = " ".join(main.stripped_strings) if main else ""

    # On limite la taille pour éviter les contextes trop gros
    return {
        "url": url,
        "content": text[:8000],
    }


if __name__ == "__main__":
    # Lance le serveur MCP (processus dédié)
    mcp.run()
