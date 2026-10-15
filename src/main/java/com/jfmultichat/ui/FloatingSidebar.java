package com.jfmultichat.ui;

import com.jfmultichat.MainApp;
import javafx.animation.AnimationTimer;
import javafx.animation.PauseTransition;
import javafx.beans.value.ChangeListener;
import javafx.geometry.Pos;
import javafx.scene.Node;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.Tooltip;
import javafx.scene.effect.DropShadow;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.HBox;
import javafx.scene.layout.StackPane;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.scene.shape.Rectangle;
import javafx.stage.Screen;
import javafx.stage.Stage;
import javafx.stage.StageStyle;
import javafx.util.Duration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;

/**
 * **浮动侧栏（窗口切换器）** —— 按用户 2026-10-13"侧栏设计契约"实现，含第二轮反馈的修正.
 *
 * <p>跟随：{@link WinEventWatcher}（WinEvent 钩子，独立线程 + 消息泵，**不轮询** ✓）+ 每帧只读
 * 版本号/事件序号（没变立刻返回 ✓ 空闲零 CPU ✓）。只跟随**内部已绑定**窗口；外部窗口**不作为** ✓。
 *
 * <p>位置：四边之一 + 该边上的 start/center/end ✓；match = 与窗口该边等长 / fit = 按按钮数自适应 ✓；
 * 两者**都不超过**窗口该边 ✓；装不下时**按钮等比缩小**（用户改定：**不要滚动条** ✓ 保持对称简约 ✓）。
 *
 * <p>贴边隐藏：目标最大化 → 贴**显示器边**收成细边 ✓；鼠标移上去**朝屏幕内**展开 ✓
 *（关键修正 ✗：先前按目标窗口算展开位置，会算到屏幕外 → 鼠标一靠近就"跑掉" → 消失/闪烁 ✓）；
 * 移开 600ms 收回 ✓。
 *
 * <p>切窗：平台窗口之间由**侧栏位置反算**窗口矩形、尺寸沿用上一个窗口 ✓；切完**冻结侧栏**一小段时间 ✓
 *（用户第 5 条：切窗时侧栏不动 ✓），并在平台自己调整完之后**量一次真实矩形**并**修正一次** ✓
 *（用户实测：新版微信会自行改动尺寸/位置，导致侧栏每次右移几像素 ✓ 用真实矩形当基准即可不再累积漂移 ✓）。
 */
public class FloatingSidebar {

    private static final Logger LOG = LoggerFactory.getLogger(FloatingSidebar.class);

    private static final long COLLAPSE_DELAY_MS = 600;      // 鼠标移开后多久收回
    // ⚠️ 切窗**不设任何定时器**（用户 2026-10-14："不要搞多少ms的这种，用钩子就好好用钩子" ✓）：
    //    先前那套"冻结 N ms + 多趟纠正"已被删除 ✗ —— 它既卡手 ✓ 又会反过来打断用户手动最大化 ✗。
    //    现在：状态**最先判、当场执行** ✓；需要"先还原再摆位"时，摆位由**目标自己的钩子事件**驱动 ✓。
    /**
     * 折叠态的**热区**（用户 2026-10-14：鼠标移到屏幕四角顶点唤不出）.
     *
     * <p>⚠️ 真因（认真查代码 + 平台机制得出）：JavaFX 的**透明窗口在 Windows 上是分层窗口、按像素命中** ✗ ——
     * **完全透明的像素收不到鼠标事件** ✓（`setPickOnBounds` 在这种窗口上不起作用 ✗）。
     * 所以先前那个 16px 热带里，**只有可见的 6px 细边**能收到 hover ✓ ——
     * 中间垂直靠近还容易中 ✓、斜着推到四角就落在带外 ✗✓ 与用户现象完全吻合 ✓。
     *
     * <p>修法 ✓：热带做成**两层背景** —— ①最外沿 6px = 主题色细边（可见 ✓）
     * ②其余 10px = **alpha≈0.4% 的近乎不可见填充**（肉眼看不见 ✓ 但 alpha&gt;0 → **能被命中** ✓）→
     * 整条屏幕边（含四角）都真正可 hover ✓。
     */
    private static final double HOT = 16;

    private static final String CSS_DARK = "/css/sidebar.css";
    private static final String CSS_LIGHT = "/css/sidebar-light.css";

    private final MainApp app;
    private final Stage stage;
    private final WinEventWatcher watcher = new WinEventWatcher();
    private SidebarPrefs prefs = SidebarPrefs.load();

    private final StackPane rootBox = new StackPane();
    private final VBox colBox = new VBox(SidebarPrefs.BTN_GAP);
    private final HBox rowBox = new HBox(SidebarPrefs.BTN_GAP);
    /**
     * 内容滚动容器（用户 2026-10-14：条长比内容短时，要能**滚轮滚 / 按住拖**才能看到其余按钮）.
     *
     * <p>用户先前定的"**不要滚动条**"依然遵守 ✓：`Hbar/Vbar Policy = NEVER` ✓（不显示条 ✓），
     * 但**滚轮**与**按住拖动**（`pannable`）照常可用 ✓ —— 既不破坏对称简约，又不丢可达性 ✓。
     */
    private final ScrollPane scroll = new ScrollPane();
    private final Rectangle clip = new Rectangle();
    private Node contentNode;

    private final List<Item> items = new ArrayList<>();
    /**
     * hwnd → 按钮（**只为了刷新"当前指向"的高亮**）.
     * <p>⚠️ 用户实测：点一下内容，滚动位置就跳回初始 ✗ —— 根因是我为了刷新高亮去 `rebuildItems()` ✓，
     * 清空子节点时内容高度瞬间变 0 → ScrollPane 把 `vvalue` 夹回 0 ✗✓。
     * 现在高亮走 {@link #updateActiveHighlight()}（只切样式类 ✓ 不重建 ✓）。
     */
    private final java.util.Map<Integer, Button> hwndButtons = new java.util.HashMap<>();

    private AnimationTimer timer;
    private PauseTransition collapseDelay;
    private long lastSeq = -1;
    private long lastStoreVersion = -1;

    private int followedHwnd;
    private int mainHwnd;
    private SidebarLayout.Rect lastTargetRect;

    private boolean collapsed;
    private boolean hoverExpanded;
    private boolean styleApplied;
    private int lastActiveHwnd;
    private boolean builtVertical;
    private boolean builtOnce;
    private double btnSize = SidebarPrefs.BTN;

    /** 我们自己的**侧栏窗口**句柄（钩子现在也收本进程事件 ✓ → 前台是它时不要跟着自己跑 ✓） */
    private int sidebarHwnd;
    /**
     * **事件驱动的补摆位**（用户 2026-10-14："用钩子就好好用钩子，不要搞多少ms的" ✓）.
     * <p>目标"原本最大化、该变普通"时要先 `SW_RESTORE` ✓，而还原是**异步**的 ✓ ——
     * 不猜时间 ✗，而是记下待摆的矩形 ✓，等**这个目标自己的钩子事件**送到（说明它动完了 ✓）再摆 ✓。
     */
    private int pendingPlaceHwnd;
    private int[] pendingPlaceRect;

