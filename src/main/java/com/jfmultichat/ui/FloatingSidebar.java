package com.jfmultichat.ui;

import com.jfmultichat.MainApp;
import javafx.beans.value.ChangeListener;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.effect.DropShadow;
import javafx.scene.input.MouseEvent;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.stage.Stage;
import javafx.stage.StageStyle;

import java.util.Objects;

/**
 * 浮动侧栏 — 2 个按钮：聚焦主窗口 / 弹出示例窗口.
 * 支持独立拖拽，可跟随主窗口移动.
 */
public class FloatingSidebar {

    private static final double WIDTH  = 56;
    private static final double HEIGHT = 140;

    private final MainApp app;
    private final Stage stage;

    // 拖拽偏移量
    private double dragOffsetX;
    private double dragOffsetY;

    public FloatingSidebar(MainApp app) {
        this.app = app;
        this.stage = new Stage();
        buildUI();
    }

    private void buildUI() {
        stage.initStyle(StageStyle.TRANSPARENT);
        stage.setAlwaysOnTop(true);

        // ---- 按钮 ----
        Button btnMain = makeSideBtn("🏠");
        btnMain.setOnAction(e -> app.focusMainWindow());

        Button btnSample = makeSideBtn("📄");
        btnSample.setOnAction(e -> app.focusSampleWindow());

        // ---- 布局 ----
        VBox root = new VBox(btnMain, btnSample);
        root.getStyleClass().add("sidebar");
        root.setAlignment(Pos.TOP_CENTER);

        // ---- 场景 ----
        Scene scene = new Scene(root, WIDTH, HEIGHT);
        scene.setFill(Color.TRANSPARENT);
        scene.getStylesheets().add(
                Objects.requireNonNull(getClass().getResource("/css/sidebar.css")).toExternalForm()
        );

        // ---- 阴影 ----
        DropShadow shadow = new DropShadow();
        shadow.setColor(Color.rgb(0, 0, 0, 0.4));
        shadow.setRadius(16);
        shadow.setOffsetX(2);
        root.setEffect(shadow);

        stage.setScene(scene);

        // ---- 拖拽 ----
        root.setOnMousePressed(this::onDragPressed);
        root.setOnMouseDragged(this::onDragDragged);
    }

    private Button makeSideBtn(String text) {
        Button btn = new Button(text);
        btn.getStyleClass().add("sidebar-btn");
        return btn;
    }

    // ========== 拖拽 ==========

    private void onDragPressed(MouseEvent e) {
        dragOffsetX = e.getSceneX();
        dragOffsetY = e.getSceneY();
    }

    private void onDragDragged(MouseEvent e) {
        stage.setX(e.getScreenX() - dragOffsetX);
        stage.setY(e.getScreenY() - dragOffsetY);
    }

    // ========== 跟随主窗口 ==========

    /**
     * 将侧栏绑定到主窗口的右侧，随主窗口移动.
     */
    public void bindToMainWindow(MainWindow mainWindow) {
        Stage mainStage = mainWindow.getStage();

        // 设置初始位置（主窗口右侧 + 8px 间距）
        stage.setX(mainStage.getX() + mainStage.getWidth() + 8);
        stage.setY(mainStage.getY() + 80);

        // 跟随主窗口移动
        ChangeListener<Number> follower = (obs, old, val) -> {
            stage.setX(mainStage.getX() + mainStage.getWidth() + 8);
            stage.setY(mainStage.getY() + 80);
        };
        mainStage.xProperty().addListener(follower);
        mainStage.yProperty().addListener(follower);
        mainStage.widthProperty().addListener(follower);
        mainStage.heightProperty().addListener(follower);
    }

    // ========== 公开方法 ==========

    public void show() {
        stage.show();
    }

    public void hide() {
        stage.hide();
    }

    public boolean isShowing() {
        return stage.isShowing();
    }

    public void close() {
        stage.close();
    }

    public Stage getStage() {
        return stage;
    }
}
