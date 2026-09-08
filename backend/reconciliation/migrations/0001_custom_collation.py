from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def add_ct_collation(apps: StateApps, schema_editor: DatabaseSchemaEditor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute('CREATE COLLATION IF NOT EXISTS "case_sensitive" (provider = icu, locale = "und-u-ks-level1", deterministic = true)')


def drop_ct_collation(apps: StateApps, schema_editor: DatabaseSchemaEditor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute('DROP COLLATION IF EXISTS "case_sensitive"')


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunPython(add_ct_collation, drop_ct_collation),
    ]