    /** 切换时沿用的**正常态尺寸**（`rcNormalPosition` ✓；20px 容差滤掉平台自行微调 ✗） */
    private double baseW;
    private double baseH;
    private boolean baseValid;
    /** 上一次**我们请求**的尺寸（用来识别"用户手动调整了窗口大小" ✓） */
    private double lastRequestedW;
    private double lastRequestedH;

    // 拖拽（用户第 8 条：暂缓 ✓ 已取消拖动侧栏本身，位置完全由"贴边 + 对齐"决定 ✓）

    private static volatile FloatingSidebar current;

    public FloatingSidebar(MainApp app) {
        this.app = app;
        this.stage = new Stage();
        current = this;
        buildUI();
    }

    // ==================== 界面骨架 ====================

    private void buildUI() {
        stage.initStyle(StageStyle.TRANSPARENT);
        stage.setAlwaysOnTop(true);

        rootBox.getStyleClass().add("sidebar");
        rootBox.setAlignment(Pos.CENTER);
        rootBox.setClip(clip);
        // 折叠态：窗口是 16px 热带、可见的只是最外沿那条细边 →
        // 整块都要能收到 hover（Region 默认按背景拾取，透明背景拾取不到 ✗）→ 打开按边界拾取 ✓
        rootBox.setPickOnBounds(true);
        rootBox.getChildren().add(scroll);

        // 滚动容器：**不显示滚动条** ✓ 但滚轮与按住拖动可用（`pannable`）✓
        scroll.getStyleClass().add("sidebar-scroll");
        scroll.setHbarPolicy(ScrollPane.ScrollBarPolicy.NEVER);
        scroll.setVbarPolicy(ScrollPane.ScrollBarPolicy.NEVER);
        scroll.setPannable(true);
        scroll.setFitToWidth(true);
        scroll.setFitToHeight(true);

        DropShadow shadow = new DropShadow();
        shadow.setColor(Color.rgb(0, 0, 0, 0.4));
        shadow.setRadius(14);
        shadow.setOffsetX(2);
        rootBox.setEffect(shadow);

        Scene scene = new Scene(rootBox, SidebarPrefs.THICKNESS, 220);
        scene.setFill(Color.TRANSPARENT);
        stage.setScene(scene);
        syncClip();
        applyTheme(readCurrentTheme());

        // 热区：折叠成细边时，鼠标移上去 → 展开；移开一会儿 → 收回（带迟滞，免得抖 ✓）
        rootBox.setOnMouseEntered(e -> {
            if (collapsed && !hoverExpanded) {
                hoverExpanded = true;
                applyGeometry();
            }
        });
        rootBox.setOnMouseExited(e -> {
            if (collapsed && hoverExpanded) {
                if (collapseDelay == null) {
                    collapseDelay = new PauseTransition(Duration.millis(COLLAPSE_DELAY_MS));
                    collapseDelay.setOnFinished(x -> {
                        hoverExpanded = false;
                        applyGeometry();
                    });
                }
                collapseDelay.playFromStart();
            }
        });

        // 注：**取消了"拖动侧栏本身"** —— 位置由"贴边 + 对齐"决定 ✓（用户第 8 条：拖拽暂缓 ✓），
        // 而且按住内容拖动现在是**滚动内容** ✓（用户 2026-10-14：条长比内容短时要能滑着看全 ✓）

        stage.widthProperty().addListener((o, a, b) -> syncClip());
        stage.heightProperty().addListener((o, a, b) -> syncClip());
    }

    private void syncClip() {
        clip.setWidth(Math.max(1, stage.getWidth()));
        clip.setHeight(Math.max(1, stage.getHeight()));
        clip.setArcWidth(14);
        clip.setArcHeight(14);
    }

    // ==================== 跟随 ====================

    public void startFollowing() {
        watcher.start();
        if (timer == null) {
            timer = new AnimationTimer() {
                @Override
                public void handle(long now) {
                    onFrame();
                }
            };
        }
        timer.start();
        LOG.info("[侧栏] 开始跟随（只跟随内部已绑定的窗口；外部窗口一概不作为）");
    }

    public void stopFollowing() {
        if (timer != null) {
            timer.stop();
            timer = null;
        }
        watcher.stop();
    }

    private void onFrame() {
        long ver = com.jfmultichat.acccore.AccRuntimeStore.version();
        if (ver != lastStoreVersion) {
            lastStoreVersion = ver;
            rebuildItems();
            if (followedHwnd != 0) applyGeometry();
        }
        long seq = watcher.getSeq();
        if (seq == lastSeq) return;
        lastSeq = seq;

        // **事件驱动的补摆位**（用户 2026-10-14："用钩子就好好用钩子，不要搞多少ms的" ✓）：
        // 需要对"原本最大化"的目标先还原再摆位 ✓，而 ShowWindow 的还原是**异步**的 ✓ →
        // 不猜时间 ✗，而是**等这个目标自己的事件送到**（LOCATIONCHANGE 等）再摆 ✓ —— 事件到了就说明它动完了 ✓
        if (pendingPlaceHwnd != 0) {
            if (watcher.getLastEventHwnd() == pendingPlaceHwnd) {
                int h = pendingPlaceHwnd;
                int[] r = pendingPlaceRect;
                pendingPlaceHwnd = 0;
                pendingPlaceRect = null;
                if (r != null && !com.jfmultichat.swcore.SwNativeOps.isMaximized(h)) {
                    com.jfmultichat.swcore.SwNativeOps.setWindowRect(h, r[0], r[1], r[2], r[3], true);
                    LOG.info("[侧栏] 还原到位（收到目标事件）→ 补摆位 hwnd=0x{} rect={},{},{},{}",
                            Integer.toHexString(h), r[0], r[1], r[2], r[3]);
                }
            } else if (watcher.getLastEventHwnd() != 0 && followedHwnd != pendingPlaceHwnd) {
                pendingPlaceHwnd = 0;                 // 目标已被换掉 → 放弃 ✓
                pendingPlaceRect = null;
            }
        }

        if (mainHwnd == 0) {
            mainHwnd = resolveOwnMainWindowHwnd();
        }
        if (followedHwnd == 0 && mainHwnd != 0) {
            followedHwnd = mainHwnd;
            lastActiveHwnd = followedHwnd;
            updateActiveHighlight();
        }

        // ---- 跟随目标：**只认钩子送来的前台事件** ✓（不再叠加 JavaFX 焦点监听 ✗ —— 两个来源会打架 ✓）----
        // 也因此**不需要跟随锁** ✓：点击切窗时我们自己设好目标 ✓，
        // 而"目标还没拿到前台"并不会产生新的前台事件 ✗ → 不会被拽回去 ✓（治"摇摆"）
        int fg = watcher.getForegroundHwnd();
        if (fg != 0 && fg != sidebarHwnd && (isFollowable(fg) || fg == mainHwnd)) {
            followedHwnd = fg;
        }
        if (followedHwnd != lastActiveHwnd) {
            lastActiveHwnd = followedHwnd;
            updateActiveHighlight();      // 只切样式类 ✓ 不重建 → 不打断滚动位置 ✓
        }
        if (followedHwnd == 0) return;

        if (!isFollowable(followedHwnd) && followedHwnd != mainHwnd) {
            if (stage.isShowing()) stage.hide();
            followedHwnd = 0;
            return;
        }
        if (followedHwnd == mainHwnd && !isWindowUsable(mainHwnd)) {
            if (stage.isShowing()) stage.hide();
            followedHwnd = 0;
            return;
        }
        if (!stage.isShowing()) {
            stage.show();
            styleApplied = false;
        }
        syncBaseFromLiveSize();
        applyGeometry();
    }

