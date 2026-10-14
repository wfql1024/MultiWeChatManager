package com.jfmultichat.ui;

/**
 * 侧栏几何计算（**纯函数、无副作用** → 可直接单测 ✓）.
 *
 * <p>两条方向相反的计算都在这里（用户 2026-10-13 第 5 条的关键）：
 * <ol>
 *   <li>{@link #sidebarRect} —— **跟随时**：由"目标窗口矩形"算出侧栏该在哪 ✓</li>
 *   <li>{@link #windowRectForSwitch} —— **切窗时**：由"侧栏矩形"反算目标窗口该在哪、
 *       尺寸沿用**上一个窗口**的尺寸 ✓（这样切窗时侧栏纹丝不动 ✓ 是窗口来就侧栏 ✓）</li>
 * </ol>
 *
 * <p>约定：所有坐标都是**逻辑像素**（JavaFX 单位），显示器矩形由调用方传入 ✓（处理多显示器/混合 DPI 的地方在调用方 ✓）。
 */
public final class SidebarLayout {

    private SidebarLayout() {}

    /** 矩形（左/上/宽/高，逻辑像素） */
    public static final class Rect {
        public final double x, y, w, h;

        public Rect(double x, double y, double w, double h) {
            this.x = x;
            this.y = y;
            this.w = w;
            this.h = h;
        }

        public double right() { return x + w; }

        public double bottom() { return y + h; }

        @Override
        public String toString() {
            return String.format("[%.0f,%.0f %.0fx%.0f]", x, y, w, h);
        }
    }

    /**
     * **跟随时**：算出侧栏矩形.
     *
     * @param prefs        个性化设置（贴边 / 对齐 / 长度模式 ✓）
     * @param target       被跟随窗口的可见矩形（逻辑像素 ✓）
     * @param screen       目标所在显示器的可见区域（逻辑像素 ✓ 用户第 9 条）
     * @param length       期望长度（match = 目标该边长度；fit = 按按钮数算出来的长度 ✓）
     * @param collapsed    是否"贴边隐藏"折叠态（用户第 2 条：最大化时贴边隐藏 + 热区唤出 ✓）
     */
    public static Rect sidebarRect(SidebarPrefs prefs, Rect target, Rect screen,
                                   double length, boolean collapsed) {
        String edge = SidebarPrefs.normalizeEdge(prefs.edge);
        String align = SidebarPrefs.normalizeAlign(prefs.align);
        boolean vertical = SidebarPrefs.EDGE_LEFT.equals(edge) || SidebarPrefs.EDGE_RIGHT.equals(edge);
        // 第 4 条：**长度永不超过目标窗口对应边**（按钮够多时就等于 match ✓），且不超出显示器
        double maxLen = Math.max(1, vertical ? target.h : target.w);
        double len = Math.min(Math.max(1, length), maxLen);
        double thick = collapsed ? SidebarPrefs.COLLAPSED : SidebarPrefs.THICKNESS;

        if (vertical) {
            double x = SidebarPrefs.EDGE_LEFT.equals(edge) ? target.x - thick : target.right();
            double y = switch (align) {
                case SidebarPrefs.ALIGN_CENTER -> target.y + (target.h - len) / 2;
                case SidebarPrefs.ALIGN_END -> target.bottom() - len;
                default -> target.y;
            };
            return new Rect(x, clampY(y, len, screen), thick, len);
        }
        double y = SidebarPrefs.EDGE_TOP.equals(edge) ? target.y - thick : target.bottom();
        double x = switch (align) {
            case SidebarPrefs.ALIGN_CENTER -> target.x + (target.w - len) / 2;
            case SidebarPrefs.ALIGN_END -> target.right() - len;
            default -> target.x;
        };
        return new Rect(clampX(x, len, screen), y, len, thick);
    }

    /**
     * 折叠态（贴边隐藏）时侧栏贴的是**显示器边缘**（最大化窗口旁边没有空间 ✓）.
     */
    public static Rect collapsedAtScreenEdge(SidebarPrefs prefs, Rect screen, double length) {
        return atScreenEdge(prefs, screen, length, SidebarPrefs.COLLAPSED);
    }

    /**
     * **热区展开态**：仍然贴**显示器边缘**、但按完整厚度**朝屏幕内**展开（用户 2026-10-13 实测问题）.
     *
     * <p>为什么必须这样 ✗：先前展开时我按"目标窗口"算位置 —— 目标已最大化、旁边没有空间 →
     * 算出来在屏幕外/窗口后面 → 鼠标一移过去侧栏就"跑掉" → 触发 mouseExited → 又收回 ✓
     * → 表现正是用户看到的"靠近反而消失/闪烁" ✗。改为**在屏幕边向内展开**：
     * 展开后的矩形**必然覆盖原来那条细边** → 鼠标始终在侧栏内 → 不再闪烁 ✓✓
     */
    public static Rect expandedAtScreenEdge(SidebarPrefs prefs, Rect screen, double length) {
        return atScreenEdge(prefs, screen, length, SidebarPrefs.THICKNESS);
    }

