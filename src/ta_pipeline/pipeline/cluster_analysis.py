from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import re

from content_pipeline.utils import extract_cves, parse_article_datetime

TA_MIN_IMPORTANCE_SCORE = 6
TA_RECENCY_WINDOW_DAYS = 21
TA_MAX_FOCUSED_CVES = 4

_ACTIVE_EXPLOIT_OR_PATCH_PATTERNS = (
    r"\bactively exploited\b",
    r"\bactive exploitation\b",
    r"\bexploited in the wild\b",
    r"\bexploitation in the wild\b",
    r"\bin the wild\b",
    r"\bzero-day\b",
    r"\b0-day\b",
    r"\bunpatched\b",
    r"\bknown exploited vulnerabilities\b",
    r"\bkev\b",
    r"\bemergency patch(?:es)?\b",
    r"\bpatched\b",
    r"\bpatch(?:ing|es)?\b",
    r"\bfixed\b",
    r"\bworkaround\b",
    r"\bmitigat(?:e|ion|ions)\b",
    r"\bremediat(?:e|ion|ions)\b",
)

_ACTIVE_CAMPAIGN_PATTERNS = (
    r"\bactive campaign\b",
    r"\bongoing campaign\b",
    r"\bcurrently targeting\b",
    r"\bcurrently exploited\b",
    r"\bcurrently being exploited\b",
    r"\btargeting\b",
    r"\bdeploy(?:ed|ing)\b",
    r"\bdelivering\b",
    r"\bstealing\b",
    r"\bobserved\b",
)

_CAMPAIGN_PATTERNS = (
    r"\bcampaign\b",
    r"\bmalware\b",
    r"\bransomware\b",
    r"\bphishing\b",
    r"\bbotnet\b",
    r"\bbackdoor\b",
    r"\bspyware\b",
    r"\bstealer\b",
    r"\btrojan\b",
    r"\brat\b",
    r"\bapt\d*\b",
    r"\bthreat actor\b",
    r"\binfostealer\b",
    r"\bloader\b",
)

_VULNERABILITY_PATTERNS = (
    r"\bvulnerability\b",
    r"\bzero-day\b",
    r"\b0-day\b",
    r"\bauthentication bypass\b",
    r"\bremote code execution\b",
    r"\bprivilege escalation\b",
    r"\bsql injection\b",
    r"\bcommand injection\b",
    r"\barbitrary code execution\b",
    r"\bfile upload\b",
)

_ROUNDUP_OR_DIGEST_PATTERNS = (
    r"\bbulletin\b",
    r"\broundup\b",
    r"\bthis week\b",
    r"\bmore stories\b",
    r"\bnews digest\b",
)

_MULTI_ISSUE_SCOPE_PATTERNS = (
    r"\bpatch tuesday\b",
    r"\bmultiple vendors\b",
    r"\b\d+\s+vulnerabilities\b",
    r"\b\d+\s+more\b",
)

_NON_ACTIONABLE_PATTERNS = (
    r"\bwebinar\b",
    r"\bwhitepaper\b",
    r"\bsurvey\b",
    r"\btraining\b",
    r"\bplaybook\b",
    r"\bgame\b",
    r"\beducational\b",
)

_RESOLVED_OR_HISTORICAL_PATTERNS = (
    r"\btakedown\b",
    r"\btaken down\b",
    r"\bdismantled\b",
    r"\bseized\b",
    r"\barrested\b",
    r"\bshutdown\b",
    r"\balready down\b",
    r"\boperation disrupted\b",
)

