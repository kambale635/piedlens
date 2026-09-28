from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0005_relationshipanomalynotificationrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactrecord",
            name="status",
            field=models.CharField(default="active", max_length=16),
        ),
        migrations.AddField(
            model_name="contactrecord",
            name="merged_into_contact_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]