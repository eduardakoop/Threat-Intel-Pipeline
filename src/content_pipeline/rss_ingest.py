import feedparser

from . import config
from .utils import clean_html, extract_cves, is_recent_article, sanitize

def fetch_rss_articles():
    """
    Fetch articles from RSS feeds defined in config.FEEDS.
    Returns a list of dicts with keys: source, title, link, published, summary, clean_content, categories, cves
    """
    articles = []

    for source, url in getattr(config, "FEEDS", []):
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[!] Failed to parse feed {url}: {e}")
            continue

        all_entries = list(getattr(feed, "entries", []))
        max_articles_per_feed = getattr(config, "MAX_ARTICLES_PER_FEED", 0)
        if max_articles_per_feed > 0:
            entries = all_entries[:max_articles_per_feed]
        else:
            entries = all_entries

        for entry in entries:
            published_value = entry.get("published", "")
            published_parsed = entry.get("published_parsed")
            if not is_recent_article(
                published=published_value,
                published_parsed=published_parsed,
                lookback_days=getattr(config, "LOOKBACK_DAYS", 7),
            ):
                continue

            # Get raw content
            raw_content = ""
            if "content" in entry and entry.content:
                raw_content = entry.content[0].value
            elif "summary" in entry:
                raw_content = entry.get("summary", "")

            clean_content = sanitize(clean_html(raw_content))

            # Tags / categories
            categories = []
            if "tags" in entry:
                for t in entry.tags:
                    if hasattr(t, "term"):
                        categories.append(t.term)

            # Extract CVEs
            cves = extract_cves(clean_content)

            # Append structured article
            articles.append({
                "source": source,
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "url": entry.get("link", ""),
                "published": published_value,
                "summary": clean_html(entry.get("summary", "")),
                "clean_content": clean_content,
                "categories": categories,
                "cves": cves
            })

    print(f"[+] {len(articles)} RSS articles fetched from {len(config.FEEDS)} feeds.")
    return articles
