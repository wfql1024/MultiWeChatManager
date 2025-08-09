
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