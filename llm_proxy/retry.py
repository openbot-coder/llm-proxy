import time


class RetryManager:
    def __init__(self, fail_threshold: int = 2, cooldown_seconds: int = 900, max_entries: int = 1000):
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_seconds
        self.max_entries = max_entries
        self._fail_counts: dict[str, int] = {}
        self._cooldowns: dict[str, float] = {}

    def _cleanup(self):
        now = time.time()
        expired = [k for k, v in self._cooldowns.items() if now >= v]
        for k in expired:
            del self._cooldowns[k]
            self._fail_counts.pop(k, None)
        if len(self._cooldowns) > self.max_entries:
            sorted_keys = sorted(self._cooldowns, key=self._cooldowns.get)
            for k in sorted_keys[:len(self._cooldowns) - self.max_entries]:
                del self._cooldowns[k]
                self._fail_counts.pop(k, None)

    def is_available(self, model_id: str) -> bool:
        if model_id in self._cooldowns:
            if time.time() < self._cooldowns[model_id]:
                return False
            del self._cooldowns[model_id]
            self._fail_counts.pop(model_id, None)
        return True

    def record_failure(self, model_id: str):
        self._fail_counts[model_id] = self._fail_counts.get(model_id, 0) + 1
        if self._fail_counts[model_id] >= self.fail_threshold:
            self._cooldowns[model_id] = time.time() + self.cooldown_seconds
            self._cleanup()

    def record_success(self, model_id: str):
        self._fail_counts.pop(model_id, None)
