import json
from collections import defaultdict
from datetime import datetime, timezone
import os
from pathlib import Path

from . import config
from .clustering import cluster_articles
from .embeddings import generate_embedding
from .rss_ingest import fetch_rss_articles
from .scraper import scrape_full_text
from .utils import compute_hash, extract_cves, sort_articles_deterministically
from .web_search import search_web_articles


def deduplicate_articles(articles):
    seen_hashes, seen_urls = set(), set()
    unique_articles = []

    for article in articles:
        content_hash = compute_hash(
            article.get("title", "") + article.get("clean_content", "")
        )
        url = article.get("link", "")
        if content_hash in seen_hashes or url in seen_urls:
            continue
        seen_hashes.add(content_hash)
        seen_urls.add(url)
        unique_articles.append(article)
    return unique_articles


def embed_articles(articles):
    for article in articles:
        if "embedding" not in article or not article["embedding"]:
            article["embedding"] = generate_embedding(
                article.get("title", ""),
                article.get("clean_content", ""),
            )
    return articles


def _count_eligible_clusters(clusters, min_articles):
    return sum(1 for articles in clusters.values() if len(articles) >= min_articles)


def cluster_articles_with_fallback(articles, similarity_threshold, min_articles):
    start = max(0.05, min(0.99, float(similarity_threshold)))

    thresholds = []
    current = start
    while current >= 0.5:
        rounded = round(current, 2)
        if rounded not in thresholds:
            thresholds.append(rounded)
        current -= 0.05

    if round(start, 2) not in thresholds:
        thresholds.insert(0, round(start, 2))

    best_clusters = {}
    best_threshold = round(start, 2)
    best_eligible_count = -1

    for threshold in thresholds:
        clusters = cluster_articles(articles, similarity_threshold=threshold)
        eligible_count = _count_eligible_clusters(clusters, min_articles)
        print(
            f"[*] Clustering with similarity_threshold={threshold:.2f} "
            f"produced {eligible_count} eligible clusters"
        )
        if eligible_count > best_eligible_count:
            best_clusters = clusters
            best_threshold = threshold
            best_eligible_count = eligible_count

    return best_clusters, best_threshold


def select_titles_for_expansion(articles):
    titles_per_source = defaultdict(list)
    for article in sort_articles_deterministically(articles):
        source = article.get("source", "unknown")
        title = (article.get("title", "") or "").strip()
        if not title:
            continue
        titles_per_source[source].append(title)

    all_titles = []
    for source in sorted(titles_per_source):
        seen_titles = set()
        for title in titles_per_source[source]:
            if title in seen_titles:
                continue
            seen_titles.add(title)
            all_titles.append(title)
            if len(seen_titles) >= config.SEARCHES_PER_SOURCE:
                break

    return all_titles


def save_clusters(clusters, run_folder, min_articles=None):
    if min_articles is None:
        min_articles = config.MIN_CLUSTER_ARTICLES

    sources_folder = Path(run_folder) / "sources"
    sources_folder.mkdir(parents=True, exist_ok=True)

    filtered_clusters = [arts for arts in clusters.values() if len(arts) >= min_articles]

    for new_cid, articles in enumerate(filtered_clusters):
        cluster_folder = sources_folder / f"cluster_{new_cid}"
        cluster_folder.mkdir(parents=True, exist_ok=True)

        cluster_output = []
        for article in articles:
            article_url = article.get("link", "") or article.get("url", "")
            full_text = scrape_full_text(article_url)
            text_to_scan = (full_text or "") + " " + (article.get("summary") or "")
            cluster_output.append(
                {
                    "source": article.get("source", ""),
                    "title": article.get("title", ""),
                    "link": article_url,
                    "url": article_url,
                    "published": article.get("published", ""),
                    "summary": article.get("summary", ""),
                    "full_text": full_text,
                    "cves": extract_cves(text_to_scan),
                }
            )

        cluster_file = cluster_folder / "articles.json"
        with open(cluster_file, "w", encoding="utf-8") as f:
            json.dump(cluster_output, f, indent=2, ensure_ascii=False)

        print(f"[+] Cluster {new_cid} saved in {cluster_file} ({len(articles)} articles)")

    print(f"[+] {len(filtered_clusters)} clusters saved (min_articles={min_articles})")


def run_content_discovery(storage_root=None):
    print("=== Autonomous Content Finder Pipeline ===")

    if storage_root is None:
        storage_root = getattr(config, "STORAGE_ROOT", None)
        if storage_root is None:
            raise ValueError("STORAGE_ROOT not set in config or function parameter")

    storage_root = str(Path(storage_root).expanduser())
    Path(storage_root).mkdir(parents=True, exist_ok=True)

    should_expand_with_serper = getattr(config, "EXPAND_FEED_TOPICS_WITH_SERPER", False)
    if should_expand_with_serper:
        api_key = config.SERPER_API_KEY or os.environ.get("SERPER_API_KEY")
        if not api_key:
            raise ValueError("SERPER_API_KEY is required when Serper expansion is enabled.")

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_root = Path(storage_root) / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    print(f"[+] RUN_ROOT: {run_root}")

    top_level = ["sources", "executive-summaries", "TA-briefs"]
    for folder in top_level:
        (run_root / folder).mkdir(exist_ok=True)
    print(f"[+] Folders created: {top_level}")

    print("[*] Fetching RSS articles...")
    articles = fetch_rss_articles()
    articles = deduplicate_articles(articles)
    articles = sort_articles_deterministically(articles)
    print(f"[+] {len(articles)} RSS articles fetched.")

    if should_expand_with_serper:
        print("[*] Expanding topics with Serper Dev...")
        all_titles = select_titles_for_expansion(articles)

        web_articles = []
        for title in all_titles:
            if not title.strip():
                continue
            if config.VERBOSE:
                print(f"  -> Searching for: {title}")
            try:
                web_articles.extend(search_web_articles(title))
            except Exception as e:
                print(f"     [!] Error fetching '{title}': {e}")

        articles.extend(web_articles)
        articles = deduplicate_articles(articles)
        articles = sort_articles_deterministically(articles)
        print(f"[+] {len(articles)} total articles after web expansion.")
    else:
        print("[*] Skipping Serper expansion; clustering feed articles only.")

    print("[*] Generating embeddings...")
    articles = embed_articles(articles)

    print("[*] Clustering articles...")
    clusters, used_threshold = cluster_articles_with_fallback(
        articles,
        similarity_threshold=config.SIMILARITY_THRESHOLD,
        min_articles=config.MIN_CLUSTER_ARTICLES,
    )
    print(f"[+] {len(clusters)} clusters created (threshold_used={used_threshold:.2f}).")

    articles_file = run_root / "sources" / "articles.json"
    with open(articles_file, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"[+] All articles saved to {articles_file}")

    print("[*] Saving clusters...")
    save_clusters(clusters, run_folder=run_root)

    print(f"[+] Pipeline complete. Run saved in {run_root}")
    return run_root


if __name__ == "__main__":
    run_content_discovery()
