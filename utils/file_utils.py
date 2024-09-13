import win32api


def get_file_version(file_path):
    version_info = win32api.GetFileVersionInfo(file_path, '\\')  # type: ignore
    version = (
        f"{win32api.HIWORD(version_info['FileVersionMS'])}."  # type: ignore
        f"{win32api.LOWORD(version_info['FileVersionMS'])}."  # type: ignore
        f"{win32api.HIWORD(version_info['FileVersionLS'])}."  # type: ignore
        f"{win32api.LOWORD(version_info['FileVersionLS'])}"  # type: ignore
    )
    return version
