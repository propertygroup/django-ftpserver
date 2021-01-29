import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_ftpserver", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FTPFileInfo",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("is_dir", models.BooleanField(verbose_name="Is directory?")),
                (
                    "permission",
                    models.CharField(
                        max_length=255, verbose_name="Permission to directory/files"
                    ),
                ),
                (
                    "links_number",
                    models.IntegerField(default=1, verbose_name="Links number"),
                ),
                ("size", models.IntegerField(verbose_name="Size [B]")),
                ("mtime", models.IntegerField(verbose_name="Last modification date")),
                ("name", models.CharField(max_length=255, verbose_name="Name")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="django_ftpserver.ftpfileinfo",
                        verbose_name="Parent",
                    ),
                ),
            ],
            options={
                "verbose_name": "FTP file info",
                "verbose_name_plural": "FTP files info",
            },
        ),
    ]
