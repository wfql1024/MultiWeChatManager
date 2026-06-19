package com.jfmultichat.bridge;

import java.awt.Desktop;
import java.net.URI;
import java.util.function.Consumer;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * JS ↔ Java 桥接 — 暴露给 JavaScript 的 Java 方法.
 */
public class JsBridge {

    private static final Logger LOG = Logger.getLogger(JsBridge.class.getName());

    private Consumer<String> scriptExecutor;
    private Consumer<String> themeChangeListener;

    public void setScriptExecutor(Consumer<String> executor) {
        this.scriptExecutor = executor;
    }

    /** 注册主题变更监听器（由 MainWindow 调用） */
    public void setThemeChangeListener(Consumer<String> listener) {
        this.themeChangeListener = listener;
    }

    /** 执行 JS 脚本 */
    public void exec(String script) {
        if (scriptExecutor != null) {
            scriptExecutor.accept(script);
        }
    }

    // ========== 暴露给 JS 的方法 ==========

    /** JS 调用：切换主题 */
    public void setTheme(String theme) {
        LOG.info("Theme changed to: " + theme);
        if (themeChangeListener != null) {
            themeChangeListener.accept(theme);
        }
    }

    /** JS 调用：报告侧栏图标中心 X 坐标，Java 据此对齐标题栏 logo */
    public void reportSidebarIconCenter(double x) {
        LOG.info("Sidebar icon center reported: " + x);
        if (themeChangeListener instanceof Consumer) {
            // 复用 listener 通道传递对齐信息
        }
        // 直接调用 MainWindow 的对齐方法
        if (alignListener != null) alignListener.accept(x);
    }

    private java.util.function.DoubleConsumer alignListener;
    public void setAlignListener(java.util.function.DoubleConsumer listener) {
        this.alignListener = listener;
    }

    /** JS 调用：用默认浏览器打开 URL */
    public void openExternal(String url) {
        try {
            Desktop.getDesktop().browse(new URI(url));
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to open URL: " + url, e);
        }
    }

    /** ping */
    public String ping() {
        return "pong";
    }
}
