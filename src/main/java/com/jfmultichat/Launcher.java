package com.jfmultichat;

import com.jfmultichat.appcore.AppCore;
import com.jfmultichat.boot.AdminBoot;
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
 *   <li>应用代理设置（应用内设置优先，否则跟随 Windows 系统代理）</li>
 * </ol>
 */
public class Launcher {

    public static void main(String[] args) {
        // -1. **把 JUL（java.util.logging）桥接到 SLF4J/logback**（用户 2026-10-11）
        //     为什么：JavaFX 等 JDK 内部用的是 JUL ✗，它走自己的 SimpleFormatter + **系统默认编码**（中文 Windows = GBK）
        //     → 控制台头几行固定乱码（实测："10?? 11, 2026 11:28:16 ???? com.sun.javafx.application.PlatformImpl startup"）。
        //     装上桥之后：JUL 的日志统一进 logback → 与其它日志**同格式、同编码（UTF-8）**。
        //     必须在任何 JUL 输出之前执行，所以放在这里（连日志目录都还没解析就先装桥）。
        try {
            org.slf4j.bridge.SLF4JBridgeHandler.removeHandlersForRootLogger();
            org.slf4j.bridge.SLF4JBridgeHandler.install();
        } catch (Throwable t) {
            // 桥装不上也不能影响启动（最坏就是回到"JUL 自己打、可能乱码"）
            System.err.println("[Launcher] 安装 JUL→SLF4J 桥失败: " + t.getMessage());
        }

        // --dev → 设置系统属性 run.mode=DEV（AppEnv 自动读取）
        // ⚠️ 必须在解析日志目录**之前**处理：RootConfig 的 Dev/Prod 是两个文件，
        //    dev 标志决定了读哪个（进而决定 user_data_path → 日志目录）。
        for (String arg : args) {
            if ("--dev".equals(arg)) {
                System.setProperty("run.mode", "DEV");
                break;
            }
        }

        // -0.5 打包版默认以管理员身份运行（用户 2026-10-24）：普通令牌下本机安全软件会
        //      拦 java.exe 写用户目录（%APPDATA%/桌面/文档全 AccessDenied），提权后正常；
        //      开发模式（--dev / 非 jar）不提权，避免打断 gradle run。
        if (AdminBoot.ensureElevated(args)) {
            return;   // 已发起提权重启，本进程退出
        }

        // 0. 预设置日志目录 — 必须在任何 LoggerFactory.getLogger() 之前，
        //    否则 Logback 会解析出 ${jfmultichat.logdir}_IS_UNDEFINED 目录。
        //    用 resolveLogsDirEarly()：它会把 RootConfig.user_data_path 考虑进来 ——
        //    用户把数据目录设到项目里时，日志**跟随**过去（用户 2026-10-11），
        //    读不出来则回落 APPDATA（永远有兜底）。
        System.setProperty("jfmultichat.logdir", AppPaths.resolveLogsDirEarly().toString());

        // 1. 初始化 ConfigManager（创建目录 + 默认配置文件）
        ConfigManager.init(AppEnv.isDev());

        // 2. 更新日志目录到实际 user_data_path（可能为自定义数据目录）
        System.setProperty("jfmultichat.logdir",
                ConfigManager.getInstance().getLogsDir().toString());

        // 3. 应用代理设置 — 必须在任何 HTTP 请求之前
        //    应用未启用代理时自动跟随 Windows 系统代理，避免直连境外站点握手被 RST
        AppCore.applyProxySetting();

        // 4. 启动 JavaFX
        Application.launch(MainApp.class, args);
    }
}
