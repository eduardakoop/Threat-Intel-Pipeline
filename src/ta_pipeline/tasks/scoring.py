import json

from ta_pipeline.models.agent import AgentSpec
from ta_pipeline.models.task import TaskPayload


def build_scoring_task(
    cluster_id: str,
    cluster_articles: list,
    agent: AgentSpec,
) -> TaskPayload:
    compact_articles = []

    for article in cluster_articles:
        compact_articles.append({
            "source": article.get("source", ""),
            "title": article.get("title", ""),
            "published": article.get("published", ""),
            "summary": (article.get("summary", "") or "")[:600],
            "cves": article.get("cves", []),
            "full_text_excerpt": (article.get("full_text", "") or "")[:400],
        })

    cluster_payload = json.dumps(compact_articles, indent=2, ensure_ascii=False)

    system_prompt = f"""
You are acting as: {agent.role}

Goal:
{agent.goal}

Background:
{agent.backstory}

You must behave like a cybersecurity intelligence analyst and return strict JSON only.
""".strip()

    user_prompt = f"""
You are given a cybersecurity article cluster with ID: {cluster_id}.

Your job is to evaluate how important this cluster is for:
- threat advisory (TA)
- executive reporting

You must score the cluster using the following dimensions:
1. Technical severity
2. Urgency
3. Business impact

Then compute an OVERALL importance score based on all factors.

Cluster data:
{cluster_payload}

Return ONLY valid JSON in this exact format:

{{
  "cluster_id": "{cluster_id}",
  "overall_importance_score": <integer from 1 to 10>,
  "severity_score": <integer from 1 to 10>,
  "urgency_score": <integer from 1 to 10>,
  "business_impact_score": <integer from 1 to 10>,
  "most_recent_incident_date": "<best ISO-like date for the latest incident in the cluster, or empty string if unknown>",
  "is_ta_eligible": <true or false>,
  "ta_eligibility_reason": "<1-3 sentence explanation for whether this cluster is suitable for a TA article>",
  "rationale": "<2-5 sentence explanation justifying the overall score>",
  "key_signals": [
    "<signal 1>",
    "<signal 2>",
    "<signal 3>"
  ],
  "recommended_for_executive_summary": <true or false>,
  "recommended_for_ta_brief": <true or false>
}}

Scoring guidance:
- 9 to 10 = critical, urgent, high-impact, must report
- 7 to 8 = important, should likely be included
- 5 to 6 = relevant but not top priority
- 3 to 4 = low importance
- 1 to 2 = minimal relevance

Rules:
- Base the score only on the provided cluster data
- Use the summaries, CVEs, article count, and excerpts as supporting context
- Set `is_ta_eligible` to true when the cluster is about a single vulnerability, a very closely related vulnerability set, a single malicious campaign, or multiple closely related issues tied together by the same threat actor, software, company, platform, or service
- Reject TA eligibility when the cluster is broad, mixed across unrelated issues, stale, promotional, purely trend-based, or not actionable for clients
- Treat active exploitation, active campaigns, or very recently patched issues as the timeliness bar for TA eligibility
- Return ONLY JSON
- No markdown fences
- No extra commentary
- Be realistic and consistent
""".strip()

    return TaskPayload(
        task_name="cluster_scoring",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_type="json",
    )
