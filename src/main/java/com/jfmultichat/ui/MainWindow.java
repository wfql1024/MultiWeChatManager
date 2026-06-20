package com.jfmultichat.ui;

import com.jfmultichat.MainApp;
import com.jfmultichat.bridge.JsBridge;
import javafx.concurrent.Worker;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.geometry.Rectangle2D;
import javafx.scene.Cursor;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.effect.DropShadow;
import javafx.scene.input.MouseEvent;
import javafx.scene.layout.*;
import javafx.scene.paint.Color;
import javafx.scene.web.WebEngine;
import javafx.scene.web.WebView;
import javafx.stage.Screen;
import javafx.stage.Stage;
import javafx.stage.StageStyle;
import netscape.javascript.JSObject;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Objects;

/**
 * 无标题栏主窗口 — WebView 嵌入 HTML/CSS/JS 界面.
 * 行为与标准 Windows 窗口一致：拖拽、双击最大化、边缘缩放.
 */
public class MainWindow {

    private static final Logger LOG = LoggerFactory.getLogger(MainWindow.class);

    private static final double WIDTH  = 1100;
    private static final double HEIGHT = 700;
    private static final double RESIZE_MARGIN = 8;   // 边缘检测范围
    private static final double DRAG_THRESHOLD = 4;  // 拖拽触发阈值（像素）

    private final MainApp app;
    private final JsBridge bridge;
    private final Stage stage;

    private StackPane root;
    private VBox contentBox;
    private Pane resizePane;
    private Scene scene;
    private DropShadow shadow;
    private javafx.scene.shape.Rectangle clipRect;
    private WebView webView;
    private WebEngine webEngine;
    private String baseUrl;
    private boolean suppressLinkIntercept;
    private javafx.scene.image.ImageView logoView;  // 供动态对齐用

    // 窗口按钮引用（用于更新图标）
    private Button btnMax;

    // 最大化状态
    private boolean maximized = false;
    private double preMaxX, preMaxY, preMaxW, preMaxH;

    // 标题栏拖拽
    private boolean isDragging;  // 是否在标题栏按下启动了拖拽
    private double dragOffsetX, dragOffsetY;
    private boolean maxOnPress;
    private double maxPressRatioX;
    private boolean dragStarted;

    // 边缘缩放
    private enum ResizeEdge { NONE, N, S, E, W, NE, NW, SE, SW }
    private ResizeEdge resizeEdge = ResizeEdge.NONE;
    private double resizeStartX, resizeStartY;
    private double resizeStartW, resizeStartH;
    private double resizeStartStageX, resizeStartStageY;

    // ==================== 构造 & 构建 ====================

    public MainWindow(MainApp app, JsBridge bridge) {
        this.app = app;
        this.bridge = bridge;
        this.stage = new Stage();
        buildUI();
    }

    private void buildUI() {
        stage.initStyle(StageStyle.TRANSPARENT);
        stage.setTitle("极峰多聊");
        stage.setMinWidth(800);
        stage.setMinHeight(500);

        HBox titleBar = buildTitleBar();
        setupWebView();

        // 内容区
        contentBox = new VBox(titleBar, webView);
        VBox.setVgrow(webView, Priority.ALWAYS);

        // 先建 root（resize handles 需要绑定 root 的宽高）
        root = new StackPane();
        root.getStyleClass().add("main-window");
        root.getChildren().add(contentBox);

        // 缩放边缘手柄（绑定 root 尺寸，盖在最上面）
        resizePane = buildResizeHandles();
        root.getChildren().add(resizePane);

        // 圆角裁剪
        clipRect = new javafx.scene.shape.Rectangle();
        clipRect.widthProperty().bind(root.widthProperty());
        clipRect.heightProperty().bind(root.heightProperty());
        clipRect.setArcWidth(24);
        clipRect.setArcHeight(24);
        root.setClip(clipRect);

        scene = new Scene(root, WIDTH, HEIGHT);
        scene.setFill(Color.TRANSPARENT);
        scene.getStylesheets().add(
                Objects.requireNonNull(getClass().getResource("/css/main.css")).toExternalForm()
        );

        shadow = new DropShadow();
        shadow.setColor(Color.rgb(0, 0, 0, 0.5));
        shadow.setRadius(24);
        shadow.setOffsetY(4);
        root.setEffect(shadow);

        // 仅 scene 级拖拽事件（标题栏移动）
        scene.addEventFilter(MouseEvent.MOUSE_PRESSED, this::onScenePressed);
        scene.addEventFilter(MouseEvent.MOUSE_DRAGGED, this::onSceneDragged);
        scene.addEventFilter(MouseEvent.MOUSE_RELEASED, this::onSceneReleased);

        stage.setScene(scene);
    }

