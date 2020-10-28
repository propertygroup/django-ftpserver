import time

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from pyftpdlib.handlers import FTPHandler, _strerror

from .formatters import format_file_info_line_list, format_file_info_line_mlsd
from .helpers import (
    create_cached_structure,
    query_based_on_split_path,
    remove_files_info_from_cache,
    split_path,
)
from .models import FTPFileInfo


class CachedFTPHandler(FTPHandler):
    def ftp_LIST(self, path):
        """Return a list of files in the specified directory to the
        client.
        On success return the directory path, else None.
        """
        path_list = split_path(path)
        try:
            file_info = FTPFileInfo.objects.get(
                **query_based_on_split_path(path_list, include_name_in_query=True)
            )
            if file_info.isdir:
                files_info = FTPFileInfo.objects.filter(
                    **query_based_on_split_path(path_list)
                )
                data_tu_push = ""
                for item in files_info:
                    data_tu_push += format_file_info_line_list(item, self.use_gmt_times)
            else:
                data_tu_push = format_file_info_line_list(file_info, self.use_gmt_times)
        except ObjectDoesNotExist as err:
            why = _strerror(err)  # TODO -> sentry?
            self.respond(f"550 File or directory does not exist")
            return
        data_tu_push = data_tu_push.encode("utf8", "replace")
        self.push_dtp_data(data_tu_push, isproducer=True, cmd="LIST")
        return path

    def ftp_MLSD(self, path):
        """Return contents of a directory in a machine-processable form
        as defined in RFC-3659.
        On success return the path just listed, else None.
        """
        # RFC-3659 requires 501 response code if path is not a directory
        try:
            path_list = split_path(path)
            FTPFileInfo.objects.get(
                **query_based_on_split_path(path_list, include_name_in_query=True),
                is_dir=True,
            )
        except ObjectDoesNotExist:
            self.respond("501 No such directory.")
            return
        try:
            files_info = FTPFileInfo.objects.filter(
                **query_based_on_split_path(path_list)
            )
            data_tu_push = ""
            for item in files_info:
                data_tu_push += format_file_info_line_mlsd(item, self.use_gmt_times)
        except ObjectDoesNotExist as err:
            why = _strerror(err)  # TODO -> sentry?
            data_tu_push = ""
        data_tu_push = data_tu_push.encode("utf8", "replace")
        self.push_dtp_data(data_tu_push, isproducer=True, cmd="MLSD")
        return path

    def ftp_STOR(self, file, mode="w"):
        # Add information about the file to the cache before downloading the file -
        # protection against sending two same files at the same time.
        file_path_split = split_path(file)
        # It is possible to send file to a non-existing directory
        # for example STOR ~/non_existing_directory/testfile
        # so we have to create this structure in the cache
        parent = create_cached_structure(file_path_split[:-1])
        file_info, _ = FTPFileInfo.objects.get_or_create(
            parent=parent,
            name=file_path_split[-1],
            is_dir=file_path_split[-1].endswith("/"),
            defaults={
                "size": 0,
                "mtime": int(time.time()),
                "permission": "elradfmw",
                "links_number": 1,
            },
        )
        try:
            return super(CachedFTPHandler, self).ftp_STOR(file, mode)
        except:
            file_info.delete()

    def ftp_RNFR(self, path):
        """Rename the specified (only the source name is specified
        here, see RNTO command)"""
        if not (self.fs.isdir(path) or self.fs.lexists(path)):
            self.respond("550 No such file or directory.")
        elif self.fs.realpath(path) == self.fs.realpath(self.fs.root):
            self.respond("550 Can't rename home directory.")
        else:
            self._rnfr = path
            self.respond("350 Ready for destination name.")

    def on_file_received(self, file):
        path_list = split_path(file)
        with transaction.atomic():
            files_info = FTPFileInfo.objects.select_for_update().get(
                **query_based_on_split_path(path_list, include_name_in_query=True)
            )
            files_info.size = self.fs.getsize(file)
            files_info.mtime = int(time.time())
            files_info.save()
            parent = files_info.parent
            parent.links_number += 1
            parent.mtime = int(time.time())
            parent.save()

    def on_incomplete_file_received(self, file):
        remove_files_info_from_cache(file)
