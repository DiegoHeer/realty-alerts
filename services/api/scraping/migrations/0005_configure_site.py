from django.conf import settings
from django.db import migrations


def set_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=getattr(settings, "SITE_ID", 1),
        defaults={"name": "Huismus", "domain": "huismusapp.com"},
    )


def unset_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.filter(pk=getattr(settings, "SITE_ID", 1)).update(name="example.com", domain="example.com")


class Migration(migrations.Migration):
    dependencies = [
        ("scraping", "0004_residence_trgm_search"),
        ("sites", "0002_alter_domain_unique"),
    ]
    operations = [migrations.RunPython(set_site, unset_site)]