    /** 构建缩放边缘手柄：8px 宽的透明 Region 覆盖四边四角 */
    private Pane buildResizeHandles() {
        Pane pane = new Pane();
        pane.setPickOnBounds(false);       // pane 本身不拦截
        pane.setMouseTransparent(false);   // 但子节点可以拦截

        double m = RESIZE_MARGIN;

        // 上边
        Region top = edge(m, 0, 0, 0, Cursor.N_RESIZE);
        top.prefWidthProperty().bind(root.widthProperty().subtract(2 * m));
        top.setLayoutX(m);
        addResizeDrag(top, ResizeEdge.N);

        // 下边
        Region bottom = edge(m, 0, 0, m, Cursor.S_RESIZE);
        bottom.prefWidthProperty().bind(root.widthProperty().subtract(2 * m));
        bottom.layoutXProperty().bind(root.widthProperty().subtract(bottom.prefWidthProperty()).divide(2));
        bottom.layoutYProperty().bind(root.heightProperty().subtract(m));
        addResizeDrag(bottom, ResizeEdge.S);

        // 左边
        Region left = edge(0, m, m, 0, Cursor.W_RESIZE);
        left.prefHeightProperty().bind(root.heightProperty().subtract(2 * m));
        left.setLayoutY(m);
        addResizeDrag(left, ResizeEdge.W);

        // 右边
        Region right = edge(0, m, m, m, Cursor.E_RESIZE);
        right.prefHeightProperty().bind(root.heightProperty().subtract(2 * m));
        right.layoutXProperty().bind(root.widthProperty().subtract(m));
        right.setLayoutY(m);
        addResizeDrag(right, ResizeEdge.E);

        // 四角 (重叠区域，后加的在上层)
        Region nw = corner(m, m, 0, 0, Cursor.NW_RESIZE); addResizeDrag(nw, ResizeEdge.NW);
        Region ne = corner(m, m, 0, m, Cursor.NE_RESIZE);
        ne.layoutXProperty().bind(root.widthProperty().subtract(m));
        addResizeDrag(ne, ResizeEdge.NE);
        Region sw = corner(m, m, m, 0, Cursor.SW_RESIZE);
        sw.layoutYProperty().bind(root.heightProperty().subtract(m));
        addResizeDrag(sw, ResizeEdge.SW);
        Region se = corner(m, m, m, m, Cursor.SE_RESIZE);
        se.layoutXProperty().bind(root.widthProperty().subtract(m));
        se.layoutYProperty().bind(root.heightProperty().subtract(m));
        addResizeDrag(se, ResizeEdge.SE);

        pane.getChildren().addAll(top, bottom, left, right, nw, ne, sw, se);
        return pane;
    }

    private Region edge(double h, double w, double topMargin, double bottomMargin, Cursor cursor) {
        Region r = new Region();
        r.setPrefHeight(h == 0 ? RESIZE_MARGIN : h);
        r.setPrefWidth(w == 0 ? RESIZE_MARGIN : w);
        r.setCursor(cursor);
        r.setStyle("-fx-background-color: transparent;");
        return r;
    }

    private Region corner(double h, double w, double topMargin, double bottomMargin, Cursor cursor) {
        Region r = new Region();
        r.setPrefSize(RESIZE_MARGIN, RESIZE_MARGIN);
        r.setCursor(cursor);
        r.setStyle("-fx-background-color: transparent;");
        return r;
    }

    private void addResizeDrag(Region region, ResizeEdge edge) {
        region.setOnMousePressed(e -> {
            if (maximized) return;
            resizeEdge = edge;
            resizeStartX = e.getScreenX();
            resizeStartY = e.getScreenY();
            resizeStartW = stage.getWidth();
            resizeStartH = stage.getHeight();
            resizeStartStageX = stage.getX();
            resizeStartStageY = stage.getY();
            e.consume();
        });
        region.setOnMouseDragged(e -> {
            if (resizeEdge == ResizeEdge.NONE) return;
            double dx = e.getScreenX() - resizeStartX;
            double dy = e.getScreenY() - resizeStartY;
            applyResize(resizeEdge, dx, dy);
            e.consume();
        });
        region.setOnMouseReleased(e -> {
            resizeEdge = ResizeEdge.NONE;
        });
    }

    // ==================== WebView ====================

