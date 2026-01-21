import requests
from bs4 import BeautifulSoup
from config import CATEGORY_URL, TOTAL_PAGES, HEADERS

def get_category_page_url(page: int) -> str:
    if page == 1:
        return CATEGORY_URL
    return f"{CATEGORY_URL}/page/{page}/"

def scrape_category_pages() -> list[str]:
    article_urls = set()

    for page in range(1, TOTAL_PAGES + 1):
        url = get_category_page_url(page)
        print(f"[CATEGORY] Scraping page {page}: {url}")

        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")

        articles = soup.find_all("article")
        for article in articles:
            h2 = article.find("h2")
            if not h2:
                continue

            link = h2.find("a", href=True)
            if link:
                article_urls.add(link["href"])

    return list(article_urls)
