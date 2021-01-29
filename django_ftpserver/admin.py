from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from . import models
from .formatters import format_time_human_format


class FTPUserGroupAdmin(admin.ModelAdmin):
    """Admin class for FTPUserGroup"""

    list_display = ("name", "permission")
    search_fields = ("name", "permission")


class FTPUserAccountAdmin(admin.ModelAdmin):
    """Admin class for FTPUserAccountAdmin"""

    list_display = ("user", "group", "last_login")
    search_fields = ("user", "group", "last_login")


class FTPFileInfoAdmin(admin.ModelAdmin):
    """Admin class for FTPFileInfoAdmin"""

    list_display = ["name", "is_dir", "parent", "mtime_human_format"]

    fields = [
        "name",
        "is_dir",
        "parent",
        "mtime_human_format",
        "permission",
        "links_number",
    ]

    readonly_fields = ["mtime_human_format"]

    def mtime_human_format(self, obj):
        return format_time_human_format(obj.mtime, use_gmt_times=True)

    mtime_human_format.short_description = _("Last modification date in human format")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(models.FTPUserGroup, FTPUserGroupAdmin)
admin.site.register(models.FTPUserAccount, FTPUserAccountAdmin)
admin.site.register(models.FTPFileInfo, FTPFileInfoAdmin)
