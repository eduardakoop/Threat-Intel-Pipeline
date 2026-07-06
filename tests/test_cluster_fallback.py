from content_pipeline.runner import cluster_articles_with_fallback


def test_cluster_articles_with_fallback_relaxes_threshold_until_cluster_is_eligible(monkeypatch):
    call_order = []

    def fake_cluster_articles(articles, similarity_threshold):
        rounded = round(similarity_threshold, 2)
        call_order.append(rounded)
        if rounded >= 0.7:
            return {0: [{"id": 1}], 1: [{"id": 2}]}
        return {0: [{"id": 1}, {"id": 2}, {"id": 3}]}

    monkeypatch.setattr(
        "content_pipeline.runner.cluster_articles",
        fake_cluster_articles,
    )

    clusters, used_threshold = cluster_articles_with_fallback(
        articles=[{"id": 1}, {"id": 2}, {"id": 3}],
        similarity_threshold=0.8,
        min_articles=3,
    )

    assert call_order == [0.8, 0.75, 0.7, 0.65, 0.6, 0.55]
    assert used_threshold == 0.65
    assert len(clusters[0]) == 3


def test_cluster_articles_with_fallback_prefers_most_eligible_clusters(monkeypatch):
    def fake_cluster_articles(articles, similarity_threshold):
        rounded = round(similarity_threshold, 2)
        if rounded == 0.8:
            return {0: [{"id": 1}], 1: [{"id": 2}]}
        if rounded == 0.75:
            return {0: [{"id": 1}, {"id": 2}]}
        if rounded == 0.7:
            return {
                0: [{"id": 1}, {"id": 2}],
                1: [{"id": 3}, {"id": 4}],
            }
        return {0: [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]}

    monkeypatch.setattr(
        "content_pipeline.runner.cluster_articles",
        fake_cluster_articles,
    )

    clusters, used_threshold = cluster_articles_with_fallback(
        articles=[{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
        similarity_threshold=0.8,
        min_articles=2,
    )

    assert used_threshold == 0.7
    assert len(clusters) == 2
