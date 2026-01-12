from __future__ import annotations

from collections import deque
from typing import Iterable, Dict, List, Set
from urllib.parse import urljoin, urlparse, urldefrag
import re
import time
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup


IGNORED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".zip",
    ".mp4",
    ".mp3",
}


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(["header", "footer", "nav", "aside"]):
        tag.decompose()
    for element in soup.select("[class*='menu'], [class*='nav'], [class*='breadcrumb'], [id*='menu']"):
        element.decompose()
    main = soup.find("main") or soup.find("article") or soup.body
    if not main:
        return ""
    return " ".join(main.stripped_strings)


def extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    return url.rstrip("/")


def should_skip(url: str) -> bool:
    lowered = url.lower()
    return any(lowered.endswith(ext) for ext in IGNORED_EXTENSIONS)


def is_allowed(url: str, allowed_domain: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    return parsed.netloc.endswith(allowed_domain)


def collect_links(html: str, base_url: str, allowed_domain: str) -> Iterable[str]:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = normalize_url(urljoin(base_url, href))
        if should_skip(absolute):
            continue
        if is_allowed(absolute, allowed_domain):
            yield absolute


def crawl_site(
    base_url: str,
    max_pages: int = 80,
    max_depth: int = 2,
    rate_limit_s: float = 1.0,
    use_sitemap: bool = True,
) -> List[Dict[str, str]]:
    base = normalize_url(base_url)
    allowed_domain = urlparse(base).netloc
    visited: Set[str] = set()
    queue = deque([(base, 0)])
    pages: List[Dict[str, str]] = []

    headers = {"User-Agent": "EpitechRAGBot/1.0 (+https://www.epitech.eu)"}
    with httpx.Client(follow_redirects=True, timeout=20, headers=headers) as client:
        if use_sitemap:
            for url in fetch_sitemap_urls(base, allowed_domain, client, max_urls=max_pages * 3):
                if url not in visited and len(queue) < max_pages * 3:
                    queue.append((url, 0))

        while queue and len(pages) < max_pages:
            url, depth = queue.popleft()
            if url in visited or depth > max_depth:
                continue
            visited.add(url)

            try:
                resp = client.get(url)
            except httpx.HTTPError:
                continue

            content_type = resp.headers.get("content-type", "")
            if resp.status_code != 200 or "text/html" not in content_type:
                continue

            html = resp.text
            text = extract_text(html)
            if text:
                pages.append({"url": url, "title": extract_title(html), "text": text})

            if depth < max_depth:
                for link in collect_links(html, url, allowed_domain):
                    if link not in visited:
                        queue.append((link, depth + 1))

            time.sleep(rate_limit_s)

    return pages


def fetch_sitemap_urls(
    base_url: str,
    allowed_domain: str,
    client: httpx.Client,
    max_urls: int = 200,
) -> List[str]:
    sitemap_urls = []
    candidates = [urljoin(base_url + "/", "sitemap_index.xml"), urljoin(base_url + "/", "sitemap.xml")]
    for candidate in candidates:
        try:
            resp = client.get(candidate)
        except httpx.HTTPError:
            continue
        if resp.status_code != 200 or "xml" not in resp.headers.get("content-type", ""):
            continue
        sitemap_urls.extend(parse_sitemap(resp.text))
        if sitemap_urls:
            break

    urls: List[str] = []
    for sitemap_url in sorted(sitemap_urls, key=sitemap_priority):
        if len(urls) >= max_urls:
            break
        try:
            resp = client.get(sitemap_url)
        except httpx.HTTPError:
            continue
        if resp.status_code != 200:
            continue
        urls.extend(parse_sitemap(resp.text))
        if len(urls) >= max_urls:
            break

    if not urls:
        return []

    normalized: List[str] = []
    for url in urls:
        url = normalize_url(url)
        if not url or url in normalized:
            continue
        if should_skip(url):
            continue
        if not is_allowed(url, allowed_domain):
            continue
        normalized.append(url)
        if len(normalized) >= max_urls:
            break
    normalized.sort(key=url_priority)
    return normalized


def parse_sitemap(xml_text: str) -> List[str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    if root.tag.endswith("sitemapindex"):
        return [loc.text.strip() for loc in root.findall("ns:sitemap/ns:loc", ns) if loc.text]
    if root.tag.endswith("urlset"):
        return [loc.text.strip() for loc in root.findall("ns:url/ns:loc", ns) if loc.text]
    return []


def sitemap_priority(url: str) -> int:
    if "page-sitemap" in url:
        return 0
    if "metiers-sitemap" in url:
        return 1
    if "post-sitemap" in url:
        return 2
    return 3


def url_priority(url: str) -> int:
    path = urlparse(url).path.lower()
    if "ecole-informatique-" in path and "ecole-informatique-apres-bac" not in path:
        return 0
    if any(token in path for token in ["admission", "programme", "formation", "bachelor", "msc", "mba"]):
        return 1
    if re.search(r"/\\d{4}/\\d{2}/\\d{2}/", path):
        return 5
    return 3
