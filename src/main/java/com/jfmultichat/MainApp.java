package com.jfmultichat;

import com.jfmultichat.bridge.JsBridge;
import com.jfmultichat.ui.FloatingSidebar;
import com.jfmultichat.ui.MainWindow;
import com.jfmultichat.ui.SampleWindow;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.image.Image;
import javafx.stage.Stage;

import java.io.InputStream;

/**
 * 应用主入口 — 管理主窗口、侧栏、示例窗口的生命周期.
 */
public class MainApp extends Application {

    private MainWindow mainWindow;
    private FloatingSidebar sidebar;
    private SampleWindow sampleWindow;

    @Override
    public void start(Stage primaryStage) {
        loadAppIcon(primaryStage);

        JsBridge bridge = new JsBridge();
        mainWindow = new MainWindow(this, bridge);

        // 只显示主窗口，侧栏和示例窗口由按钮触发
        mainWindow.show();
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
            if (sidebar == null || !sidebar.isShowing()) {
                if (sidebar == null) {
                    sidebar = new FloatingSidebar(this);
                    sidebar.bindToMainWindow(mainWindow);
                }
                sidebar.show();
            } else {
                sidebar.hide();
            }
        });
    }

    /** 打开（或聚焦）示例窗口 */
    public void focusSampleWindow() {
        Platform.runLater(() -> {
            if (sampleWindow == null || !sampleWindow.isShowing()) {
                sampleWindow = new SampleWindow();
                sampleWindow.show();
            } else {
                sampleWindow.getStage().toFront();
            }
        });
    }

    /** 退出应用 */
    public void exit() {
        if (sampleWindow != null) sampleWindow.close();
        if (sidebar != null) sidebar.close();
        Platform.exit();
    }

    @Override
    public void stop() {
        exit();
    }
}
