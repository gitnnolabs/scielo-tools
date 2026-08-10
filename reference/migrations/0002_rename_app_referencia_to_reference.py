from django.db import migrations


def _table_exists(schema_editor, name):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = %s
            """,
            [name],
        )
        return cursor.fetchone() is not None


def rename_legacy_tables(apps, schema_editor):
    mapping = (
        ("referencia_reference", "reference_reference"),
        ("referencia_elementcitation", "reference_elementcitation"),
    )
    with schema_editor.connection.cursor() as cursor:
        for old_name, new_name in mapping:
            old_exists = _table_exists(schema_editor, old_name)
            new_exists = _table_exists(schema_editor, new_name)
            if old_exists and not new_exists:
                cursor.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')
            elif old_exists and new_exists:
                cursor.execute(f'DROP TABLE "{old_name}" CASCADE')


def revert_legacy_tables(apps, schema_editor):
    mapping = (
        ("reference_reference", "referencia_reference"),
        ("reference_elementcitation", "referencia_elementcitation"),
    )
    with schema_editor.connection.cursor() as cursor:
        for old_name, new_name in mapping:
            old_exists = _table_exists(schema_editor, old_name)
            new_exists = _table_exists(schema_editor, new_name)
            if old_exists and not new_exists:
                cursor.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')


def rename_app_label(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="referencia").update(app_label="reference")


def revert_app_label(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="reference").update(app_label="referencia")


class Migration(migrations.Migration):
    dependencies = [
        ("reference", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(rename_legacy_tables, revert_legacy_tables),
        migrations.RunPython(rename_app_label, revert_app_label),
    ]