    /**
     * 把"**用户手动调整过**的尺寸"接纳为新基准 ✓，同时**过滤掉平台的自行微调** ✗.
     *
     * <p>两者区分：平台自行调整幅度只有几像素 ✓；用户手动拖出来的尺寸变化通常远大于 20px ✓ → 用容差区分 ✓。
     */
    private void syncBaseFromLiveSize() {
        if (followedHwnd == 0) return;
        // ⚠️ 基准一律取**正常态矩形**（`GetWindowPlacement.rcNormalPosition` ✓）——
        // 用户 2026-10-14 指正 ✓：窗口最大化时也要记住它的正常位置与尺寸 ✓；
        // 若用"当前可见矩形"当基准 ✗，最大化会把整屏尺寸灌进基准 ✓ → 传给下一个窗口就变成
        // "摆到最大化的位置和尺寸"而不是真正最大化 ✗
        SidebarLayout.Rect base = normalRectLogical(followedHwnd);
        if (base == null) base = lastTargetRect;
        if (base == null) return;
        double dw = Math.abs(base.w - lastRequestedW);
        double dh = Math.abs(base.h - lastRequestedH);
        if (dw > 20 || dh > 20) {
            baseW = base.w;
            baseH = base.h;
            baseValid = true;
            lastRequestedW = base.w;
            lastRequestedH = base.h;
            LOG.info("[侧栏] 正常态尺寸被调整（或首次确立）→ 基准 {}x{}", Math.round(baseW), Math.round(baseH));
        }
    }

    /** 窗口"正常态"矩形（逻辑像素）；取不到返回 null ✓ */
    private SidebarLayout.Rect normalRectLogical(int hwnd) {
        int[] r = com.jfmultichat.swcore.SwNativeOps.getNormalRect(hwnd);
        return r == null ? null : toLogical(r);
    }

    private boolean isFollowable(int hwnd) {
        if (hwnd == 0) return false;
        try {
            if (!com.jfmultichat.acccore.AccRuntimeStore.allHwnds().contains(hwnd)) return false;
        } catch (Throwable t) {
            return false;
        }
        return isWindowUsable(hwnd);
    }

    private boolean isWindowUsable(int hwnd) {
        if (hwnd == 0) return false;
        try {
            return com.jfmultichat.swcore.SwNativeOps.isWindow(hwnd)
                    && com.jfmultichat.swcore.SwNativeOps.isWindowVisible(hwnd)
                    && !com.jfmultichat.swcore.SwNativeOps.isMinimized(hwnd);
        } catch (Throwable t) {
            return false;
        }
    }

    // ==================== 几何 ====================

    private void applyGeometry() {
        int[] phys = com.jfmultichat.swcore.SwNativeOps.getVisualRect(followedHwnd);
        if (phys == null) return;
        SidebarLayout.Rect target = toLogical(phys);
        lastTargetRect = target;

        SidebarLayout.Rect screen = monitorOf(target);
        boolean maximized = isEffectivelyMaximized(followedHwnd, target, screen);
        collapsed = maximized;

        double avail = prefs.vertical() ? target.h : target.w;
        layoutContent(target, avail);

        double content = SidebarPrefs.contentLength(items.size(), btnSize);
        // match = 与窗口该边**等长**；fit = 内容长度（按钮已按可用长度缩过 → 必然 ≤ avail ✓）；
        // 两者都**不超过**窗口该边 ✓（用户第 4 条 ✓）
        double length = SidebarPrefs.SIZE_FIT.equals(prefs.sizeMode) ? Math.min(content, avail) : avail;

        // ⚠️⚠️ 临时压测开关（用户 2026-10-14 要求）：fit 模式下把**侧栏长度**缩短一个按钮
        //      （= 内容里仍显示"主窗口按钮 + 全部账号按钮"，但条长只够账号按钮 ✓）
        //      —— 按钮尺寸**不缩** ✓（用户明确："里面按钮等内容当然不变" ✓）。测完删掉这两行即可 ✓
        if (SidebarPrefs.SIZE_FIT.equals(prefs.sizeMode)) {
            length = Math.min(SidebarPrefs.contentLength(Math.max(0, items.size() - 1), btnSize), avail);
        }

        SidebarLayout.Rect r;
        boolean hidden = maximized && !hoverExpanded;
        if (maximized) {
            double edgeLen = prefs.vertical() ? screen.h : screen.w;
            if (hidden) {
                // 折叠：**热带 16px**（透明）+ 可见细边只画在最外沿 ✓ → 屏幕四角也在热区内 ✓
                r = SidebarLayout.atScreenEdgeHot(prefs, screen, edgeLen, HOT);
            } else {
                r = SidebarLayout.expandedAtScreenEdge(prefs, screen, length);
            }
        } else {
            r = SidebarLayout.sidebarRect(prefs, target, screen, length, false);
        }
        stage.setX(r.x);
        stage.setY(r.y);
        stage.setWidth(r.w);
        stage.setHeight(r.h);
        applyCollapsedVisual(hidden, r);
        syncClip();
        ensureWindowStyle();
    }

