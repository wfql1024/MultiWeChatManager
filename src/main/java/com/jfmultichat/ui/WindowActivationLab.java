package com.jfmultichat.ui;

import com.jfmultichat.swcore.WindowActivationOps;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.RadioButton;
import javafx.scene.control.ScrollPane;
import javafx.scene.control.TextArea;
import javafx.scene.control.TextField;
import javafx.scene.control.ToggleGroup;
import javafx.scene.control.Tooltip;
import javafx.scene.layout.HBox;
import javafx.scene.layout.Priority;
import javafx.scene.layout.Region;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;
import javafx.stage.StageStyle;

import java.time.LocalTime;
import java.time.format.DateTimeFormatter;

/**
 * **窗口唤起测试台**（用户 2026-10-14 指定的研究工具）.
 *
 * <p>用途：QQNT（Electron）窗口被关闭/收起后再用 hwnd 唤起，会出现「界面出来了但卡住、点不动」✓。
 * 本窗口把 {@link WindowActivationOps} 里汇总的**各种唤起方式逐行列出** ✓，用**单选钮**选一种 ✓，
 * 再由**下方同一套动作按钮**对它做 唤起 / 最大化 / 尺寸 / 移动 ✓ —— 一次只试一种 ✓ 便于对比 ✓。
 *
 * <p>布局（按用户 2026-10-14 第二次要求调整 ✓：单选框已表达"选哪一种"→ **不必每行都摆按钮** ✗；
 * 日志区**加大** ✓）：
 * <ol>
 *   <li>顶部：目标 hwnd + 托盘图标 id + 两个便捷取值按钮 ✓</li>
 *   <li>动作栏（**公共一套** ✓）：唤起 / 最大化 / 尺寸(w,h) / 移动(dx,dy) —— 作用于**当前选中的方式** ✓</li>
 *   <li>方式列表：每行 = 单选钮 + 编号名称 + 右侧「?」（悬停看要填什么、什么原理 ✓）</li>
 *   <li>底部：**大日志区**（每次操作都写进来 ✓ 便于逐条对比 ✓）</li>
 * </ol>
 *
 * <p>移动量按用户定义：**正数向右向上、负数向左向下** ✓。
 * 三个复合动作都是「**先用选中的方式唤起，再执行动作**」✓ —— 这样每种方式在四种模式下同条件可比 ✓。
 */
public class WindowActivationLab {

    private static final DateTimeFormatter T = DateTimeFormatter.ofPattern("HH:mm:ss");
    private static WindowActivationLab current;

    private final Stage stage = new Stage();
    private final TextField hwndField = new TextField();
    private final TextField uidField = new TextField("3");
    private final TextField sizeW = new TextField("1200");
    private final TextField sizeH = new TextField("800");
    private final TextField moveDx = new TextField("100");
    private final TextField moveDy = new TextField("0");
    private final TextArea log = new TextArea();
    private final ToggleGroup group = new ToggleGroup();
    private final Label selectedLabel = new Label("未选中");

    public static void open() {
        if (current != null && current.stage.isShowing()) {
            current.stage.toFront();
            return;
        }
        current = new WindowActivationLab();
        // 用户 2026-10-14：**直接最大化打开** ✓（先前默认尺寸偏大、会超出屏幕 ✓ 每次都要手动拖出来 ✓）
        current.stage.setMaximized(true);
        current.stage.show();
    }

