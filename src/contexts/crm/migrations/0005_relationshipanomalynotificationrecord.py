import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0004_contactrecord_purchase_history"),
    ]

    operations = [
        migrations.CreateModel(
            name="RelationshipAnomalyNotificationRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("merchant_id", models.UUIDField()),
                ("contact_id", models.UUIDField()),
                ("last_purchase_order_id", models.UUIDField()),
                ("days_since_last_purchase", models.FloatField()),
                ("usual_interval_days", models.FloatField()),
                ("notified_at", models.DateTimeField()),
            ],
            options={
                "db_table": "crm_relationship_anomaly_notifications",
            },
        ),
        migrations.AddConstraint(
            model_name="relationshipanomalynotificationrecord",
            constraint=models.UniqueConstraint(
                fields=("contact_id", "last_purchase_order_id"),
                name="uniq_crm_anomaly_contact_silence",
            ),
        ),
        migrations.AddIndex(
            model_name="relationshipanomalynotificationrecord",
            index=models.Index(
                fields=["merchant_id", "notified_at"],
                name="crm_rel_anomaly_merchant_idx",
            ),
        ),
    ]