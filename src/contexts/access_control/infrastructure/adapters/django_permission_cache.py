from django.core.cache import cache


class DjangoPermissionCache:
    epoch_key = "access_control:permission_cache_epoch"

    def __init__(self, ttl_seconds: int | None = None) -> None:
        from django.conf import settings

        self.ttl_seconds = ttl_seconds or settings.ACCESS_CONTROL_PERMISSION_CACHE_TTL_SECONDS

    def get(self, user_id, permission, scope_key):
        epoch = cache.get(self.epoch_key, 0)
        return cache.get(self._key(epoch, user_id, permission, scope_key))

    def set(self, user_id, permission, scope_key, allowed):
        epoch = cache.get(self.epoch_key, 0)
        cache.set(self._key(epoch, user_id, permission, scope_key), bool(allowed), self.ttl_seconds)

    def invalidate_all(self):
        if not cache.add(self.epoch_key, 1, timeout=None):
            try:
                cache.incr(self.epoch_key)
            except ValueError:
                cache.set(self.epoch_key, 1, timeout=None)

    @staticmethod
    def _key(epoch, user_id, permission, scope_key):
        return f"access_control:permission:{epoch}:{user_id}:{permission}:{scope_key}"