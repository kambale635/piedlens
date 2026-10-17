import unittest
from datetime import datetime, timezone
from uuid import uuid4

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from contexts.access_control.application.use_cases.assign_owner_role_on_merchant_registered_use_case import (
    AssignOwnerRoleOnMerchantRegisteredUseCase,
)
from contexts.access_control.application.use_cases.assign_role_to_user_use_case import (
    AssignRoleToUserUseCase,
)
from contexts.access_control.application.use_cases.check_permission_use_case import (
    CheckPermissionUseCase,
)
from contexts.access_control.domain.entities.role import Role
from contexts.access_control.domain.entities.role_assignment import RoleAssignment
from contexts.access_control.domain.exceptions.access_control_exceptions import (
    InsufficientPrivilegeToGrant,
)
from contexts.access_control.infrastructure.adapters.django_permission_cache import (
    DjangoPermissionCache,
)


class AccessControlUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.cache = FakeCache()
        self.outbox = FakeOutbox()
        self.clock = FakeClock()
        self.owner_role = Role(uuid4(), "Owner", frozenset({"contact.read", "role.assign"}), True,
                               self.clock.now_utc())
        self.repository.roles[self.owner_role.id] = self.owner_role
        self.repository.by_name[self.owner_role.name] = self.owner_role
        self.actor_id = uuid4()
        self.target_id = uuid4()
        self.merchant_id = uuid4()

    def test_assignment_cannot_grant_permissions_actor_does_not_have(self):
        excessive_role = Role(uuid4(), "Elevated", frozenset({"role.assign", "role.revoke"}), False,
                              self.clock.now_utc())
        self.repository.roles[excessive_role.id] = excessive_role
        self.repository.user_permissions[(self.actor_id, self.merchant_id)] = {"role.assign"}
        use_case = self._assign_use_case()
        with self.assertRaises(InsufficientPrivilegeToGrant):
            use_case.execute(self.target_id, excessive_role.id,
                             {"merchantId": str(self.merchant_id)}, self.actor_id)
        self.assertEqual(self.repository.assignments, {})

    def test_assignment_records_actor_scope_event_and_invalidates_cache(self):
        self.repository.user_permissions[(self.actor_id, self.merchant_id)] = set(self.owner_role.permissions)
        result = self._assign_use_case().execute(
            self.target_id, self.owner_role.id,
            {"merchantId": str(self.merchant_id)}, self.actor_id,
        )
        assignment = self.repository.assignments[result["roleAssignmentId"]]
        self.assertEqual(assignment.granted_by, str(self.actor_id))
        self.assertEqual(assignment.scope_id, self.merchant_id)
        self.assertEqual(self.outbox.events[-1].granted_by, str(self.actor_id))
        self.assertEqual(self.cache.invalidations, 1)

    def test_owner_assignment_is_idempotent_and_uses_system_actor(self):
        use_case = AssignOwnerRoleOnMerchantRegisteredUseCase(
            self.repository, self.clock, self.cache, self.outbox, FakeUnitOfWork()
        )
        first = use_case.execute(self.merchant_id, self.target_id)
        second = use_case.execute(self.merchant_id, self.target_id)
        self.assertEqual(first, second)
        self.assertEqual(len(self.repository.assignments), 1)
        self.assertEqual(next(iter(self.repository.assignments.values())).granted_by, "system")

    def test_owner_consumer_uses_event_ledger_on_redelivery(self):
        processed = FakeProcessedEvents()
        use_case = AssignOwnerRoleOnMerchantRegisteredUseCase(
            self.repository, self.clock, self.cache, self.outbox, FakeUnitOfWork(), processed
        )
        event_id = uuid4()
        first = use_case.execute(self.merchant_id, self.target_id, event_id)
        second = use_case.execute(self.merchant_id, self.target_id, event_id)
        self.assertEqual(first, second)
        self.assertEqual(len(self.outbox.events), 1)
        self.assertTrue(processed.has_processed(event_id, type(use_case).__name__))

    def test_permission_checker_uses_scope_and_cache(self):
        self.repository.user_permissions[(self.target_id, self.merchant_id)] = {"contact.read"}
        use_case = CheckPermissionUseCase(self.repository, self.cache)
        scope = str(self.merchant_id)
        self.assertTrue(use_case.execute(self.target_id, "contact.read", scope)["allowed"])
        self.repository.user_permissions[(self.target_id, self.merchant_id)].clear()
        self.assertTrue(use_case.execute(self.target_id, "contact.read", scope)["allowed"])
        self.cache.invalidate_all()
        self.assertFalse(use_case.execute(self.target_id, "contact.read", scope)["allowed"])

    def _assign_use_case(self):
        return AssignRoleToUserUseCase(
            self.repository, self.clock, self.cache, self.outbox, FakeUnitOfWork()
        )


class FakeRepository:
    def __init__(self):
        self.roles = {}
        self.by_name = {}
        self.assignments = {}
        self.user_permissions = {}

    def find_role(self, role_id):
        return self.roles.get(role_id)

    def find_role_by_name(self, name):
        return self.by_name.get(name)

    def save_role(self, role):
        self.roles[role.id] = role
        self.by_name[role.name] = role

    def find_assignment(self, assignment_id):
        return self.assignments.get(assignment_id)

    def find_active_assignment(self, user_id, role_id, scope_id):
        return next((a for a in self.assignments.values()
                     if a.user_id == user_id and a.role_id == role_id
                     and a.scope_id == scope_id and a.revoked_at is None), None)

    def save_assignment(self, assignment):
        self.assignments[assignment.id] = assignment

    def permissions_for(self, user_id, scope_type, scope_id):
        return frozenset(self.user_permissions.get((user_id, scope_id), set()))


class FakeCache:
    def __init__(self):
        self.values = {}
        self.invalidations = 0

    def get(self, user_id, permission, scope_key):
        return self.values.get((user_id, permission, scope_key))

    def set(self, user_id, permission, scope_key, allowed):
        self.values[(user_id, permission, scope_key)] = allowed

    def invalidate_all(self):
        self.values.clear()
        self.invalidations += 1


class FakeOutbox:
    def __init__(self):
        self.events = []

    def add(self, event):
        self.events.append(event)


class FakeProcessedEvents:
    def __init__(self):
        self.events = set()

    def has_processed(self, event_id, consumer_name):
        return (event_id, consumer_name) in self.events

    def mark_processed(self, event_id, consumer_name):
        self.events.add((event_id, consumer_name))


class FakeClock:
    def now_utc(self):
        return datetime.now(timezone.utc)


class FakeUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        return False


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "permission-cache-unit-test",
        }
    }
)
class PermissionCacheTests(SimpleTestCase):
    def test_epoch_invalidation_hides_cached_permission_decisions(self):
        cache.clear()
        permissions = DjangoPermissionCache(ttl_seconds=5)
        user_id = uuid4()
        permissions.set(user_id, "role.assign", "merchant-1", True)
        self.assertTrue(permissions.get(user_id, "role.assign", "merchant-1"))
        permissions.invalidate_all()
        self.assertIsNone(permissions.get(user_id, "role.assign", "merchant-1"))


if __name__ == "__main__":
    unittest.main()