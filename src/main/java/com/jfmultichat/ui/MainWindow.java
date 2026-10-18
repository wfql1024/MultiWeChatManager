package com.jfmultichat.ui;

import com.jfmultichat.MainApp;
import com.jfmultichat.bridge.JsBridge;
import javafx.animation.PauseTransition;
import javafx.concurrent.Worker;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.geometry.Rectangle2D;
import javafx.scene.Cursor;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.effect.DropShadow;
import javafx.scene.Group;
import javafx.scene.input.MouseEvent;
import javafx.scene.layout.*;
import javafx.scene.paint.Color;
import javafx.scene.shape.StrokeLineCap;
import javafx.scene.shape.StrokeLineJoin;
import javafx.scene.shape.SVGPath;
import javafx.scene.web.WebEngine;
import javafx.scene.web.WebView;
import javafx.stage.Screen;
import javafx.stage.Stage;
import javafx.stage.StageStyle;
import javafx.util.Duration;
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
    private Button btnRefresh;
    /** 任务中心入口（右上角，与窗口按钮同排）；角标显示进行中任务数 */
    private Button btnTasks;
    private javafx.scene.control.Label taskBadge;

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

        // 供快捷键录入捕获使用（JsBridge Scene 级 EventFilter）
        bridge.setScene(scene);

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
        // 关掉 WebView 自带的右键菜单（用户 2026-10-07）：里面那个"重新加载页"会整页重载，
        // 而现在已经有了专门的刷新按钮 —— 留着只会误触。页面内的自定义右键菜单不受影响
        //（列头菜单/行菜单都是页面自己画的 HTML，不走 WebView 默认菜单）
        webView.setContextMenuEnabled(false);
        webEngine = webView.getEngine();
        webEngine.setJavaScriptEnabled(true);
        webView.setStyle("-fx-background-color: transparent;");

        // JS console.log → Java 日志（终端可见，需要 --add-exports）
        com.sun.javafx.webkit.WebConsoleListener.setDefaultListener(
            (wv, msg, line, src) ->
                LOG.info("[WebView-{}] L{} {}", src, line, msg));

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
                // ⚠️ **用户 2026-10-18 第 1 条（启动时主题不一致）** ✓：
                //   原来只有"用户改主题"时才会走到 `applyTitleBarTheme` ✗ →
                //   启动后：WebView 内容按**系统**主题（深 ✓）、侧栏按**配置**（浅 ✓）、**标题栏仍是系统深色** ✗✓
                //   → 桥就绪这一刻，**主动按配置里的 theme 应用一次** ✓（标题栏 ✓ 侧栏 ✓ 页面 ✓ 一次到位 ✓）
                //   `auto` 时返回 null → **不主动改** ✓（两边本来就都跟随系统 ✓，避免反而改错 ✓）
                String startupTheme = savedTheme();
                if (startupTheme != null) {
                    applyTitleBarTheme(startupTheme);
                }
                // 桥就绪后触发主侧栏平台列表加载 + 任务中心初始化（拉一次列表并装上 Java 推送监听）
                webEngine.executeScript("if(JFC.pages.main)JFC.pages.main.init()");
                webEngine.executeScript("if(JFC.taskCenter)JFC.taskCenter.init()");
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
        // 侧栏是**独立的 JavaFX 窗口**，它拿不到本窗口的样式表 → 一并通知它换肤
        //（用户 2026-10-13：侧栏颜色不跟主题变 ✗）
        try {
            if (app != null) app.onThemeChanged(theme);
        } catch (Throwable t) {
            LOG.warn("通知侧栏换肤失败: {}", t.getMessage());
        }
        // ⚠️ **用户 2026-10-18 第 1 条**：**WebView 里的页面**也要一起切 ✓ ——
        //   原来只切 JavaFX 的样式表 ✗，页面的 `data-theme` 要等"打开外观页"才被设置 ✓
        //   → 于是启动后出现"内容还是系统主题、标题栏却已按配置"这种不一致 ✓
        //   → 这里统一下发一次 ✓（启动时、用户改主题时都会走到 ✓ 一处生效 ✓）
        try {
            if (webEngine != null) {
                webEngine.executeScript(
                        "document.documentElement.setAttribute('data-theme','" + ("light".equals(theme) ? "light" : "dark") + "')");
            }
        } catch (Throwable t) {
            LOG.warn("同步页面主题失败: {}", t.getMessage());
        }
    }

    /**
     * 读配置里的主题 ✓（启动时主动应用一次，见 `applyTitleBarTheme` 的调用点 ✓）.
     *
     * @return "light" / "dark"；配置为 `auto`（跟随系统）时返回 **null** ✓
     *         —— 那种情况**什么都不做**最稳 ✓（JavaFX 与页面本来就都按系统走 ✓，
     *         若这里硬猜一个值反而会把"跟随系统"变成"锁定" ✗）
     */
    private static String savedTheme() {
        try {
            String t = com.jfmultichat.config.ConfigManager.getInstance()
                    .getGlobalConfig().path("theme").asText("auto");
            if ("light".equalsIgnoreCase(t)) return "light";
            if ("dark".equalsIgnoreCase(t)) return "dark";
            return null;                         // auto ✓ → 交给系统 ✓
        } catch (Throwable ignored) {
            return null;
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

        // 刷新当前页：由前端 JFC.router 自行识别"现在显示的是哪个页面"
        // 图标 = Lucide rotate-cw（MIT，24×24 设计稿、stroke-width 2、圆头圆角）
        btnRefresh = makeSvgTitleBtn(null,
                "M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8",
                "M21 3v5h-5");
        // **用户 2026-10-17 第 5 条**：图标改用**项目现成的 SVG 那套** ✓（与"刷新"同一套组件 ✓
        //   `makeSvgTitleBtn` ✓ 描边矢量 ✓ 颜色交给 CSS `.title-bar-icon` ✓ 跟随深浅主题 ✓ 大小与其他图标一致 ✓）
        //   形状取经典的"左侧面板"：外框圆角矩形 + 中间一条竖线 ✓（左侧即侧栏所在的一侧 ✓）
        Button btnSidebar = makeSvgTitleBtn(null,
                "M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
                "M9 3v18");
        // **用户 2026-10-17 第 7 条**：点一下**唤出**侧栏 ✓ 再点一下**关掉** ✓（`toggleSidebar` 内已按 isShowing 分流 ✓）
        btnSidebar.setOnAction(e -> app.toggleSidebar());

        Button btnMin = makeTitleBtn("─", null);
        btnMax = makeTitleBtn("☐", null);
        Button btnClose = makeTitleBtn("✕", "close-btn");

        // 任务中心：图标用 Lucide activity（脉冲线）——角标 = 主题色**实心圆 + 白字数字**，
        // 像 QQ 未读那样贴在按钮右上角（用户 2026-10-12 明确了样式）。
        //
        // 为什么前两次没显示（真正的技术原因）：
        //   第 1 次：JS 调的 bridge.setTaskBadge 根本不在 JsBridge 上 → 静默失效；
        //   第 2 次：角标设了 setManaged(false) → **StackPane 不给它做布局 → 它的 width/height 永远是 0** → 画不出来 ✗。
        //   现在：managed(true)（让 StackPane 正常布局）+ 固定 18×18 + TOP_RIGHT 对齐 + 负边距溢出到角上 ✓
        btnTasks = makeSvgTitleBtn(null, "M22 12h-4l-3 9L9 3l-3 9H2");
        taskBadge = new javafx.scene.control.Label();
        taskBadge.setVisible(false);
        taskBadge.setManaged(true);
        taskBadge.setMouseTransparent(true);
        taskBadge.setMinSize(16, 16);
        taskBadge.setPrefSize(16, 16);
        taskBadge.setMaxSize(16, 16);
        taskBadge.setAlignment(Pos.CENTER);
        taskBadge.setStyle("-fx-background-color: #4aa3ff; -fx-background-radius: 8;"
                + " -fx-text-fill: #ffffff; -fx-font-size: 10px; -fx-font-weight: bold;"
                + " -fx-border-color: transparent; -fx-padding: 0;"
                + " -fx-effect: dropshadow(gaussian, rgba(0,0,0,0.5), 4, 0, 0, 1);");
        javafx.scene.layout.StackPane taskBox = new javafx.scene.layout.StackPane(btnTasks, taskBadge);
        javafx.scene.layout.StackPane.setAlignment(taskBadge, Pos.TOP_RIGHT);
        // ⚠️ 上边距不能是负的：标题栏就在窗口最顶，负值会把角标顶出窗口边界被截断（用户 2026-10-12 反馈）
        javafx.scene.layout.StackPane.setMargin(taskBadge, new Insets(0, -3, 0, 0));
        taskBox.setPickOnBounds(false);
        btnTasks.setOnAction(e -> toggleTaskCenter());

        // 角标跟随任务状态（单一写入点：只在这里更新；不依赖前端回调）
        com.jfmultichat.core.task.TaskRegistry.get().addListener(snap -> {
            int active = 0;
            for (java.util.Map<String, Object> m : snap) {
                if (Boolean.TRUE.equals(m.get("active"))) active++;
            }
            setTaskBadge(String.valueOf(active));
        });

        btnRefresh.setOnAction(e -> refreshCurrentPage());
        btnMin.setOnAction(e -> stage.setIconified(true));
        btnMax.setOnAction(e -> toggleMaximize());
        btnClose.setOnAction(e -> app.exit());

        HBox.setMargin(taskBox, new Insets(0, 4, 0, 0));
        bar.getChildren().addAll(logoView, spacer, btnRefresh, btnSidebar, taskBox, btnMin, btnMax, btnClose);
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

    /** 标题栏图标按钮的图标像素尺寸（24 设计稿等比缩放到此值，与 14px 字形按钮观感相当） */
    private static final double TITLE_ICON_PX = 16;

    /** 刷新不应期（毫秒）：与前端 JFC.router 的 REFRESH_COOLDOWN_MS 同一语义（此值只管按钮置灰） */
    private static final long REFRESH_COOLDOWN_MS = 2000;

    /**
     * 图标版标题栏按钮：用 SVG path 画，不用字体字形.
     *
     * <p>字号字形在 JavaFX 里的观感取决于系统字体回退，既不可控也不好看；SVG path 是矢量，
     * 描边粗细/圆头都可控，颜色交给 CSS（{@code .title-bar-icon { -fx-stroke: … }}）跟随深浅主题.
     *
     * @param extraClass 额外样式类（可为 null）
     * @param pathData   一条或多条 SVG path 数据（24×24 设计稿，stroke-width 2）
     */
    private Button makeSvgTitleBtn(String extraClass, String... pathData) {
        Group icon = new Group();
        for (String d : pathData) {
            SVGPath p = new SVGPath();
            p.setContent(d);
            p.setFill(null);
            p.setStrokeWidth(2);
            p.setStrokeLineCap(StrokeLineCap.ROUND);
            p.setStrokeLineJoin(StrokeLineJoin.ROUND);
            p.getStyleClass().add("title-bar-icon");
            icon.getChildren().add(p);
        }
        // 整体缩放（必须放在 Group 上：逐条缩放会各自围绕自身中心，破坏两条 path 的相对位置）
        double scale = TITLE_ICON_PX / 24.0;
        icon.setScaleX(scale);
        icon.setScaleY(scale);

        Button btn = new Button();
        btn.setGraphic(icon);
        btn.getStyleClass().add("title-bar-btn");
        if (extraClass != null) btn.getStyleClass().add(extraClass);
        return btn;
    }

    /**
     * 刷新按钮：让前端"刷新当前页".
     * 前端 {@code JFC.router.refresh()} 自行识别当前显示的是哪个页面（平台页 / 设置页），
     * 与"最左栏再次点击当前平台"走同一条前端路径；**2 秒防连点不应期也在前端那一个入口里**，
     * 这样按钮与"再点当前平台"两条路共用同一道闸，不会出现两个各管一半的计数器.
     *
     * <p>前端返回 {@code true} 表示真的刷新了 → 按钮进入 2 秒不应期并**置灰**（可见反馈）；
     * 返回 {@code false}（被不应期挡下）则什么也不做，避免"没刷新却灰了"的假反馈.
     */
    private void refreshCurrentPage() {
        if (webEngine == null || btnRefresh == null || btnRefresh.isDisabled()) return;
        boolean refreshed = false;
        try {
            Object r = webEngine.executeScript(
                    "(JFC.router&&JFC.router.refresh)?JFC.router.refresh():false");
            refreshed = Boolean.TRUE.equals(r);
        } catch (Exception e) {
            LOG.warn("Failed to refresh current page", e);
        }
        if (!refreshed) return;
        btnRefresh.setDisable(true);
        PauseTransition cooldown = new PauseTransition(Duration.millis(REFRESH_COOLDOWN_MS));
        cooldown.setOnFinished(e -> btnRefresh.setDisable(false));
        cooldown.play();
    }

    // ==================== 任务中心 ====================

    /** 点标题栏任务图标 → 让前端面板开/合（面板本体在 HTML 里，与全局观感一致） */
    private void toggleTaskCenter() {
        if (webEngine == null) return;
        try {
            webEngine.executeScript("if(window.JFC&&JFC.taskCenter)JFC.taskCenter.toggle()");
        } catch (Exception e) {
            LOG.warn("toggleTaskCenter 失败: {}", e.getMessage());
        }
    }

    /**
     * 更新角标（进行中任务数）—— 由前端在每次任务变化时回调 {@code JFC.bridge.setTaskBadge(n)}.
     * <p>⚠️ 参数用 **String**：本项目 JSObject 桥对固定参数的匹配以 String/boolean 最稳（数字用字符串传）。
     */
    public void setTaskBadge(String active) {
        int n;
        try {
            n = Integer.parseInt(active == null ? "0" : active.trim());
        } catch (Exception e) {
            n = 0;
        }
        final int count = n;
        javafx.application.Platform.runLater(() -> {
            if (taskBadge == null) return;
            if (count <= 0) {
                taskBadge.setVisible(false);
                taskBadge.setText("");
            } else {
                taskBadge.setText(count > 99 ? "99+" : String.valueOf(count));
                taskBadge.setVisible(true);
                taskBadge.toFront();
            }
        });
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
