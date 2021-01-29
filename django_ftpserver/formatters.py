import time

from pyftpdlib.filesystems import _months_map

SIX_MONTHS = 180 * 24 * 60 * 60


def format_mtime_list(st_mtime, use_gmt_times):
    if use_gmt_times:
        time_func = time.gmtime
    else:
        time_func = time.localtime
    mtime = time_func(st_mtime)
    now = time.time()
    # if modification time > 6 months shows "month year"
    # else "month hh:mm";  this matches proftpd format, see:
    # https://github.com/giampaolo/pyftpdlib/issues/187
    if (now - st_mtime) > SIX_MONTHS:
        fmtstr = "%d  %Y"
    else:
        fmtstr = "%d %H:%M"
    try:
        mtimestr = "%s %s" % (_months_map[mtime.tm_mon], time.strftime(fmtstr, mtime))
    except ValueError:
        # It could be raised if last mtime happens to be too
        # old (prior to year 1900) in which case we return
        # the current time as last mtime.
        mtime = time_func()
        mtimestr = "%s %s" % (
            _months_map[mtime.tm_mon],
            time.strftime("%d %H:%M", mtime),
        )

    return mtimestr


def format_time_mlsd(st_time, use_gmt_times):
    if use_gmt_times:
        time_func = time.gmtime
    else:
        time_func = time.localtime
    mtime = time_func(st_time)

    return time.strftime("%Y%m%d%H%M%S", mtime)


def format_time_human_format(st_time, use_gmt_times):
    if use_gmt_times:
        time_func = time.gmtime
    else:
        time_func = time.localtime
    mtime = time_func(st_time)

    return time.strftime("%d-%m-%Y %H:%M:%S", mtime)


def format_file_info_line_list(file_info, use_gmt_times):
    """
    This is how output appears to client:
    -rw-rw-rw-   1 owner   group    7045120 Sep 02  3:47 music.mp3
    """
    return "%s %3s %-8s %-8s %8s %s %s\r\n" % (
        file_info.permission,
        file_info.links_number,
        1000,
        1000,
        file_info.size,
        format_mtime_list(file_info.mtime, use_gmt_times),
        file_info.name,
    )


def format_file_info_line_mlsd(file_info, use_gmt_times):
    """
    This is how output appears to client:
    type=file;size=156;perm=r;modify=20071029155301;unique=8012; music.mp3
    """
    return "type={type};size={size};perm={perm};modify={modify};owner={owner};group={group};unique={unique}; {name}\r\n".format(
        type="dir" if file_info.is_dir else "file",
        size=file_info.size,
        perm=file_info.permission,
        modify=format_time_mlsd(file_info.mtime, use_gmt_times),
        owner=1000,
        group=1000,
        unique="%xg%x" % (0, 0),
        name=file_info.name,
    )
