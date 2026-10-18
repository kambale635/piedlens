from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_connectors", "0002_outboxeventrecord_next_attempt_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessedEventRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField()),
                ("consumer_name", models.CharField(max_length=160)),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "platform_connectors_processed_events"},
        ),
        migrations.AddConstraint(
            model_name="processedeventrecord",
            constraint=models.UniqueConstraint(
                fields=("event_id", "consumer_name"),
                name="uniq_platform_connectors_processed_event",
            ),
        ),
        migrations.CreateModel(
            name="MerchantDeletionProgressRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField()),
                ("merchant_id", models.UUIDField()),
                ("aggregate_type", models.CharField(max_length=32)),
                ("aggregate_id", models.UUIDField()),
            ],
            options={"db_table": "platform_connectors_deletion_progress"},
        ),
        migrations.AddConstraint(
            model_name="merchantdeletionprogressrecord",
            constraint=models.UniqueConstraint(
                fields=("event_id", "aggregate_type", "aggregate_id"),
                name="uniq_platform_deletion_progress_item",
            ),
        ),
    ]