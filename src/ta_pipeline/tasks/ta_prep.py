import json

from ta_pipeline.models.agent import AgentSpec
from ta_pipeline.models.task import TaskPayload


def build_ta_prep_task(
    cluster_id: str,
    scored_cluster: dict,
    cluster_articles: list,
    executive_summary: dict,
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
            "full_text_excerpt": (article.get("full_text", "") or "")[:4000],
            "url": article.get("url", ""),
        })

    scored_cluster_payload = json.dumps(scored_cluster, indent=2, ensure_ascii=False)
    articles_payload = json.dumps(compact_articles, indent=2, ensure_ascii=False)
    executive_summary_payload = json.dumps(executive_summary, indent=2, ensure_ascii=False)

    system_prompt = f"""
You are acting as: {agent.role}

Goal:
{agent.goal}

Background:
{agent.backstory}

You must behave like a cybersecurity threat advisory preparation analyst and return strict JSON only.
""".strip()

    user_prompt = f"""
You are given a selected cybersecurity cluster with ID: {cluster_id}.

Your job is to prepare an internal Threat Advisory writing brief based on:
1. The cluster scoring output
2. The supporting article data
3. The executive summary already generated for leadership

Scored cluster:
{scored_cluster_payload}

Supporting articles:
{articles_payload}

Executive summary:
{executive_summary_payload}

Return ONLY valid JSON in this exact format:

{{
  "cluster_id": "{cluster_id}",
  "title": "<clear professional title>",
  "subtitle": "<one-sentence subtitle>",
  "introduction": "<brief introduction for an internal cybersecurity audience>",
  "threat_landscape_targets": "<broader threat context and who may be affected>",
  "ttps": [
    "<ttp 1>",
    "<ttp 2>"
  ],
  "iocs": [
    "<ioc or IOC-related line 1>",
    "<ioc or IOC-related line 2>"
  ],
  "defensive_strategies_best_practices": [
    "<defensive action 1>",
    "<defensive action 2>"
  ],
  "references": [
    "<source title> - <url>",
    "<source title> - <url>"
  ]
}}

Formatting requirements:
- All arrays must contain plain strings only
- Do not return nested JSON objects
- If a paragraph section is unsupported, write: "Not reported."
- If a list section is unsupported, return ["Not reported."]

Rules:
- Base the brief only on the provided inputs
- Use the executive summary as high-level framing, but rely on the source articles for technical detail
- Do not invent facts, indicators, attribution, or technical details
- If information is missing or unsupported, clearly say so
- Do not mention the prompt, the instructions, formatting rules, or your reasoning
- Do not write phrases like "Wait, one detail", "the prompt says", "I will", or "Here is the brief"
- Return ONLY JSON
- No markdown fences
- No extra commentary
""".strip()

    return TaskPayload(
        task_name="ta_prep",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_type="json",
    )
