import time
from llm_proxy.retry import RetryManager


def test_model_available_initially():
    rm = RetryManager(fail_threshold=2, cooldown_seconds=60)
    assert rm.is_available("model-a") is True


def test_cooldown_triggers_after_threshold():
    rm = RetryManager(fail_threshold=2, cooldown_seconds=60)
    rm.record_failure("model-a")
    rm.record_failure("model-a")
    assert rm.is_available("model-a") is False


def test_success_resets_count():
    rm = RetryManager(fail_threshold=2, cooldown_seconds=60)
    rm.record_failure("model-a")
    rm.record_success("model-a")
    rm.record_failure("model-a")
    assert rm.is_available("model-a") is True


def test_cooldown_expires():
    rm = RetryManager(fail_threshold=1, cooldown_seconds=1)
    rm.record_failure("model-a")
    assert rm.is_available("model-a") is False
    time.sleep(1.1)
    assert rm.is_available("model-a") is True


def test_different_models_independent():
    rm = RetryManager(fail_threshold=2, cooldown_seconds=60)
    rm.record_failure("model-a")
    rm.record_failure("model-a")
    assert rm.is_available("model-a") is False
    assert rm.is_available("model-b") is True
