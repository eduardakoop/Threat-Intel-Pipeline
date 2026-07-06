import json

from ta_pipeline.models.agent import AgentSpec
from ta_pipeline.models.task import TaskPayload


def build_executive_summary_task(
    cluster_id: str,
    scored_cluster: dict,
    cluster_articles: list,
    agent: AgentSpec,
) -> TaskPayload:
    compact_articles = []

    for article in cluster_articles:
        compact_articles.append({
            "source": article.get("source", ""),
            "title": article.get("title", ""),
            "published": article.get("published", ""),
            "summary": (article.get("summary", "") or "")[:1000],
            "cves": article.get("cves", []),
            "full_text_excerpt": (article.get("full_text", "") or "")[:4000],
        })

    scored_cluster_payload = json.dumps(scored_cluster, indent=2, ensure_ascii=False)
    articles_payload = json.dumps(compact_articles, indent=2, ensure_ascii=False)

    system_prompt = f"""
You are acting as: {agent.role}

Goal:
{agent.goal}

Background:
{agent.backstory}

You must behave like an executive cybersecurity summary writer and return strict JSON only.
""".strip()

    user_prompt = f"""
You are given a selected cybersecurity cluster with ID: {cluster_id}.

Your job is to write one executive-ready summary for leadership based on:
1. The cluster scoring output
2. The supporting article data

Scored cluster:
{scored_cluster_payload}

Supporting articles:
{articles_payload}

Return ONLY valid JSON in this exact format:

{{
  "cluster_id": "{cluster_id}",
  "headline": "<short executive headline>",
  "executive_summary": "<4-6 sentence executive-level summary>",
  "why_it_matters": "<2-4 sentence explanation of why this matters to leadership>",
  "key_takeaways": [
    "<takeaway 1>",
    "<takeaway 2>",
    "<takeaway 3>"
  ],
  "priority": "<low, medium, high, or critical>"
}}

Writing guidance:
- Write for executives, not SOC analysts
- Be concise, clear, and decision-oriented
- Focus on impact, urgency, scale, risk, and strategic importance
- Do not invent facts not present in the input
- Reflect the scoring data in the tone and priority
- If the cluster appears severe and highly relevant, make that clear
- Use the article evidence to support the summary

Rules:
- Return ONLY JSON
- No markdown fences
- No extra commentary
- No preamble
""".strip()

    return TaskPayload(
        task_name="executive_summary",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_type="json",
    )