    private WindowActivationLab() {
        stage.initStyle(StageStyle.DECORATED);
        stage.setTitle("窗口唤起测试台 — QQNT / Electron 专项（选一行，点动作）");

        VBox root = new VBox(8);
        root.setPadding(new Insets(12));
        root.setStyle("-fx-background-color: #1e1e1e;");

        hwndField.setPrefWidth(150);
        uidField.setPrefWidth(56);
        sizeW.setPrefWidth(64);
        sizeH.setPrefWidth(64);
        moveDx.setPrefWidth(64);
        moveDy.setPrefWidth(64);

        // ---------- ① 目标 ----------
        HBox top = new HBox(8);
        top.setAlignment(Pos.CENTER_LEFT);
        top.getChildren().addAll(
                bold("目标 hwnd"),
                hwndField,
                smallBtn("取前台窗口", () -> {
                    int fg = com.jfmultichat.swcore.SwNativeOps.getForegroundWindow();
                    hwndField.setText(String.valueOf(fg));
                    append("取前台窗口 → " + fg + "（0x" + Integer.toHexString(fg) + "）");
                }),
                smallBtn("取侧栏当前窗口", () -> {
                    FloatingSidebar s = FloatingSidebar.getCurrent();
                    int h = s == null ? 0 : s.getFollowedHwnd();
                    hwndField.setText(String.valueOf(h));
                    append("取侧栏当前跟随窗口 → " + h + (h == 0 ? "（侧栏没在跟随任何窗口）" : ""));
                }),
                spacer(),
                bold("托盘图标 id"),
                uidField,
                spacer(),
                bold("尺寸 w/h"),
                sizeW, sizeH,
                bold("位移 dx/dy"),
                moveDx, moveDy,
                hint("位移：正数向右向上、负数向左向下 ✓"));
        root.getChildren().add(top);

        // ---------- ② 执行栏（选中的**方案**自带最合适的最大化/尺寸/位置做法 ✓）----------
        HBox actions = new HBox(8);
        actions.setAlignment(Pos.CENTER_LEFT);
        actions.setPadding(new Insets(6, 8, 6, 8));
        actions.setStyle("-fx-background-color: #2b2b2b; -fx-background-radius: 5;");
        Button run = new Button("执行方案");
        run.setStyle("-fx-font-size: 13px; -fx-font-weight: bold; -fx-background-color: #2f6f3f;"
                + " -fx-text-fill: #ffffff;");
        run.setOnAction(e -> runSelected());
        actions.getChildren().addAll(
                bold("当前方案："), selectedLabel,
                spacer(),
                run,
                hint("尺寸/位移仅「★托盘唤醒 + 摆位」会用到 ✓"));
        root.getChildren().add(actions);

        // ---------- ③ 方案列表（只放单选 + ?）----------
        VBox rows = new VBox(4);
        for (WindowActivationOps.Plan p : WindowActivationOps.plans()) {
            rows.getChildren().add(buildRow(p));
        }
        ScrollPane sp = new ScrollPane(rows);
        sp.setFitToWidth(true);
        sp.setPrefHeight(230);                     // 列表固定高度 ✓ 剩下的高度全给日志 ✓
        sp.setStyle("-fx-background: #1e1e1e; -fx-background-color: #1e1e1e;");
        root.getChildren().add(sp);

        // ---------- ④ 大日志区 ----------
        log.setEditable(false);
        log.setPrefRowCount(22);
        log.setStyle("-fx-font-family: 'Consolas', monospace; -fx-font-size: 12px;"
                + " -fx-control-inner-background: #101010; -fx-text-fill: #d0d0d0;");
        VBox.setVgrow(log, Priority.ALWAYS);
        HBox logBar = new HBox(8);
        logBar.setAlignment(Pos.CENTER_LEFT);
        logBar.getChildren().addAll(bold("日志"), smallBtn("清空", () -> log.clear()),
                hint("建议顺序：①诊断·窗口状态 ②诊断·列窗口与类名 ③★托盘唤醒 ④★解冻连打 ⑤其余"));
        root.getChildren().addAll(logBar, log);

        stage.setScene(new Scene(root, 1060, 960));
        append("测试台就绪 ✓ 共 " + WindowActivationOps.plans().size() + " 项（含 2 项诊断）："
                + "在下面选一个方案，再点「执行方案」✓");
        append("每个方案都自带最合适的最大化/尺寸/位置做法 ✓（悬停「?」能看到它会怎么摆窗口）");
        append("位移约定：正数向右/向上，负数向左/向下 ✓");
        WindowActivationOps.Plan def = WindowActivationOps.plans().stream()
                .filter(p -> p.id == 2).findFirst().orElse(WindowActivationOps.plans().get(0));
        group.getToggles().stream()
                .filter(t -> t.getUserData() == def)
                .findFirst().ifPresent(t -> t.setSelected(true));
        selectedLabel.setText("#" + def.id + " " + def.name);
    }

