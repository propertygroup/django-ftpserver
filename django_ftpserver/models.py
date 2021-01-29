import os

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


class FTPUserGroup(models.Model):
    name = models.CharField(
        _("Group name"), max_length=30, null=False, blank=False, unique=True
    )
    permission = models.CharField(
        _("Permission"), max_length=8, null=False, blank=False, default="elradfmw"
    )
    home_dir = models.CharField(
        _("Home directory"), max_length=1024, null=True, blank=True
    )

    def __str__(self):
        return "{0}".format(self.name)

    class Meta:
        verbose_name = _("FTP user group")
        verbose_name_plural = _("FTP user groups")


class FTPUserAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name=_("User"), on_delete=models.CASCADE
    )
    group = models.ForeignKey(
        FTPUserGroup,
        verbose_name=_("FTP user group"),
        null=False,
        blank=False,
        on_delete=models.CASCADE,
    )
    last_login = models.DateTimeField(_("Last login"), editable=False, null=True)
    home_dir = models.CharField(
        _("Home directory"), max_length=1024, null=True, blank=True
    )

    def __str__(self):
        try:
            user = self.user
        except ObjectDoesNotExist:
            user = None
        return "{0}".format(user)

    def get_username(self):
        try:
            user = self.user
        except ObjectDoesNotExist:
            user = None
        return user and user.username or ""

    def update_last_login(self, value=None):
        self.last_login = value or timezone.now()

    def get_home_dir(self):
        if self.home_dir:
            directory = self.home_dir
        elif self.group and self.group.home_dir:
            directory = self.group.home_dir
        else:
            directory = os.path.join(
                os.path.dirname(os.path.expanduser("~")), "{username}"
            )
        return directory.format(username=self.get_username())

    def has_perm(self, perm, path):
        return perm in self.get_perms()

    def get_perms(self):
        return self.group.permission

    class Meta:
        verbose_name = _("FTP user account")
        verbose_name_plural = _("FTP user accounts")


class FTPFileInfo(models.Model):
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Parent"),
        blank=True,
        null=True,
        related_name="children",
        on_delete=models.PROTECT,
    )
    is_dir = models.BooleanField(verbose_name=_("Is directory?"))
    permission = models.CharField(
        verbose_name=_("Permission to directory/files"), max_length=255
    )
    links_number = models.IntegerField(verbose_name=_("Links number"), default=1)
    size = models.IntegerField(verbose_name=_("Size [B]"))
    mtime = models.IntegerField(verbose_name=_("Last modification date"))
    name = models.CharField(verbose_name=_("Name"), max_length=255)

    class Meta:
        verbose_name = _("FTP file info")
        verbose_name_plural = _("FTP files info")

    def __str__(self):
        return f"{self.name}{'/' if self.is_dir else ''}"
