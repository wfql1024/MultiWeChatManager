package com.jfmultichat;

import com.jfmultichat.bridge.JsBridge;
import com.jfmultichat.config.ConfigManager;
import com.jfmultichat.ui.FloatingSidebar;
import com.jfmultichat.ui.MainWindow;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.image.Image;
import javafx.stage.Stage;

import java.io.InputStream;

/**
 * 应用主入口 — 管理主窗口与**浮动侧栏**（窗口切换器）的生命周期.
 *
 * <p>2026-10-13：示例窗口按用户要求**删除**（侧栏改成"主窗口 + 已绑定窗口"的真实切换器 ✓）。
 */
public class MainApp extends Application {

    private MainWindow mainWindow;
    private FloatingSidebar sidebar;

    @Override
    public void start(Stage primaryStage) {
        // 确保 ConfigManager 已初始化（由 Launcher 初始化，此处二次确认）
        ConfigManager.getInstance();

        loadAppIcon(primaryStage);

        JsBridge bridge = new JsBridge();
        // 注册事件订阅者（平台进入维护 / 账号数据定向推送）
        PlatformEventBootstrap.install(bridge);
        mainWindow = new MainWindow(this, bridge);

        // 只显示主窗口，侧栏由标题栏按钮触发
        mainWindow.show();

        // **启动全局扫描（一次性）**：当前平台照旧优先加载 ✓，其它平台的 pid/hwnd 由后台线程补齐到内存 ✓
        //  → 用户点侧栏时即可直接看到所有已在线账号 ✓（走任务中心 ✓ 运行中在任务中心可见 ✓）
        com.jfmultichat.acccore.StartupAccountScan.submit();

        // **用户 2026-10-18 第 4 条（a）**：注入"确保侧栏可见"回调 ✓
        //   —— 刚开软件时侧栏对象**还没创建** ✗，而设置页一打开就要求显示侧栏 ✓
        //   → 这里在**启动时**就装好 ✓，由它负责"没建就建、建了就显示" ✓
        FloatingSidebar.ensureShown = () -> Platform.runLater(this::ensureSidebarVisible);
    }

    /** 确保侧栏存在且可见 ✓（设置页"侧栏"一打开就会调 ✓ 见 `FloatingSidebar.setDemoMode`） */
    private void ensureSidebarVisible() {
        if (sidebar == null) {
            sidebar = new FloatingSidebar(this);
            sidebar.bindToMainWindow(mainWindow);
            sidebar.startFollowing();
        }
        if (!sidebar.isShowing()) {
            sidebar.show();
        }
    }

    private void loadAppIcon(Stage stage) {
        try {
            InputStream is = getClass().getResourceAsStream("/icons/logo.png");
            if (is == null) {
                java.io.File f = new java.io.File("logo.png");
                if (f.exists()) {
                    stage.getIcons().add(new Image(f.toURI().toString()));
                }
            } else {
                stage.getIcons().add(new Image(is));
            }
        } catch (Exception e) {
            System.err.println("Failed to load app icon: " + e.getMessage());
        }
    }

    /** 将主窗口移至最前 */
    public void focusMainWindow() {
        Platform.runLater(() -> {
            Stage stage = mainWindow.getStage();
            if (stage.isIconified()) stage.setIconified(false);
            stage.toFront();
        });
    }

    /** 切换侧栏可见性 */
    public void toggleSidebar() {
        Platform.runLater(() -> {
            // **用户 2026-10-19 原则②**：只有"侧栏设置页"会**强制显示** ✓ —— 其他页面可自由隐藏 ✓
            //   所以这里**不碰** `demoMode` ✗（上一版在这里清掉它 ✗ → 于是"设置页里也能隐藏" ✗）
            //   `demoMode` 的生命周期交给前端 ✓（进"侧栏"页 = true ✓ 离开那一页/离开设置 = false ✓）
            if (sidebar == null || !sidebar.isShowing()) {
                if (sidebar == null) {
                    sidebar = new FloatingSidebar(this);
                    sidebar.bindToMainWindow(mainWindow);
                    // 开始跟随（WinEvent 钩子线程 + 每帧消费）
                    //  —— 隐藏时**不**停钩子（再显示要立刻跟上，装卸钩子反而更贵）；退出时才停（见 exit）
                    sidebar.startFollowing();
                    // **用户 2026-10-18 第 4 条（a）**：注入"确保可见"回调 ✓
                    //   （刚开软件时侧栏对象还不存在 ✓ 设置页要求显示时由这里创建 ✓）
                    FloatingSidebar.ensureShown = () -> {
                        if (sidebar != null && !sidebar.isShowing()) sidebar.show();
                    };
                }
                sidebar.show();
            } else {
                sidebar.hide();
            }
        });
    }

    /** 取侧栏（设置页改"贴边/对齐/长度模式"时用；没有就返回 null） */
    public FloatingSidebar getSidebar() {
        return sidebar;
    }

    /**
     * 主题变化时通知**侧栏**（用户 2026-10-13：侧栏颜色写死了 ✗ 不跟主题变）.
     * <p>侧栏是原生 JavaFX 窗口，拿不到网页的 CSS 变量 → 走项目既有套路：
     * 深/浅两份样式表互斥切换（与标题栏 {@code applyTitleBarTheme} 同一思路 ✓）。
     */
    public void onThemeChanged(String theme) {
        FloatingSidebar.applyThemeFromBridge(theme);
    }

    /** 退出应用 — 保存所有配置后退出 */
    public void exit() {
        try {
            ConfigManager.getInstance().saveAll();
        } catch (Exception e) {
            System.err.println("Failed to save config on exit: " + e.getMessage());
        }
        if (sidebar != null) sidebar.close();
        Platform.exit();
    }

    @Override
    public void stop() {
        exit();
    }
}
