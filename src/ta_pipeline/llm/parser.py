import json
import re


def extract_json_object(raw_text: str) -> dict:
    matches = re.findall(r"\{.*?\}", raw_text, re.DOTALL)

    for match in reversed(matches):
        try:
            return json.loads(match)
        except Exception:
            continue

    raise ValueError("No valid JSON object found in model output")
