package com.jfmultichat;

import com.jfmultichat.config.AppEnv;
import com.jfmultichat.config.AppPaths;
import com.jfmultichat.config.ConfigManager;
import javafx.application.Application;

/**
 * 应用入口 — 规避 JavaFX 模块启动限制.
 * <p>
 * 在启动 JavaFX 之前：
 * <ol>
 *   <li>设置 logback 日志目录系统属性（供 logback.xml 读取）</li>
 *   <li>初始化 ConfigManager（创建目录结构和默认配置文件）</li>
 *   <li>更新 logback 日志目录到实际 user_data_path</li>
 * </ol>
 */
public class Launcher {

    public static void main(String[] args) {
        // --dev → 设置系统属性 run.mode=DEV（AppEnv 自动读取）
        for (String arg : args) {
            if ("--dev".equals(arg)) {
                System.setProperty("run.mode", "DEV");
                break;
            }
        }

        // 1. 预设置日志目录（Logback 配置之前）
        String defaultLogDir = AppPaths.getLogsDir().toString();
        System.setProperty("jfmultichat.logdir", defaultLogDir);

        // 2. 初始化 ConfigManager（创建目录 + 默认配置文件）
        ConfigManager.init(AppEnv.isDev());

        // 3. 更新日志目录到实际 user_data_path
        String actualLogDir = ConfigManager.getInstance().getLogsDir().toString();
        System.setProperty("jfmultichat.logdir", actualLogDir);

        // 4. 启动 JavaFX
        Application.launch(MainApp.class, args);
    }
}
