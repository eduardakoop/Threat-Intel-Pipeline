from dataclasses import dataclass


@dataclass
class TaskPayload:
    task_name: str
    system_prompt: str
    user_prompt: str
    output_type: str  # "json" or "text"