    /** 折叠态视觉切换：内容隐藏、只留**最外沿那条细边** ✓ */
    private void applyCollapsedVisual(boolean hidden, SidebarLayout.Rect r) {
        if (hidden) {
            if (!rootBox.getStyleClass().contains("collapsed")) rootBox.getStyleClass().add("collapsed");
        } else {
            rootBox.getStyleClass().remove("collapsed");
        }
        if (contentNode != null) contentNode.setVisible(!hidden);
        if (scroll != null) scroll.setVisible(!hidden);
        if (!hidden) {
            rootBox.setStyle("");            // 还原：正常态背景由样式表控制
            return;
        }
        String edge = SidebarPrefs.normalizeEdge(prefs.edge);
        boolean vertical = prefs.vertical();
        //   ① 最外沿 6px = 主题色细边（可见）
        //   ② 其余 10px  = alpha 0.4% 的近乎不可见填充 —— **关键** ✓
        //      JavaFX 透明窗口在 Windows 上按像素命中 ✗ → 全透明区域收不到 hover ✓（四角唤不出的真因）
        String sliver = "-jf-sb-bg";
        // alpha 取 1%（≈2.5/255）：肉眼仍看不出（只在窗口最外沿 10px 一圈）✓，
        // 但远高于任何"按像素命中"的透明阈值 → 一定能收到 hover ✓
        String hot = "rgba(0,0,0,0.01)";
        double rest = Math.max(0, HOT - SidebarPrefs.COLLAPSED);
        String insetsSliver;
        String insetsHot;
        if (vertical) {
            // 左：细边在左 → ①右内缩 rest；②左内缩 6。右：镜像
            boolean left = SidebarPrefs.EDGE_LEFT.equals(edge);
            insetsSliver = left ? "0 " + rest + " 0 0" : "0 0 0 " + rest;
            insetsHot = left ? "0 0 0 " + SidebarPrefs.COLLAPSED : "0 " + SidebarPrefs.COLLAPSED + " 0 0";
        } else {
            boolean top = SidebarPrefs.EDGE_TOP.equals(edge);
            insetsSliver = top ? "0 0 " + rest + " 0" : rest + " 0 0 0";
            insetsHot = top ? SidebarPrefs.COLLAPSED + " 0 0 0" : "0 0 0 " + SidebarPrefs.COLLAPSED;
        }
        rootBox.setStyle("-fx-background-color: " + sliver + ", " + hot + ";"
                + "-fx-background-insets: " + insetsSliver + ", " + insetsHot + ";");
    }

    /**
     * 是否"最大化" —— **一律以实际几何为准** ✓（用户 2026-10-14 第三条：
     * "获取的状态并不是真实的最新状态" ✗）。
     *
     * <p>为什么不信 {@code GetWindowPlacement} 的 showCmd ✗：平台自己改尺寸/最大化时，
     * showCmd 与**眼睛看到的**可能不一致（滞回 ✓），于是"状态在账号之间流转"就会传错 ✓
     * —— 用户实测"切回 A 反而把 A 变成最大化了" ✓ 就是拿到了不真实的旧状态 ✓。
     * <p>判据：视觉矩形基本铺满所在显示器（≥95% 且四边贴边 ✓）→ 就是最大化 ✓（眼见为实 ✓）。
     * 这条同时覆盖 JavaFX 主窗口（它最大化时 showCmd 未必报 MAXIMIZED ✗）与"手动拖到铺满" ✓。
     */
    private boolean isEffectivelyMaximized(int hwnd, SidebarLayout.Rect target, SidebarLayout.Rect screen) {
        if (target == null || screen == null) return false;
        double tol = 6;
        boolean covers = target.w >= screen.w * 0.95 && target.h >= screen.h * 0.95;
        boolean flush = Math.abs(target.x - screen.x) <= tol && Math.abs(target.y - screen.y) <= tol
                && Math.abs(target.right() - screen.right()) <= tol
                && Math.abs(target.bottom() - screen.bottom()) <= tol;
        if (covers && flush) return true;
        // 几何没铺满 → 一定不是最大化 ✓（即使 showCmd 说是，也以看得见的为准 ✓）
        return false;
    }

    private static SidebarLayout.Rect toLogical(int[] phys) {
        double s = uiScale();
        return new SidebarLayout.Rect(phys[0] / s, phys[1] / s, (phys[2] - phys[0]) / s, (phys[3] - phys[1]) / s);
    }

    /** 内容方向/按钮尺寸变了就重建（Node 不能有两个父容器 ✓ 尺寸也要跟着可用长度走 ✓） */
    private void layoutContent(SidebarLayout.Rect target, double avail) {
        boolean vertical = prefs.vertical();
        double want = SidebarPrefs.buttonSize(items.size(), avail);
        if (!builtOnce || builtVertical != vertical || Math.abs(want - btnSize) > 0.5) {
            btnSize = want;
            rebuildItems();
        }
        Node content = vertical ? colBox : rowBox;
        if (scroll.getContent() != content) {
            scroll.setContent(content);            // 一次只挂一个容器 ✓（早先两个都挂 → 空长条 ✗）
            contentNode = content;
        }
        scroll.setFitToWidth(vertical);
        scroll.setFitToHeight(!vertical);
        colBox.setAlignment(Pos.TOP_CENTER);
        rowBox.setAlignment(Pos.CENTER_LEFT);
        colBox.setSpacing(SidebarPrefs.BTN_GAP);
        rowBox.setSpacing(SidebarPrefs.BTN_GAP);
    }

    private SidebarLayout.Rect monitorOf(SidebarLayout.Rect r) {
        try {
            var screens = Screen.getScreensForRectangle(r.x, r.y, Math.max(1, r.w), Math.max(1, r.h));
            Screen s = screens.isEmpty() ? Screen.getPrimary() : screens.get(0);
            javafx.geometry.Rectangle2D b = s.getVisualBounds();
            return new SidebarLayout.Rect(b.getMinX(), b.getMinY(), b.getWidth(), b.getHeight());
        } catch (Throwable t) {
            javafx.geometry.Rectangle2D b = Screen.getPrimary().getVisualBounds();
            return new SidebarLayout.Rect(b.getMinX(), b.getMinY(), b.getWidth(), b.getHeight());
        }
    }

    private static double uiScale() {
        try {
            return Screen.getPrimary().getOutputScaleX();
        } catch (Throwable t) {
            return 1.0;
        }
    }

    // ==================== 按钮 ====================

    private static final class Item {
        final boolean main;
        final String sw;
        final String acc;
        final int hwnd;
        final String title;

        Item(boolean main, String sw, String acc, int hwnd, String title) {
            this.main = main;
            this.sw = sw;
            this.acc = acc;
            this.hwnd = hwnd;
            this.title = title;
        }
    }

