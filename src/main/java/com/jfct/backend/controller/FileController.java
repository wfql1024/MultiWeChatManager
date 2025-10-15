package com.jfct.backend.controller;

import com.jfct.backend.util.Shell32Flags;
import com.sun.jna.platform.win32.*;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.File;
import java.util.Random;

import com.sun.jna.platform.win32.WinNT.HRESULT;
import com.sun.jna.ptr.PointerByReference;



@RestController
public class FileController {

    @GetMapping("/create-random-folder")
    public String createRandomFolder() {
        try {
            // 初始化 COM
            Ole32.INSTANCE.CoInitializeEx(null, Ole32.COINIT_MULTITHREADED);

            // 获取桌面路径
            PointerByReference ppszPath = new PointerByReference();
            HRESULT hr = Shell32.INSTANCE.SHGetKnownFolderPath(
                    KnownFolders.FOLDERID_Desktop,
                    Shell32Flags.KF_FLAG_DEFAULT,
                    null,
                    ppszPath
            );


            if (!hr.equals(W32Errors.S_OK)) {
                return "获取桌面路径失败: " + hr.intValue();
            }

            String desktopPath = ppszPath.getValue().getWideString(0);

            // 创建随机文件夹
            String folderName = "folder_" + new Random().nextInt(10000);
            File folder = new File(desktopPath, folderName);

            if (!folder.exists()) {
                folder.mkdirs();
            }

            return "Created folder: " + folder.getAbsolutePath();

        } catch (Exception e) {
            return "错误: " + e.getMessage();
        } finally {
            Ole32.INSTANCE.CoUninitialize();
        }
    }
}
