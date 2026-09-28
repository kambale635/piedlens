from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0003_outboxeventrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactrecord",
            name="purchase_history",
            field=models.JSONField(default=list),
        ),
    ]