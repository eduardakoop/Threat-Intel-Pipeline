from datetime import datetime, timezone

from content_pipeline.runner import select_titles_for_expansion
from content_pipeline.utils import is_recent_article, sort_articles_deterministically
from ta_pipeline.pipeline.selection import select_top_articles


def test_is_recent_article_filters_to_lookback_window():
    now = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)

    assert is_recent_article(
        published="Apr 15, 2026",
        lookback_days=7,
        now=now,
    ) is True
    assert is_recent_article(
        published="Apr 01, 2026",
        lookback_days=7,
        now=now,
    ) is False
    assert is_recent_article(
        published="2 days ago",
        lookback_days=7,
        now=now,
    ) is True
    assert is_recent_article(
        published="",
        lookback_days=7,
        now=now,
    ) is False


def test_sort_articles_deterministically_prefers_newer_then_title():
    articles = [
        {"title": "Zulu", "source": "Feed", "published": "Apr 14, 2026", "url": "https://z.example"},
        {"title": "Alpha", "source": "Feed", "published": "Apr 15, 2026", "url": "https://a.example"},
        {"title": "Bravo", "source": "Feed", "published": "Apr 15, 2026", "url": "https://b.example"},
    ]

    ordered = sort_articles_deterministically(articles)

    assert [article["title"] for article in ordered] == ["Alpha", "Bravo", "Zulu"]


def test_select_titles_for_expansion_is_deterministic_per_source(monkeypatch):
    monkeypatch.setattr(
        "content_pipeline.runner.config.SEARCHES_PER_SOURCE",
        2,
    )

    articles = [
        {"source": "Feed B", "title": "B old", "published": "Apr 10, 2026"},
        {"source": "Feed A", "title": "A newer", "published": "Apr 15, 2026"},
        {"source": "Feed A", "title": "A older", "published": "Apr 14, 2026"},
        {"source": "Feed B", "title": "B newer", "published": "Apr 16, 2026"},
    ]

    assert select_titles_for_expansion(articles) == [
        "A newer",
        "A older",
        "B newer",
        "B old",
    ]


def test_select_top_articles_uses_deterministic_recent_order():
    articles = [
        {"title": "Older", "source": "Feed", "published": "Apr 10, 2026", "url": "https://older.example"},
        {"title": "Newest", "source": "Feed", "published": "Apr 16, 2026", "url": "https://newest.example"},
        {"title": "Middle", "source": "Feed", "published": "Apr 15, 2026", "url": "https://middle.example"},
    ]

    selected = select_top_articles(articles, max_articles=2)

    assert [article["title"] for article in selected] == ["Newest", "Middle"]
