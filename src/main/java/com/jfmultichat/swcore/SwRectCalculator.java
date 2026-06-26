package com.jfmultichat.swcore;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 截图区域计算器 — 根据裁切参数计算截图矩形
 * <p>
 * 对应 Python: SwInfoFuncCore._calc_rect (L1818-L1926)
 * <p>
 * 支持多种裁切格式：
 * - 整数像素值
 * - 百分比: "50%w", "30%h"
 * - 缩放因子: "1.5*" (乘以当前缩放因子)
 * - 负值: "-30" 表示从另一侧计算（边距反转）

 * 依赖: 无（纯数学计算）
 */
public final class SwRectCalculator {

    private static final Logger LOG = LoggerFactory.getLogger(SwRectCalculator.class);
    private SwRectCalculator() {}

    /**
     * 截图区域结果
     */
    public static class Rect {
        public final int x;       // 左上角 X
        public final int y;       // 左上角 Y
        public final int width;   // 宽度
        public final int height;  // 高度

        public Rect(int x, int y, int width, int height) {
            this.x = x;
            this.y = y;
            this.width = width;
            this.height = height;
        }

        @Override
        public String toString() {
            return String.format("Rect(%d,%d,%d,%d)", x, y, width, height);
        }
    }

    /**
     * 解析裁切值
     * 对应 Python: _calc_rect._parse_value (L1825-L1872)
     *
     * @param value     裁切值，支持 int / String("%w", "%h", "*")
     * @param targetAxis 目标轴尺寸（宽度或高度）
     * @param axisChar  轴字符: 'w' 或 'h'
     * @return {value, isNegative}
     */
    private static int[] parseValue(Object value, int targetAxis, char axisChar) {
        boolean isNegative = false;

        if (value instanceof Number) {
            int v = ((Number) value).intValue();
            if (v < 0) {
                isNegative = true;
                v = -v;
            }
            return new int[]{v, isNegative ? 1 : 0};
        }

        if (!(value instanceof String)) {
            throw new IllegalArgumentException("无效类型: " + value);
        }

        String s = ((String) value).trim().toLowerCase();

        // 处理负号形式 "-30%"
        if (s.startsWith("-")) {
            isNegative = true;
            s = s.substring(1).trim();
        }

        // 自动补全 "%" -> "%w/%h"
        if (s.endsWith("%")) {
            s = s + axisChar;
        }

        // 处理 "数字*" -> 数字 * 缩放因子
        if (s.endsWith("*")) {
            try {
                // TODO: 从配置获取缩放因子，目前默认为 1.0
                double num = Double.parseDouble(s.substring(0, s.length() - 1));
                double scaleFactor = 1.0; // Config.get_scale_factor()
                return new int[]{(int) Math.ceil(num * scaleFactor), isNegative ? 1 : 0};
            } catch (NumberFormatException e) {
                throw new IllegalArgumentException("无效的缩放格式: " + value);
            }
        }

        // 格式必须是 xx%w 或 xx%h
        if (!s.endsWith("%w") && !s.endsWith("%h")) {
            throw new IllegalArgumentException("无效的百分比格式: " + value);
        }

        try {
            double pct = Double.parseDouble(s.substring(0, s.length() - 2)) / 100.0;
            int base = (s.endsWith("w")) ? targetAxis : targetAxis; // 高度也用 targetAxis 传入
            // 注意：Python 代码中高度用 target_h，需要调用方传入正确的值
            int baseValue = s.endsWith("w") ? targetAxis : targetAxis;
            return new int[]{(int) Math.ceil(baseValue * pct), isNegative ? 1 : 0};
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("无效的百分比数值: " + value);
        }
    }

    /**
     * 根据裁切配置计算截图区域的左上角坐标和宽高
     * 对应 Python: _calc_rect (L1818-L1926)
     *
     * @param targetWidth   目标宽度（控件宽度）
     * @param targetHeight  目标高度（控件高度）
     * @param lCut          左边距
     * @param tCut          上边距
     * @param rCut          右边距
     * @param bCut          下边距
     * @param widthCut      宽度裁剪（null=不指定，正数=居中截取，负数=边距模式）
     * @param heightCut     高度裁剪（null=不指定，正数=居中截取，负数=边距模式）
     * @return Rect 结果
     */
    public static Rect calcRect(int targetWidth, int targetHeight,
                                 Object lCut, Object tCut, Object rCut, Object bCut,
                                 Object widthCut, Object heightCut) {

        int[] lMargin = parseValue(lCut, targetWidth, 'w');
        int[] tMargin = parseValue(tCut, targetHeight, 'h');
        int[] rMargin = parseValue(rCut, targetWidth, 'w');
        int[] bMargin = parseValue(bCut, targetHeight, 'h');

        int[] widthCutParsed = (widthCut != null) ? parseValue(widthCut, targetWidth, 'w') : null;
        int[] heightCutParsed = (heightCut != null) ? parseValue(heightCut, targetHeight, 'h') : null;

        // 处理 cut 的负值逻辑（反向计算）
        if (lMargin[1] == 1) lMargin[0] = targetWidth - lMargin[0];
        if (rMargin[1] == 1) rMargin[0] = targetWidth - rMargin[0];
        if (tMargin[1] == 1) tMargin[0] = targetHeight - tMargin[0];
        if (bMargin[1] == 1) bMargin[0] = targetHeight - bMargin[0];

        // 处理宽度优先级逻辑
        int needLeft, needWidth;
        if (widthCutParsed != null) {
            int wVal = widthCutParsed[0];
            boolean wNeg = widthCutParsed[1] == 1;
            if (wNeg) {
                // 负 width = 边距模式
                lMargin[0] = wVal;
                rMargin[0] = wVal;
                needWidth = targetWidth - lMargin[0] - rMargin[0];
                needLeft = lMargin[0];
            } else {
                // 正 width = 居中截取
                needWidth = wVal;
                needLeft = (targetWidth - wVal) / 2;
            }
        } else {
            needLeft = lMargin[0];
            needWidth = targetWidth - lMargin[0] - rMargin[0];
        }

        // 处理高度优先级逻辑
        int needTop, needHeight;
        if (heightCutParsed != null) {
            int hVal = heightCutParsed[0];
            boolean hNeg = heightCutParsed[1] == 1;
            if (hNeg) {
                // 负 height = 边距模式
                tMargin[0] = hVal;
                bMargin[0] = hVal;
                needHeight = targetHeight - tMargin[0] - bMargin[0];
                needTop = tMargin[0];
            } else {
                // 正 height = 居中截取
                needHeight = hVal;
                needTop = (targetHeight - hVal) / 2;
            }
        } else {
            needTop = tMargin[0];
            needHeight = targetHeight - tMargin[0] - bMargin[0];
        }

        return new Rect(needLeft, needTop, needWidth, needHeight);
    }

    /**
     * 简化的截图区域计算 — 仅使用四个边距
     *
     * @param targetWidth   目标宽度
     * @param targetHeight  目标高度
     * @param left          左边距（像素）
     * @param top           上边距（像素）
     * @param right         右边距（像素）
     * @param bottom        下边距（像素）
     * @return Rect 结果
     */
    public static Rect calcRectSimple(int targetWidth, int targetHeight,
                                       int left, int top, int right, int bottom) {
        return calcRect(targetWidth, targetHeight,
                left, top, right, bottom,
                null, null);
    }
}
