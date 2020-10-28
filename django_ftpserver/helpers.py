import time

from django.core.exceptions import ObjectDoesNotExist

from .models import FTPFileInfo


def query_based_on_split_path(split_path, include_name_in_query=False):
    start = 0 if include_name_in_query else 1
    return {
        f"{'parent__' * i}name": item for i, item in enumerate(split_path[::-1], start)
    }


def split_path(path):
    if path.startswith("/"):
        path = path[1:]
    if path.endswith("/"):
        path = path[:-1]
    return path.split("/")


def create_cached_structure(file_path_split):
    try:
        parent = FTPFileInfo.objects.get(
            **query_based_on_split_path(file_path_split, include_name_in_query=True),
            is_dir=True,
        )
    except ObjectDoesNotExist:
        parent = None
        for name in file_path_split:
            parent, parent_created = FTPFileInfo.objects.get_or_create(
                name=name,
                parent=parent,
                is_dir=True,
                defaults={
                    "size": 0,
                    "mtime": int(time.time()),
                    "permission": "elradfmw",
                    "links_number": 1,
                },
            )
    return parent


def remove_files_info_from_cache(path):
    path_list = split_path(path)
    try:
        file_info = FTPFileInfo.objects.get(
            **query_based_on_split_path(path_list, include_name_in_query=True)
        )
        file_info.delete()
    except ObjectDoesNotExist:
        pass


def remove_empty_ancestors(parent):
    ancestor = parent.parent
    while ancestor:
        files_info = FTPFileInfo.objects.filter(parent=parent).select_related("parent")
        if not files_info.exists():
            parent.delete()
            parent = parent.parent
        else:
            break


def list_dir(path):
    path_list = split_path(path)
    files_info = FTPFileInfo.objects.filter(
        **query_based_on_split_path(path_list, include_name_in_query=False)
    ).order_by("name")
    files_list = list()
    for item in files_info:
        if item.isdir:
            files_list.append(f"{item.name}/")
        else:
            files_list.append(item.name)
    return files_list


def exists(path):
    return FTPFileInfo.objects.filter(
        **query_based_on_split_path(split_path(path), include_name_in_query=True)
    ).exists()


def is_dir(path):
    try:
        return FTPFileInfo.objects.get(
            **query_based_on_split_path(split_path(path), include_name_in_query=True)
        ).is_dir
    except ObjectDoesNotExist:
        return False


def rm_dir(path):
    FTPFileInfo.objects.get(
        **query_based_on_split_path(split_path(path), include_name_in_query=True),
        is_dir=True,
    ).delete()
