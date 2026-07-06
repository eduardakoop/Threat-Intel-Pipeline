from openai import OpenAI
from ta_pipeline.app_config import AppConfig


def build_llm_client(config: AppConfig) -> OpenAI:
    return OpenAI(
        base_url=config.base_url,
        api_key=config.model_api_key,
    )