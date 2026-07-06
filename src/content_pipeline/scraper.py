import requests
from bs4 import BeautifulSoup


def scrape_full_text(link):
    if not link:
        return ""

    try:
        response = requests.get(
            link,
            headers={"User-Agent": "TAsAutomation/0.1"},
            timeout=10,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        return " ".join(p.get_text() for p in paragraphs)
    except requests.RequestException:
        return ""
