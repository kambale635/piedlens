from django.db import migrations


def install_append_only_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        CREATE OR REPLACE FUNCTION event_bus_reject_audit_log_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit log is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    schema_editor.execute(
        """
        CREATE TRIGGER event_bus_audit_log_append_only
        BEFORE UPDATE OR DELETE ON event_bus_audit_log
        FOR EACH ROW EXECUTE FUNCTION event_bus_reject_audit_log_mutation();
        """
    )


def remove_append_only_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "DROP TRIGGER IF EXISTS event_bus_audit_log_append_only ON event_bus_audit_log;"
    )
    schema_editor.execute("DROP FUNCTION IF EXISTS event_bus_reject_audit_log_mutation();")


class Migration(migrations.Migration):
    dependencies = [("event_bus", "0001_initial")]

    operations = [migrations.RunPython(install_append_only_trigger, remove_append_only_trigger)]