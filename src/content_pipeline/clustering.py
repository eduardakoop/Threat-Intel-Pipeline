from __future__ import annotations

import re

import numpy as np

from .embeddings import cosine_similarity, generate_embedding


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+'./_-]*")
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)

# Broad security words are intentionally filtered out so clusters form around
# the concrete story, vendor, product, or vulnerability name instead of generic
# cybersecurity vocabulary.
GENERIC_STORY_TOKENS = {
    "access",
    "across",
    "active",
    "actively",
    "ad",
    "ads",
    "alert",
    "analysis",
    "arbitrary",
    "attack",
    "attacks",
    "behind",
    "build",
    "bulletin",
    "campaign",
    "campaigns",
    "code",
    "critical",
    "cyber",
    "cybersecurity",
    "data",
    "day",
    "days",
    "deliver",
    "delivers",
    "edition",
    "eliminate",
    "enables",
    "enabling",
    "environment",
    "execution",
    "expanded",
    "exploitation",
    "exploited",
    "find",
    "findings",
    "fix",
    "fixes",
    "flaw",
    "flaws",
    "fraud",
    "game",
    "great",
    "high",
    "how",
    "hour",
    "hours",
    "important",
    "increase",
    "issue",
    "issues",
    "known",
    "launches",
    "looks",
    "low",
    "malware",
    "moderate",
    "more",
    "new",
    "patch",
    "patches",
    "post",
    "recap",
    "release",
    "released",
    "releases",
    "report",
    "requires",
    "risk",
    "scam",
    "security",
    "server",
    "servers",
    "service",
    "services",
    "show",
    "shows",
    "skill",
    "skills",
    "software",
    "stories",
    "story",
    "system",
    "systems",
    "target",
    "targeted",
    "targets",
    "team",
    "teams",
    "threat",
    "threats",
    "today",
    "unpatched",
    "update",
    "updates",
    "user",
    "users",
    "using",
    "validation",
    "vulnerability",
    "vulnerabilities",
    "webinar",
    "weekly",
    "what",
    "why",
    "wild",
    "within",
    "with",
    "zero",
    "disclosure",
}

LOW_SIGNAL_TOKENS = {
    "agent",
    "agentic",
    "architecture",
    "auditor",
    "client",
    "consumption",
    "contract",
    "deterministic",
    "exploit",
    "investigator",
    "researcher",
    "researchers",
    "surface",
}

SINGULAR_MAP = {
    "attacks": "attack",
    "campaigns": "campaign",
    "devices": "device",
    "editions": "edition",
    "extensions": "extension",
    "findings": "finding",
    "fixes": "fix",
    "flaws": "flaw",
    "patches": "patch",
    "reports": "report",
    "risks": "risk",
    "servers": "server",
    "services": "service",
    "stories": "story",
    "systems": "system",
    "targets": "target",
    "teams": "team",
    "threats": "threat",
    "updates": "update",
    "users": "user",
    "vulnerabilities": "vulnerability",
}

ROUNDUP_TITLE_MARKERS = (
    " and more",
    " bulletin",
    " edition",
    " recap",
    " roundup",
    " more stories",
)


def _normalize_token(token: str) -> str:
    normalized = token.lower().replace("–", "-").replace("—", "-").strip("'._-+ ")
    if not normalized:
        return ""

    if normalized.endswith("'s"):
        normalized = normalized[:-2]

    if normalized in SINGULAR_MAP:
        return SINGULAR_MAP[normalized]

    if len(normalized) > 4 and normalized.endswith("ies"):
        return normalized[:-3] + "y"
    if len(normalized) > 5 and normalized.endswith("es") and not normalized.endswith("ses"):
        return normalized[:-2]
    if len(normalized) > 4 and normalized.endswith("s") and not normalized.endswith("ss"):
        return normalized[:-1]

    return normalized


def _extract_story_anchors(article) -> set[str]:
    title = article.get("title", "") or ""
    anchors = set()

    for raw_token in TOKEN_RE.findall(title):
        token = _normalize_token(raw_token)
        if len(token) < 3 or token.isdigit():
            continue
        if token in GENERIC_STORY_TOKENS or token in LOW_SIGNAL_TOKENS:
            continue
        if token in {"apt", "c2", "ioc", "iocs", "rat", "rce", "ttp", "ttps"}:
            continue
        anchors.add(token)

    return anchors


def _extract_story_cves(article) -> set[str]:
    text = " ".join(
        part
        for part in (
            article.get("title", ""),
            article.get("summary", ""),
            article.get("clean_content", ""),
        )
        if part
    )
    return {match.upper() for match in CVE_RE.findall(text)}


def _is_roundup_article(article) -> bool:
    title = (article.get("title", "") or "").lower()
    return any(marker in title for marker in ROUNDUP_TITLE_MARKERS)


def _embedding_for(article) -> np.ndarray:
    embedding = article.get("embedding")
    if embedding:
        return np.array(embedding, dtype=float)
    return np.array(generate_embedding(article.get("title", ""), article.get("clean_content", "")))


def _pair_is_story_match(features_a, features_b, similarity_threshold: float) -> bool:
    semantic_similarity = cosine_similarity(features_a["embedding"], features_b["embedding"])
    shared_cves = features_a["cves"] & features_b["cves"]
    shared_anchors = features_a["anchors"] & features_b["anchors"]

    if shared_cves:
        if (features_a["is_roundup"] or features_b["is_roundup"]) and not shared_anchors:
            return False
        return True

    if len(shared_anchors) >= 2 and semantic_similarity >= max(0.55, similarity_threshold - 0.05):
        return True

    if len(shared_anchors) >= 1 and semantic_similarity >= max(0.62, similarity_threshold):
        return True

    return False


def cluster_articles(articles, similarity_threshold=0.7, min_cluster_size=2):
    if not articles:
        return {}

    _ = min_cluster_size  # kept for compatibility with the previous function signature

    features = [
        {
            "embedding": _embedding_for(article),
            "anchors": _extract_story_anchors(article),
            "cves": _extract_story_cves(article),
            "is_roundup": _is_roundup_article(article),
        }
        for article in articles
    ]

    adjacency = {index: set() for index in range(len(articles))}

    for left_index in range(len(articles)):
        for right_index in range(left_index + 1, len(articles)):
            if _pair_is_story_match(
                features[left_index],
                features[right_index],
                similarity_threshold=similarity_threshold,
            ):
                adjacency[left_index].add(right_index)
                adjacency[right_index].add(left_index)

    clusters = {}
    visited = set()
    next_id = 0

    for start_index in range(len(articles)):
        if start_index in visited:
            continue

        stack = [start_index]
        component = []

        while stack:
            current = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - visited, reverse=True))

        component.sort()
        clusters[next_id] = [articles[index] for index in component]
        next_id += 1

    return clusters
