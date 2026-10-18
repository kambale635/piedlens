from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rules_engine", "0002_outboxeventrecord_next_attempt_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="MerchantDeletionProgressRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField()),
                ("merchant_id", models.UUIDField()),
                ("rule_set_id", models.UUIDField()),
            ],
            options={"db_table": "rules_engine_deletion_progress"},
        ),
        migrations.AddConstraint(
            model_name="merchantdeletionprogressrecord",
            constraint=models.UniqueConstraint(
                fields=("event_id", "rule_set_id"),
                name="uniq_rules_engine_deletion_progress",
            ),
        ),
    ]