"""
本文件的使用方法：
将v3中符合以下格式的字典数据，拷贝到input.json中，然后运行本文件，即可生成v4格式的json数据，拷贝回v4即可
格式：
{版本号: {"STABLE": {"alias": "xxx", "changes": "xxx", "pattern": "xxx"}, "PATCH": {"alias": "xxx", "changes": "xxx", "pattern": "xxx"}},...}
"""

import json
from collections import OrderedDict


def convert_format(data):
    """
    批量转换多个版本的数据格式
    输入格式: {版本号: {"STABLE": {...}, "PATCH": {...}}, ...}
    输出格式: {版本号: [转换后的数据], ...}
    """
    converted_data = {}

    for version, version_data in data.items():
        new_data = []

        # 分割 changes 和 pattern
        stable_changes = version_data["STABLE"]["changes"].split(",")
        stable_patterns = version_data["STABLE"]["pattern"].split(",")
        patch_changes = version_data["PATCH"]["changes"].split(",")
        patch_patterns = version_data["PATCH"]["pattern"].split(",")

        # 确保所有分割后的列表长度相同
        if not (len(stable_changes) == len(stable_patterns) == len(patch_changes) == len(patch_patterns)):
            raise ValueError(f"版本 {version} 的 changes 和 pattern 数量不匹配")

        # 为每个分割后的项创建新字典
        for i in range(len(stable_changes)):
            new_item = {
                "STABLE": {
                    "alias": version_data["STABLE"]["alias"],
                    "changes": stable_changes[i].strip(),
                    "pattern": stable_patterns[i].strip()
                },
                "PATCH": {
                    "alias": version_data["PATCH"]["alias"],
                    "changes": patch_changes[i].strip(),
                    "pattern": patch_patterns[i].strip()
                }
            }
            new_data.append(new_item)

        converted_data[version] = new_data

    return converted_data


def version_key(version_str):
    """将版本字符串转换为可排序的元组"""
    return tuple(map(int, version_str.split('.')))


def convert_format2(data):
    # 提取所有版本号并按数字顺序排序（从新到旧）
    versions = sorted(data.keys(), key=version_key, reverse=True)

    converted_data = OrderedDict()

    # 处理每个版本
    for i, current_ver in enumerate(versions):
        converted_items = []
        pre_ver = versions[i + 1] if i + 1 < len(versions) else None

        for item in data[current_ver]:
            # 提取原版和补丁信息
            stable = item["STABLE"]
            patch = item["PATCH"]

            # 构建新格式
            new_item = {
                "pre_ver": pre_ver,
                "original": [stable["pattern"]],
                "modified": [patch["pattern"]],
                "ver_diff": [stable["changes"]],
                "mod_diff": [patch["changes"]],
                "note": f"{stable['alias']}，{patch['alias']}"
            }
            converted_items.append(new_item)

        converted_data[current_ver] = converted_items

    return converted_data


# 主程序
if __name__ == "__main__":
    # 输入文件和输出文件路径
    input_file = "input.json"
    output_file1 = "output1.json"
    output_file2 = "output2.json"

    # 读取输入文件
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 转换格式
    converted_data = convert_format(data)
    # 写入输出文件
    with open(output_file1, "w", encoding="utf-8") as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=4)
    print(f"转换成功！结果已保存到 {output_file1}")

    # 相同方式将output1.json转换为output2.json
    with open(output_file1, "r", encoding="utf-8") as f:
        data = json.load(f)
    converted_data = convert_format2(data)
    # 写入输出文件
    with open(output_file2, "w", encoding="utf-8") as f:
        json.dump(converted_data, f, ensure_ascii=False, indent=4)
    print(f"转换成功！结果已保存到 {output_file2}")