    private void rebuildItems() {
        items.clear();
        hwndButtons.clear();
        if (prefs.mainBtnAtEnd) {
            addBoundItems();
            addMainItem();
        } else {
            addMainItem();
            addBoundItems();
        }
        boolean vertical = prefs.vertical();
        // 重建会短暂清空内容 → ScrollPane 的 vvalue/hvalue 会被夹回 0 ✗
        // → 先记下滚动位置，重建后（布局完成那一拍）再还原 ✓
        final double v = scroll.getVvalue();
        final double h = scroll.getHvalue();
        colBox.getChildren().clear();
        rowBox.getChildren().clear();
        for (Item it : items) {
            Node node = buildButton(it);
            if (node instanceof Button b) {
                hwndButtons.put(it.main ? MAIN_KEY : it.hwnd, b);
            }
            if (vertical) {
                colBox.getChildren().add(node);
            } else {
                rowBox.getChildren().add(node);
            }
        }
        // 末尾追加"测试按钮"（不参与切换 ✓ 只开测试台 ✓）
        Node test = buildTestButton();
        if (vertical) {
            colBox.getChildren().add(test);
        } else {
            rowBox.getChildren().add(test);
        }
        builtVertical = vertical;
        builtOnce = true;
        if (v > 0 || h > 0) {
            // 立刻设一次 + 布局完成那一拍再设一次（防止"内容高度暂时为 0"把值夹回去 ✓）
            scroll.setVvalue(v);
            scroll.setHvalue(h);
            javafx.application.Platform.runLater(() -> {
                scroll.setVvalue(v);
                scroll.setHvalue(h);
            });
        }
        LOG.info("[侧栏] 按钮重建（{}，按钮 {}px）：主窗口 + {} 个已绑定窗口",
                vertical ? "竖排" : "横排", Math.round(btnSize), Math.max(0, items.size() - 1));
    }

    /** 主窗口按钮在表里的键（主窗口 hwnd 可能一时为 0，用一个负数哨兵避免和真实 hwnd 撞 ✓） */
    private static final int MAIN_KEY = -1;

    /**
     * **只刷新高亮**（不重建内容 ✓）—— 用户点按钮/前台变化都会调它 ✓，
     * 这样**滚动位置不会被打断** ✓（用户 2026-10-14 实测"点一下就回到初始进度" ✓）。
     */
    private void updateActiveHighlight() {
        hwndButtons.forEach((keyHwnd, btn) -> {
            boolean active = (keyHwnd == MAIN_KEY)
                    ? (mainHwnd != 0 && followedHwnd == mainHwnd)
                    : (keyHwnd == followedHwnd);
            if (active) {
                if (!btn.getStyleClass().contains("active")) btn.getStyleClass().add("active");
                revealActive(btn);            // 高亮的同时**最短步**滑到它 ✓（用户 2026-10-14）
            } else {
                btn.getStyleClass().remove("active");
            }
        });
    }

    /**
     * **最短步**把当前项滑进可视区（用户 2026-10-14：像播放器随机切歌要跳到当前歌 ✓）.
     *
     * <p>"尽量短路逻辑" ✓ 的落地：**只在它看不见时才动** ——
     * 在下方 → 只往下滑到它**刚露头**为止 ✓；在上方 → 只往上滑到它刚露头 ✓；本来就可见 → **一步都不动** ✓。
     * 位置用"内容长度 - 可视长度"换算出像素偏移 ✓（ScrollPane 的 vvalue 0..1 与可滚动范围是线性对应 ✓）。
     */
    private void revealActive(Button btn) {
        javafx.application.Platform.runLater(() -> {
            try {
                boolean vertical = prefs.vertical();
                Node content = scroll.getContent();
                if (content == null) return;
                double contentLen = vertical ? content.getBoundsInLocal().getHeight()
                                             : content.getBoundsInLocal().getWidth();
                double viewLen = vertical ? scroll.getViewportBounds().getHeight()
                                          : scroll.getViewportBounds().getWidth();
                double range = contentLen - viewLen;
                if (range <= 1) return;                       // 内容没超出 → 无需滑动 ✓
                double cur = (vertical ? scroll.getVvalue() : scroll.getHvalue()) * range;
                double a = vertical ? btn.getBoundsInParent().getMinY() : btn.getBoundsInParent().getMinX();
                double b = vertical ? btn.getBoundsInParent().getMaxY() : btn.getBoundsInParent().getMaxX();
                double want = cur;
                if (b > cur + viewLen) {
                    want = b - viewLen;                       // 在下方：往下滑到刚露出 ✓（不多滑 ✗）
                } else if (a < cur) {
                    want = a;                                 // 在上方：往上滑到刚露出 ✓
                }
                if (Math.abs(want - cur) > 0.5) {
                    double v = Math.max(0, Math.min(1, want / range));
                    if (vertical) scroll.setVvalue(v); else scroll.setHvalue(v);
                    LOG.info("[侧栏] 已最短步滑到当前窗口按钮（{}px → {}px）", Math.round(cur), Math.round(want));
                }
            } catch (Throwable t) {
                LOG.debug("[侧栏] 自动滑动失败: {}", t.getMessage());
            }
        });
    }

    private void addMainItem() {
        items.add(new Item(true, null, null, mainHwnd, "主窗口"));
    }

    /**
     * 末尾的**测试按钮**（用户 2026-10-14：把 QQNT/Electron 唤起测试小窗放进侧栏的一个"测试按钮"里 ✓）.
     * <p>它不参与"切换窗口" ✓，点一下只打开测试台 ✓。
     */
    private Node buildTestButton() {
        double size = Math.max(SidebarPrefs.MIN_BTN, btnSize);
        Button btn = new Button();
        btn.getStyleClass().add("sidebar-btn");
        btn.setPrefSize(size, size);
        btn.setMinSize(size, size);
        btn.setMaxSize(size, size);
        Label icon = new Label("🧪");
        icon.getStyleClass().add("sidebar-btn-label");
        btn.setGraphic(icon);
        Tooltip.install(btn, new Tooltip("窗口唤起测试台（QQNT/Electron 卡死窗口专项 ✓）"));
        btn.setOnAction(e -> {
            LOG.info("[侧栏] 打开窗口唤起测试台");
            WindowActivationLab.open();
        });
        return btn;
    }

    /** 侧栏当前跟随的窗口（测试台「取侧栏当前窗口」用 ✓） */
    public int getFollowedHwnd() {
        return followedHwnd;
    }

    /**
     * **挂一个"待补摆位"**（`AccOperatorCore.placeForSwitch` 在"还原还没生效"时调用 ✓）.
     * <p>为什么需要：`ShowWindow(SW_RESTORE)` 是**异步**的 ✗ —— 紧接着 `SetWindowPos` 会落在
     * 仍处于最大化的窗口上（无效 ✗）。这里记下来 ✓，等**这个窗口自己的钩子事件**送到再补摆一次 ✓
     * （不猜时间、不加定时器 ✓ 用户 2026-10-14 的要求 ✓）。
     */
    public static void armPendingPlace(int hwnd, int[] rect) {
        FloatingSidebar s = current;
        if (s == null || hwnd == 0 || rect == null || rect.length != 4) return;
        s.pendingPlaceHwnd = hwnd;
        s.pendingPlaceRect = rect.clone();
    }

    private void addBoundItems() {
        for (com.jfmultichat.acccore.AccRuntimeStore.Bound b : com.jfmultichat.acccore.AccRuntimeStore.allBounds()) {
            items.add(new Item(false, b.sw, b.acc, b.hwnd, b.sw + " - " + safeDisplayName(b.sw, b.acc)));
        }
    }