_RELATION_TOKEN_PATTERN = (
    r"(?:"
    r"[A-Z][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*"
    r"|[A-Z]{2,}\d*"
    r"|[a-z]+\d+[a-z0-9-]*"
    r"|[A-Za-z]+[A-Z][A-Za-z0-9-]*"
    r")"
)
_RELATION_PHRASE_RE = re.compile(
    rf"\b{_RELATION_TOKEN_PATTERN}(?:\s+{_RELATION_TOKEN_PATTERN}){{0,3}}\b"
)
_RELATION_STOPWORDS = {
    "active",
    "actively",
    "advisory",
    "alert",
    "alerts",
    "april",
    "august",
    "being",
    "brief",
    "campaign",
    "campaigns",
    "critical",
    "customers",
    "cisa",
    "cve",
    "cves",
    "december",
    "detected",
    "emergency",
    "executive",
    "exploited",
    "exploitation",
    "february",
    "fix",
    "fixed",
    "flaw",
    "flaws",
    "friday",
    "high",
    "incident",
    "incidents",
    "issue",
    "issues",
    "january",
    "july",
    "june",
    "kev",
    "known",
    "low",
    "march",
    "may",
    "medium",
    "monday",
    "more",
    "new",
    "news",
    "november",
    "observed",
    "october",
    "patch",
    "patched",
    "patches",
    "patching",
    "priority",
    "recent",
    "recently",
    "released",
    "researchers",
    "rce",
    "saturday",
    "score",
    "security",
    "september",
    "stories",
    "summary",
    "sunday",
    "ta",
    "targeting",
    "threat",
    "threats",
    "thursday",
    "top",
    "tuesday",
    "update",
    "updates",
    "vulnerability",
    "vulnerabilities",
    "warning",
    "warnings",
    "wednesday",
    "week",
    "wild",
    "zero-day",
}


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _cluster_text(score: dict, articles: list[dict]) -> str:
    parts = [
        score.get("rationale", ""),
        *score.get("key_signals", []),
    ]

    for article in articles:
        parts.extend(
            [
                article.get("title", ""),
                article.get("summary", ""),
                article.get("full_text", "")[:2000],
            ]
        )

    return "\n".join(str(part) for part in parts if part)


def _collect_cluster_cves(articles: list[dict], cluster_text: str) -> list[str]:
    cves = set()

    for article in articles:
        for cve in article.get("cves", []) or []:
            if cve:
                cves.add(str(cve).upper())

        article_text = " ".join(
            [
                article.get("title", ""),
                article.get("summary", ""),
                article.get("full_text", "")[:500],
            ]
        )
        for cve in extract_cves(article_text):
            cves.add(cve.upper())

    for cve in extract_cves(cluster_text):
        cves.add(cve.upper())

    return sorted(cves)


def _normalize_relation_candidate(candidate: str) -> str | None:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9-/]*", candidate)
    if not words:
        return None

    while words and words[0].casefold() in _RELATION_STOPWORDS:
        words = words[1:]
    while words and words[-1].casefold() in _RELATION_STOPWORDS:
        words = words[:-1]

    if not words:
        return None

    lowered_words = [word.casefold() for word in words]
    if any(word.startswith("cve-") for word in lowered_words):
        return None

    if len(words) == 1 and (lowered_words[0] in _RELATION_STOPWORDS or len(words[0]) < 3):
        return None

    if all(word in _RELATION_STOPWORDS for word in lowered_words):
        return None

    return " ".join(words).casefold()


def _extract_relation_candidates(text: str) -> list[str]:
    candidates: list[str] = []

    for match in _RELATION_PHRASE_RE.finditer(text):
        normalized = _normalize_relation_candidate(match.group(0))
        if normalized is None:
            continue

        candidates.append(normalized)

        parts = normalized.split()
        if len(parts) > 1 and parts[0] not in _RELATION_STOPWORDS:
            candidates.append(parts[0])

    return candidates


def _collect_related_context_terms(articles: list[dict], cluster_text: str) -> set[str]:
    article_term_counts: Counter[str] = Counter()

    for article in articles:
        article_text = " ".join(
            [
                article.get("title", ""),
                article.get("summary", ""),
                (article.get("full_text", "") or "")[:1200],
            ]
        )
        article_term_counts.update(set(_extract_relation_candidates(article_text)))

    cluster_term_counts = Counter(_extract_relation_candidates(cluster_text))

    shared_article_terms = {
        term
        for term, count in article_term_counts.items()
        if count >= 2
    }
    dominant_cluster_terms = {
        term
        for term, count in cluster_term_counts.items()
        if count >= 2
    }

    return shared_article_terms | dominant_cluster_terms


def get_most_recent_incident_at(
    score: dict,
    articles: list[dict],
) -> tuple[datetime | None, str]:
    for key in ("most_recent_incident", "most_recent_incident_at", "most_recent_incident_date"):
        value = score.get(key, "")
        if not value:
            continue

        parsed = parse_article_datetime(published=str(value))
        if parsed is not None:
            return parsed, key

    article_dates = []
    for article in articles:
        parsed = parse_article_datetime(
            published=article.get("published", ""),
            published_parsed=article.get("published_parsed"),
        )
        if parsed is not None:
            article_dates.append(parsed)

    if not article_dates:
        return None, "unavailable"

    return max(article_dates), "article.published"