    private void setupWebView() {
        webView = new WebView();
        webEngine = webView.getEngine();
        webEngine.setJavaScriptEnabled(true);
        webView.setStyle("-fx-background-color: transparent;");

        // WebView 级鼠标事件 — 确保内容区也能触发缩放
        webView.addEventFilter(MouseEvent.MOUSE_MOVED, this::onMouseMoved);
        webView.addEventFilter(MouseEvent.MOUSE_PRESSED, this::onScenePressed);
        webView.addEventFilter(MouseEvent.MOUSE_DRAGGED, this::onSceneDragged);
        webView.addEventFilter(MouseEvent.MOUSE_RELEASED, this::onSceneReleased);

        webEngine.getLoadWorker().stateProperty().addListener((obs, oldState, newState) -> {
            if (newState == Worker.State.SUCCEEDED) injectJsBridge();
        });

        webEngine.setOnError(event ->
            LOG.warn("WebView error: " + event.getMessage())
        );

        baseUrl = Objects.requireNonNull(
                getClass().getResource("/web/index.html")
        ).toExternalForm();
        webEngine.load(baseUrl);
        LOG.info("Loading: " + baseUrl);

        // 外部链接 → 默认浏览器
        webEngine.locationProperty().addListener((obs, oldLoc, newLoc) -> {
            if (suppressLinkIntercept) return;
            if (newLoc != null && !newLoc.equals(baseUrl) && !newLoc.startsWith("about:")) {
                javafx.application.Platform.runLater(() -> {
                    suppressLinkIntercept = true;
                    try { java.awt.Desktop.getDesktop().browse(new java.net.URI(newLoc)); }
                    catch (Exception ex) { LOG.warn("Failed to open URL: " + newLoc, ex); }
                    webEngine.load(baseUrl);
                });
            }
            // baseUrl 重载后清除抑制标志
            if (newLoc != null && newLoc.equals(baseUrl) && suppressLinkIntercept) {
                suppressLinkIntercept = false;
            }
        });
    }

    private void injectJsBridge() {
        try {
            JSObject window = (JSObject) webEngine.executeScript("window");
            if (window != null) {
                window.setMember("javaObject", bridge);
                bridge.setScriptExecutor(script ->
                    javafx.application.Platform.runLater(() -> {
                        try { webEngine.executeScript(script); }
                        catch (Exception e) { LOG.warn("Failed to exec script: " + script, e); }
                    })
                );
                bridge.setThemeChangeListener(this::applyTitleBarTheme);
                bridge.setAlignListener(this::alignLogo);
                LOG.info("JS Bridge injected successfully");
            }
        } catch (Exception e) {
            LOG.error("Failed to inject JS bridge", e);
        }
    }

    /** JS 报告侧栏图标中心后，动态对齐 logo */
    private void alignLogo(double iconCenterX) {
        if (logoView == null || logoView.getImage() == null) return;
        double logoW = logoView.getImage().getWidth();
        double logoH = logoView.getImage().getHeight();
        double renderedW = logoView.getFitHeight() * logoW / logoH;  // preserveRatio
        // logo 中心 = border(1) + titlePadding(8) + margin + renderedW/2 = iconCenterX
        double margin = iconCenterX - 1.0 - 8.0 - renderedW / 2.0;
        HBox.setMargin(logoView, new Insets(0, 0, 0, Math.max(0, margin)));
        LOG.info("Logo aligned: iconCenter=" + iconCenterX + " margin=" + margin);
    }

    private void applyTitleBarTheme(String theme) {
        String darkCss = getClass().getResource("/css/main.css").toExternalForm();
        String lightCss = getClass().getResource("/css/main-light.css").toExternalForm();
        scene.getStylesheets().remove(darkCss);
        scene.getStylesheets().remove(lightCss);
        if ("light".equals(theme)) {
            scene.getStylesheets().add(lightCss);
        } else {
            scene.getStylesheets().add(darkCss);
        }
    }

    // ==================== 标题栏 ====================

