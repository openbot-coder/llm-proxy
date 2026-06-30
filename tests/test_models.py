from llm_proxy.models import BackendModel, ModelGroup, ApiKey


def test_backend_model_create():
    m = BackendModel(id="gpt4o", provider="openai", api_base="https://api.openai.com/v1",
                     api_key="sk-test", model_name="gpt-4o", rpm=120)
    assert m.id == "gpt4o"


def test_model_group_create():
    g = ModelGroup(name="fast", models=["gpt4o", "flash"], weights={"gpt4o": 60, "flash": 40})
    assert g.name == "fast"


def test_api_key_create():
    k = ApiKey(key_hash="abc123", name="test-app", models=["fast"])
    assert k.name == "test-app"


def test_api_key_no_models_restriction():
    k = ApiKey(key_hash="abc123", name="admin", models=None)
    assert k.models is None
