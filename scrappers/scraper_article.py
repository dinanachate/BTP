import requests
from bs4 import BeautifulSoup
from config import HEADERS
from utils import clean_text

def scrape_article(article_url: str) -> dict:
    print(f"[ARTICLE] {article_url}")

    r = requests.get(article_url, headers=HEADERS, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    title = soup.find("h1")
    title_text = title.get_text(strip=True) if title else ""

    content_div = soup.find("div", class_="entry-content")
    content_html = str(content_div) if content_div else ""
    content_text = clean_text(content_html)

    pdf_urls = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" in href.lower():
            pdf_urls.append(href)

    return {
        "title": title_text,
        "url": article_url,
        "content_html": content_html,
        "content_text": content_text,
        "pdf_urls": list(set(pdf_urls))
    }
