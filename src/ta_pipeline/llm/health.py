import requests
from ta_pipeline.app_config import AppConfig


def check_model_server(config: AppConfig, timeout: int = 60) -> dict:
    response = requests.get(
        f"{config.base_url}/models",
        headers={"Authorization": f"Bearer {config.model_api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()

    return {
        "status_code": response.status_code,
        "body": response.text,
    }