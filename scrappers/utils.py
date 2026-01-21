from bs4 import BeautifulSoup

def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    # supprimer scripts / styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    return " ".join(text.split())