    private String safeDisplayName(String sw, String acc) {
        try {
            return com.jfmultichat.acccore.AccInfoFuncCore.getAccDisplayName(sw, acc);
        } catch (Throwable t) {
            return acc;
        }
    }

    /**
     * 按钮 = **账号头像 + 右下角平台图标角标**（角标放在按钮**图形内部** ✓）。
     *
     * <p>⚠️ 修正（用户 2026-10-13 实测"只有点角标才有反应"✗）：早先我把头像放进 Button 的 graphic，
     * 却把**点击事件挂在 Button 外面的容器上** ✗ —— Button 自己会消费鼠标事件 → 点主体到不了外层容器 ✓。
     * 现在**角标也放进 graphic**、点击一律走 `btn.setOnAction` ✓ → 整块（含角标）都可点 ✓。
     */
    private Node buildButton(Item it) {
        double size = Math.max(SidebarPrefs.MIN_BTN, btnSize);
        double inner = Math.max(12, size - 8);

        StackPane box = new StackPane();
        box.setPrefSize(size, size);
        box.setMinSize(size, size);
        box.setMaxSize(size, size);

        if (it.main) {
            Label icon = new Label("🏠");
            icon.getStyleClass().add("sidebar-btn-label");
            box.getChildren().add(icon);
        } else {
            Image avatar = loadAvatar(it.sw, it.acc);
            if (avatar != null) {
                ImageView iv = new ImageView(avatar);
                iv.setFitWidth(inner);
                iv.setFitHeight(inner);
                iv.setPreserveRatio(true);
                iv.setSmooth(true);
                Rectangle c = new Rectangle(inner, inner);
                c.setArcWidth(12);
                c.setArcHeight(12);
                iv.setClip(c);
                box.getChildren().add(iv);
            } else {
                // 文字兜底：**与账号表同一条规则** —— 名称**末尾 4 个字符宽**（中文/全角算 2 ✓）
                // 直接复用 AvatarUtils.textAvatarLabel ✓（单一来源，别在这儿再写一遍 ✗）
                String label;
                try {
                    label = com.jfmultichat.utils.AvatarUtils.textAvatarLabel(safeDisplayName(it.sw, it.acc));
                } catch (Throwable t) {
                    label = it.acc == null || it.acc.isEmpty() ? "?" : it.acc.substring(it.acc.length() - 1);
                }
                Label fallback = new Label(label);
                fallback.getStyleClass().add("sidebar-btn-label");
                box.getChildren().add(fallback);
            }
        }

        // 平台角标（右下角；加载不到就不加 ✓）—— 放进 graphic 内 → 与按钮同属一个控件 ✓
        if (!it.main && it.sw != null) {
            Image badge = loadPlatformIcon(it.sw);
            if (badge != null) {
                double bs = Math.max(12, size * 0.36);
                ImageView bv = new ImageView(badge);
                bv.setFitWidth(bs - 2);
                bv.setFitHeight(bs - 2);
                bv.setPreserveRatio(true);
                bv.setSmooth(true);
                StackPane badgeBox = new StackPane(bv);
                badgeBox.setMinSize(bs, bs);
                badgeBox.setMaxSize(bs, bs);
                badgeBox.getStyleClass().add("sidebar-badge");
                StackPane.setAlignment(badgeBox, Pos.BOTTOM_RIGHT);
                box.getChildren().add(badgeBox);
            }
        }

        Button btn = new Button();
        btn.getStyleClass().add("sidebar-btn");
        btn.setPrefSize(size, size);
        btn.setMinSize(size, size);
        btn.setMaxSize(size, size);
        btn.setGraphic(box);
        Tooltip.install(btn, new Tooltip(it.title));
        btn.setOnAction(e -> onItemClick(it));
        if ((it.main && mainHwnd != 0 && followedHwnd == mainHwnd) || (!it.main && it.hwnd == followedHwnd)) {
            btn.getStyleClass().add("active");
        }
        return btn;
    }

    /** 头像缓存（正/负）—— 重建按钮不反复读盘 ✓；**负缓存带过期**（头像文件可能是后来才生成的 ✓） */
    private static final java.util.Map<String, Image> IMG_CACHE = new java.util.concurrent.ConcurrentHashMap<>();
    private static final java.util.Map<String, Long> IMG_NEG_AT = new java.util.concurrent.ConcurrentHashMap<>();
    private static final Image NONE = new javafx.scene.image.WritableImage(1, 1);
    private static final long NEG_TTL_MS = 5000;

    /**
     * 取账号头像（**data 里与账号表同源**：同一份文件、同一套回退 ✓）。
     *
     * <p>做法：**直接读本地头像文件** ✓（账号表的头像最终也来自这个文件 ✓）——
     * 这样绕开两个坑 ✗：
     * <ol>
     *   <li>base64 data URL 解析（多一层编解码、还可能拿到 {@code data:image/svg+…} ✗
     *       —— **JavaFX 的 Image 不认 SVG** ✓ 网页端能渲染、这里渲染不了 ✓）</li>
     *   <li>头像文件可能**后来**才生成/下载好 ✓ → 负缓存 5 秒过期，允许重试 ✓</li>
     * </ol>
     * 共存账号按链路回退到**链接账号**的头像文件 ✓（与 {@code getCoexistAvatarDataUrl} 一致 ✓）。
     */
    private Image loadAvatar(String sw, String acc) {
        String key = sw + "/" + acc;
        Image cached = IMG_CACHE.get(key);
        if (cached != null) return cached == NONE ? null : cached;
        Long negAt = IMG_NEG_AT.get(key);
        if (negAt != null && System.currentTimeMillis() - negAt < NEG_TTL_MS) return null;

        try {
            java.nio.file.Path userDir = com.jfmultichat.config.ConfigManager.getInstance().getUserDataPath();
            if (userDir != null) {
                // 自身优先；共存账号回退到 linked_acc 的文件（与前端/Java 两侧的回退规则一致 ✓）
                java.util.List<String> candidates = new java.util.ArrayList<>();
                candidates.add(acc);
                try {
                    String real = com.jfmultichat.acccore.AccInfoFuncCore.getRealAcc(sw, acc);
                    if (real != null && !real.equals(acc)) candidates.add(real);
                } catch (Throwable ignore) {
                    // 没有链接账号就用自身
                }
                for (String cand : candidates) {
                    for (String ext : new String[]{".jpg", ".jpeg", ".png", ".bmp"}) {
                        java.io.File f = userDir.resolve(sw).resolve(cand).resolve(cand + ext).toFile();
                        if (f.isFile()) {
                            // **按原分辨率加载** ✓（用户反馈"清晰度太低"✗：先前在加载时就缩到 44px ✓
                            // 再显示时又缩一次 → 两次重采样 ✗）。交给 ImageView 平滑缩放 ✓ 一次到位 ✓
                            Image img = new Image(f.toURI().toString(), true);
                            if (!img.isError()) {
                                LOG.info("[侧栏] 头像文件已加载 {}/{} ← {}（原图 {}x{}）", sw, acc, f.getName(),
                                        (int) img.getWidth(), (int) img.getHeight());
                                IMG_CACHE.put(key, img);
                                IMG_NEG_AT.remove(key);
                                return img;
                            }
                        }
                    }
                }
            }
            LOG.info("[侧栏] 没有本地头像文件 {}/{} → 用字母兜底（负缓存 {}s 后重试）", sw, acc, NEG_TTL_MS / 1000);
        } catch (Throwable t) {
            LOG.info("[侧栏] 头像加载异常 {}/{}: {}", sw, acc, t.getMessage());
        }
        IMG_NEG_AT.put(key, System.currentTimeMillis());
        return null;
    }

