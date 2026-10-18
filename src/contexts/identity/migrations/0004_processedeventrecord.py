from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0003_outboxeventrecord_next_attempt_at"),
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
            options={"db_table": "identity_processed_events"},
        ),
        migrations.AddConstraint(
            model_name="processedeventrecord",
            constraint=models.UniqueConstraint(
                fields=("event_id", "consumer_name"),
                name="uniq_identity_processed_event_consumer",
            ),
        ),
    ]