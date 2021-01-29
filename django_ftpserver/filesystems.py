import logging
import os
from collections import namedtuple

from django.core.files.storage import get_storage_class as _get_storage_class
from pyftpdlib.filesystems import AbstractedFS, FilesystemError

from .exceptions import CachedStorageExceptions
from .helpers import (
    create_cached_structure,
    exists,
    is_dir,
    query_based_on_split_path,
    remove_files_info_from_cache,
    rm_dir,
    split_path,
)
from .models import FTPFileInfo

logger = logging.getLogger(__name__)

PseudoStat = namedtuple(
    "PseudoStat",
    [
        "st_size",
        "st_mtime",
        "st_nlink",
        "st_mode",
        "st_uid",
        "st_gid",
        "st_dev",
        "st_ino",
    ],
)


class StoragePatch:
    """Base class for patches to StorageFS."""

    patch_methods = ()

    @classmethod
    def apply(cls, fs):
        """replace bound methods of fs."""
        logger.debug("Patching %s with %s.", fs.__class__.__name__, cls.__name__)
        fs._patch = cls
        for method_name in cls.patch_methods:
            # if fs hasn't method, raise AttributeError.
            origin = getattr(fs, method_name)
            method = getattr(cls, method_name)
            bound_method = method.__get__(fs, fs.__class__)
            setattr(fs, method_name, bound_method)
            setattr(fs, "_origin_" + method_name, origin)


class FileSystemStoragePatch(StoragePatch):
    """StoragePatch for Django's FileSystemStorage."""

    patch_methods = (
        "mkdir",
        "rmdir",
        "stat",
    )

    def mkdir(self, path):
        os.mkdir(self.storage.path(path))

    def rmdir(self, path):
        os.rmdir(self.storage.path(path))

    def stat(self, path):
        return os.stat(self.storage.path(path))


class S3Boto3StoragePatch(StoragePatch):
    """StoragePatch for S3Boto3Storage(provided by django-storages)."""

    patch_methods = "getmtime"

    def getmtime(self, path):
        if self.isdir(path):
            return 0
        return self._origin_getmtime(path)


class DjangoGCloudStoragePatch(StoragePatch):
    """StoragePatch for DjangoGCloudStorage(provided by django-gcloud-storage)."""

    patch_methods = (
        "getmtime",
        "listdir",
    )

    def _exists(self, path):
        """GCS directory is not blob."""
        if path.endswith("/"):
            return True
        return self.storage.exists(path)

    def isdir(self, path):
        return not self.isfile(path)

    def getmtime(self, path):
        if self.isdir(path):
            return 0
        return self._origin_getmtime(path)


class StorageFS(AbstractedFS):
    """FileSystem for bridge to Django storage."""

    storage_class = None
    patches = {
        "FileSystemStorage": FileSystemStoragePatch,
        "S3Boto3Storage": S3Boto3StoragePatch,
        "DjangoGCloudStorage": DjangoGCloudStoragePatch,
    }

    def apply_patch(self):
        """apply adjustment patch for storage"""
        patch = self.patches.get(self.storage.__class__.__name__)
        if patch:
            patch.apply(self)

    def __init__(self, root, cmd_channel):
        super(StorageFS, self).__init__(root, cmd_channel)
        self.storage = self.get_storage()
        self.apply_patch()

    def get_storage_class(self):
        if self.storage_class is None:
            return _get_storage_class()
        return self.storage_class

    def get_storage(self):
        storage_class = self.get_storage_class()
        return storage_class()

    def open(self, filename, mode):
        path = os.path.join(self._cwd, filename)
        return self.storage.open(path, mode)

    def mkstemp(self, suffix="", prefix="", dir=None, mode="wb"):
        raise NotImplementedError

    def chdir(self, path):
        assert isinstance(path, str), path
        self._cwd = self.fs2ftp(path)

    def mkdir(self, path):
        self.storage.mkdir(path)

    def move(self, src, dst):
        self.storage.move(src, dst)

    def listdir(self, path):
        assert isinstance(path, str), path
        if path == "/":
            path = ""
        try:
            directories, files = self.storage.listdir(path)
            return directories + files
        except CachedStorageExceptions:
            raise FilesystemError

    def rmdir(self, path):
        self.storage.rmdir(path)

    def remove(self, path):
        assert isinstance(path, str), path
        self.storage.delete(path)

    def chmod(self, path, mode):
        raise NotImplementedError

    def stat(self, path):
        if self.isfile(path):
            st_mode = 0o0100770
        else:
            # directory
            st_mode = 0o0040770
        return PseudoStat(
            st_size=self.getsize(path),
            st_mtime=int(self.getmtime(path)),
            st_nlink=1,
            st_mode=st_mode,
            st_uid=1000,
            st_gid=1000,
            st_dev=0,
            st_ino=0,
        )

    lstat = stat

    def _exists(self, path):
        if path == "/":
            return self.storage.exists("")
        return self.storage.exists(path)

    def isfile(self, path):
        return self.storage.isfile(path)

    def islink(self, path):
        return False

    def isdir(self, path):
        return self.storage.isdir(path)

    def getsize(self, path):
        if self.isdir(path):
            return 0
        try:
            return self.storage.size(path)
        except CachedStorageExceptions:
            raise FilesystemError

    def getmtime(self, path):
        return self.storage.get_modified_time(path)

    def realpath(self, path):
        return path

    def lexists(self, path):
        return self._exists(path)

    def get_user_by_uid(self, uid):
        return "owner"

    def get_group_by_gid(self, gid):
        return "group"

    def rename(self, src, dst):
        self.storage.rename(src, dst)


