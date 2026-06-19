package com.jfmultichat.ui;

import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.Label;
import javafx.scene.effect.DropShadow;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.stage.Stage;
import javafx.stage.StageStyle;

/**
 * 示例窗口 — 用于验证侧栏窗口切换功能.
 * 点击侧栏 📄 按钮时弹出或聚焦此窗口.
 */
public class SampleWindow {

    private static final double WIDTH  = 400;
    private static final double HEIGHT = 300;

    private final Stage stage;
    private boolean showing = false;

    public SampleWindow() {
        this.stage = new Stage();
        buildUI();
    }

    private void buildUI() {
        stage.initStyle(StageStyle.TRANSPARENT);

        VBox root = new VBox();
        root.setAlignment(Pos.CENTER);
        root.setSpacing(12);
        root.setStyle(
            "-fx-background-color: #1e1e1e;" +
            "-fx-background-radius: 12px;" +
            "-fx-border-radius: 12px;" +
            "-fx-border-color: rgba(255,255,255,0.08);" +
            "-fx-border-width: 1px;"
        );

        Label icon = new Label("📄");
        icon.setStyle("-fx-font-size: 48px;");

        Label title = new Label("示例窗口");
        title.setStyle("-fx-text-fill: #d4d4d4; -fx-font-size: 18px; -fx-font-family: 'Microsoft YaHei';");

        Label hint = new Label("点击侧栏「🏠」可聚焦主窗口");
        hint.setStyle("-fx-text-fill: #6c6c6c; -fx-font-size: 13px; -fx-font-family: 'Microsoft YaHei';");

        root.getChildren().addAll(icon, title, hint);

        Scene scene = new Scene(root, WIDTH, HEIGHT);
        scene.setFill(Color.TRANSPARENT);

        DropShadow shadow = new DropShadow();
        shadow.setColor(Color.rgb(0, 0, 0, 0.5));
        shadow.setRadius(20);
        root.setEffect(shadow);

        stage.setScene(scene);
        stage.setTitle("示例窗口");

        stage.setOnHidden(e -> showing = false);
    }

    public void show() {
        showing = true;
        stage.setX(300);
        stage.setY(150);
        stage.show();
    }

    public void close() {
        stage.close();
        showing = false;
    }

    public boolean isShowing() {
        return showing && stage.isShowing();
    }

    public Stage getStage() {
        return stage;
    }
}
