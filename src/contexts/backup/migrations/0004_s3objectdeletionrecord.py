from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("backup", "0003_merchantdeletiontokenrecord"),
    ]

    operations = [
        migrations.CreateModel(
            name="S3ObjectDeletionRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=512, unique=True)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("last_error_type", models.CharField(blank=True, max_length=160)),
            ],
            options={"db_table": "backup_s3_object_deletions"},
        ),
    ]