    /** 贴显示器某条边、按给定厚度朝内摆（折叠/展开共用 ✓） */
    public static Rect atScreenEdge(SidebarPrefs prefs, Rect screen, double length, double thickness) {
        String edge = SidebarPrefs.normalizeEdge(prefs.edge);
        String align = SidebarPrefs.normalizeAlign(prefs.align);
        boolean vertical = SidebarPrefs.EDGE_LEFT.equals(edge) || SidebarPrefs.EDGE_RIGHT.equals(edge);
        double len = Math.min(Math.max(1, length), vertical ? screen.h : screen.w);
        if (vertical) {
            // 贴左 → 左边与屏幕左边重合、向内（右）展开；贴右 → 右边与屏幕右边重合、向内（左）展开
            double x = SidebarPrefs.EDGE_LEFT.equals(edge) ? screen.x : screen.right() - thickness;
            double y = alignOf(align, screen.y, screen.h, len);
            return new Rect(x, y, thickness, len);
        }
        double y = SidebarPrefs.EDGE_TOP.equals(edge) ? screen.y : screen.bottom() - thickness;
        double x = alignOf(align, screen.x, screen.w, len);
        return new Rect(x, y, len, thickness);
    }

    /**
     * 折叠态的**热带**（用户 2026-10-14：鼠标移到屏幕四角唤不出）.
     *
     * <p>可见细边只有 6px ✗，斜着把鼠标推到角上很容易落在带外 ✓ → 窗口本身做成更厚的**透明热带** ✓
     * （可见部分由调用方只画在最外沿 ✓），这样整条屏幕边（含四角）都在热区内 ✓。
     * 长度固定为**整条屏幕边** ✓（不随窗口/对齐变化 ✓）。
     */
    public static Rect atScreenEdgeHot(SidebarPrefs prefs, Rect screen, double length, double hotThickness) {
        return atScreenEdge(prefs, screen, length, hotThickness);
    }

    /**
     * **切窗时**：由侧栏矩形**反算**目标窗口的矩形（用户第 5 条：切窗时侧栏不动 ✓）.
     *
     * <p>规则：
     * <ul>
     *   <li>窗口摆在侧栏的**另一侧**（侧栏贴左 → 窗口在侧栏右边 ✓ 以此类推）</li>
     *   <li>尺寸 = **上一个窗口的尺寸** ✓（用户第 3 条："平台窗口之间切换时，目标窗口会被更改成上一个窗口的大小" ✓），
     *       再夹到显示器范围内 ✓</li>
     *   <li>侧栏已折叠（目标最大化）时以**显示器**为基准摆 ✓</li>
     * </ul>
     *
     * @param prevW 上一个窗口的宽（逻辑像素）；&lt;=0 表示没有参照 → 返回 null（调用方只激活、不摆位 ✓）
     * @param prevH 上一个窗口的高
     */
    public static Rect windowRectForSwitch(SidebarPrefs prefs, Rect sidebar, Rect screen,
                                           double prevW, double prevH) {
        if (prevW <= 1 || prevH <= 1) return null;
        String edge = SidebarPrefs.normalizeEdge(prefs.edge);
        double w = Math.min(prevW, screen.w);
        double h = Math.min(prevH, screen.h);
        double x;
        double y;
        switch (edge) {
            case SidebarPrefs.EDGE_RIGHT -> {
                x = sidebar.x - w;
                y = sidebar.y;
            }
            case SidebarPrefs.EDGE_TOP -> {
                x = sidebar.x;
                y = sidebar.bottom();
            }
            case SidebarPrefs.EDGE_BOTTOM -> {
                x = sidebar.x;
                y = sidebar.y - h;
            }
            default -> {                       // 贴左 → 窗口在侧栏右侧
                x = sidebar.right();
                y = sidebar.y;
            }
        }
        // 夹进显示器（别把窗口摆出屏幕 ✓）
        x = Math.max(screen.x, Math.min(x, screen.right() - w));
        y = Math.max(screen.y, Math.min(y, screen.bottom() - h));
        return new Rect(x, y, w, h);
    }

    /** fit 模式：按按钮个数算长度（含两端 padding ✓） */
    public static double fitLength(int buttonCount) {
        int n = Math.max(1, buttonCount);
        return n * SidebarPrefs.BTN + (n - 1) * SidebarPrefs.BTN_GAP + 12;
    }

    /** 该边长度是否**装不下**（第 4 条：装不下 → 按钮**缩小**而不是滚动 ✓ 用户 2026-10-13 改定） */
    public static boolean needsScroll(SidebarPrefs prefs, Rect target, double wantedLength) {
        boolean vertical = prefs.vertical();
        double avail = vertical ? target.h : target.w;
        return wantedLength > avail + 0.5;
    }

    private static double alignOf(String align, double origin, double extent, double len) {
        return switch (align) {
            case SidebarPrefs.ALIGN_CENTER -> origin + (extent - len) / 2;
            case SidebarPrefs.ALIGN_END -> origin + extent - len;
            default -> origin;
        };
    }

    private static double clampY(double y, double len, Rect screen) {
        double max = screen.bottom() - len;
        return Math.max(screen.y, Math.min(y, Math.max(screen.y, max)));
    }

    private static double clampX(double x, double len, Rect screen) {
        double max = screen.right() - len;
        return Math.max(screen.x, Math.min(x, Math.max(screen.x, max)));
    }
}