    private Image loadPlatformIcon(String sw) {
        try {
            java.nio.file.Path userDir = com.jfmultichat.config.ConfigManager.getInstance().getUserDataPath();
            if (userDir == null) return null;
            java.io.File f = userDir.resolve(sw).resolve(sw + ".png").toFile();
            if (f.isFile()) {
                return new Image(f.toURI().toString(), 32, 32, true, true, true);
            }
        } catch (Throwable t) {
            LOG.debug("[侧栏] 平台图标加载失败 {}: {}", sw, t.getMessage());
        }
        return null;
    }

    // ==================== 点击切窗 ====================

    /**
     * 点按钮 → 唤起/切换窗口（用户第 3/5 条 + 2026-10-14 的"三件事"）.
     *
     * <p>**纯钩子、零定时器**（用户 2026-10-14："不要搞多少ms的这种，用钩子就好好用钩子" ✓）：
     * <ol>
     *   <li>**当场现读**上一个窗口的信息（状态以**几何**为准 ✓ 不信 showCmd 的滞回 ✗）</li>
     *   <li>状态**最先判、短路执行** ✓：该最大化就立刻 `SW_MAXIMIZE` + 抬升 ✓（不等任何 ms ✗）</li>
     *   <li>该普通而目标正最大化 → 先 `SW_RESTORE` ✓，摆位则**等目标的钩子事件**到了再补 ✓（还原是异步的 ✓）</li>
     *   <li>切完**立刻** `applyGeometry()` ✓（不等事件 ✗ —— 否则从主窗口切过去时侧栏不跟 ✓ 用户实测问题①）</li>
     * </ol>
     */
    private void onItemClick(Item it) {
        try {
            if (it.main) {
                app.focusMainWindow();
                followedHwnd = mainHwnd;
                lastActiveHwnd = followedHwnd;
                updateActiveHighlight();      // 只切高亮 ✓ 不重建（保住滚动位置 ✓）
                applyGeometry();
                return;
            }
            SidebarLayout.Rect screen = lastTargetRect == null
                    ? monitorOf(new SidebarLayout.Rect(0, 0, 1, 1)) : monitorOf(lastTargetRect);
            SidebarLayout.Rect here = new SidebarLayout.Rect(stage.getX(), stage.getY(),
                    stage.getWidth(), stage.getHeight());
            boolean prevIsPlatform = followedHwnd != 0 && followedHwnd != mainHwnd;

            // ① 当场现读 A（用户建议①）：状态 + 正常态尺寸
            SidebarLayout.Rect prevFresh = null;
            int[] prevPhys = prevIsPlatform
                    ? com.jfmultichat.swcore.SwNativeOps.getVisualRect(followedHwnd) : null;
            if (prevPhys != null) prevFresh = toLogical(prevPhys);
            boolean prevMaximized = prevFresh != null
                    && isEffectivelyMaximized(followedHwnd, prevFresh, monitorOf(prevFresh));
            if (prevIsPlatform) {
                SidebarLayout.Rect base = normalRectLogical(followedHwnd);
                if (base == null) base = prevFresh;
                // 20px 容差：滤掉"平台自行微调几像素"（否则越切越小 ✗），但接纳用户手动调整 ✓
                if (base != null && (!baseValid
                        || Math.abs(base.w - baseW) > 20 || Math.abs(base.h - baseH) > 20)) {
                    baseW = base.w;
                    baseH = base.h;
                    baseValid = true;
                    LOG.info("[侧栏] 切换基准尺寸当场确立 {}x{}（A 的正常态 ✓）", Math.round(baseW), Math.round(baseH));
                }
            } else {
                // 从主窗口切来：**不改尺寸**（用户第 3 条 ✓），但把该窗口的正常态尺寸记为后续基准 ✓（当场 ✓）
                SidebarLayout.Rect base = normalRectLogical(it.hwnd);
                if (base != null) {
                    baseW = base.w;
                    baseH = base.h;
                    baseValid = true;
                }
            }

            // ② 目标矩形：只在不同**平台账号窗口**之间、且 A 不是最大化时才摆位 ✓
            //    （A 最大化 → 一律不传矩形 ✗：传了就变成"摆成整屏"而不是"真最大化" ✓ 用户指正 ✓）
            SidebarLayout.Rect want = (prevIsPlatform && !prevMaximized && baseValid)
                    ? SidebarLayout.windowRectForSwitch(prefs, here, screen, baseW, baseH)
                    : null;
            int[] rect = want == null ? null
                    : new int[]{(int) Math.round(want.x * uiScale()), (int) Math.round(want.y * uiScale()),
                                (int) Math.round(want.w * uiScale()), (int) Math.round(want.h * uiScale())};

            // ③ 激活：走**平台适配器** ✓（QQNT = 托盘唤醒 ✓ 实测唯一可用 ✓；没适配类的平台走默认保状态激活 ✓）
            boolean ok = com.jfmultichat.acccore.AccOperatorCore.switchToSwAccountWnd(it.sw, it.acc, null);
            // 唤活后主窗口可能**重生**（QQNT 关闭再唤起就是这种情况 ✓）→ 必须跟着**新 hwnd** 走 ✓
            int liveHwnd = it.hwnd;
            Long rebound = com.jfmultichat.acccore.AccRuntimeStore.getHwnd(it.sw, it.acc);
            if (rebound != null && rebound != 0 && rebound.intValue() != it.hwnd) {
                liveHwnd = rebound.intValue();
                LOG.info("[侧栏] {}/{} 的窗口重生 → 跟随新 hwnd=0x{}", it.sw, it.acc, Integer.toHexString(liveHwnd));
            }
            LOG.info("[侧栏] 切到 {}/{}（hwnd=0x{}）：{}；A 最大化={}；摆位={}", it.sw, it.acc,
                    Integer.toHexString(liveHwnd), ok ? "成功" : "失败", prevMaximized,
                    want == null ? "不改尺寸" : want.toString());

            // ④ **状态最先判、当场短路执行** ✓（状态与摆位也都交给适配器 ✓）
            if (prevIsPlatform) {
                if (prevMaximized) {
                    com.jfmultichat.acccore.AccOperatorCore.placeForSwitch(it.sw, it.acc, liveHwnd, null, true);
                    LOG.info("[侧栏] 短路执行：A 最大化 → 当场最大化 hwnd=0x{}", Integer.toHexString(liveHwnd));
                } else if (rect != null) {
                    // 适配器会决定"摆位前要不要先叫活/还原" ✓ 以及摆位后要不要解冻 ✓
                    com.jfmultichat.acccore.AccOperatorCore.placeForSwitch(it.sw, it.acc, liveHwnd, rect, false);
                    lastRequestedW = want.w;
                    lastRequestedH = want.h;
                }
            }

            // ⑤ **立刻**跟随（不等事件 ✗ —— 否则从主窗口切过去时侧栏不跟过去 ✓ 用户实测问题①）
            followedHwnd = liveHwnd;
            lastActiveHwnd = liveHwnd;
            updateActiveHighlight();            // 只刷新高亮 ✓ 不重建内容 → 滚动位置不被打断 ✓
            applyGeometry();
        } catch (Throwable t) {
            LOG.warn("[侧栏] 切窗失败: {}", t.getMessage());
        }
    }

