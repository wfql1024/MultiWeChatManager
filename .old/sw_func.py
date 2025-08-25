
class SwOperator:
    @staticmethod
    def _open_sw_without_freely_multirun(sw, multirun_mode):
        """非全局多开模式下打开微信"""
        start_time = time.time()
        proc = None
        sub_proc = None
        sw_path = SwInfoFunc.try_get_path_of_(sw, LocalCfg.INST_PATH)
        # ————————————————————————————————handle————————————————————————————————
        if multirun_mode == MultirunMode.HANDLE or multirun_mode == MultirunMode.BUILTIN:
            success = SwOperator._kill_mutex_by_inner_mode(sw, multirun_mode)
            # if success:
            #     # 更新 has_mutex 为 False 并保存
            #     print(f"成功关闭：{time.time() - start_time:.4f}秒")
            # else:
            #     print(f"关闭互斥体失败！")
            proc = process_utils.create_process_without_admin(sw_path, None)
        # # ————————————————————————————————WeChatMultiple_Anhkgg.exe————————————————————————————————
        # elif multirun_mode == "WeChatMultiple_Anhkgg.exe":
        #     sub_proc = process_utils.create_process_without_admin(
        #         f"{Config.PROJ_EXTERNAL_RES_PATH}/{multirun_mode}",
        #         creation_flags=subprocess.CREATE_NO_WINDOW
        #     )
        # # ————————————————————————————————WeChatMultiple_lyie15.exe————————————————————————————————
        # elif multirun_mode == "WeChatMultiple_lyie15.exe":
        #     sub_proc = process_utils.create_process_without_admin(
        #         f"{Config.PROJ_EXTERNAL_RES_PATH}/{multirun_mode}"
        #     )
        #     sub_exe_hwnd = hwnd_utils.win32_wait_hwnd_by_class("WTWindow", 8)
        #     print(f"子程序窗口：{sub_exe_hwnd}")
        #     if sub_exe_hwnd:
        #         button_handle = hwnd_utils.get_child_hwnd_list_of_(
        #             sub_exe_hwnd
        #         )[1]
        #         if button_handle:
        #             button_details = hwnd_utils.get_hwnd_details_of_(button_handle)
        #             button_cx = int(button_details["width"] / 2)
        #             button_cy = int(button_details["height"] / 2)
        #             hwnd_utils.do_click_in_wnd(button_handle, button_cx, button_cy)

