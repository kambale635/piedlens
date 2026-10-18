from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("access_control", "0004_outboxeventrecord_next_attempt_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="MerchantDeletionAuditRecord",
            fields=[
                ("assignment_id", models.UUIDField(primary_key=True, serialize=False)),
                ("user_id", models.UUIDField()),
                ("role_id", models.UUIDField()),
                ("scope_id", models.UUIDField()),
                ("granted_by", models.CharField(max_length=64)),
                ("granted_at", models.DateTimeField()),
                ("revoked_by", models.CharField(blank=True, max_length=64, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("purged_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "access_control_merchant_deletion_audit"},
        ),
        migrations.CreateModel(
            name="MerchantDeletionProgressRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField()),
                ("merchant_id", models.UUIDField()),
                ("assignment_id", models.UUIDField()),
            ],
            options={"db_table": "access_control_merchant_deletion_progress"},
        ),
        migrations.AddConstraint(
            model_name="merchantdeletionprogressrecord",
            constraint=models.UniqueConstraint(
                fields=("event_id", "assignment_id"),
                name="uniq_access_control_merchant_deletion_progress",
            ),
        ),
    ]