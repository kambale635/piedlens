from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("order_detection", "0006_outboxeventrecord_next_attempt_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="MerchantDeletionProgressRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField()),
                ("merchant_id", models.UUIDField()),
                ("aggregate_type", models.CharField(max_length=32)),
                ("aggregate_id", models.UUIDField()),
            ],
            options={"db_table": "order_detection_deletion_progress"},
        ),
        migrations.AddConstraint(
            model_name="merchantdeletionprogressrecord",
            constraint=models.UniqueConstraint(
                fields=("event_id", "aggregate_type", "aggregate_id"),
                name="uniq_order_detection_deletion_progress",
            ),
        ),
    ]