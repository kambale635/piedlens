import unittest

from django.urls import URLPattern, URLResolver, get_resolver


class RouteSecurityPolicyTests(unittest.TestCase):
    def test_every_resolved_route_declares_an_explicit_security_policy(self):
        missing_policies = []

        def visit(patterns, prefix=""):
            for pattern in patterns:
                route = f"{prefix}{pattern.pattern}"
                if isinstance(pattern, URLResolver):
                    visit(pattern.url_patterns, route)
                    continue
                if not isinstance(pattern, URLPattern):
                    continue
                callback = pattern.callback
                policy_declared = bool(
                    getattr(callback, "required_permission", None)
                    or getattr(callback, "public_route", False)
                    or getattr(callback, "allow_anonymous", False)
                )
                if not policy_declared:
                    missing_policies.append(f"{route} -> {callback.__module__}.{callback.__name__}")

        visit(get_resolver().url_patterns)

        self.assertEqual(missing_policies, [], "Routes without explicit policy:\n" + "\n".join(missing_policies))


if __name__ == "__main__":
    unittest.main()