    private HBox buildTitleBar() {
        HBox bar = new HBox();
        bar.getStyleClass().add("title-bar");
        bar.setAlignment(Pos.CENTER_LEFT);

        // 左侧 Logo — 左边距对齐侧栏图标 (21px)
        // 左侧 Logo — JS 会动态测量侧栏图标中心后回调 alignLogo() 对齐
        logoView = new javafx.scene.image.ImageView();
        logoView.setFitHeight(30);
        logoView.setPreserveRatio(true);
        logoView.setSmooth(true);
        logoView.setCache(true);
        // 初始 margin 在 JS 回调 alignLogo() 后动态设置
        HBox.setMargin(logoView, new Insets(0, 0, 0, 8)); // 临时值，会被 JS 回调覆盖
        try {
            java.io.InputStream is = getClass().getResourceAsStream("/icons/logo.png");
            if (is != null) {
                javafx.scene.image.Image img = new javafx.scene.image.Image(is, 0, 30, true, true);
                logoView.setImage(img);
            }
        } catch (Exception e) {
            LOG.warn("Failed to load logo: " + e.getMessage());
        }
        logoView.setOnMouseClicked(e -> app.focusMainWindow());
        logoView.setStyle("-fx-cursor: hand;");

        Region spacer = new Region();
        HBox.setHgrow(spacer, Priority.ALWAYS);

        Button btnSidebar = makeTitleBtn("☰", null);
        btnSidebar.setOnAction(e -> app.toggleSidebar());

        Button btnMin = makeTitleBtn("─", null);
        btnMax = makeTitleBtn("☐", null);
        Button btnClose = makeTitleBtn("✕", "close-btn");

        btnMin.setOnAction(e -> stage.setIconified(true));
        btnMax.setOnAction(e -> toggleMaximize());
        btnClose.setOnAction(e -> app.exit());

        bar.getChildren().addAll(logoView, spacer, btnSidebar, btnMin, btnMax, btnClose);
        bar.setPadding(new Insets(0, 8, 0, 8));

        // 标题栏双击 → 最大化/恢复
        bar.setOnMouseClicked(e -> {
            if (e.getClickCount() == 2 && !(e.getTarget() instanceof Button)) {
                toggleMaximize();
            }
        });

        // 标题栏拖拽（由 scene 级事件统一处理，此处不再单独绑定）
        return bar;
    }

    private Button makeTitleBtn(String text, String extraClass) {
        Button btn = new Button(text);
        btn.getStyleClass().add("title-bar-btn");
        if (extraClass != null) btn.getStyleClass().add(extraClass);
        return btn;
    }

    // ==================== 最大化/恢复 ====================

    private void toggleMaximize() {
        if (maximized) restore(); else maximize();
    }

    private void maximize() {
        preMaxX = stage.getX();
        preMaxY = stage.getY();
        preMaxW = stage.getWidth();
        preMaxH = stage.getHeight();

        Rectangle2D vb = Screen.getPrimary().getVisualBounds();
        stage.setX(vb.getMinX());
        stage.setY(vb.getMinY());
        stage.setWidth(vb.getWidth());
        stage.setHeight(vb.getHeight());

        maximized = true;
        btnMax.setText("❐");
        root.getStyleClass().add("maximized");
        root.setEffect(null);
        resizePane.setVisible(false);
        clipRect.setArcWidth(0);
        clipRect.setArcHeight(0);
    }

    private void restore() {
        stage.setX(preMaxX);
        stage.setY(preMaxY);
        stage.setWidth(preMaxW);
        stage.setHeight(preMaxH);

        maximized = false;
        btnMax.setText("☐");
        root.getStyleClass().remove("maximized");
        root.setEffect(shadow);
        resizePane.setVisible(true);
        clipRect.setArcWidth(24);
        clipRect.setArcHeight(24);
    }

    // ==================== 全局鼠标事件 ====================

    /** 鼠标移动 — 切换边缘光标 */
    private void onMouseMoved(MouseEvent e) {
        if (maximized || resizeEdge != ResizeEdge.NONE) return;

        ResizeEdge edge = detectEdge(e.getSceneX(), e.getSceneY());
        // root.setCursor 对 WebView 区域更可靠
        switch (edge) {
            case N:  root.setCursor(Cursor.N_RESIZE); break;
            case S:  root.setCursor(Cursor.S_RESIZE); break;
            case E:  root.setCursor(Cursor.E_RESIZE); break;
            case W:  root.setCursor(Cursor.W_RESIZE); break;
            case NE: root.setCursor(Cursor.NE_RESIZE); break;
            case NW: root.setCursor(Cursor.NW_RESIZE); break;
            case SE: root.setCursor(Cursor.SE_RESIZE); break;
            case SW: root.setCursor(Cursor.SW_RESIZE); break;
            default: root.setCursor(Cursor.DEFAULT); break;
        }
    }