    /** 一行 = 一个方案：**只有**单选钮 + 编号名称 + 「?」提示 ✓ */
    private HBox buildRow(WindowActivationOps.Plan m) {
        HBox row = new HBox(6);
        row.setAlignment(Pos.CENTER_LEFT);
        row.setPadding(new Insets(2, 6, 2, 6));
        row.setStyle("-fx-background-color: #262626; -fx-background-radius: 4;");

        RadioButton radio = new RadioButton();
        radio.setToggleGroup(group);
        radio.setUserData(m);
        radio.setOnAction(e -> {
            selectedLabel.setText("#" + m.id + " " + m.name);
            append("已选中方式 #" + m.id + " " + m.name);
        });

        Label name = new Label("#" + m.id + "   " + m.name);
        name.setStyle("-fx-text-fill: #e8e8e8; -fx-font-size: 12.5px;");

        Label q = new Label("?");
        q.setStyle("-fx-text-fill: #0b0b0b; -fx-background-color: #d0a020; -fx-background-radius: 8;"
                + " -fx-min-width: 16; -fx-min-height: 16; -fx-alignment: center; -fx-font-size: 11px;");
        Tooltip tip = new Tooltip(m.tip);
        tip.setWrapText(true);
        tip.setMaxWidth(620);
        Tooltip.install(q, tip);

        row.getChildren().addAll(radio, name, q);
        return row;
    }

    /** 执行当前选中的**方案**（方案已自带最合适的最大化/尺寸/位置做法 ✓） */
    private void runSelected() {
        WindowActivationOps.Plan p = selected();
        if (p == null) {
            append("⚠️ 请先在下面选一个方案（单选钮）");
            return;
        }
        int hwnd = intOf(hwndField.getText());
        if (hwnd == 0) {
            append("⚠️ 请先填目标 hwnd（可用顶部「取前台窗口」/「取侧栏当前窗口」）");
            return;
        }
        int[] args = new int[]{hwnd, intOf(uidField.getText()),
                intOf(sizeW.getText()), intOf(sizeH.getText()),
                intOf(moveDx.getText()), intOf(moveDy.getText())};
        append("── 方案 #" + p.id + " " + p.name + " ──");
        append("  " + oneLine(WindowActivationOps.run(p.id, args)));
    }

    private WindowActivationOps.Plan selected() {
        if (group.getSelectedToggle() == null) return null;
        Object o = group.getSelectedToggle().getUserData();
        return o instanceof WindowActivationOps.Plan p ? p : null;
    }

    private void append(String s) {
        log.appendText("[" + LocalTime.now().format(T) + "] " + s + "\n");
        log.setScrollTop(Double.MAX_VALUE);
    }

    private static String oneLine(String s) {
        return s == null ? "" : s.replace('\n', ' ');
    }

    private static int intOf(String s) {
        try {
            String t = s == null ? "" : s.trim();
            if (t.isEmpty()) return 0;
            if (t.startsWith("0x") || t.startsWith("0X")) return (int) Long.parseLong(t.substring(2), 16);
            return (int) Long.parseLong(t);
        } catch (Exception e) {
            return 0;
        }
    }

    private static Label bold(String s) {
        Label l = new Label(s);
        l.setStyle("-fx-text-fill: #e8e8e8; -fx-font-size: 12.5px; -fx-font-weight: bold;");
        return l;
    }

    private static Label hint(String s) {
        Label l = new Label(s);
        l.setStyle("-fx-text-fill: #9a9a9a; -fx-font-size: 11.5px;");
        return l;
    }

    private static Button smallBtn(String text, Runnable r) {
        Button b = new Button(text);
        b.setStyle("-fx-font-size: 11.5px;");
        b.setOnAction(e -> r.run());
        return b;
    }

    private static Region spacer() {
        Region r = new Region();
        HBox.setHgrow(r, Priority.ALWAYS);
        return r;
    }
}
