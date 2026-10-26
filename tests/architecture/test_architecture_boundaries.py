import ast
import unittest
from pathlib import Path

from django.apps import apps


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
CONTEXTS_ROOT = SOURCE_ROOT / "contexts"


def _context_roots() -> list[Path]:
    return sorted(path for path in CONTEXTS_ROOT.iterdir() if path.is_dir())


def _resolve_import(path: Path, node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level == 0:
        return [node.module or ""]

    relative_path = path.relative_to(SOURCE_ROOT).with_suffix("")
    package_parts = list(relative_path.parts[:-1])
    package_parts = package_parts[: len(package_parts) - node.level + 1]
    if node.module:
        package_parts.extend(node.module.split("."))
    return [".".join(package_parts)]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        imported
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for imported in _resolve_import(path, node)
    ]


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_channel_provider_names_do_not_leak_into_domain_or_application(self):
        import re

        forbidden = re.compile(
            r"(?:['\"])(?:whatsapp|instagram|facebook|mpesa|airtel|orange|flexpay|maxicash|pawapay)(?:['\"])",
            re.IGNORECASE,
        )
        violations = []
        legacy_exceptions = {
            CONTEXTS_ROOT / "crm/application/use_cases/send_bulk_message_use_case.py",
            CONTEXTS_ROOT / "platform_connectors/domain/value_objects/platform_type.py",
        }
        for context_root in _context_roots():
            for layer in ("domain", "application"):
                for path in (context_root / layer).glob("**/*.py"):
                    if path in legacy_exceptions:
                        continue
                    source = path.read_text(encoding="utf-8")
                    if forbidden.search(source):
                        violations.append(str(path))
        self.assertEqual(violations, [])

    def test_all_contexts_keep_domain_modules_in_subpackages(self):
        for context_root in _context_roots():
            with self.subTest(context=context_root.name):
                domain_root = context_root / "domain"
                misplaced = [
                    path.name
                    for path in domain_root.glob("*.py")
                    if path.name != "__init__.py"
                ]
                self.assertEqual(misplaced, [])

    def test_domain_does_not_import_other_layers(self):
        violations = []
        for context_root in _context_roots():
            for path in (context_root / "domain").glob("**/*.py"):
                context = context_root.name
                for imported in _imports(path):
                    if imported.startswith("shared_kernel"):
                        continue
                    if imported.startswith("contexts."):
                        parts = imported.split(".")
                        if len(parts) < 3 or parts[1] != context or parts[2] != "domain":
                            violations.append(f"{path}: {imported}")
        self.assertEqual(violations, [])

    def test_application_does_not_import_infrastructure_or_presentation(self):
        violations = []
        for context_root in _context_roots():
            for path in (context_root / "application").glob("**/*.py"):
                context = context_root.name
                for imported in _imports(path):
                    if imported.startswith(f"contexts.{context}.infrastructure"):
                        violations.append(f"{path}: {imported}")
                    if imported.startswith(f"contexts.{context}.presentation"):
                        violations.append(f"{path}: {imported}")
        self.assertEqual(violations, [])

    def test_contexts_do_not_import_each_other(self):
        violations = []
        for context_root in _context_roots():
            for path in context_root.glob("**/*.py"):
                for imported in _imports(path):
                    if not imported.startswith("contexts."):
                        continue
                    target_parts = imported.split(".")
                    if len(target_parts) > 1 and target_parts[1] != context_root.name:
                        violations.append(f"{path}: {imported}")
        self.assertEqual(violations, [])

    def test_context_tables_use_their_bounded_context_prefix(self):
        violations = []
        for context_root in _context_roots():
            context_label = context_root.name
            for model in apps.get_app_config(context_label).get_models():
                expected_prefix = f"{context_label}_"
                if not model._meta.db_table.startswith(expected_prefix):
                    violations.append(
                        f"{context_label}.{model.__name__}: {model._meta.db_table} "
                        f"does not start with {expected_prefix}"
                    )
        self.assertEqual(violations, [])

    def test_context_models_have_no_cross_context_orm_relations(self):
        context_labels = {path.name for path in _context_roots()}
        violations = []
        for context_label in sorted(context_labels):
            for model in apps.get_app_config(context_label).get_models():
                for field in model._meta.get_fields():
                    if not getattr(field, "is_relation", False):
                        continue
                    if getattr(field, "auto_created", False):
                        continue
                    remote_model = getattr(getattr(field, "remote_field", None), "model", None)
                    target_context = getattr(getattr(remote_model, "_meta", None), "app_label", None)
                    if target_context != context_label:
                        violations.append(
                            f"{context_label}.{model.__name__}.{field.name} -> "
                            f"{target_context}.{getattr(remote_model, '__name__', remote_model)}"
                        )
        self.assertEqual(violations, [])
