from scraper_category import scrape_category_pages
from scraper_article import scrape_article
from models import AgnoDocument

def main():
    documents = []

    article_urls = scrape_category_pages()
    print(f"\n[INFO] {len(article_urls)} articles trouvés\n")

    for url in article_urls:
        data = scrape_article(url)

        if not data["content_text"]:
            continue

        doc = AgnoDocument(
            content=data["content_text"],
            metadata={
                "source": "btp-cours",
                "category": "cours",
                "title": data["title"],
                "url": data["url"],
                "pdf_urls": data["pdf_urls"]
            }
        )

        documents.append(doc)

    print(f"\n[SUCCESS] {len(documents)} documents prêts pour Agno")
    return documents

if __name__ == "__main__":
    docs = main()
