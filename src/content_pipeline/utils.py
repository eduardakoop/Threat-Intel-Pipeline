# utils.py
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import re
from time import struct_time

from bs4 import BeautifulSoup

def clean_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text()

def sanitize(text):
    return re.sub(r'\s+', ' ', text).strip()

def extract_cves(text):
    return re.findall(r'CVE-\d{4}-\d{4,7}', text)

def compute_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ensure_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_article_datetime(published="", published_parsed=None, now=None):
    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(published_parsed, datetime):
        return _ensure_utc(published_parsed)

    if isinstance(published_parsed, struct_time):
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)

    if isinstance(published_parsed, (tuple, list)) and len(published_parsed) >= 6:
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)

    text = (published or "").strip()
    if not text:
        return None

    lowered = text.lower()

    if lowered == "yesterday":
        return now - timedelta(days=1)

    relative_match = re.fullmatch(
        r"(a|an|\d+)\s+(minute|hour|day|week|month|year)s?\s+ago",
        lowered,
    )
    if relative_match:
        raw_amount, unit = relative_match.groups()
        amount = 1 if raw_amount in {"a", "an"} else int(raw_amount)
        unit_days = {
            "minute": timedelta(minutes=amount),
            "hour": timedelta(hours=amount),
            "day": timedelta(days=amount),
            "week": timedelta(weeks=amount),
            "month": timedelta(days=30 * amount),
            "year": timedelta(days=365 * amount),
        }
        return now - unit_days[unit]

    try:
        return _ensure_utc(parsedate_to_datetime(text))
    except Exception:
        pass

    iso_candidate = text.replace("Z", "+00:00")
    try:
        return _ensure_utc(datetime.fromisoformat(iso_candidate))
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d, %Y %H:%M:%S",
        "%B %d, %Y %H:%M:%S",
        "%d %b %Y",
        "%d %B %Y",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def is_recent_article(published="", published_parsed=None, lookback_days=7, now=None):
    if now is None:
        now = datetime.now(timezone.utc)

    published_at = parse_article_datetime(
        published=published,
        published_parsed=published_parsed,
        now=now,
    )
    if published_at is None:
        return False

    return published_at >= now - timedelta(days=lookback_days)


def article_sort_key(article):
    published_at = parse_article_datetime(
        published=article.get("published", ""),
        published_parsed=article.get("published_parsed"),
    )
    published_rank = -int(published_at.timestamp()) if published_at is not None else float("inf")

    return (
        published_rank,
        (article.get("source", "") or "").casefold(),
        (article.get("title", "") or "").casefold(),
        (article.get("url") or article.get("link") or "").casefold(),
    )


def sort_articles_deterministically(articles):
    return sorted(articles, key=article_sort_key)
