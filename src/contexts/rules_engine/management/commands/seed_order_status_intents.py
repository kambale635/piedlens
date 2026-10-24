from uuid import uuid4

from django.core.management.base import BaseCommand
from django.db import transaction

from contexts.rules_engine.infrastructure.persistence.models import RuleSetRecord


STATUS_RULES = (
    {
        "language": "fr",
        "intent": "payment_received",
        "patterns": ["c'est payé", "c’est payé", "payé", "payée", "paiement reçu"],
    },
    {
        "language": "en",
        "intent": "payment_received",
        "patterns": ["it's paid", "it’s paid", "paid", "payment received", "payment made"],
    },
    {
        "language": "fr",
        "intent": "delivery_confirmed",
        "patterns": ["bien reçu", "reçu", "reçue", "livré", "livrée", "livraison reçue"],
    },
    {
        "language": "en",
        "intent": "delivery_confirmed",
        "patterns": ["well received", "received", "delivered", "delivery confirmed"],
    },
)


class Command(BaseCommand):
    help = "Seed configurable French and English payment/delivery intent rules."

    def handle(self, *args, **options):
        with transaction.atomic():
            record, _ = RuleSetRecord.objects.get_or_create(
                scope="global",
                defaults={"id": uuid4(), "version": 1, "rules": []},
            )
            rules = list(record.rules)
            known_keys = {
                item.get("config", {}).get("seed_key")
                for item in rules
                if isinstance(item, dict)
            }
            additions = []
            for rule in STATUS_RULES:
                seed_key = f"order-status:{rule['language']}:{rule['intent']}"
                if seed_key in known_keys:
                    continue
                additions.append(
                    {
                        "rule_id": str(uuid4()),
                        "rule_type": "ConfiguredIntent",
                        "language": rule["language"],
                        "pattern": rule["patterns"],
                        "weight": 100,
                        "is_active": True,
                        "currency": None,
                        "config": {"intent": rule["intent"], "seed_key": seed_key},
                    }
                )
            if additions:
                record.rules = rules + additions
                record.version += 1
                record.save(update_fields=["rules", "version"])
        self.stdout.write(self.style.SUCCESS(f"Added {len(additions)} order status intent rules."))