    // ==================== 自身窗口样式 ====================

    private void ensureWindowStyle() {
        if (styleApplied) return;
        try {
            int pid = (int) ProcessHandle.current().pid();
            double scale = uiScale();
            int wantW = (int) Math.round(stage.getWidth() * scale);
            int wantH = (int) Math.round(stage.getHeight() * scale);
            for (int h : com.jfmultichat.swcore.SwNativeOps.listOwnTopLevelWindows(pid)) {
                int[] r = com.jfmultichat.swcore.SwNativeOps.getVisualRect(h);
                if (r == null) continue;
                int w = r[2] - r[0];
                int hh = r[3] - r[1];
                if ((Math.abs(w - wantW) <= 8 && Math.abs(hh - wantH) <= 8)
                        || (Math.abs(w - wantH) <= 8 && Math.abs(hh - wantW) <= 8)) {
                    com.jfmultichat.swcore.SwNativeOps.applyNoActivateToolWindow(h);
                    sidebarHwnd = h;                 // 记住自己那个窗口 ✓（前台事件里要忽略它 ✓）
                    styleApplied = true;
                    return;
                }
            }
        } catch (Throwable t) {
            LOG.debug("[侧栏] 设置自身窗口样式失败: {}", t.getMessage());
        }
    }

    // ==================== 主题 ====================

    public void applyTheme(String t) {
        String want = "light".equalsIgnoreCase(t) ? "light" : "dark";
        try {
            Scene scene = stage.getScene();
            if (scene == null) return;
            String dark = getClass().getResource(CSS_DARK).toExternalForm();
            String light = getClass().getResource(CSS_LIGHT).toExternalForm();
            scene.getStylesheets().removeAll(dark, light);
            scene.getStylesheets().add("light".equals(want) ? light : dark);
            LOG.info("[侧栏] 主题切换为 {}", want);
        } catch (Throwable e) {
            LOG.warn("[侧栏] 切换主题失败: {}", e.getMessage());
        }
    }

    private static String readCurrentTheme() {
        try {
            return com.jfmultichat.config.ConfigManager.getInstance()
                    .getGlobalConfig().path("theme").asText("dark");
        } catch (Throwable t) {
            return "dark";
        }
    }

    public static void applyThemeFromBridge(String theme) {
        FloatingSidebar s = current;
        if (s == null) return;
        javafx.application.Platform.runLater(() -> s.applyTheme(theme));
    }

    public static void applyPrefsFromBridge(SidebarPrefs p) {
        if (p == null) return;
        FloatingSidebar s = current;
        if (s == null) return;
        javafx.application.Platform.runLater(() -> s.applyPrefs(p));
    }

    public static FloatingSidebar getCurrent() {
        return current;
    }

    // ==================== 对外 ====================

    /**
     * 记住我们自己主窗口的句柄（跟随它 + 切窗判据要用 ✓）.
     *
     * <p>⚠️ 用户 2026-10-14："不要搞监听" ✓ —— 这里**不再挂 JavaFX 的焦点/几何监听** ✗。
     * 先前那个 `focusedProperty` 监听与钩子事件是**两个来源** ✓ → 切到主窗口时两边的结论互相打架 ✓
     * → 表现就是"侧栏闪着跟了一下主窗口，然后又跟回平台窗口" ✗✓。
     * <p>现在：钩子**不再跳过本进程** ✓（见 {@code WinEventWatcher}）→ 主窗口的前台/移动事件
     * 与平台窗口**走同一条路** ✓，单一来源、不会打架 ✓。
     */
    public void bindToMainWindow(MainWindow mainWindow) {
        if (mainHwnd == 0) mainHwnd = resolveOwnMainWindowHwnd();
        rebuildItems();
    }

    /** 主窗口句柄：本进程顶层窗口里**面积最大**的那个（侧栏很小 ✓ 不会认错 ✓） */
    private int resolveOwnMainWindowHwnd() {
        try {
            int pid = (int) ProcessHandle.current().pid();
            int best = 0;
            long bestArea = -1;
            for (int h : com.jfmultichat.swcore.SwNativeOps.listOwnTopLevelWindows(pid)) {
                int[] r = com.jfmultichat.swcore.SwNativeOps.getVisualRect(h);
                if (r == null) continue;
                long area = (long) Math.max(0, r[2] - r[0]) * Math.max(0, r[3] - r[1]);
                if (area > bestArea) {
                    bestArea = area;
                    best = h;
                }
            }
            if (best != 0) LOG.info("[侧栏] 认出主窗口 hwnd=0x{}（面积 {}）", Integer.toHexString(best), bestArea);
            return best;
        } catch (Throwable t) {
            return 0;
        }
    }

    public void applyPrefs(SidebarPrefs newPrefs) {
        this.prefs = newPrefs;
        btnSize = 0;                 // 强制按新方向/新可用长度重算按钮尺寸 ✓
        builtOnce = false;
        if (stage.isShowing() && followedHwnd != 0) applyGeometry();
        else rebuildItems();
    }

    public SidebarPrefs getPrefs() {
        return prefs;
    }

    public void show() {
        stage.show();
        styleApplied = false;
        syncClip();
        if (mainHwnd == 0) mainHwnd = resolveOwnMainWindowHwnd();
        if (followedHwnd == 0 && mainHwnd != 0) {
            followedHwnd = mainHwnd;
            lastActiveHwnd = followedHwnd;
        }
        rebuildItems();
        if (followedHwnd != 0) applyGeometry();
    }

    public void hide() {
        stage.hide();
    }

    public boolean isShowing() {
        return stage.isShowing();
    }

    public void close() {
        stopFollowing();
        stage.close();
        if (current == this) current = null;
    }

    public Stage getStage() {
        return stage;
    }
}
