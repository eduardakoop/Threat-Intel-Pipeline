from content_pipeline.clustering import cluster_articles


def _article(title, embedding, summary=""):
    return {
        "title": title,
        "summary": summary,
        "embedding": embedding,
    }


def test_cluster_articles_rejects_generic_semantic_similarity_without_shared_story_anchors():
    articles = [
        _article("Client Auditor", [1.0, 0.0]),
        _article("Contract Auditor", [0.99, 0.01]),
        _article(
            "April Patch Tuesday Fixes Critical Flaws Across SAP, Adobe, Microsoft, Fortinet, and More",
            [0.0, 1.0],
        ),
        _article("Patch Tuesday, April 2026 Edition", [0.2, 0.98]),
        _article("Microsoft Patch Tuesday Fixes SharePoint Zero-Day", [0.3, 0.95]),
    ]

    clusters = cluster_articles(articles, similarity_threshold=0.8, min_cluster_size=2)
    eligible_clusters = [
        {article["title"] for article in cluster}
        for cluster in clusters.values()
        if len(cluster) >= 2
    ]

    assert eligible_clusters == [
        {
            "April Patch Tuesday Fixes Critical Flaws Across SAP, Adobe, Microsoft, Fortinet, and More",
            "Patch Tuesday, April 2026 Edition",
            "Microsoft Patch Tuesday Fixes SharePoint Zero-Day",
        }
    ]


def test_cluster_articles_does_not_group_broad_topic_matches_when_semantics_are_too_weak():
    articles = [
        _article(
            "108 Malicious Chrome Extensions Steal Google and Telegram Data, Affecting 20,000 Users",
            [1.0, 0.0],
        ),
        _article(
            "Browser Extensions Are the New AI Consumption Channel That No One Is Talking About",
            [0.4, 0.9165],
        ),
    ]

    clusters = cluster_articles(articles, similarity_threshold=0.55, min_cluster_size=2)

    assert [len(cluster) for cluster in clusters.values()] == [1, 1]


def test_cluster_articles_ignores_shared_exploitation_language_when_the_story_is_different():
    articles = [
        _article(
            "ShowDoc RCE Flaw CVE-2025-0520 Actively Exploited on Unpatched Servers",
            [1.0, 0.0],
        ),
        _article(
            "Marimo RCE Flaw CVE-2026-39987 Exploited Within 10 Hours of Disclosure",
            [0.698, 0.716],
        ),
    ]

    clusters = cluster_articles(articles, similarity_threshold=0.65, min_cluster_size=2)

    assert [len(cluster) for cluster in clusters.values()] == [1, 1]


def test_cluster_articles_do_not_link_roundups_to_specific_stories_on_summary_cves_alone():
    articles = [
        _article(
            "Patch Tuesday, April 2026 Edition",
            [1.0, 0.0],
            summary="Emergency updates also addressed CVE-2026-34621 in Adobe Reader.",
        ),
        _article(
            "Adobe Patches Actively Exploited Acrobat Reader Flaw CVE-2026-34621",
            [0.0, 1.0],
        ),
    ]

    clusters = cluster_articles(articles, similarity_threshold=0.7, min_cluster_size=2)

    assert [len(cluster) for cluster in clusters.values()] == [1, 1]


def test_cluster_articles_links_shared_cve_even_when_wording_differs():
    articles = [
        _article(
            "Vendor advisory for CVE-2026-12345 parser bug",
            [1.0, 0.0],
        ),
        _article(
            "CISA warns of active exploitation",
            [0.0, 1.0],
            summary="Analysts confirmed CVE-2026-12345 exploitation in the wild.",
        ),
    ]

    clusters = cluster_articles(articles, similarity_threshold=0.8, min_cluster_size=2)
    eligible_clusters = [cluster for cluster in clusters.values() if len(cluster) >= 2]

    assert len(eligible_clusters) == 1
    assert {article["title"] for article in eligible_clusters[0]} == {
        "Vendor advisory for CVE-2026-12345 parser bug",
        "CISA warns of active exploitation",
    }
