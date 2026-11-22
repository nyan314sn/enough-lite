"""Provider choice: Anthropic when its key is set, else OpenAI (gpt-6-luna) when OPENAI_API_KEY is set; ENOUGH_PROVIDER forces one."""
from app import config, llm


def test_no_keys_means_no_ai():
    assert config.get_settings().has_key is False


def test_anthropic_key_wins(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    s = config.get_settings()
    assert (s.provider, s.model, s.has_key) == ("anthropic", config.DEFAULT_MODEL, True)
    assert "anthropic_effort" in llm.model_settings("low")


def test_openai_key_alone_uses_gpt_6_luna(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    s = config.get_settings()
    assert (s.provider, s.model, s.has_key) == ("openai", "gpt-6-luna", True)
    ms = llm.model_settings("low")
    assert ms["openai_reasoning_effort"] == "low" and not any(k.startswith("anthropic_") for k in ms)
    assert "temperature" not in ms
    m = llm.make_model()
    assert type(m).__name__ == "OpenAIResponsesModel" and m.model_name == "gpt-6-luna"


def test_portkey_key_alone_is_not_used(monkeypatch):
    monkeypatch.setenv("PORTKEY_API_KEY", "pk-test")
    assert config.get_settings().has_key is False


def test_forced_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ENOUGH_PROVIDER", "openai")
    assert config.get_settings().provider == "openai"


def test_openai_cache_writes_priced_as_plain_input():
    assert llm.cost_usd("gpt-6-luna", 0, 0, 1_000_000, 0) == llm.cost_usd("gpt-6-luna", 1_000_000, 0, 0, 0)


def test_health_names_the_provider(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    h = TestClient(app).get("/api/health").json()
    assert h["provider"] == "openai" and h["model"] == "gpt-6-luna" and h["ai_available"] is True