def evaluate_ta_article_eligibility(
    score: dict,
    articles: list[dict],
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    if now is None:
        now = datetime.now(timezone.utc)

    importance_score = int(score.get("overall_importance_score", 0) or 0)
    cluster_text = _cluster_text(score, articles)
    cluster_cves = _collect_cluster_cves(articles, cluster_text)
    related_context_terms = _collect_related_context_terms(articles, cluster_text)
    most_recent_incident_at, _ = get_most_recent_incident_at(score, articles)

    has_recent_incident = (
        most_recent_incident_at is not None
        and most_recent_incident_at >= now - timedelta(days=TA_RECENCY_WINDOW_DAYS)
    )
    has_campaign_signal = _matches_any(cluster_text, _CAMPAIGN_PATTERNS)
    has_active_campaign_signal = has_campaign_signal and _matches_any(
        cluster_text,
        _ACTIVE_CAMPAIGN_PATTERNS,
    )
    has_exploit_or_patch_signal = _matches_any(
        cluster_text,
        _ACTIVE_EXPLOIT_OR_PATCH_PATTERNS,
    ) or has_active_campaign_signal
    has_roundup_or_digest_format = _matches_any(cluster_text, _ROUNDUP_OR_DIGEST_PATTERNS)
    has_multi_issue_scope = _matches_any(cluster_text, _MULTI_ISSUE_SCOPE_PATTERNS) or (
        len(cluster_cves) > TA_MAX_FOCUSED_CVES
    )
    is_non_actionable_context = _matches_any(cluster_text, _NON_ACTIONABLE_PATTERNS)
    is_resolved_story = _matches_any(cluster_text, _RESOLVED_OR_HISTORICAL_PATTERNS)
    has_focused_vulnerability = 0 < len(cluster_cves) <= TA_MAX_FOCUSED_CVES
    has_single_campaign = len(cluster_cves) == 0 and has_campaign_signal
    has_named_vulnerability_focus = len(cluster_cves) == 0 and _matches_any(
        cluster_text,
        _VULNERABILITY_PATTERNS,
    )
    has_related_multi_issue_focus = (
        bool(related_context_terms)
        and (len(cluster_cves) > 1 or has_campaign_signal or has_multi_issue_scope)
    )
    is_broad_or_mixed = has_roundup_or_digest_format or (
        has_multi_issue_scope and not has_related_multi_issue_focus
    )
    has_clear_focus = (
        has_focused_vulnerability
        or has_single_campaign
        or has_named_vulnerability_focus
        or has_related_multi_issue_focus
    )

    heuristic_eligible = all(
        (
            importance_score >= TA_MIN_IMPORTANCE_SCORE,
            has_recent_incident,
            has_exploit_or_patch_signal,
            not is_broad_or_mixed,
            not is_non_actionable_context,
            not is_resolved_story,
            has_clear_focus,
        )
    )

    model_eligible = score.get("is_ta_eligible")
    if isinstance(model_eligible, bool):
        is_ta_eligible = model_eligible and heuristic_eligible
    else:
        is_ta_eligible = heuristic_eligible

    if importance_score < TA_MIN_IMPORTANCE_SCORE:
        return False, "The cluster is not important enough to justify a client-facing TA."
    if not has_recent_incident:
        return False, "The cluster is too old to qualify as currently exploited or very recently patched."
    if has_roundup_or_digest_format:
        return False, "The cluster is a general bulletin or roundup instead of a focused TA-worthy issue set."
    if is_broad_or_mixed:
        return False, "The cluster is too broad or mixes unrelated issues instead of one clear vulnerability or campaign."
    if is_non_actionable_context or is_resolved_story:
        return False, "The cluster is informational, promotional, or already-resolved context rather than an actionable current threat."
    if not has_exploit_or_patch_signal:
        return False, "The cluster does not show active exploitation, an ongoing campaign, or a very recent patch window."
    if not has_clear_focus:
        return False, "The cluster is not centered on a single vulnerability set or a single malicious campaign."
    if isinstance(model_eligible, bool) and not model_eligible:
        return False, "The scorer marked the cluster as unsuitable for TA writing."

    return True, "The cluster is focused, recent, and actionable enough for a client-facing TA."


def enrich_cluster_score(
    score: dict,
    articles: list[dict],
    *,
    now: datetime | None = None,
) -> dict:
    enriched = dict(score)
    most_recent_incident_at, incident_source = get_most_recent_incident_at(enriched, articles)
    is_ta_eligible, ta_eligibility_reason = evaluate_ta_article_eligibility(
        enriched,
        articles,
        now=now,
    )

    enriched["most_recent_incident"] = (
        most_recent_incident_at.isoformat() if most_recent_incident_at is not None else ""
    )
    enriched["most_recent_incident_source"] = incident_source
    enriched["is_ta_eligible"] = is_ta_eligible
    enriched["ta_eligibility_reason"] = ta_eligibility_reason

    return enriched