class CachedStorageFS(StorageFS):
    def listdir(self, path):
        assert isinstance(path, str), path
        path_list = split_path(path)
        files_info = FTPFileInfo.objects.filter(
            **query_based_on_split_path(path_list, include_name_in_query=False)
        ).order_by("name")
        files_list = list()
        for item in files_info:
            if item.isdir:
                files_list.append(item.name)
            else:
                files_list.append(item.name)
        return files_list

    def stat(self, path):
        path_list = split_path(path)
        file_info = FTPFileInfo.objects.get(
            **query_based_on_split_path(path_list, include_name_in_query=True)
        )
        return PseudoStat(
            st_size=file_info.size,
            st_mtime=file_info.mtime,
            st_nlink=file_info.links_number,
            st_mode=0o0100770 if self.isfile(path) else 0o0040770,
            st_uid=1000,
            st_gid=1000,
            st_dev=0,
            st_ino=0,
        )

    def _exists(self, path):
        return exists(path)

    def isdir(self, path):
        return is_dir(path)

    def remove(self, path):
        super(CachedStorageFS, self).remove(path)
        remove_files_info_from_cache(path)

    def rmdir(self, path):
        rm_dir(path)

    def _rename(self, src, dst):
        # Only used in the StoragePatch based on Object Storages -> S3/Minio/GCloud classes,
        # because directory is not object/blob ...
        src_split_path = split_path(src)
        if self.isfile(src):
            try:
                self.move(src, dst)
            finally:
                # Find File in models and change has parent
                file_info = FTPFileInfo.objects.get(
                    **query_based_on_split_path(
                        src_split_path, include_name_in_query=True
                    )
                )
                # It is possible to change to a non-existing directory
                # for example/test_directory/testfile /test_directory/non_existing_directory/testfile
                # so we have to create this structure in the cache
                dst_split_path = split_path(dst)
                parent = create_cached_structure(dst_split_path[:-1])
                file_info.parent = parent
                file_info.name = dst_split_path[-1]
                file_info.save()
        else:
            # Because directory is not object/blob... in ObjectStorages if we want to move a directory containing files,
            # we must move each file in this directory separately
            files_info = FTPFileInfo.objects.filter(
                **query_based_on_split_path(src_split_path, include_name_in_query=False)
            ).select_related("parent")
            for item in files_info:
                self._rename(
                    f"{src}{'' if src.endswith('/') else '/'}{item.name}",
                    f"{dst}{'' if dst.endswith('/') else '/'}{item.name}",
                )
            item.parent.delete()

    def mkdir(self, path):
        path_list = split_path(path)
        # It is possible to create new directory in a non-existing directory
        # for example mkdir ~/non_existing_directory/new_directory
        # so we have to create this structure in the cache
        create_cached_structure(path_list)

    def chmod(self, path, mode):
        # Do you need it?
        # Using Files FTP Cache (Cache Storage) method to change permission is not necessary
        pass
