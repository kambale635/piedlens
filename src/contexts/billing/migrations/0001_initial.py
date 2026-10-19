import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PlanDefinitionRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(max_length=32, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("display_order", models.PositiveIntegerField()),
            ],
            options={
                "db_table": "billing_plan_definitions",
                "ordering": ["display_order", "code"],
            },
        ),
        migrations.CreateModel(
            name="PlanPriceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("country", models.CharField(max_length=2)),
                ("currency", models.CharField(max_length=3)),
                ("period_days", models.PositiveIntegerField()),
                ("amount_minor", models.PositiveBigIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="prices", to="billing.plandefinitionrecord")),
            ],
            options={"db_table": "billing_plan_prices"},
        ),
        migrations.AddConstraint(
            model_name="planpricerecord",
            constraint=models.UniqueConstraint(fields=("plan", "country", "currency", "period_days"), name="uniq_billing_plan_price_scope"),
        ),
        migrations.CreateModel(
            name="PlanEntitlementRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64)),
                ("value", models.JSONField()),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entitlements", to="billing.plandefinitionrecord")),
            ],
            options={"db_table": "billing_plan_entitlements"},
        ),
        migrations.AddConstraint(
            model_name="planentitlementrecord",
            constraint=models.UniqueConstraint(fields=("plan", "key"), name="uniq_billing_plan_entitlement"),
        ),
    ]