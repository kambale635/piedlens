# Generated migration for the CRM transactional Outbox.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0002_remove_contactrecord_currency_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="OutboxEventRecord",
            fields=[
                ("event_id", models.UUIDField(primary_key=True, serialize=False)),
                ("event_type", models.CharField(max_length=160)),
                ("event_version", models.PositiveSmallIntegerField(default=1)),
                ("occurred_at", models.DateTimeField()),
                ("produced_by", models.CharField(default="crm", max_length=80)),
                ("correlation_id", models.UUIDField(blank=True, null=True)),
                ("payload", models.JSONField()),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
            ],
            options={
                "db_table": "crm_outbox_events",
                "indexes": [
                    models.Index(
                        fields=["published_at", "occurred_at"],
                        name="crm_outbox__publish_ea743b_idx",
                    )
                ],
            },
        ),
    ]