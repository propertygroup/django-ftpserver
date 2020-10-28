import logging
import time

from botocore.exceptions import ClientError
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import FileSystemStorage, Storage
from storages.backends.s3boto3 import S3Boto3Storage

from django_ftpserver import utils
from django_ftpserver.exceptions import CachedStorageExceptions
from django_ftpserver.helpers import (
    create_cached_structure,
    exists,
    is_dir,
    query_based_on_split_path,
    remove_files_info_from_cache,
    split_path,
)
from django_ftpserver.models import FTPFileInfo
from tests.django_project.project import settings

logger = logging.getLogger(__name__)


class CustomFileSystemStorage(FileSystemStorage):
    def move(self, src, dst):
        raise NotImplementedError


class CustomS3Boto3Storage(S3Boto3Storage):
    def move(self, src, dst):
        for obj in self.bucket.objects.filter(Prefix=src):
            copy_source = {"Bucket": self.bucket.name, "Key": obj.key}
            new_pre = f"{dst[1:]}{obj.key[len(src):]}"
            self.bucket.Object(new_pre).copy(copy_source)
            self.delete(obj.key)


class CachedStorage(Storage):
    storage_class = None
    patches = {
        "FileSystemStorage": CustomFileSystemStorage,
        "S3Boto3Storage": CustomS3Boto3Storage,
    }

    def __init__(self):
        self.storage = self.patches.get(
            utils.get_settings_value("FTPSERVER_FILE_STORAGE"), CustomS3Boto3Storage
        )()

    def delete(self, name):
        self.storage.delete(name)
        remove_files_info_from_cache(name)

    def exists(self, name):
        return exists(name)

    def get_modified_time(self, name):
        sp = split_path(path=name)

        file_info = FTPFileInfo.objects.get(
            **query_based_on_split_path(sp, include_name_in_query=True)
        )
        return file_info.mtime

    def isdir(self, path):
        return is_dir(path)

    def isfile(self, path):
        return not is_dir(path)

    def listdir(self, path):
        path_list = split_path(path)
        try:
            files_info = FTPFileInfo.objects.filter(
                **query_based_on_split_path(path_list, include_name_in_query=False)
            ).order_by("name")
            files_list = list()
            directory_list = list()
            for item in files_info:
                if item.is_dir:
                    directory_list.append(f"{item.name}/")
                else:
                    files_list.append(item.name)
            return directory_list, files_list
        except ObjectDoesNotExist:
            raise CachedStorageExceptions

    def mkdir(self, path):
        path_list = split_path(path)
        create_cached_structure(path_list)

    def rename(self, src, dst):
        # Only used in the StoragePatch based on Object Storages -> S3/Minio/GCloud classes,
        # because directory is not object/blob ...
        src_split_path = split_path(src)
        dst_split_path = split_path(dst)
        if self.isfile(src):
            try:
                self.storage.move(src, dst)
            except ClientError as exc:
                logger.error(f"Rename file ERROR - {exc}")
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
                parent = create_cached_structure(dst_split_path[:-1])
                file_info.parent = parent
                file_info.name = dst_split_path[-1]
                file_info.save()
        else:
            # Because directory is not object/blob... in ObjectStorages if we want to move a directory containing files,
            # we must move each file in this directory separately
            try:
                self.storage.move(src, dst)
                parent = create_cached_structure(dst_split_path[:-1])
                FTPFileInfo.objects.filter(
                    **query_based_on_split_path(
                        src_split_path, include_name_in_query=True
                    )
                ).update(parent=parent)
            except (ClientError, ObjectDoesNotExist) as exc:
                logger.error(f"Rename directory ERROR - {exc}")

    def rmdir(self, path):
        directory = FTPFileInfo.objects.get(
            **query_based_on_split_path(split_path(path), include_name_in_query=True),
            is_dir=True,
        )
        try:
            for files in directory.children.all():
                self.storage.delete(f"{path}/{files.name}")
            directory.delete()
        except (ClientError, ObjectDoesNotExist) as exc:
            logger.error(f"Remove directory ERROR - {exc}")

    def size(self, name):
        sp = split_path(path=name)
        try:
            file_info = FTPFileInfo.objects.get(
                **query_based_on_split_path(sp, include_name_in_query=True)
            )
            if not file_info.size:
                try:
                    file_info.size = self.storage.size(name)
                    file_info.save()
                except ClientError as exc:
                    logger.error(f"Get file/directory {name} size ERROR - {exc}")
            return file_info.size
        except ObjectDoesNotExist:
            raise CachedStorageExceptions

    def _open(self, name, mode="rb"):
        if mode.startswith("wb"):
            file_path_split = split_path(name)
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
            return self.storage._open(name, mode)
        except Exception as exc:
            logger.error(f"Open file ERROR - {exc}")
            if mode.startswith("wb"):
                file_info.delete()
            return None

    def _save(self, name, content):
        self.storage._save(name, content)
