package com.jfmultichat.ui;

import com.jfmultichat.config.ConfigManager;
import com.fasterxml.jackson.databind.JsonNode;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 侧栏的**个性化位置模型**（用户 2026-10-13 定，见素材卡"侧栏设计契约"）.
 *
 * <p>模型（照 Windows 任务栏那种思路 ✓）：
 * <ul>
 *   <li><b>一级：贴哪条边</b> {@link #edge} ∈ {left, right, top, bottom}</li>
 *   <li><b>二级：在这条边上的对齐</b> {@link #align} ∈ {start, center, end}
 *       —— 贴左/右时是上/中/下；贴上/下时是左/中/右 ✓</li>
 *   <li><b>长度模式</b> {@link #sizeMode} ∈ {match, fit}
 *       —— match = 与该边等长；fit = 按按钮数自适应（**永不超过**目标窗口该边 ✓ 用户第 4 条）</li>
 *   <li><b>主窗口按钮的位置</b> {@link #mainBtnAtEnd}
 *       —— 用户第 7 条："像任务栏的开始菜单一样，放这条区域的哪一端都行" ✓</li>
 * </ul>
 *
 * <p>持久化：写在 {@code LocalGlobalConfig.json} 的 {@code sidebar} 节点下（属**软件偏好** ✓，
 * 与 {@code theme}/{@code account_columns} 同级 ✓）。
 */
public final class SidebarPrefs {

    // 一级：贴边
    public static final String EDGE_LEFT = "left";
    public static final String EDGE_RIGHT = "right";
    public static final String EDGE_TOP = "top";
    public static final String EDGE_BOTTOM = "bottom";
    // 二级：对齐
    public static final String ALIGN_START = "start";
    public static final String ALIGN_CENTER = "center";
    public static final String ALIGN_END = "end";
    // 长度模式
    public static final String SIZE_MATCH = "match";
    public static final String SIZE_FIT = "fit";

    /** 侧栏厚度（未折叠时的条宽/条高，逻辑像素） */
    public static final double THICKNESS = 56;
    /** 按钮尺寸 + 间距（fit 模式算长度用） */
    public static final double BTN = 44;
    /** 按钮最小尺寸 —— 按钮太多时**缩小而不是滚动**（用户 2026-10-13：滚动条不简约、也没法对称 ✓） */
    public static final double MIN_BTN = 22;
    public static final double BTN_GAP = 8;
    /** 两端留白（算长度用） */
    public static final double PADDING = 12;
    /** 折叠后贴边宽度（贴边隐藏时留的"细边"，鼠标热区就靠它 ✓；用户要求热区大一点 → 6px ✓） */
    public static final double COLLAPSED = 6;

    /**
     * **按可用长度算按钮尺寸**（用户 2026-10-13 第 4 条 + "不要滚动条" ✓）：
     * 装得下就是标准 44px ✓；装不下就**等比缩小**（最小 {@link #MIN_BTN}）✓ ——
     * 这样"按钮足够多时等价于 match" ✓ 且始终对称、始终无滚动条 ✓。
     */
    public static double buttonSize(int count, double avail) {
        if (count <= 0) return BTN;
        double usable = Math.max(0, avail - PADDING);
        double size = (usable - (count - 1) * BTN_GAP) / count;
        return Math.max(MIN_BTN, Math.min(BTN, size));
    }

    /** 内容实际长度（按钮 + 间距 + 两端留白） */
    public static double contentLength(int count, double btn) {
        if (count <= 0) return PADDING;
        return count * btn + (count - 1) * BTN_GAP + PADDING;
    }

    public String edge = EDGE_LEFT;
    public String align = ALIGN_START;
    public String sizeMode = SIZE_MATCH;
    /** 主窗口按钮是否放在末尾（false = 开头） */
    public boolean mainBtnAtEnd = false;

    public static SidebarPrefs load() {
        SidebarPrefs p = new SidebarPrefs();
        try {
            JsonNode node = ConfigManager.getInstance().getGlobalConfig().get("sidebar");
            if (node != null && node.isObject()) {
                p.edge = text(node, "edge", p.edge);
                p.align = text(node, "align", p.align);
                p.sizeMode = text(node, "size_mode", p.sizeMode);
                JsonNode m = node.get("main_btn_at_end");
                if (m != null && m.isBoolean()) p.mainBtnAtEnd = m.asBoolean();
            }
        } catch (Throwable t) {
            // 读不到就用默认值（不打扰用户）
        }
        return p;
    }

    public void save() {
        try {
            Map<String, Object> sidebar = new LinkedHashMap<>();
            sidebar.put("edge", normalizeEdge(edge));
            sidebar.put("align", normalizeAlign(align));
            sidebar.put("size_mode", SIZE_FIT.equals(sizeMode) ? SIZE_FIT : SIZE_MATCH);
            sidebar.put("main_btn_at_end", mainBtnAtEnd);
            ConfigManager.getInstance().updateGlobalConfig(Map.of("sidebar", sidebar));
        } catch (Throwable t) {
            // 保存失败不影响使用
        }
    }

    public boolean vertical() {
        return EDGE_LEFT.equals(edge) || EDGE_RIGHT.equals(edge);
    }

    private static String text(JsonNode node, String key, String def) {
        JsonNode v = node.get(key);
        return v != null && v.isTextual() && !v.asText().isBlank() ? v.asText() : def;
    }

    public static String normalizeEdge(String v) {
        if (EDGE_RIGHT.equals(v) || EDGE_TOP.equals(v) || EDGE_BOTTOM.equals(v)) return v;
        return EDGE_LEFT;
    }

    public static String normalizeAlign(String v) {
        if (ALIGN_CENTER.equals(v) || ALIGN_END.equals(v)) return v;
        return ALIGN_START;
    }
}
