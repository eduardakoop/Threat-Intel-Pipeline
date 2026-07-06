import os

import requests

from . import config
from .utils import clean_html, extract_cves, is_recent_article

def search_web_articles(query, max_results=None):
    """
    Search the web using Serper Dev API and return structured article results.
    """
    API_KEY = config.SERPER_API_KEY or os.environ.get("SERPER_API_KEY")
    if not API_KEY:
        raise ValueError("SERPER_API_KEY not set!")

    if max_results is None:
        max_results = config.MAX_WEB_RESULTS

    lookback_days = getattr(config, "LOOKBACK_DAYS", 7)
    time_period = "w" if lookback_days <= 7 else "m"

    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": API_KEY}
    data = {"q": query, "num": max_results, "timePeriod": time_period}

    resp = requests.post(url, json=data, headers=headers)
    resp.raise_for_status()

    results = resp.json().get("organic", [])

    EXCLUDED_DOMAINS = [
        "twitter.com", "x.com", "linkedin.com",
        "facebook.com", "reddit.com",
        "instagram.com", "youtube.com", "tiktok.com"
    ]

    articles = []

    for r in results:
        link = r.get("link", "")
        if any(domain in link for domain in EXCLUDED_DOMAINS):
            continue

        published_value = r.get("date", "")
        if not is_recent_article(
            published=published_value,
            lookback_days=lookback_days,
        ):
            continue

        snippet = clean_html(r.get("snippet", ""))

        articles.append({
            "source": r.get("source", "Web News"),
            "title": r.get("title", ""),
            "link": link,
            "url": link,
            "published": published_value,
            "summary": snippet,
            "clean_content": snippet,
            "categories": [],
            "cves": extract_cves(snippet)
        })

    return articles