class SwInfoFunc:
    """
    当前版本，所使用的适配表结构如下：
    平台sw -> 补丁模式mode -> 分支(精确precise,特征feature,说明channel) -> 版本号 -> 频道 -> 路径地址 -> 特征码
    其中,
        precise: 精确版本适配，只适配当前版本. 结构为 版本号 -> 频道 -> 特征码
        feature: 特征码适配，适配当前版本及其兼容版本. 结构为 版本号 -> 频道 -> 特征码
        channel: 频道，区分不同特征/作者的适配. 结构为 频道 -> (标题,说明,作者)
    """

    @classmethod
    def resolve_sw_path(cls, sw, addr: str):
        """解析补丁路径, 路径中可以包含%包裹的引用地址, 如%dll_dir%/WeChatWin.dll"""
        resolved_parts = []
        for part in addr.replace("\\", "/").split("/"):
            if not part:
                continue
            if part.startswith("%") and part.endswith("%") and len(part) > 2:
                var_name = part[1:-1]
                try:
                    if var_name == LocalCfg.INST_DIR:
                        inst_path = cls.try_get_path_of_(sw, LocalCfg.INST_PATH)
                        resolved = os.path.dirname(inst_path).replace("\\", "/")
                    else:
                        resolved = cls.try_get_path_of_(sw, var_name)
                    resolved_parts.append(resolved.strip("/\\"))
                except KeyError:
                    raise ValueError(f"路径变量未定义: %{var_name}%")
            else:
                resolved_parts.append(part)
        return "/".join(resolved_parts)

    @classmethod
    def get_coexist_path_from_address(cls, sw, address, channel, s):
        print(address)
        coexist_patch_wildcard_addr_dict = subfunc_file.get_remote_cfg(
            sw, RemoteCfg.COEXIST, "channel", channel, "patch_wildcard")
        coexist_patch_wildcard_addr = coexist_patch_wildcard_addr_dict.get(address, "")
        print(f"{coexist_patch_wildcard_addr}")
        coexist_patch_wildcard = cls.resolve_sw_path(sw, coexist_patch_wildcard_addr)
        coexist_patch_file = coexist_patch_wildcard.replace("?", s).replace("\\", "/")
        return coexist_patch_file

    @classmethod
    def _identify_multi_state_patching_of_files_in_channel(cls, sw, channel_addresses_dict, channel=None, s=None):
        """对于非二元状态切换的, 只需要检测原始串即可"""
        addr_res_dict = {}
        for addr in channel_addresses_dict.keys():
            # Printer().debug(f"检查文件地址 {addr} 的特征码适配")
            if not isinstance(channel, str) or not isinstance(s, str):
                patch_file = cls.resolve_sw_path(sw, addr)
            else:
                patch_file = cls.get_coexist_path_from_address(sw, addr, channel, s)
            original_list = channel_addresses_dict[addr]["original"]
            modified_list = channel_addresses_dict[addr]["modified"]
            has_original_list = DllUtils.find_hex_patterns_from_file(patch_file, *original_list)
            # 转换为集合检查一致性,集合中只允许有一个元素，True表示list全都是True，False表示list全都是False，其他情况不合法
            # Printer().debug(f"特征码列表:\n{has_original_list}")
            has_original_set = set(has_original_list)
            # 判断匹配状态
            if len(has_original_set) == 1 and True in has_original_set:
                available = True
                message = "包含该模式"
            else:
                available = False
                message = "没有该模式"
            # 将结果存入字典
            addr_res_dict[addr] = (available, message, patch_file, original_list, modified_list)

        return addr_res_dict

    @classmethod
    def _identify_binary_state_patching_of_files_in_channel(cls, sw, channel_addresses_dict, channel=None,
                                                            s=None) -> dict:
        """
        二元状态, 对渠道内的文件分别检测原始串和补丁串来识别状态
        参数: channel_addresses_dict: 渠道-文件适配字典 {addr: {"original": [...], "modified": [...]}}
        返回:
            { addr1: (status, message, patch_file, original_list, modified_list),
                addr2: (status, message, patch_file, original_list, modified_list), ...}
            其中, status: True/False/None; message: 状态描述字符串; patch_file: 补丁文件路径;
                original_list: 原始串列表; modified_list: 补丁串列表
        """
        addr_res_dict = {}
        for addr in channel_addresses_dict.keys():
            # Printer().debug(f"检查文件地址 {addr} 的特征码适配")
            if not isinstance(channel, str) or not isinstance(s, str):
                patch_file = cls.resolve_sw_path(sw, addr)
            else:
                patch_file = cls.get_coexist_path_from_address(sw, addr, channel, s)
            original_list = channel_addresses_dict[addr]["original"]
            modified_list = channel_addresses_dict[addr]["modified"]
            has_original_list = DllUtils.find_hex_patterns_from_file(patch_file, *original_list)
            has_modified_list = DllUtils.find_hex_patterns_from_file(patch_file, *modified_list)
            # 转换为集合检查一致性,集合中只允许有一个元素，True表示list全都是True，False表示list全都是False，其他情况不合法
            has_original_set = set(has_original_list)
            has_modified_set = set(has_modified_list)
            # 初始化默认值
            status = None
            message = "未知状态"
            # 判断匹配状态
            if len(has_original_set) == 1 and len(has_modified_set) == 1:
                all_original = True if True in has_original_set else False if False in has_original_set else None
                all_modified = True if True in has_modified_set else False if False in has_modified_set else None
                if all_original is True and all_modified is False:
                    status = False
                    message = "未开启"
                elif all_original is False and all_modified is True:
                    status = True
                    message = "已开启"
                elif all_original is True or all_modified is True:
                    message = "文件有多处匹配，建议优化补丁替换列表"
            else:
                message = "文件匹配结果不一致"
            # 将结果存入字典
            addr_res_dict[addr] = (status, message, patch_file, original_list, modified_list)

        return addr_res_dict

    @classmethod
    def _identify_patching_of_channels_in_ver(cls, sw, ver_channels_dict, multi_state=False, coexist_channel=None,
                                              s=None) -> dict:
        """
        对版本适配字典中的所有通道进行状态识别
        参数:
            ver_adaptation: 版本适配字典 {channel: {addr: {"original": [...], "modified": [...]}}}
            only_original: 是否为多元状态, 二元状态为False, 多元状态为True; 多元状态只需要检测原始串
        返回:
            { channel1: (status, message, addr_res_dict),
                channel2: (status, message, addr_res_dict), ...}
            status: True/False/None
            message: 状态描述字符串
        """
        results = {}
        status_set = set()
        for channel in ver_channels_dict.keys():
            addr_msg_dict = {}
            channel_files_dict = ver_channels_dict[channel]
            if multi_state:
                addr_res_dict = cls._identify_multi_state_patching_of_files_in_channel(
                    sw, channel_files_dict, coexist_channel, s)
            else:
                addr_res_dict = cls._identify_binary_state_patching_of_files_in_channel(
                    sw, channel_files_dict, coexist_channel, s)
            # 对频道的所有地址状态进行判定,全为True则为True,全为False则为False,其他情况为None
            for addr in addr_res_dict.keys():
                if isinstance(addr_res_dict[addr], tuple) and len(addr_res_dict[addr]) == 5:
                    status, addr_msg, _, _, _ = addr_res_dict[addr]
                    if (multi_state is False and status is None) or (multi_state is True and status is not True):
                        addr_msg_dict[addr] = addr_msg
                else:
                    status = None
                    addr_msg_dict[addr] = "返回格式错误"
                status_set.add(status)
            channel_status = status_set.pop() \
                if len(status_set) == 1 and next(iter(status_set)) in (True, False) else None
            results[channel] = channel_status, f"文件情况:{addr_msg_dict}", addr_res_dict
        return results

    @classmethod
    def _identify_dll_by_precise_channel_in_mode_dict(
            cls, sw, mode_branches_dict, multi_state=False, channel=None, s=None) -> Tuple[Optional[dict], str]:
        """通过精确版本分支进行识别dll状态"""
        cur_sw_ver = cls.calc_sw_ver(sw)
        if cur_sw_ver is None:
            return None, f"错误：未知当前版本"
        if "precise" not in mode_branches_dict:
            return None, f"错误：该模式没有精确版本分支用以适配"
        precise_vers_dict = mode_branches_dict["precise"]
        if cur_sw_ver not in precise_vers_dict:
            return None, f"错误：精确分支中未找到版本{cur_sw_ver}的适配"
        ver_channels_dict = precise_vers_dict[cur_sw_ver]
        channel_res_dict = cls._identify_patching_of_channels_in_ver(sw, ver_channels_dict, multi_state, channel, s)
        if len(channel_res_dict) == 0:
            return None, f"错误：该版本{cur_sw_ver}的适配在本地平台中未找到"
        return channel_res_dict, f"成功：找到版本{cur_sw_ver}的适配"

    @classmethod
    def _update_adaptation_from_remote_to_cache(cls, sw, mode):
        """根据远程表内容更新额外表"""
        config_data = subfunc_file.read_remote_cfg_in_rules()
        if not config_data:
            return
        remote_mode_branches_dict, = subfunc_file.get_remote_cfg(sw, **{mode: None})
        if remote_mode_branches_dict is None:
            return
        # 尝试寻找兼容版本并添加到额外表中
        cur_sw_ver = cls.calc_sw_ver(sw)
        if "precise" in remote_mode_branches_dict:
            precise_vers_dict = remote_mode_branches_dict["precise"]
            if cur_sw_ver in precise_vers_dict:
                # 用精确版本特征码查找适配
                precise_ver_adaptations = precise_vers_dict[cur_sw_ver]
                for channel, adaptation in precise_ver_adaptations.items():
                    subfunc_file.update_extra_cfg(
                        sw, mode, "precise", cur_sw_ver, **{channel: adaptation})
        if "feature" in remote_mode_branches_dict:
            feature_vers = list(remote_mode_branches_dict["feature"].keys())
            compatible_ver = VersionUtils.pkg_find_compatible_version(cur_sw_ver, feature_vers)
            cache_ver_channels_dict = subfunc_file.get_cache_cfg(sw, mode, "precise", cur_sw_ver)
            if compatible_ver:
                # 用兼容版本特征码查找适配
                feature_ver_channels_dict = remote_mode_branches_dict["feature"][compatible_ver]
                for channel in feature_ver_channels_dict.keys():
                    if cache_ver_channels_dict is not None and channel in cache_ver_channels_dict:
                        print("已存在缓存的精确适配")
                        continue
                    channel_res_dict = {}
                    channel_failed = False
                    feature_channel_addr_dict = feature_ver_channels_dict[channel]
                    for addr in feature_channel_addr_dict.keys():
                        addr_feature_dict = feature_channel_addr_dict[addr]
                        # 对原始串和补丁串需要扫描匹配, 其余节点拷贝
                        patch_file = cls.resolve_sw_path(sw, addr)
                        original_feature = addr_feature_dict["original"]
                        modified_feature = addr_feature_dict["modified"]
                        addr_res_dict = SwInfoUtils.search_patterns_and_replaces_by_features(
                            patch_file, (original_feature, modified_feature))
                        if not addr_res_dict:
                            channel_failed = True
                            break
                        channel_res_dict[addr] = addr_res_dict
                        for key in addr_feature_dict:
                            if key not in ["original", "modified"]:
                                channel_res_dict[addr][key] = addr_feature_dict[key]
                    if not channel_failed:
                        # 添加到缓存表中
                        subfunc_file.update_extra_cfg(
                            sw, mode, "precise", cur_sw_ver, **{channel: channel_res_dict})

    @classmethod
    def _identify_dll_by_cache_cfg(cls, sw, mode, multi_state=False, channel=None, s=None) -> Tuple[
        Optional[dict], str]:
        """从缓存表中获取"""
        try:
            mode_branches_dict, = subfunc_file.get_cache_cfg(sw, **{mode: None})
            if mode_branches_dict is None:
                return None, f"错误：平台未适配{mode}"
            return cls._identify_dll_by_precise_channel_in_mode_dict(sw, mode_branches_dict, multi_state, channel, s)
        except Exception as e:
            Logger().error(e)
            return None, f"错误：{e}"

    @classmethod
    def identify_dll(cls, sw, mode, multi_state=False, channel=None, s=None) -> Tuple[Optional[dict], str]:
        """
        检查当前补丁状态，返回结果字典,若没有适配则返回None
        结果字典格式: {channel1: (status, msg, addr_res_dict), channel2: (status, msg, addr_res_dict) ...}
        地址字典addr_res_dict格式: {addr1: (status, msg, patch_path, original, modified),
                                    addr2: (status, msg, patch_path, original, modified) ...}
        """
        dll_dir = cls.try_get_path_of_(sw, LocalCfg.DLL_DIR)
        if dll_dir is None:
            return None, "错误：没有找到dll目录"
        cls._update_adaptation_from_remote_to_cache(sw, mode)
        mode_channel_res_dict, msg = cls._identify_dll_by_cache_cfg(sw, mode, multi_state, channel, s)
        return mode_channel_res_dict, msg

    @classmethod
    def clear_adaptation_cache(cls, sw, mode):
        """清除当前版本模式的适配缓存"""
        curr_ver = cls.calc_sw_ver(sw)
        subfunc_file.clear_some_extra_cfg(sw, mode, "precise", curr_ver)