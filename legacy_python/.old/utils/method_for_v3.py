import mmap

from legacy_python.utils.file_utils import DllUtils


def identify_dll_of_ver_by_dict(data, cur_sw_ver, dll_path):
    ver_adaptation = data.get(cur_sw_ver, None)
    if ver_adaptation is None:
        return None, f"错误：未找到版本{cur_sw_ver}的适配", None, None

    try:
        stable_result = ver_adaptation["STABLE"]["pattern"]
        patch_result = ver_adaptation["PATCH"]["pattern"]
        stable_hex_list = stable_result.split(',')
        patch_hex_list = patch_result.split(',')
    except Exception as e:
        return None, f"错误：未找到版本{cur_sw_ver}的适配: {e}", None, None

    try:
        for stable_hex, patch_hex in zip(stable_hex_list, patch_hex_list):
            has_stable = DllUtils.find_patterns_from_dll_in_hexadecimal(dll_path, stable_hex)
            has_patch = DllUtils.find_patterns_from_dll_in_hexadecimal(dll_path, patch_hex)
            if has_stable and not has_patch:
                return False, "未开启", stable_hex, patch_hex
            elif has_patch and not has_stable:
                return True, "已开启", stable_hex, patch_hex
            elif has_stable and has_patch:
                return None, "错误，非独一无二的特征码", None, None
        return None, "不可用", None, None
    except (PermissionError, FileNotFoundError, KeyError, TimeoutError, RuntimeError, Exception) as e:
        error_msg = {
            PermissionError: "权限不足，无法检查 DLL 文件。",
            FileNotFoundError: "未找到文件，请检查路径。",
            KeyError: "未找到该版本的适配：",
            TimeoutError: "请求超时。",
            RuntimeError: "运行时错误。",
            Exception: "发生错误。"
        }.get(type(e), "发生未知错误。")
        return None, f"错误：{error_msg}{str(e)}", None, None


def edit_patterns_in_dll_in_hexadecimal(dll_path, **hex_patterns_dicts):
    """
    在 DLL 文件中查找指定的十六进制模式，并替换为新的十六进制模式。可以批量处理多处，并返回一个布尔列表，
    :param dll_path: DLL 文件的路径
    :param hex_patterns_dicts: 一个或多个十六进制模式的字典，每个字典包含旧模式和新模式
    :return: 一个布尔列表，每个元素对应一个模式，True 表示替换成功，False 表示未找到对应模式
    """
    # print(hex_patterns_dicts)
    results = []

    with open(dll_path, 'r+b') as f:
        # 使用 mmap 来更高效地操作文件内容
        mmap_file = mmap.mmap(f.fileno(), 0)
        # 遍历所有传入的旧模式和新模式
        for old_pattern, new_pattern in hex_patterns_dicts.items():
            old, new = bytes.fromhex(old_pattern), bytes.fromhex(new_pattern)
            pos = mmap_file.find(old)
            # 查找并替换模式
            if pos != -1:
                mmap_file[pos: pos + len(old)] = new
                print(f"替换完成：{old_pattern} -> {new_pattern}")
                results.append(True)  # 替换成功
            else:
                print(f"未找到对应的HEX模式：{old_pattern}")
                results.append(False)  # 替换失败

        mmap_file.flush()
        mmap_file.close()

    # 如果传入多个模式，返回布尔列表；如果只有一个，返回单一布尔值
    return results if len(results) > 1 else results[0]