    /** 全局按下 — 仅处理标题栏拖拽 */
    private void onScenePressed(MouseEvent e) {
        if (maximized) {
            if (isInTitleBar(e.getSceneY())) {
                maxOnPress = true;
                maxPressRatioX = e.getSceneX() / stage.getWidth();
                dragStarted = false;
            }
            return;
        }
        if (isInTitleBar(e.getSceneY())) {
            isDragging = true;
            dragOffsetX = e.getSceneX();
            dragOffsetY = e.getSceneY();
            dragStarted = false;
        } else {
            isDragging = false;
        }
    }

    /** 全局拖拽 — 标题栏移动 + 最大化拖拽恢复 */
    private void onSceneDragged(MouseEvent e) {
        if (maxOnPress) {
            double dx = Math.abs(e.getScreenX() - (stage.getX() + maxPressRatioX * stage.getWidth()));
            if (dx > DRAG_THRESHOLD || Math.abs(e.getScreenY() - e.getSceneY()) > DRAG_THRESHOLD) {
                double newX = e.getScreenX() - preMaxW * maxPressRatioX;
                double newY = e.getScreenY() - e.getSceneY();
                restore();
                stage.setX(newX);
                stage.setY(newY);
                isDragging = true;
                dragOffsetX = preMaxW * maxPressRatioX;
                dragOffsetY = e.getSceneY();
                maxOnPress = false;
            }
            return;
        }
        if (isDragging && !maximized) {
            stage.setX(e.getScreenX() - dragOffsetX);
            stage.setY(e.getScreenY() - dragOffsetY);
        }
    }

    /** 全局释放 */
    private void onSceneReleased(MouseEvent e) {
        if (maxOnPress && !dragStarted) {
            maxOnPress = false;
        }
        isDragging = false;
    }

    // ==================== 辅助方法 ====================

    /** 根据边缘类型 + 增量 调整窗口大小 */
    private void applyResize(ResizeEdge edge, double dx, double dy) {
        double nw = resizeStartW, nh = resizeStartH;
        double nx = resizeStartStageX, ny = resizeStartStageY;

        switch (edge) {
            case E:  nw = Math.max(800, resizeStartW + dx); break;
            case W:  nw = Math.max(800, resizeStartW - dx); nx = resizeStartStageX + resizeStartW - nw; break;
            case S:  nh = Math.max(500, resizeStartH + dy); break;
            case N:  nh = Math.max(500, resizeStartH - dy); ny = resizeStartStageY + resizeStartH - nh; break;
            case SE: nw = Math.max(800, resizeStartW + dx); nh = Math.max(500, resizeStartH + dy); break;
            case SW: nw = Math.max(800, resizeStartW - dx); nx = resizeStartStageX + resizeStartW - nw; nh = Math.max(500, resizeStartH + dy); break;
            case NE: nw = Math.max(800, resizeStartW + dx); nh = Math.max(500, resizeStartH - dy); ny = resizeStartStageY + resizeStartH - nh; break;
            case NW: nw = Math.max(800, resizeStartW - dx); nx = resizeStartStageX + resizeStartW - nw; nh = Math.max(500, resizeStartH - dy); ny = resizeStartStageY + resizeStartH - nh; break;
        }
        stage.setX(nx);
        stage.setY(ny);
        stage.setWidth(nw);
        stage.setHeight(nh);
    }

    /** 检测鼠标在窗口边缘的位置 */
    private ResizeEdge detectEdge(double x, double y) {
        double w = stage.getWidth();
        double h = stage.getHeight();
        boolean top = y < RESIZE_MARGIN;
        boolean bottom = y > h - RESIZE_MARGIN;
        boolean left = x < RESIZE_MARGIN;
        boolean right = x > w - RESIZE_MARGIN;

        if (top && left) return ResizeEdge.NW;
        if (top && right) return ResizeEdge.NE;
        if (bottom && left) return ResizeEdge.SW;
        if (bottom && right) return ResizeEdge.SE;
        if (top) return ResizeEdge.N;
        if (bottom) return ResizeEdge.S;
        if (left) return ResizeEdge.W;
        if (right) return ResizeEdge.E;
        return ResizeEdge.NONE;
    }

    /** 判断 y 坐标是否在标题栏区域（36px 高度） */
    private boolean isInTitleBar(double sceneY) {
        return sceneY >= 0 && sceneY <= 36;
    }

    // ==================== 公开方法 ====================

    public void show() { stage.show(); }
    public Stage getStage() { return stage; }
    public double getX() { return stage.getX(); }
    public double getY() { return stage.getY(); }
    public double getWidth()  { return stage.getWidth(); }
    public double getHeight() { return stage.getHeight(); }
}
