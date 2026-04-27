from app.services.llm import AIClientError, call_chat_completion_content
from app.services.settings.errors import SettingsError
from app.services.settings.normalization import normalize_single_ai_model


def test_ai_model_config(model_config: object) -> str:
    config = normalize_single_ai_model(model_config)
    try:
        return call_chat_completion_content(
            config,
            [
                {
                    "role": "system",
                    "content": "You are a connection test endpoint. Reply with one short hello sentence.",
                },
                {"role": "user", "content": "hello"},
            ],
            timeout=30,
            temperature=0,
        )
    except AIClientError as exc:
        raise SettingsError(str(exc)) from exc
