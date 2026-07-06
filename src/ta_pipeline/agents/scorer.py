from ta_pipeline.models.agent import AgentSpec


def build_scorer_agent() -> AgentSpec:
    return AgentSpec(
        role="Cyber Threat Cluster Scorer",
        goal=(
            "Evaluate a cybersecurity article cluster and assign an importance score "
            "based on relevance, severity, exploitability, business impact, and urgency."
        ),
        backstory=(
            "You are a cybersecurity intelligence analyst responsible for triaging grouped "
            "threat reporting. You read clustered article data, identify the most important "
            "signals, and produce a concise, structured justification for why the cluster "
            "does or does not matter. Your scoring must be consistent, practical, and "
            "defensible."
        ),
    )