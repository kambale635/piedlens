from django.urls import URLPattern, URLResolver, get_resolver


class DjangoPermissionCatalog:
    def declared_permissions(self) -> frozenset[str]:
        return frozenset(self._permissions(get_resolver().url_patterns))

    @classmethod
    def _permissions(cls, patterns):
        for pattern in patterns:
            if isinstance(pattern, URLResolver):
                yield from cls._permissions(pattern.url_patterns)
            elif isinstance(pattern, URLPattern):
                permission = getattr(pattern.callback, "required_permission", None)
                if permission:
                    yield permission