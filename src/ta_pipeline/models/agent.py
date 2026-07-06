from dataclasses import dataclass


@dataclass
class AgentSpec:
    role: str
    goal: str
    backstory: str