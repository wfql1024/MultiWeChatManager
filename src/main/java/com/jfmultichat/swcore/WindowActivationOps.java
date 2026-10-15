package com.jfmultichat.swcore;

import com.sun.jna.Library;
import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.platform.win32.WinDef;
import com.sun.jna.platform.win32.WinUser;
import com.sun.jna.ptr.IntByReference;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

/**
 * **窗口唤起方案库**（QQNT/Electron 卡死窗口的专项研究工具）.
 *
 * <p>用户 2026-10-14 的两次要求决定了本类的形态 ✓：
 * ①先要"把所有能试的唤起办法汇总" ✓；②试过之后明确"**很多不是唤起的方法**" ✗，
 * 要"**每种唤起方法 + 你组合好的最合适的最大化/尺寸/位置做法 = 一个方案**" ✓。
 * 所以这里列的是**方案**（{@link #plans()}）而不是裸 API ✓ ——
 * 每个方案的说明里都写清"**它会怎么摆窗口**" ✓。
 *
 * <p>背景资料（[自建任务栏 qq关闭后再打开窗口，窗口卡死解决办法](https://misuseds.blog.csdn.net/article/details/166489064)、
 * [Electron PR #54119](https://github.com/electron/electron/pull/54119#3)）：
 * QQNT 是 Electron ✓，窗口一旦被系统判定为「不在屏幕上」（最小化 / 整窗移出屏幕 /
 * **被别的进程 ShowWindow+AttachThreadInput 硬拉前台** ✗）→ **Chromium 渲染器停住** ✓：
 * 界面在、点不动 ✓。正解方向是**把这一下点击交还给程序自己的托盘处理** ✓：
 * 对 `Electron_NotifyIconHostWindow` 发 `WM_APP+1(0x8001)`、`wParam`=图标 id（QQ 是 3 ✓）、
 * `lParam`=`WM_LBUTTONDOWN(0x201)` ✓。（发 `WM_LBUTTONUP`/`NIN_SELECT` 无效 ✗）
 *
 * <p>约定：入参一律**物理像素** ✓；位移按用户定义「**正数向右向上、负数向左向下**」✓。
 */
public final class WindowActivationOps {

    private static final Logger LOG = LoggerFactory.getLogger(WindowActivationOps.class);

    private WindowActivationOps() {}

    /** 入参下标（物理像素；位移正 = 右/上 ✓） */
    public static final int A_HWND = 0, A_UID = 1, A_W = 2, A_H = 3, A_DX = 4, A_DY = 5;

    /** 一个**方案**：名字 + 悬停说明（原理 + 要填什么 + 怎么摆窗口）+ 执行体 */
    public static final class Plan {
        public final int id;
        public final String name;
        public final String tip;
        final Function<int[], String> action;

        Plan(int id, String name, String tip, Function<int[], String> action) {
            this.id = id;
            this.name = name;
            this.tip = tip;
            this.action = action;
        }
    }

    private static final List<Plan> PLANS = new ArrayList<>();

    private static void plan(int id, String name, String tip, Function<int[], String> fn) {
        PLANS.add(new Plan(id, name, tip, fn));
    }

    /** 全部方案（顺序 = 测试台行序 ✓ 由温和到强硬 ✓；最后两行是诊断 ✓） */
    public static List<Plan> plans() {
        return PLANS;
    }

    /** 执行某个方案 ✓；返回一句话结果（测试台显示 + 日志 ✓） */
    public static String run(int planId, int[] args) {
        for (Plan p : PLANS) {
            if (p.id == planId) {
                try {
                    String r = p.action.apply(args);
                    String out = (r == null ? "完成" : r);
                    LOG.info("[测试台] 方案#{} {} → {}", planId, p.name, out.replace('\n', ' '));
                    return out;
                } catch (Throwable t) {
                    LOG.warn("[测试台] 方案#{} {} 异常", planId, p.name, t);
                    return "异常: " + t;
                }
            }
        }
        return "未知方案 id=" + planId;
    }

    // ==================== 共用小步骤（每个方案挑合适的组合 ✓） ====================

    private static final int SWP_NOSIZE = 0x0001, SWP_NOMOVE = 0x0002, SWP_NOZORDER = 0x0004;
    private static final int SWP_NOACTIVATE = 0x0010, SWP_FRAMECHANGED = 0x0020, SWP_SHOWWINDOW = 0x0040;
    private static final int RDW_INVALIDATE = 0x0001, RDW_ALLCHILDREN = 0x0080, RDW_UPDATENOW = 0x0100;
    // 专治「大灰框」（框架/非客户区没重画 ✓）用的常量 —— **必须声明在 static{} 之前** ✗
    //（静态初始化块里前向引用静态字段 = 非法前向引用，直接编译不过 ✓ 实测踩到 ✓）
    private static final int RDW_FRAME = 0x0400;
    private static final int SWP_NOCOPYBITS = 0x0100;
    private static final int SWP_ASYNCWINDOWPOS = 0x4000;
    private static final int WM_NCPAINT = 0x0085;
    private static final int WM_NCACTIVATE = 0x0086;

    /** 假鼠标移动（komorebi 配方里那一步 ✓）：让系统认为"调用者刚有输入" ✓ 从而允许抢前台 ✓ */
    private static void mouseMove(int dx, int dy) {
        Ext.INSTANCE.mouse_event(0x0001 /*MOUSEEVENTF_MOVE*/, dx, dy, 0, null);
    }

    /** 抬到最前（只改 Z 序 ✓ 不动几何/状态 ✓） */
    private static boolean raise(int hwnd) {
        return Ext.INSTANCE.SetWindowPos(h(hwnd), null, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
    }

    /** 置前请求（常被系统拒绝 ✓ 返回 false 也正常 ✓） */
    private static boolean foreground(int hwnd) {
        return Ext.INSTANCE.SetForegroundWindow(h(hwnd));
    }

    /** 重算框架（触发重绘 ✓） */
    private static void framechange(int hwnd) {
        Ext.INSTANCE.SetWindowPos(h(hwnd), null, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED);
    }

    /** 强制重画（含子窗口 ✓） */
    private static boolean redraw(int hwnd) {
        Ext.INSTANCE.InvalidateRect(h(hwnd), null, true);
        return Ext.INSTANCE.RedrawWindow(h(hwnd), null, null,
                RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN);
    }

    /** 尺寸抖 ±1px（**Chromium 合成器主要在尺寸变化时重新出帧** ✓ 解冻主力 ✓） */
    private static String jiggle(int hwnd) {
        int[] r = SwNativeOps.getVisualRect(hwnd);
        if (r == null) return "抖动失败(取矩形失败)";
        int w0 = r[2] - r[0], h0 = r[3] - r[1];
        setWindowPos(hwnd, 0, 0, Math.max(1, w0 + 1), Math.max(1, h0), SWP_NOMOVE);
        sleep(30);
        setWindowPos(hwnd, 0, 0, w0, h0, SWP_NOMOVE);
        return "已抖动 " + w0 + "x" + h0;
    }

    /**
     * **免激活摆位**（切窗/复位专用 ✓）：先按当前左上角加位移 (dx, dy)、再设尺寸 (w, h) ✓。
     * <p>用 `SWP_NOACTIVATE` ✓ —— 摆位本身**不改变前台** ✓（改前台由唤起步骤负责 ✓），
     * 也不会把 Electron 拖进"硬拉"那种冻结状态 ✓。
     */
    private static String place(int hwnd, int w, int h, int dx, int dy) {
        int[] r = SwNativeOps.getVisualRect(hwnd);
        if (r == null) return "摆位失败(取矩形失败)";
        int x = r[0] + dx;
        int y = r[1] - dy;                       // 屏幕 Y 向下 ✓「向上」= y 减小 ✓
        int ww = w > 0 ? w : (r[2] - r[0]);
        int hh = h > 0 ? h : (r[3] - r[1]);
        boolean ok = Ext.INSTANCE.SetWindowPos(h(hwnd), null, x, y, ww, hh,
                SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW);
        return (ok ? "已摆位 " : "摆位失败 ") + x + "," + y + " " + ww + "x" + hh;
    }

    private static boolean setWindowPos(int hwnd, int x, int y, int w, int h, int extraFlags) {
        return Ext.INSTANCE.SetWindowPos(h(hwnd), null, x, y, w, h,
                SWP_NOZORDER | SWP_NOACTIVATE | extraFlags);
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    // ==================== 方案表 ====================

    static {
        // ---- 方案 1：温和唤醒（只抬升/置前 + 轻量重绘；不动状态、不动几何） ----
        plan(1, "温和唤醒（不动几何）",
                "要填：无（只读 hwnd）。\n"
                        + "步骤：抬到最前 → 置顶闪一下(TOPMOST→NOTOPMOST) → SWP_FRAMECHANGED → RedrawWindow → SetForegroundWindow。\n"
                        + "怎么摆窗口：**完全不碰**尺寸/位置/最大化状态 ✓（最安全的一种）。\n"
                        + "用途：先试它 —— 若它唤不出，基本可判定是 Electron 渲染器冻结，转「托盘唤醒」或「解冻连打」✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    StringBuilder sb = new StringBuilder();
                    sb.append("抬升=").append(raise(hwnd)).append(' ');
                    WinDef.HWND topmost = new WinDef.HWND(Pointer.createConstant(-1));
                    WinDef.HWND notTop = new WinDef.HWND(Pointer.createConstant(-2));
                    Ext.INSTANCE.SetWindowPos(h(hwnd), topmost, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
                    Ext.INSTANCE.SetWindowPos(h(hwnd), notTop, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
                    framechange(hwnd);
                    sb.append("重画=").append(redraw(hwnd)).append(' ');
                    sb.append("置前=").append(foreground(hwnd));
                    return sb.toString();
                });

        // ---- 方案 2：★托盘唤醒（仅唤醒；资料里的正解方向） ----
        plan(2, "★托盘唤醒（仅唤醒）",
                "要填：托盘图标 id（QQ 是 3；不确定先跑最后一行「诊断·列窗口与类名」）。\n"
                        + "步骤：在本进程里找类名 Electron_NotifyIconHostWindow 的窗口 → "
                        + "PostMessageW(WM_APP+1=0x8001, wParam=图标id, lParam=WM_LBUTTONDOWN=0x201) → 抬到最前 → 置前。\n"
                        + "原理：这正是「用户点了托盘图标」时系统发给它的那条消息 → **让 QQ 自己把窗口弄回来** ✓（不会冻结）。\n"
                        + "怎么摆窗口：**不碰**尺寸/位置/状态 ✓（让程序自己决定 ✓）。\n"
                        + "⚠️ 必须发**按下** 0x201；发松开 0x202 / NIN_SELECT 无效 ✗。",
                a -> tray(a[A_HWND], a[A_UID], false, false, a));

        // ---- 方案 3：★托盘唤醒 + 摆位（切窗用） ----
        plan(3, "★托盘唤醒 + 摆位",
                "要填：托盘图标 id ✓ + 尺寸 w/h ✓ + 位移 dx/dy ✓（正数向右向上、负数向左向下）。\n"
                        + "步骤：同方案 2 的托盘点击 → 抬升 → 置前 → **免激活摆位**(SetWindowPos + SWP_NOACTIVATE) "
                        + "把窗口设成 w×h 并平移 (dx,dy)。\n"
                        + "怎么摆窗口：**先唤醒、再摆位**，尺寸用你填的 w×h ✓。\n"
                        + "用途：切窗场景 —— 唤醒目标后按「上一个窗口的正常态尺寸」把它摆到侧栏旁边 ✓"
                        + "（且摆位不带激活、不会诱发冻结 ✓）。",
                a -> tray(a[A_HWND], a[A_UID], false, true, a));

        // ---- 方案 4：★托盘唤醒 + 最大化 ----
        plan(4, "★托盘唤醒 + 最大化",
                "要填：托盘图标 id（QQ 是 3）。\n"
                        + "步骤：托盘点击 → 抬升 → 置前 → ShowWindow(SW_MAXIMIZE)。\n"
                        + "怎么摆窗口：唤醒后**最大化**（真最大化 ✓ 不是把它摆成整屏大小 ✓）。\n"
                        + "用途：切窗场景 —— 上一个窗口是最大化时，目标也最大化 ✓。",
                a -> tray(a[A_HWND], a[A_UID], true, false, a));

        // ---- 方案 5：★解冻连打（画面冻住专用） ----
        plan(5, "★解冻连打（画面冻住专用）",
                "要填：无。\n"
                        + "步骤：尺寸抖 ±1px → SWP_FRAMECHANGED → RedrawWindow → DwmFlush → 抬到最前 → SetForegroundWindow。\n"
                        + "原理：**Chromium 合成器主要只在尺寸变化时重新出帧** ✓，隐藏/冻结后它不重绘 —— "
                        + "单招往往不够，所以这几步一起上 ✓。\n"
                        + "怎么摆窗口：抖动后会**还原成原尺寸** ✓ 位置不变 ✓（净效果 = 没动几何 ✓）。\n"
                        + "用途：界面出来了但画面停住/白屏时优先试它 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    String j = jiggle(hwnd);
                    framechange(hwnd);
                    boolean rd = redraw(hwnd);
                    int fl = Dwm.INSTANCE.DwmFlush();
                    boolean flOk = fl == 0;
                    boolean rs = raise(hwnd);
                    return j + "，重画=" + rd + "，DwmFlush=" + fl + (flOk ? "(S_OK)" : "(非0)")
                            + "，抬升=" + rs + "，置前=" + foreground(hwnd);
                });

        // ---- 方案 6：真实输入激活（点客户区 / 双击标题区） ----
        plan(6, "真实输入激活（点 / 双击标题区）",
                "要填：无。\n"
                        + "步骤：把鼠标移到窗口中心点一下 → 再在标题区 (8,8) 处双击 → 抬升 → 置前。\n"
                        + "原理：**真实输入**是最「合法」的激活路径 ✓（不触发前台限制 ✓）。\n"
                        + "怎么摆窗口：不主动摆 ✓；但**双击标题区可能切换它的最大化状态** ⚠️（这是模拟真实双击的副作用）。\n"
                        + "⚠️ 会移动你的鼠标 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    int[] r = SwNativeOps.getVisualRect(hwnd);
                    if (r == null) return "取窗口矩形失败";
                    clickAt((r[0] + r[2]) / 2, (r[1] + r[3]) / 2);
                    sleep(80);
                    clickAt(r[0] + 8, r[1] + 8);
                    sleep(60);
                    clickAt(r[0] + 8, r[1] + 8);
                    raise(hwnd);
                    return "已点击客户区 + 双击标题区，置前=" + foreground(hwnd);
                });

        // ---- 方案 7：前台锁绕过（ALT 轻敲 + 允许置前） ----
        plan(7, "前台锁绕过（ALT 轻敲）",
                "要填：无。\n"
                        + "步骤：模拟按下/抬起 ALT → AllowSetForegroundWindow(ASFW_ANY=-1) → 抬到最前 → SetForegroundWindow。\n"
                        + "原理：系统对「刚按过 ALT」的进程放宽前台限制 ✓；AllowSetForegroundWindow 再补一道许可 ✓。\n"
                        + "怎么摆窗口：不动几何/状态 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    Ext.INSTANCE.keybd_event((byte) 0x12, (byte) 0, 0, null);
                    Ext.INSTANCE.keybd_event((byte) 0x12, (byte) 0, 2, null);
                    boolean allow = Ext.INSTANCE.AllowSetForegroundWindow(-1);
                    raise(hwnd);
                    return "ALT 轻敲✓，AllowSetForegroundWindow=" + allow + "，置前=" + foreground(hwnd);
                });

        // ---- 方案 8：异步显示唤醒 ----
        plan(8, "异步显示唤醒（不阻塞）",
                "要填：无。\n"
                        + "步骤：ShowWindowAsync(SW_SHOW) → ShowWindowAsync(SW_RESTORE) → 抬到最前 → 置前。\n"
                        + "原理：**异步**版本不等待目标线程 —— 目标 UI 线程正忙/卡住时，同步的 ShowWindow 会把你一起卡住 ✓。\n"
                        + "怎么摆窗口：SW_RESTORE 会把它从**最小化**恢复出来 ✓（普通/最大化窗口不受影响 ✓），位置尺寸由系统还原 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    boolean s1 = Ext.INSTANCE.ShowWindowAsync(h(hwnd), 5);   // SW_SHOW
                    boolean s2 = Ext.INSTANCE.ShowWindowAsync(h(hwnd), 9);   // SW_RESTORE
                    raise(hwnd);
                    return "ShowWindowAsync(SW_SHOW)=" + s1 + "，ShowWindowAsync(SW_RESTORE)=" + s2
                            + "，置前=" + foreground(hwnd);
                });

        // ---- 方案 9：硬拉激活（✗ 资料点名会冻结，留作对照） ----
        plan(9, "硬拉激活（✗ 慎用·会诱发冻结）",
                "要填：无。\n"
                        + "步骤：AttachThreadInput(自己的线程 ↔ 目标线程) → SetForegroundWindow → SetFocus → SetActiveWindow → 解除绑定。\n"
                        + "原理：共用输入队列后可以绕过前台限制 ✓。\n"
                        + "⚠️⚠️ 资料明确点名：**硬拉会让 QQNT/Electron 进入冻结** ✓ —— 留这行是为了让你对照它与托盘法的差别 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    IntByReference pid = new IntByReference();
                    int tid = Ext.INSTANCE.GetWindowThreadProcessId(h(hwnd), pid);
                    int myTid = Kernel32.INSTANCE.GetCurrentThreadId();
                    boolean at = tid != 0 && tid != myTid && Ext.INSTANCE.AttachThreadInput(myTid, tid, true);
                    boolean fg = Ext.INSTANCE.SetForegroundWindow(h(hwnd));
                    Ext.INSTANCE.SetFocus(h(hwnd));
                    Ext.INSTANCE.SetActiveWindow(h(hwnd));
                    if (at) Ext.INSTANCE.AttachThreadInput(myTid, tid, false);
                    return "AttachThreadInput=" + at + "，SetForegroundWindow=" + fg;
                });

        // ---- 方案 10：状态重置（✗ 慎用） ----
        plan(10, "状态重置 + 置前（✗ 慎用）",
                "要填：无。\n"
                        + "步骤：读 GetWindowPlacement → 把 showCmd 改成 SW_SHOWNORMAL(1) → SetWindowPlacement → 抬升 → 置前。\n"
                        + "原理：等于告诉系统「这窗口就是普通态」→ 有些被系统当成隐藏的窗口会因此重新出现 ✓。\n"
                        + "⚠️ 会**强行取消最大化** ✓（所以标慎用）；另可搭配方案 5 一起试 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    WinUser.WINDOWPLACEMENT wp = new WinUser.WINDOWPLACEMENT();
                    wp.length = wp.size();
                    if (!Ext.INSTANCE.GetWindowPlacement(h(hwnd), wp)) return "GetWindowPlacement 失败";
                    wp.showCmd = 1;
                    boolean ok = Ext.INSTANCE.SetWindowPlacement(h(hwnd), wp);
                    raise(hwnd);
                    return "强制普通态=" + ok + "，置前=" + foreground(hwnd);
                });

        // ---- 诊断（不是方案，但试的时候离不开 ✓） ----
        plan(11, "诊断 · 窗口状态",
                "不填额外内容。打印：类名/进程/可见/是否响应(IsHungAppWindow)/"
                        + "showCmd(1普通 2最小化 3最大化)/矩形/扩展样式。\n"
                        + "原理：先分清它是「被系统藏起来」还是「真的卡住」——资料建议的第一步 ✓。",
                a -> describe(a[A_HWND]));

        plan(12, "诊断 · 列窗口与类名",
                "不填额外内容。列出**目标进程**的全部顶层窗口：句柄 / 类名 / 可见 / 矩形。\n"
                        + "原理：Electron 的托盘宿主类名是 Electron_NotifyIconHostWindow ✓ —— "
                        + "用这行确认它存在（顺便核对 CHROME_WIDGET 那几个主窗口是谁 ✓）。结果写进下方日志 ✓。",
                a -> listWindows(a[A_HWND]));

        // ==================== 续写（用户 2026-10-14 晚：专治 Weixin「大灰框」） ====================
        // 现象 ✓：新版微信（平台 id = Weixin ✓ 不是 Electron ✗）从托盘唤起后，
        //   窗口**被一大圈灰框包住**，**手动拖动一下才消失** ✓。
        // 判断 ✓：这是 **DWM/非客户区(框架)没有重画** 留下的旧像素 ✓（拖动会触发系统重算框架 ✓ 所以一拖就好 ✓）。
        // 所以下面这几种都是围绕"**把框架重画一遍**"，并且各自配好了合适的尺寸/位置/最大化处理 ✓。
        // 左边已有的方案**一行未动** ✓（用户要求 ✓）。

        plan(13, "★Weixin 温和唤起 + 修边框",
                "要填：无。\n"
                        + "步骤：ShowWindowAsync(SW_SHOW) → ShowWindowAsync(SW_RESTORE) → 抬到最前 → 置前 → "
                        + "SWP_FRAMECHANGED → RedrawWindow(RDW_FRAME) → 置前。\n"
                        + "原理：先走**最轻**的显示路径 ✓（不合成点击 → 不会留下「被按住」的视觉态 ✓），"
                        + "再单独把**框架**重画一遍 ✓（RDW_FRAME 专管非客户区 ✓）。\n"
                        + "怎么摆窗口：**不动几何/状态** ✓（只唤醒 + 修边框 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    boolean s1 = Ext.INSTANCE.ShowWindowAsync(h(hwnd), 5);
                    boolean s2 = Ext.INSTANCE.ShowWindowAsync(h(hwnd), 9);
                    raise(hwnd);
                    boolean fg = foreground(hwnd);
                    framechange(hwnd);
                    boolean rf = redrawFrame(hwnd);
                    return "ShowAsync(SHOW)=" + s1 + "，ShowAsync(RESTORE)=" + s2 + "，置前=" + fg
                            + "，重算框架✓，重画框架=" + rf;
                });

        plan(14, "★灰框专治连打（不动几何）",
                "要填：无。\n"
                        + "步骤：SWP_FRAMECHANGED → RedrawWindow(RDW_FRAME|RDW_UPDATENOW|RDW_ALLCHILDREN) → "
                        + "SendMessage(WM_NCPAINT, 1) → SendMessage(WM_NCACTIVATE, TRUE) → DwmFlush。\n"
                        + "原理：这四步分别对应「重算框架 / 重画框架+子窗 / 强制重画非客户区 / 非客户区激活态」 ✓，"
                        + "最后冲刷 DWM 合成 ✓ —— 这正是你手动拖一下时系统替你做的事 ✓。\n"
                        + "怎么摆窗口：**完全不动**几何/状态 ✓（只修画面 ✓）。\n"
                        + "用法：任何「唤出来后带灰框/白边」的情况都可以叠在其它方案后面点一下 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    framechange(hwnd);
                    boolean rf = redrawFrame(hwnd);
                    boolean np = Ext.INSTANCE.SendMessageW(h(hwnd), WM_NCPAINT, w(1), l(0));
                    boolean na = Ext.INSTANCE.SendMessageW(h(hwnd), WM_NCACTIVATE, w(1), l(0));
                    int fl = Dwm.INSTANCE.DwmFlush();
                    boolean flOk = fl == 0;
                    return "重算框架✓ 重画框架=" + rf + " WM_NCPAINT=" + np + " WM_NCACTIVATE=" + na
                            + " DwmFlush(HRESULT)=" + fl + (flOk ? "(S_OK)" : "(非0)");
                });

        plan(15, "★1px 轻推（模拟你手动拖一下）",
                "要填：无（用当前位置自动推）。\n"
                        + "步骤：把窗口**往右推 1px**（SWP_NOCOPYBITS → 不复制旧像素 ✓）→ 等 30ms → **推回原位**。\n"
                        + "原理：**移动**会触发系统重算框架并重画 ✓ —— 你手动拖一下灰框就没了 ✓，"
                        + "这里只是把那「一下」做成程序化的、净位移为 0 ✓。\n"
                        + "怎么摆窗口：**净几何不变** ✓（推出去又推回来 ✓）；状态也不动 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    int[] r = SwNativeOps.getVisualRect(hwnd);
                    if (r == null) return "取窗口矩形失败";
                    int x = r[0], y = r[1];
                    int w0 = r[2] - r[0], h0 = r[3] - r[1];
                    Ext.INSTANCE.SetWindowPos(h(hwnd), null, x + 1, y, w0, h0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOCOPYBITS);
                    sleep(30);
                    Ext.INSTANCE.SetWindowPos(h(hwnd), null, x, y, w0, h0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOCOPYBITS);
                    return "已 1px 轻推并复位（净位移 0 ✓ 模拟手动拖动 ✓）";
                });

        plan(16, "★Weixin 唤起 + 免激活摆位 + 修边框",
                "要填：尺寸 w/h ✓ 位移 dx/dy ✓（正数向右向上、负数向左向下）。\n"
                        + "步骤：ShowWindowAsync(SW_SHOW/SW_RESTORE) → 免激活摆位到 w×h 且平移 (dx,dy) → "
                        + "SWP_FRAMECHANGED → RedrawWindow(RDW_FRAME) → 1px 轻推复位。\n"
                        + "怎么摆窗口：**按你填的 w×h 摆位** ✓ 且摆位**不带激活** ✓（不会诱发 Electron 那种冻结 ✓），"
                        + "最后轻推一下把边框画干净 ✓。\n"
                        + "用途：**切窗场景** —— 唤醒 Weixin 后按「上一个窗口的正常态尺寸」摆到侧栏旁边 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    Ext.INSTANCE.ShowWindowAsync(h(hwnd), 5);
                    Ext.INSTANCE.ShowWindowAsync(h(hwnd), 9);
                    raise(hwnd);
                    String pl = place(hwnd, a[A_W], a[A_H], a[A_DX], a[A_DY]);
                    framechange(hwnd);
                    redrawFrame(hwnd);
                    nudge(hwnd);
                    return pl + "，重算框架✓ 重画框架✓ 轻推✓ 置前=" + foreground(hwnd);
                });

        plan(17, "老办法对照 + 修边框（现在的兜底）",
                "要填：无。\n"
                        + "步骤：**完整复刻现在的兜底**（保状态激活 + 不可见时在标题区合成双击 ✓）"
                        + "→ 紧接着跑「灰框专治连打 + 1px 轻推」 ✓。\n"
                        + "原理：老办法能把 Weixin 从托盘叫出来 ✓，但会留下大灰框 ✓（合成点击的副作用 ✓）；"
                        + "这行就是验证「**叫出来之后马上程序化地把框架修好**」能不能省掉你手动拖那一下 ✓。\n"
                        + "怎么摆窗口：不动几何/状态 ✓。\n"
                        + "⚠️ 会移动鼠标（合成双击 ✓）且可能留下短暂颜色态 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    boolean ok = SwNativeOps.restoreWindowAndActivate("Weixin", hwnd);
                    sleep(120);
                    framechange(hwnd);
                    boolean rf = redrawFrame(hwnd);
                    Ext.INSTANCE.SendMessageW(h(hwnd), WM_NCPAINT, w(1), l(0));
                    Ext.INSTANCE.SendMessageW(h(hwnd), WM_NCACTIVATE, w(1), l(0));
                    Dwm.INSTANCE.DwmFlush();
                    nudge(hwnd);
                    return "老办法=" + ok + "，随后修边框：重画框架=" + rf + "、NCPAINT✓、NCACTIVATE✓、轻推✓";
                });

        plan(18, "SetWindowPlacement 正规还原 + 修边框",
                "要填：无。\n"
                        + "步骤：读 GetWindowPlacement → showCmd 改 SW_SHOWNORMAL(1) → SetWindowPlacement → "
                        + "抬到最前 → 置前 → SWP_FRAMECHANGED → RedrawWindow(RDW_FRAME) → DwmFlush。\n"
                        + "原理：`SetWindowPlacement` 是**系统正规的还原路径** ✓（比 ShowWindow 更像「用户自己还原」 ✓），"
                        + "框架通常会被正确重画 ✓；后面再补一道修边框 ✓。\n"
                        + "怎么摆窗口：还原到它**自己的正常态**位置尺寸 ✓（`rcNormalPosition` ✓）；"
                        + "⚠️ 会取消最大化 ✓（标慎用 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    WinUser.WINDOWPLACEMENT wp = new WinUser.WINDOWPLACEMENT();
                    wp.length = wp.size();
                    if (!Ext.INSTANCE.GetWindowPlacement(h(hwnd), wp)) return "GetWindowPlacement 失败";
                    wp.showCmd = 1;
                    boolean ok = Ext.INSTANCE.SetWindowPlacement(h(hwnd), wp);
                    raise(hwnd);
                    boolean fg = foreground(hwnd);
                    framechange(hwnd);
                    boolean rf = redrawFrame(hwnd);
                    Dwm.INSTANCE.DwmFlush();
                    return "SetWindowPlacement=" + ok + "，置前=" + fg + "，重画框架=" + rf;
                });

        // ==================== 第二轮调研后续写（用户 2026-10-14 晚） ====================
        // 来源 ✓：[komorebi 架构剖析](https://raw.githubusercontent.com/AegiosOT/YTile/main/docs/komorebi-architecture-digest.md)
        //   —— 一个成熟 Windows 平铺窗管对"顽固窗口"的处理总结 ✓。
        // 两条实证 ✓：①前台锁绕过的标准配方（假输入 + HWND_TOP + SetForegroundWindow + 置 0 前台锁超时 ✓）；
        //            ②`DwmSetWindowAttribute(DWMWA_CLOAK)` 对**别人的窗口**返回 E_ACCESSDENIED ✗
        //              → 灰框**不能**靠强解遮蔽 ✗，只能**检测** ✓（方案 20 就是检测它 ✓）。
        // 另有一条来自用户实测的推论 ✓：兜底（**合成点击消息**）有效、而真实 `mouse_event` 无效 ✓
        //   → 方案 21 改用"**把点击消息直接 Post 进客户区**" ✓（不移动鼠标 ✓ 不抢前台 ✓）。

        plan(19, "★前台锁绕过（komorebi 配方）",
                "要填：无。\n"
                        + "步骤：SystemParametersInfo(SPI_SETFOREGROUNDLOCKTIMEOUT, 0) → "
                        + "SendInput 一个**假鼠标移动**（对我们自己进程 ✓ 用来解除「调用者无输入」限制 ✓）→ "
                        + "SetWindowPos(HWND_TOP, NOSIZE|NOMOVE|NOACTIVATE) → SetForegroundWindow。\n"
                        + "原理：专业窗管（komorebi）激活窗口用的就是这条配方 ✓ —— "
                        + "先用假输入让系统认为「你刚有输入」 ✓，再置顶 + 置前 ✓，成功率远高于裸的 SetForegroundWindow ✓。\n"
                        + "怎么摆窗口：不动几何/状态 ✓（只抢前台 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    // ① 把前台锁超时置 0（进程级 ✓ 只调一次也无害 ✓）
                    IntByReference old = new IntByReference();
                    boolean spiSet = Ext.INSTANCE.SystemParametersInfoW(0x2001 /*SPI_SETFOREGROUNDLOCKTIMEOUT*/,
                            0, new com.sun.jna.ptr.PointerByReference(com.sun.jna.Pointer.createConstant(0)), 0);
                    Ext.INSTANCE.SystemParametersInfoW(0x2000 /*SPI_GETFOREGROUNDLOCKTIMEOUT*/, 0, old, 0);
                    // ② 假输入（鼠标移动 0 像素 ✓）
                    mouseMove(0, 0);
                    // ③ 置顶 + 置前
                    Ext.INSTANCE.SetWindowPos(h(hwnd), null, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW);
                    boolean fg = foreground(hwnd);
                    return "前台锁超时置0=" + spiSet + "（原值 " + old.getValue() + "ms），假输入✓，置顶✓，置前=" + fg;
                });

        plan(20, "诊断 · 是否被 DWM 遮蔽(Cloak) + 阴影矩形",
                "要填：无。\n"
                        + "读三项：①DWMWA_CLOAKED（**该窗口是否被 DWM 整窗遮蔽** ✓ 被遮蔽时就是一片灰/空 ✗）"
                        + "②DWMWA_EXTENDED_FRAME_BOUNDS（**真正被绘制的区域** ✓）"
                        + "③GetWindowRect（含不可见阴影的**外框** ✓）→ 算两者差（窗管叫它 shadow rect ✓）。\n"
                        + "原理：**灰框有两种可能** ✓：(a) 窗口被 DWM 遮蔽（cloaked ✓→ 那一片就是「没画」 ✗）；"
                        + "(b) 外框与绘制区不一致（阴影/非客户区算错 ✓）。这行先告诉我们到底是哪种 ✓。\n"
                        + "⚠️ 来源结论：**不能**用 `DwmSetWindowAttribute(DWMWA_CLOAK)` 强解别人的窗口 ✗（返回 E_ACCESSDENIED ✓）→ 这行只做检测 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    IntByReference cloak = new IntByReference(-1);
                    int c1 = Dwm.INSTANCE.DwmGetWindowAttribute(h(hwnd), 14 /*DWMWA_CLOAKED*/,
                            cloak.getPointer(), 4);
                    WinDef.RECT fr = new WinDef.RECT();
                    int c2 = Dwm.INSTANCE.DwmGetWindowAttribute(h(hwnd), 9 /*DWMWA_EXTENDED_FRAME_BOUNDS*/,
                            fr.getPointer(), fr.size());
                    WinDef.RECT wr = new WinDef.RECT();
                    boolean c3 = Ext.INSTANCE.GetWindowRect(h(hwnd), wr);
                    String s = "cloaked=" + (c1 == 0 ? cloak.getValue() : -1) + "（1/2/4=被遮蔽 ✗ 0=正常 ✓）"
                            + " | 绘制区=" + (c2 == 0 ? fr.left + "," + fr.top + " " + (fr.right - fr.left) + "x"
                                    + (fr.bottom - fr.top) : "?")
                            + " | 外框=" + (c3 ? wr.left + "," + wr.top + " " + (wr.right - wr.left) + "x"
                                    + (wr.bottom - wr.top) : "?")
                            + " | 阴影差=" + (c2 == 0 && c3 ? (wr.left - fr.left) + "/" + (wr.top - fr.top) : "?");
                    LOG.info("[测试台] {}", s);
                    return s;
                });

        plan(21, "★客户区合成点击（不移动鼠标）",
                "要填：无。\n"
                        + "步骤：算出**客户区中心**（ClientToScreen ✓）→ PostMessageW(WM_LBUTTONDOWN/UP, MK_LBUTTON, 客户区坐标) "
                        + "→ 抬到最前 → 置前 → 修边框。\n"
                        + "原理：你实测的关键线索 ✓ —— **兜底那种「合成点击消息」能解冻微信 ✓，而我方案 6 用的真实 "
                        + "`mouse_event` 不行 ✗**。这行就是把「合成点击」从**标题区**（兜底的位置 ✓）搬到**客户区中心** ✓，"
                        + "既解冻、又不移动你的鼠标 ✓、也不会留下标题栏「被按住」的颜色态 ✓。\n"
                        + "怎么摆窗口：不动几何/状态 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    WinDef.RECT cr = new WinDef.RECT();
                    if (!Ext.INSTANCE.GetClientRect(h(hwnd), cr)) return "GetClientRect 失败";
                    int cx = (cr.right - cr.left) / 2, cy = (cr.bottom - cr.top) / 2;
                    int lp = (cy << 16) | (cx & 0xFFFF);
                    Ext.INSTANCE.PostMessageW(h(hwnd), 0x0201 /*WM_LBUTTONDOWN*/, w(0x0001 /*MK_LBUTTON*/), l(lp));
                    sleep(40);
                    Ext.INSTANCE.PostMessageW(h(hwnd), 0x0202 /*WM_LBUTTONUP*/, w(0), l(lp));
                    raise(hwnd);
                    boolean fg = foreground(hwnd);
                    framechange(hwnd);
                    redrawFrame(hwnd);
                    return "已向客户区 (" + cx + "," + cy + ") 合成点击，置前=" + fg + "，并修边框✓";
                });

        plan(22, "异步摆位 + 框架重算（不阻塞）",
                "要填：尺寸 w/h ✓ 位移 dx/dy ✓（正数向右向上、负数向左向下）。\n"
                        + "步骤：ShowWindowAsync(SW_SHOW/RESTORE) → "
                        + "SetWindowPos(**SWP_ASYNCWINDOWPOS**|NOACTIVATE|NOCOPYBITS|FRAMECHANGED) 摆到 w×h 且平移 (dx,dy) → 1px 轻推复位。\n"
                        + "原理：专业窗管的摆位标配是 **ASYNCWINDOWPOS + NOCOPYBITS + FRAMECHANGED** ✓ —— "
                        + "异步（不阻塞、不等目标线程 ✓）＋不复制旧像素（避免把灰框搬过来 ✓）＋重算框架（重画 ✓）。"
                        + "对「目标忙/卡」的窗口，这比同步摆位稳 ✓。\n"
                        + "怎么摆窗口：**按你填的 w×h 摆位并平移 (dx,dy)** ✓；不动最大化状态 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    Ext.INSTANCE.ShowWindowAsync(h(hwnd), 5);
                    Ext.INSTANCE.ShowWindowAsync(h(hwnd), 9);
                    int[] r = SwNativeOps.getVisualRect(hwnd);
                    if (r == null) return "取窗口矩形失败";
                    int w0 = a[A_W] > 0 ? a[A_W] : (r[2] - r[0]);
                    int h0 = a[A_H] > 0 ? a[A_H] : (r[3] - r[1]);
                    int x = r[0] + a[A_DX];
                    int y = r[1] - a[A_DY];
                    boolean ok = Ext.INSTANCE.SetWindowPos(h(hwnd), null, x, y, w0, h0,
                            SWP_NOACTIVATE | SWP_NOCOPYBITS | SWP_FRAMECHANGED | SWP_ASYNCWINDOWPOS);
                    nudge(hwnd);
                    return (ok ? "已异步摆位 " : "异步摆位失败 ") + x + "," + y + " " + w0 + "x" + h0
                            + "，并 1px 轻推✓";
                });

        // ==================== 第三轮续写（实测只有兜底有效 → 转向"微信自己的通道"） ====================
        // 关键推论 ✓：一堆"外部强制"手法全无效 ✗，唯独**合成双击标题栏**（一次真实用户动作 ✓）有效 ✓
        //   → 微信认的是"**它自己被用户召唤的路径**" ✓（与 QQNT 认托盘消息同一类 ✓）。
        // 所以下面两条都是"**替用户做那个动作**" ✓：
        //   23 = 按微信自己的**全局热键**（默认 Ctrl+Alt+W「打开/隐藏微信」✓）
        //   24 = **真去点它的托盘图标**（`Shell_NotifyIconGetRect` 找到图标矩形再真点击 ✓）
        // 资料 ✓：[只调出微信](http://getquicker.net/Common/Topics/ViewTopic/32288)、
        //        [微信显示/隐藏快捷键](https://xoofee.github.io/posts/2026/06/ubuntu-wechat-toggle-shortcut/)

        plan(23, "★微信全局热键调出（Ctrl+Alt+W）",
                "要填：无。\n"
                        + "步骤：模拟按下 **Ctrl+Alt+W**（微信默认「打开/隐藏微信」热键 ✓）→ 抬到最前 → 置前 → 修边框。\n"
                        + "原理：这是**微信自己的召唤通道** ✓ —— 等于你亲手按了那个热键 ✓，"
                        + "它内部会走「真正把主窗口显示出来」的流程 ✓（不是被外部 ShowWindow 硬拉 ✗ → 那种才会冻住 ✓）。\n"
                        + "怎么摆窗口：不动几何/状态 ✓。\n"
                        + "⚠️ 若你在微信设置里改过这个热键 ✗，告我一声，我按你的键改 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    hotkeyCtrlAltW();
                    sleep(150);
                    raise(hwnd);
                    boolean fg = foreground(hwnd);
                    framechange(hwnd);
                    redrawFrame(hwnd);
                    return "已发送 Ctrl+Alt+W，抬升✓ 置前=" + fg + "，修边框✓";
                });

        plan(24, "★真点托盘图标（原生版托盘法）",
                "要填：无（图标 id 自动枚举 0~20 试 ✓）。\n"
                        + "步骤：遍历**目标进程**的顶层窗口 × 图标 id 0~20，用 `Shell_NotifyIconGetRect` 找**托盘图标矩形** ✓ "
                        + "→ 找到就把鼠标移过去**真点一下左键**（点完把鼠标位置还原 ✓）→ 再抬升 + 置前 + 修边框。\n"
                        + "原理：这就是**你手动点托盘图标**那一下 ✓ —— 微信收到的是它**自己的托盘回调** ✓，"
                        + "与 QQNT 那条 `WM_APP+1` 同一个道理 ✓（原生程序没有 Electron 宿主窗口，所以必须真点 ✓）。\n"
                        + "怎么摆窗口：不动几何/状态 ✓。\n"
                        + "⚠️ 会挪一下你的鼠标（点完还原 ✓）；图标在折叠区里也能拿到位置 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    int[] icon = findTrayIconRect(hwnd);
                    if (icon == null) return "没找到该进程的托盘图标矩形（图标可能被删了或不在通知区 ✓）";
                    int cx = (icon[0] + icon[2]) / 2, cy = (icon[1] + icon[3]) / 2;
                    int[] old = new int[2];
                    boolean saved = Ext.INSTANCE.GetCursorPos(old);
                    Ext.INSTANCE.SetCursorPos(cx, cy);
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0002, 0, 0, 0, null);
                    sleep(40);
                    Ext.INSTANCE.mouse_event(0x0004, 0, 0, 0, null);
                    sleep(200);
                    if (saved) Ext.INSTANCE.SetCursorPos(old[0], old[1]);
                    raise(hwnd);
                    boolean fg = foreground(hwnd);
                    framechange(hwnd);
                    redrawFrame(hwnd);
                    return "已点托盘图标 (" + cx + "," + cy + ")" + (saved ? "（鼠标已还原 ✓）" : "")
                            + "，置前=" + fg + "，修边框✓";
                });

        // ==================== 第四轮续写（用户关键线索 ✓） ====================
        // 用户实测 ✓：**鼠标真拖动窗口 → 黑框消失 ✓；但"1px 轻推"(SetWindowPos) → 窗口动了、黑框不消 ✗**
        // 推论 ✓（决定性 ✓）：真实拖动会让系统进入**模态移动循环** ✓
        //   （`WM_ENTERSIZEMOVE` → 一串 `WM_MOVING`/`WM_SIZE` → `WM_EXITSIZEMOVE` ✓），
        //   微信的渲染器**认这个"正在被用户拖动"的状态**才会恢复出帧 ✓；
        //   而 `SetWindowPos` **完全绕过**该循环 ✗ → 渲染器照旧睡着 ✓ → 黑框不消 ✓✓
        // 所以下面三条都是围绕"**把那个模态循环补上**"：
        //   25 = 手工补 `WM_ENTERSIZEMOVE/EXITSIZEMOVE` 消息（不动鼠标 ✓ 最轻 ✓）
        //   26 = 用真实输入**做一次微型真实拖动**（最忠实于"用户拖动" ✓ 会挪一下鼠标 ✓）
        //   27 = **兜底增强版**：先双击解冻（唯一有效 ✓）再微拖清框（唯一能消黑框 ✓）→ 副作用清零 ✓

        plan(25, "★补模态移动循环（WM_ENTERSIZEMOVE）",
                "要填：无。\n"
                        + "步骤：SendMessage(WM_ENTERSIZEMOVE) → 尺寸抖 ±1px（在循环「内」动一下 ✓）→ "
                        + "SendMessage(WM_EXITSIZEMOVE) → WM_SIZE/WM_MOVE 补一发 → 修边框连打。\n"
                        + "原理：**这是你说的「拖动才消黑框」的程序化版本** ✓ —— 真实拖动会让系统进入模态移动循环 ✓，"
                        + "应用据此把渲染器切回「正在被拖动」的出帧模式 ✓；`SetWindowPos` 没有这个循环 ✗ 所以没用 ✓。\n"
                        + "怎么摆窗口：抖动后**还原原尺寸与位置** ✓（净几何不变 ✓）；不动状态 ✓。\n"
                        + "优点：**不动鼠标** ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    Ext.INSTANCE.SendMessageW(h(hwnd), 0x0231 /*WM_ENTERSIZEMOVE*/, w(0), l(0));
                    String j = jiggle(hwnd);
                    nudge(hwnd);
                    Ext.INSTANCE.SendMessageW(h(hwnd), 0x0232 /*WM_EXITSIZEMOVE*/, w(0), l(0));
                    int[] r = SwNativeOps.getVisualRect(hwnd);
                    if (r != null) {
                        int w0 = r[2] - r[0], h0 = r[3] - r[1];
                        Ext.INSTANCE.PostMessageW(h(hwnd), 0x0005 /*WM_SIZE*/, w(0),
                                l((h0 << 16) | (w0 & 0xFFFF)));
                        Ext.INSTANCE.PostMessageW(h(hwnd), 0x0003 /*WM_MOVE*/, w(0), l((r[1] << 16) | (r[0] & 0xFFFF)));
                    }
                    framechange(hwnd);
                    redrawFrame(hwnd);
                    Dwm.INSTANCE.DwmFlush();
                    return "已补 ENTERSIZEMOVE→" + j + "→EXITSIZEMOVE，并修边框✓";
                });

        plan(26, "★微型真实拖动（最忠实于手动拖）",
                "要填：无。\n"
                        + "步骤：记下原矩形 → 把鼠标移到**标题栏**并按左键 → 向右拖 6px → 再拖回原位 → 松开左键 → "
                        + "把窗口矩形按原值校正一次 → 修边框。净位移 0 ✓。\n"
                        + "原理：**你说的「手动拖一下就好」就是这个动作** ✓ —— 这里用真实输入复刻它 ✓，"
                        + "让系统进入模态移动循环 ✓、让微信的渲染器真正恢复出帧 ✓。\n"
                        + "怎么摆窗口：拖完**回到原位与原尺寸** ✓（微小的偏差会用 SetWindowPos 校正 ✓）。\n"
                        + "⚠️ 会挪一下你的鼠标（拖完还原位置 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    int[] r = SwNativeOps.getVisualRect(hwnd);
                    if (r == null) return "取窗口矩形失败";
                    int x0 = r[0], y0 = r[1], w0 = r[2] - r[0], h0 = r[3] - r[1];
                    int[] old = new int[2];
                    boolean saved = Ext.INSTANCE.GetCursorPos(old);
                    // 在标题栏按下 → 微拖 → 拖回 → 松开（真实输入 ✓ 触发模态移动循环 ✓）
                    Ext.INSTANCE.SetCursorPos(x0 + 60, y0 + 8);
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0002, 0, 0, 0, null);      // LEFTDOWN
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0001, 6, 0, 0, null);      // MOVE 右 6px
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0001, -6, 0, 0, null);     // MOVE 回原位
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0004, 0, 0, 0, null);      // LEFTUP
                    sleep(120);
                    if (saved) Ext.INSTANCE.SetCursorPos(old[0], old[1]);
                    setWindowPos(hwnd, x0, y0, w0, h0, 0);                // 校正回原矩形 ✓
                    framechange(hwnd);
                    redrawFrame(hwnd);
                    Dwm.INSTANCE.DwmFlush();
                    return "已微型真实拖动（净位移 0 ✓）并校正回原矩形 ✓，修边框✓";
                });

        plan(27, "★★兜底增强版：双击解冻 + 微拖清框",
                "要填：无。\n"
                        + "步骤：①**先用兜底**（保状态激活 + 不可见时标题区合成双击 ✓ 实测唯一能解冻 ✓）"
                        + "→ ②再跑**微型真实拖动**（实测唯一能消黑框 ✓）→ ③修边框连打。\n"
                        + "原理：把两条「实测有效」的拼起来 ✓ —— 双击负责**解冻** ✓、微拖负责**清黑框** ✓，"
                        + "这样就能把老办法的副作用（那圈黑/灰框 ✓）去掉 ✓，不用你手动补一下 ✓。\n"
                        + "怎么摆窗口：不动几何/状态 ✓（拖动已校正回原矩形 ✓）。\n"
                        + "⚠️ 会挪一下鼠标（会还原 ✓）；会有一次合成双击的颜色态（老办法本来就有 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    boolean ok = SwNativeOps.restoreWindowAndActivate("Weixin", hwnd);   // ① 解冻 ✓
                    sleep(150);
                    int[] r = SwNativeOps.getVisualRect(hwnd);
                    if (r == null) return "兜底已执行=" + ok + "，但取矩形失败";
                    int x0 = r[0], y0 = r[1], w0 = r[2] - r[0], h0 = r[3] - r[1];
                    int[] old = new int[2];
                    boolean saved = Ext.INSTANCE.GetCursorPos(old);
                    Ext.INSTANCE.SetCursorPos(x0 + 60, y0 + 8);           // ② 微拖清框 ✓
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0002, 0, 0, 0, null);
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0001, 6, 0, 0, null);
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0001, -6, 0, 0, null);
                    sleep(60);
                    Ext.INSTANCE.mouse_event(0x0004, 0, 0, 0, null);
                    sleep(120);
                    if (saved) Ext.INSTANCE.SetCursorPos(old[0], old[1]);
                    setWindowPos(hwnd, x0, y0, w0, h0, 0);                // 校正 ✓
                    framechange(hwnd);
                    redrawFrame(hwnd);
                    Ext.INSTANCE.SendMessageW(h(hwnd), WM_NCPAINT, w(1), l(0));
                    Dwm.INSTANCE.DwmFlush();
                    return "兜底(双击)=" + ok + " + 微拖清框✓ + 校正✓ + 修边框✓";
                });

        // ==================== 第五轮续写（用户 2026-10-14 亲测有效的三条交互序列 ✓） ====================
        // 用户实证 ✓（三条都能"先出黑框、再去掉黑框、窗口激活" ✓）：
        //   ① hwnd 唤醒 → **双击 → 再双击**标题栏
        //   ② hwnd 唤醒 → 点**最大化按钮 → 再点一次**（最大化↔还原 走一遍）
        //   ③ hwnd 唤醒 → 点**最小化按钮 → 再恢复**
        // 共性 ✓：都是**微信自己控件的点击** ✓（走它自己的命中判定/消息处理 ✓）→ 它才会唤醒渲染器 ✓；
        //   这也解释了为什么"外部强制"全无效 ✗（前几轮结论 ✓）。
        // 实现 ✓：唤醒用**纯净版**（只还原/抬升/置前 ✓ 不含合成点击 ✗ 免得和序列里的点击撞车 ✓）；
        //   点击一律用 `SwNativeOps.clickInWindow`（**投递点击消息** ✓ 实测有效的那一种 ✓ 不是真实鼠标 ✗）。

        plan(28, "★双击 + 再双击标题栏（用户实证① · 计时）",
                "要填：无。\n"
                        + "步骤：纯净唤醒（最小化才还原 + 抬升 + 置前 ✓）→ 标题栏 (8,8) **双击** → 停 350ms → **再双击** → 停 200ms → 抬升 ✓。\n"
                        + "原理：你的亲测① ✓ —— 两次双击 = 让微信自己的标题栏命中判定跑两遍 ✓（先出黑框、再去掉 ✓）→ 渲染器被唤醒 ✓。\n"
                        + "怎么摆窗口：双击标题栏在微信里等价于最大化↔还原 ✓ 跑两遍 → **净状态不变** ✓。\n"
                        + "📊 会打印**总耗时(ms)** ✓ —— 与方案 38（点按钮）**等待时间完全一致**（350+200 ✓）✓"
                        + "，所以两者的差值就是**机制本身的快慢** ✓ 这正是你要的对比 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    long t0 = System.currentTimeMillis();
                    pureWake(hwnd);
                    clickTwice(hwnd, 8, 8);
                    sleep(350);
                    clickTwice(hwnd, 8, 8);
                    sleep(200);
                    raise(hwnd);
                    long ms = System.currentTimeMillis() - t0;
                    return "耗时=" + ms + "ms；标题栏双击 ×2 ✓，置前=" + foreground(hwnd);
                });

        // ⚠️ 原 29/30（"**按坐标**点最大化/最小化按钮"）**已删除** ✗ —— 用户 2026-10-14 指出：
        //   各版本标题栏布局不同 → 坐标法不通用 ✓；要用就该用**控件**（UIA）去点 ✓。
        //   下面的 29 是"**无坐标的命令行版**"（发系统命令 ✓ 比坐标稳 ✓ 但仍**不是**点控件 ✗）；
        //   真正的"控件点击"（UIA FindFirst + InvokePattern.Invoke ✓）需要扩 `swcore.UiaOps`
        //   （它目前**只读属性、不做树遍历** ✗）→ 作为下一步单独做 ✓。

        plan(29, "★系统命令版：最大化↔还原（无坐标）",
                "要填：无（**完全不用坐标** ✓ 直接发系统命令 ✓）。\n"
                        + "步骤：纯净唤醒 → SendMessage(WM_SYSCOMMAND, **SC_MAXIMIZE**) → 停 300ms → "
                        + "SendMessage(WM_SYSCOMMAND, **SC_RESTORE**) → 抬升 + 置前 ✓。\n"
                        + "原理：这是「最大化按钮/还原按钮」在系统层面的等价命令 ✓（不是坐标 ✓，也不动你的鼠标 ✓）。\n"
                        + "⚠️ 差别 ✓：用户实证②是**点微信自己的按钮** ✓ 走它的自绘命中判定 ✓；"
                        + "这条是**发系统命令** ✓ —— 微信若没处理该命令，效果可能不同 ✓ 两条都留着对比 ✓。\n"
                        + "怎么摆窗口：最大化再还原 ✓ → 位置尺寸应回到原样 ✓（没回准用方案 3/16 摆一次 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    pureWake(hwnd);
                    Ext.INSTANCE.SendMessageW(h(hwnd), 0x0112 /*WM_SYSCOMMAND*/, w(0xF030 /*SC_MAXIMIZE*/), l(0));
                    sleep(300);
                    Ext.INSTANCE.SendMessageW(h(hwnd), 0x0112 /*WM_SYSCOMMAND*/, w(0xF120 /*SC_RESTORE*/), l(0));
                    sleep(200);
                    raise(hwnd);
                    return "已发送 SC_MAXIMIZE → SC_RESTORE，置前=" + foreground(hwnd);
                });

        plan(30, "★UIA 诊断：列出窗口的控件（精准定位）",
                "要填：无。\n"
                        + "做法：用 **UI Automation** 遍历目标窗口的**后代控件** ✓，打印每个控件的 "
                        + "`name / controlType / automationId / uiaClass / rect` ✓（最多 60 个 ✓）。\n"
                        + "原理：**「能精准就不要瞎猜位置」的第一步** ✓ —— 先看微信的最大化/还原/最小化按钮"
                        + "在 UIA 里**叫什么名字** ✓，后面方案 31/32 就按名字 `Invoke` ✓ 完全不用坐标 ✓。\n"
                        + "⚠️ UIA 是跨进程调用 ✓ 目标 UI 线程忙时可能慢/超时（项目已有 800ms 超时 + 熔断 ✓）。\n"
                        + "怎么摆窗口：不动几何/状态 ✓（只读 ✓）。",
                a -> {
                    java.util.List<String> lines = UiaOps.dumpDescendants(a[A_HWND]);
                    if (lines == null) return "UIA 列举失败（可能超时/熔断 ✓ 稍后再试）";
                    StringBuilder sb = new StringBuilder("UIA 后代控件 " + lines.size() + " 个：\n");
                    for (String s : lines) sb.append("  ").append(s).append('\n');
                    LOG.info("[测试台] {}", sb.toString().replace('\n', ' '));
                    return sb.toString();
                });

        plan(31, "（单次）UIA 点一次「最大化」按钮",
                "要填：无。\n"
                        + "步骤：纯净唤醒 → **只点一次** `class=mmui::XButton` + `name=最大化` ✓ → 停 400ms → 打印"
                        + "**点之前/之后的最大化状态** ✓（`isMaximized` ✓）与**命中的名字** ✓。**不点第二次** ✓、不还原 ✓。\n"
                        + "原理：**这是一条「到底点没点到」的判定测试** ✓ —— 你怀疑「卡住时点不动 ✗」或「我点错按钮了 ✗」 ✓，"
                        + "这条把变量降到只剩一个 ✓：如果点完后窗口**真的最大化了** ✓ → 说明 UIA 点击**有效** ✓（那 35 卡住就是别的原因 ✓）；"
                        + "如果**没有任何变化** ✗ → 要么该按钮在被冻住时不响应 ✗、要么命中的不是它 ✗（见日志里的命中名字 ✓）。\n"
                        + "怎么摆窗口：⚠️ **会留在最大化状态** ✓（用方案 3/16 或再点一次 31 可恢复 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    pureWake(hwnd);
                    boolean before = SwNativeOps.isMaximized(hwnd);
                    String hit = clickButtonByUia(hwnd, "最大化");
                    sleep(400);
                    boolean after = SwNativeOps.isMaximized(hwnd);
                    raise(hwnd);
                    String verdict = (before != after) ? "✓ 状态变了 → 这条路径**有效** ✓"
                            : "✗ 状态没变 → 位置或机制仍需调整 ✗";
                    return hit + "；最大化状态 " + before + " → " + after + "；" + verdict
                            + "；标题栏子控件=" + UiaOps.titleBarChildren(hwnd);
                });

        plan(32, "（单次）UIA 点一次「最小化」按钮",
                "要填：无。\n"
                        + "步骤：纯净唤醒 → **只点一次** `class=mmui::XButton` + `name=最小化` ✓ → 停 500ms → 打印"
                        + "**点之前/之后的最小化状态**（`isMinimized` ✓）与**命中的名字** ✓。**不自动恢复** ✓。\n"
                        + "原理：与 31 同一目的 ✓ —— 只验证「最小化按钮点得到吗」 ✓；"
                        + "若状态真的变成最小化 ✓ → UIA 点击有效 ✓（你手动还原即可 ✓）；"
                        + "若毫无变化 ✗ → 说明冻结状态下控件不响应 ✗（或命中错了 ✓ 看日志名字 ✓）。\n"
                        + "怎么摆窗口：⚠️ **窗口会最小化** ✓（任务栏点一下即可恢复 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    pureWake(hwnd);
                    boolean before = SwNativeOps.isMinimized(hwnd);
                    String hit = clickButtonByUia(hwnd, "最小化");
                    sleep(500);
                    boolean after = SwNativeOps.isMinimized(hwnd);
                    String verdict = (before != after) ? "✓ 状态变了 → 这条路径**有效** ✓"
                            : "✗ 状态没变 → 位置或机制仍需调整 ✗";
                    return hit + "；最小化状态 " + before + " → " + after + "；" + verdict
                            + "；标题栏子控件=" + UiaOps.titleBarChildren(hwnd);
                });

        // ==================== 第六轮续写（依用户给的微信 UIA 实况 ✓） ====================
        // 实况 ✓：微信 4.0 是 **Qt（mmui）** 应用 ✓；`uiaClass` 有值 ✓（mmui::XButton / mmui::XIcon … ✓）、
        //   `automationId` 全空 ✗、`name` 大多空 ✗；`controlType`/`rect` 我读的按序推下标**实测不准** ✗（弃用 ✓）。
        // ⇒ **按 `uiaClass` 找控件**才是正路 ✓（零坐标 ✓ 且不依赖名字 ✓）。

        plan(33, "★UIA 按类名列举（放开 60 上限）",
                "要填：无。\n"
                        + "做法：用 UIA 遍历**全部后代**（上限放宽到 1500 ✓），只打印 `uiaClass`/`name`/`automationId` ✓，"
                        + "并按一组关键字过滤：TitleBar / Window / Button / Tool / Close / Min / Max / Caption / Icon ✓。\n"
                        + "原理：你给的那份 dump 证明 ✓ —— 微信是 Qt 应用 ✓、**类名是填好的** ✓、名字/id 大多是空的 ✗；"
                        + "而标题栏按钮**不在前 60 条里** ✗ → 这条就是把它们捞出来 ✓（为 34 提供精确类名 ✓）。\n"
                        + "怎么摆窗口：只读 ✓ 不动几何/状态 ✓。",
                a -> {
                    java.util.List<String> lines = UiaOps.listByClassKeyword(a[A_HWND], 1500,
                            "TitleBar", "Window", "Button", "Tool", "Close", "Min", "Max", "Caption", "Icon");
                    if (lines == null) return "UIA 列举失败（可能超时/熔断 ✓）";
                    StringBuilder sb = new StringBuilder("命中 」 + lines.size() + 「 个（按类名过滤 ✓）：\n");
                    for (String s : lines) sb.append("  ").append(s).append('\n');
                    LOG.info("[测试台] {}", sb.toString().replace('\n', ' '));
                    return sb.toString();
                });

        plan(34, "★UIA 按类名调用：最大化/还原/最小化（零坐标）",
                "要填：无（**零坐标** ✓ 也不用名字 ✓）。\n"
                        + "步骤：纯净唤醒 → 依次按类名关键字调用控件：先试 最大化(Max) → 再试 还原(Restore/Normal) → "
                        + "（若需要）最小化(Min) ✓；每一步都打印命中的**类名** ✓ 便于继续校准 ✓。\n"
                        + "原理：微信的按钮没有名字 ✗ 但**有 Qt 类名** ✓ → 按类名 Invoke ✓ 就是「点控件」 ✓"
                        + "（与用户实证②/③等价 ✓ 但不依赖标题栏像素位置 ✓）。\n"
                        + "⚠️ 若某个关键字**没命中或命中了却点错** ✗ → 先跑 **33** 把它真实的类名发我 ✓，我改关键字 ✓"
                        + "（可改成精确类名匹配 ✓ 绝不瞎点 ✓）。\n"
                        + "怎么摆窗口：最大化↔还原 走一遍 ✓ 净状态不变 ✓；最小化那步随后用 SW_RESTORE 恢复 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    pureWake(hwnd);
                    String max = UiaOps.invokeByClassKeyword(hwnd, "XWindowMaxButton", "MaxButton", "Maximize", "Max");
                    sleep(250);
                    String restore = UiaOps.invokeByClassKeyword(hwnd, "XWindowRestoreButton", "RestoreButton",
                            "Restore", "Normal");
                    sleep(200);
                    raise(hwnd);
                    return "最大化命中=" + max + "，还原命中=" + restore + "，置前=" + foreground(hwnd);
                });

        // ==================== 第七轮续写（用户用 UISpy 给出**精确类名+名字** ✓） ====================
        // 实况 ✓：微信 4.0 的标题栏按钮 = `mmui::XButton` +
        //   `Name = 最小化 / 最大化 / 关闭` ✓（UISpy 实证 ✓；我先前 60 条上限没捞到 ✓）
        // ⇒ 用**完全相等**匹配（类名 + 名字）✓ —— 不用"包含"（会误点「隐藏窗口截图」✗）也不用坐标 ✓

        plan(35, "序列② hwnd唤醒 + 两次最大化（UIA 精确点按钮）",
                "要填：无（**零坐标、零猜测** ✓）。\n"
                        + "步骤：①纯净唤醒（= hwnd 唤醒 ✓）→ ②**点最大化按钮**：先按名字精确点 "
                        + "`class=mmui::XButton, name=最大化` ✓，没命中就按**标题栏位置**兜底 "
                        + "（`mmui::TitleBar` 的子控件从末尾数第 2 个 ✓ **与语言无关** ✓）→ ③ 停 350ms → **再点同一个按钮**"
                        + "（此时它是「还原」：依次试 向下还原/还原/最大化，再兜底按位置 ✓）→ 抬升 ✓。\n"
                        + "原理：**就是你的实证②** ✓ ——「最大化 → 再点一次」走一遍微信自己的命令处理 ✓ → 黑框消失、窗口激活 ✓；"
                        + "只是把「点按钮」从坐标改成了 **UIA 点控件** ✓。\n"
                        + "怎么摆窗口：最大化↔还原 各一次 ✓ → 净状态不变 ✓。\n"
                        + "⚠️ 英文版 ✓：`Name` 是本地化文本 ✗ 不可靠 → 所以这条**必须**带按位置的兜底 ✓",
                a -> {
                    int hwnd = a[A_HWND];
                    pureWake(hwnd);
                    String max = UiaOps.invokeButtonExact(hwnd, "mmui::XButton", "最大化");
                    if (max == null) max = "位置兜底:" + UiaOps.invokeTitleBarButtonByIndex(hwnd, 1);
                    sleep(350);
                    String back = UiaOps.invokeButtonExact(hwnd, "mmui::XButton", "向下还原", "还原", "最大化");
                    if (back == null) back = "位置兜底:" + UiaOps.invokeTitleBarButtonByIndex(hwnd, 1);
                    sleep(200);
                    raise(hwnd);
                    return "第1次(最大化)=" + max + "，第2次(还原)=" + back + "，置前=" + foreground(hwnd);
                });

        plan(36, "序列③ hwnd唤醒 + 最小化→恢复（UIA 精确点按钮）",
                "要填：无。\n"
                        + "步骤：①纯净唤醒 → ②点**最小化按钮**：先按名字精确点 `class=mmui::XButton, name=最小化` ✓，"
                        + "没命中就按**标题栏位置**兜底（从末尾数第 3 个 ✓ 与语言无关 ✓）→ ③ 停 450ms → "
                        + "`SW_RESTORE` 恢复 + 抬升 + 置前 ✓。\n"
                        + "原理：**就是你的实证③** ✓ ——「最小化 → 再恢复」让微信走一遍它自己的显示切换 ✓ → 黑框消失 ✓；"
                        + "点按钮改用 UIA 控件 ✓（不是坐标 ✗）。\n"
                        + "怎么摆窗口：恢复后按 `rcNormalPosition` 还原 ✓（没回准可用方案 3/16 ✓）。",
                a -> {
                    int hwnd = a[A_HWND];
                    pureWake(hwnd);
                    String hit = UiaOps.invokeButtonExact(hwnd, "mmui::XButton", "最小化");
                    if (hit == null) hit = "位置兜底:" + UiaOps.invokeTitleBarButtonByIndex(hwnd, 2);
                    sleep(450);
                    if (hit != null && !hit.endsWith("null")) SwNativeOps.restoreWindowOnly(hwnd);
                    raise(hwnd);
                    return "最小化=" + hit + "，已恢复，置前=" + foreground(hwnd);
                });

        // ==================== 第八轮续写：方案 A（用户 2026-10-15 选定 ✓） ====================
        // 目的 ✓（用户原话）：**对比「点按钮」与「双击×2」哪个最快最无感** ✓ → 两条都做 ✓ 并打印**耗时** ✓。
        // 依据 ✓（我自己跑探针得到 ✓）：标题栏 = `mmui::TitleBar`，**恰好 4 个标准右对齐子控件**
        //   `[0]置顶 [1]最小化 [2]最大化 [3]关闭` ✓；UIA **不给几何** ✗（矩形全空 ✓ 已证 ✓）
        //   → 按**窗口矩形 + 标准标题栏按钮排布**算位置 ✓（有据可依 ✓ 不是随机猜 ✗）。

        plan(38, "方案A · 点「最大化」按钮（结构算位 + 计时）",
                "要填：无。\n"
                        + "步骤：纯净唤醒 → **按窗口矩形算**右上角按钮位置（标准 46×32 右对齐 ✓：关闭最右 ✓、"
                        + "最大化为其左一格 ✓）→ 发一次点击 → 停 350ms → **再点同一位置**（此时是还原 ✓）→ 抬升 ✓。\n"
                        + "原理：**方案 A** ✓ —— 用「标题栏结构」（探针已证：4 个标准右对齐子控件 ✓）算位置 ✓，"
                        + "不依赖 UIA 几何（微信不给 ✗）也不手填像素 ✓；与用户实证②同一套动作 ✓。\n"
                        + "怎么摆窗口：最大化→还原 各一次 ✓ 净状态不变 ✓。\n"
                        + "📊 结果会打印**总耗时(ms)** ✓ 可与方案 28 直接对比 ✓。\n"
                        + "⚠️ 若点偏了（DPI≠100% 或版本改了按钮尺寸 ✓）→ 告我偏差方向 ✓ 我调 46/32 两个常数 ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    long t0 = System.currentTimeMillis();
                    pureWake(hwnd);
                    boolean before = SwNativeOps.isMaximized(hwnd);
                    String r1 = clickCaptionButton(hwnd, 2);            // [2] = 最大化 ✓
                    sleep(350);
                    String r2 = clickCaptionButton(hwnd, 2);            // 此时该格是「还原」✓
                    sleep(200);
                    raise(hwnd);
                    boolean after = SwNativeOps.isMaximized(hwnd);
                    long ms = System.currentTimeMillis() - t0;
                    return "耗时=" + ms + "ms；" + r1 + "；" + r2 + "；最大化 " + before + " → " + after
                            + (before == after ? " ✓净状态不变" : " ⚠状态变了");
                });

        plan(39, "方案A · 点「最小化」按钮 + 恢复（结构算位 + 计时）",
                "要填：无。\n"
                        + "步骤：纯净唤醒 → 按窗口矩形算**最小化**按钮位置（[1] = 关闭左边两格 ✓）→ 发一次点击 → "
                        + "停 450ms → `SW_RESTORE` 恢复 + 抬升 + 置前 ✓。\n"
                        + "原理：同 38 ✓（**方案 A** ✓ 结构算位 ✓）；这是用户实证③的程序化版 ✓。\n"
                        + "怎么摆窗口：恢复后按 `rcNormalPosition` 还原 ✓（没回准可用方案 3/16 ✓）。\n"
                        + "📊 会打印**总耗时(ms)** ✓。",
                a -> {
                    int hwnd = a[A_HWND];
                    long t0 = System.currentTimeMillis();
                    pureWake(hwnd);
                    String r = clickCaptionButton(hwnd, 1);             // [1] = 最小化 ✓
                    sleep(450);
                    boolean min = SwNativeOps.isMinimized(hwnd);
                    SwNativeOps.restoreWindowOnly(hwnd);
                    raise(hwnd);
                    long ms = System.currentTimeMillis() - t0;
                    return "耗时=" + ms + "ms；" + r + "；点击后 最小化=" + min + "；已恢复 ✓ 置前=" + foreground(hwnd);
                });
    }

    /**
     * **按「标题栏结构」点击右上角第 {@code slot} 个按钮** ✓（方案 A ✓）.
     *
     * <p>依据 ✓（我自己跑探针实测 ✓）：微信标题栏 = `mmui::TitleBar`，4 个**标准右对齐**子控件
     * → 从右往左：`[3]关闭`、`[2]最大化/还原`、`[1]最小化`、`[0]置顶` ✓。
     * <p>按钮标准尺寸按 **46×32**（Win 标准 caption 按钮 ≈ 45×30 ✓ 取整便于算 ✓）；位置 = 客户区右上角 ✓。
     * <p>⚠️ DPI ≠ 100% 或版本改了按钮宽度时会偏 ✓ → 两个常数 {@link #CAPTION_BTN_W}/{@link #CAPTION_BTN_H} 可直接调 ✓。
     *
     * @param slot 1=最小化 ✓ 2=最大化/还原 ✓ 3=关闭 ✓
     */
    private static String clickCaptionButton(int hwnd, int slot) {
        WinDef.RECT cr = new WinDef.RECT();
        if (!Ext.INSTANCE.GetClientRect(h(hwnd), cr)) return "GetClientRect 失败";
        int cw = cr.right - cr.left;
        int cx = cw - (3 - slot) * CAPTION_BTN_W - CAPTION_BTN_W / 2;   // slot3=最右 ✓ slot1=往左两格 ✓
        int cy = CAPTION_BTN_H / 2;
        SwNativeOps.clickInWindow(hwnd, cx, cy);                        // 发真实点击消息 ✓（实测有效 ✓）
        LOG.info("[测试台] 方案A 点标题栏按钮 slot={} 客户区=({},{}) 客户区宽={} 按钮={}x{}",
                slot, cx, cy, cw, CAPTION_BTN_W, CAPTION_BTN_H);
        return "点击 slot" + slot + " @客户区(" + cx + "," + cy + ")";
    }

    /** 标题栏按钮标准尺寸（方案 A 的两个可调常数 ✓） */
    private static final int CAPTION_BTN_W = 46;
    private static final int CAPTION_BTN_H = 32;

    /**
     * **按 UIA 给的精确位置发点击**（微信正解 ✓ 用户 2026-10-14 实测定性）.
     *
     * <p>实测链条 ✓：① UIA 按名字精确命中"最大化"按钮 ✓（`class=mmui::XButton` ✓）；
     * ② `InvokePattern.Invoke()` 返回成功 ✓ 但窗口状态 `false → false` 没变 ✗ ⇒ **微信的 Invoke 是空操作** ✗；
     * ③ 而用户**用鼠标真点**同样位置却有效 ✓ ⇒ 微信只认**真实点击消息** ✓。
     * <p>所以：**位置用 UIA 精确取**（`BoundingRectangle` / `ClickablePoint` ✓）→ 换算成客户区坐标 →
     * 发**点击消息**（`clickInWindow` ✓ 与老兜底同一机制 ✓）。**全程不猜像素** ✓。
     *
     * @return 一句话结果（含取到的坐标 ✓ 便于核对）
     */
    private static String clickButtonByUia(int hwnd, String exactName) {
        int[] r = UiaOps.buttonScreenRect(hwnd, "mmui::XButton", exactName);
        if (r == null) return "取不到「" + exactName + "」按钮位置（UIA 属性下标可能需校正）";
        int sx = (r[0] + r[2]) / 2, sy = (r[1] + r[3]) / 2;
        WinDef.POINT pt = new WinDef.POINT(sx, sy);
        if (!Ext.INSTANCE.ScreenToClient(h(hwnd), pt)) return "ScreenToClient 失败";
        int cx = pt.x, cy = pt.y;
        SwNativeOps.clickInWindow(hwnd, cx, cy);          // 发真实点击消息 ✓（不是 UIA Invoke ✗）
        LOG.info("[测试台] 按 UIA 位置点击：{} 屏幕=({},{}) 客户区=({},{})", exactName, sx, sy, cx, cy);
        return "已在 UIA 位置点「" + exactName + "」（屏幕 " + sx + "," + sy + " → 客户区 " + cx + "," + cy + "）";
    }

    // ==================== 第五轮新增小件（交互序列 ✓） ====================

    /**
     * **Weixin 的正解：标题栏"双击 ×2"** ✓（用户 2026-10-14 亲测 ✓ 方案 28 的正式入口）.
     *
     * <p>为什么有效 ✓：双击标题栏走的是**微信自己的命中判定**（自绘标题栏 ✓）→
     * 它内部做一遍"最大化↔还原"就顺带把渲染器唤醒 ✓（先出黑框、再去掉 ✓）。
     * 两遍 → **净状态不变** ✓（位置尺寸回到原样 ✓）。
     *
     * <p>为什么不用别的 ✗：外部强制（ShowWindow / SetWindowPos / 重画 / 强制激活）全无效 ✓
     * —— 微信只认"用户点了它自己的控件"这条路 ✓。
     *
     * @return 一句话结果（日志/测试台用 ✓）
     */
    public static String weixinWakeByTitleBarDoubleClick(int hwnd) {
        if (hwnd == 0) return "hwnd 为空";
        pureWake(hwnd);                       // ① 唤醒：最小化才还原 + 抬升 + 置前 ✓（不含合成点击 ✗）
        clickTwice(hwnd, 8, 8);               // ② 第一次双击 ✓（出黑框）
        sleep(250);
        clickTwice(hwnd, 8, 8);               // ③ 第二次双击 ✓（去掉黑框 + 激活）
        sleep(150);
        raise(hwnd);
        String r = "标题栏双击 ×2 完成，置前=" + foreground(hwnd);
        LOG.info("[唤起] Weixin 标题栏双击 ×2: {}", r);
        return r;
    }

    /** **纯净唤醒** ✓：最小化才还原 ✓、否则只抬升 + 置前 ✓ —— 不含任何合成点击 ✗（次数由序列自己控制 ✓） */
    private static void pureWake(int hwnd) {
        try {
            if (SwNativeOps.isMinimized(hwnd)) SwNativeOps.restoreWindowOnly(hwnd);
            raise(hwnd);
            foreground(hwnd);
        } catch (Throwable t) {
            LOG.debug("[测试台] pureWake 异常: {}", t.getMessage());
        }
    }

    /** 投递**一次**点击（`clickInWindow` ✓ 客户区坐标 ✓ —— 实测有效的那种"合成点击消息" ✓） */
    private static void clickOnce(int hwnd, int x, int y) {
        SwNativeOps.clickInWindow(hwnd, x, y);
    }

    /** 投递**一次双击**（= 两次单击 ✓ 与老兜底同一手法 ✓） */
    private static void clickTwice(int hwnd, int x, int y) {
        SwNativeOps.clickInWindow(hwnd, x, y);
        sleep(40);
        SwNativeOps.clickInWindow(hwnd, x, y);
    }

    /**
     * 算标题栏按钮位置（**客户区坐标** ✓）：`x = 客户区宽 - rightOffset`、`y = 16` ✓.
     *
     * @param rightOffset 距客户区右边多少像素（最大化按钮约 46 ✓ 最小化按钮约 110 ✓ —— 按标题栏布局估的 ✓）
     */
    private static int[] captionButton(int hwnd, int rightOffset) {
        WinDef.RECT cr = new WinDef.RECT();
        if (!Ext.INSTANCE.GetClientRect(h(hwnd), cr)) return null;
        int cw = cr.right - cr.left;
        return new int[]{Math.max(8, cw - rightOffset), 16};
    }

    /**
     * **探针：找出微信真正的托盘图标** ✓（用户 2026-10-15 要求研究"托盘唤出" ✓）.
     *
     * <p>为什么先前找不到 ✗：我只扫了**主窗口那个 pid** 的窗口 ✗ —— 而微信有**多个进程** ✓
     * （用户机器上 5 个 Weixin 进程 ✓），托盘图标很可能挂在**另一个进程**的窗口上 ✓✓。
     * <p>做法 ✓：把传入的**所有 pid** 的**全部顶层窗口**都拿来当候选宿主 ✓，uid 试 0~30 ✓，
     * 谁让 `Shell_NotifyIconGetRect` 返回 `S_OK(0)` 谁就是 ✓（并且把窗口类名一起打出来 ✓ 便于后续直接发它自己的托盘消息 ✓）。
     *
     * @return 每个命中一行（hwnd / 类名 / pid / uid / 图标矩形 ✓）
     */
    public static java.util.List<String> probeTrayIcons(int... pids) {
        java.util.List<String> out = new java.util.ArrayList<>();
        final java.util.Set<Integer> want = new java.util.HashSet<>();
        for (int p : pids) want.add(p);
        out.add("候选进程: " + want);
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            int pid = pidOfHwnd(hwnd);
            if (!want.contains(pid)) return true;
            int h = hwndValue(hwnd);
            String cls = className(hwnd);
            int[] wr = SwNativeOps.getVisualRect(h);
            out.add("窗口 hwnd=0x" + Integer.toHexString(h) + " pid=" + pid + " class=" + cls
                    + " visible=" + Ext.INSTANCE.IsWindowVisible(hwnd)
                    + (wr == null ? "" : " rect=" + wr[0] + "," + wr[1] + " " + (wr[2] - wr[0]) + "x" + (wr[3] - wr[1])));
            for (int uid = 0; uid <= 30; uid++) {
                Shell32.NOTIFYICONIDENTIFIER id = new Shell32.NOTIFYICONIDENTIFIER();
                id.hWnd = h(h);
                id.uID = uid;
                id.guidItem = new com.sun.jna.platform.win32.Guid.GUID();
                WinDef.RECT r = new WinDef.RECT();
                int hr = Shell32.INSTANCE.Shell_NotifyIconGetRect(id, r);
                if (hr == 0) {
                    out.add("  ★托盘图标命中！host=0x" + Integer.toHexString(h) + " class=" + cls
                            + " uid=" + uid + " rect=" + r.left + "," + r.top + " "
                            + (r.right - r.left) + "x" + (r.bottom - r.top));
                }
            }
            return true;
        }, null);
        return out;
    }

    /**
     * **探针：枚举"托盘回调消息"** ✓ —— 找出能让微信**自己把窗口收回来**的那条消息 ✓.
     *
     * <p>背景 ✓（用户 2026-10-15 要研究"托盘唤出" ✓ 探针实测 ✓）：
     * 微信的托盘宿主窗口类名是 **`Qt51514WxTrayIconMessageWindowClass`** ✓（我探针找到的 ✓），
     * 而 `Shell_NotifyIconGetRect` **查不到图标矩形** ✗（多次实测 ✓ 可能用了 GUID 注册 ✗ 或图标被系统隐藏 ✓）
     * → 那就**绕开图标** ✓：直接往那个宿主窗口投"托盘点击"回调消息 ✓（与 QQNT 的 `WM_APP+1` 同一思路 ✓）。
     *
     * <p>安全 ✓：只发 **`WM_APP+0..40` 与 `WM_USER+0..40`** ✓（避开 `WM_CLOSE/WM_DESTROY/WM_QUIT` 等危险区 ✗），
     * 错的消息一般被忽略 ✓；每发一条就检查**主窗口是否变可见** ✓ —— **自己验证** ✓ 不让用户点 ✓。
     *
     * @return 逐条结果（命中即停 ✓）
     */
    public static java.util.List<String> probeTrayClickMessages(int mainHwnd, int hostHwnd) {
        java.util.List<String> out = new java.util.ArrayList<>();
        if (mainHwnd == 0 || hostHwnd == 0) {
            out.add("参数不全（mainHwnd/hostHwnd 需要非 0 ✓）");
            return out;
        }
        boolean vis0 = SwNativeOps.isWindowVisible(mainHwnd);
        out.add("起始：主窗口 visible=" + vis0 + "（收进托盘时应为 false ✓）host=0x" + Integer.toHexString(hostHwnd));
        java.util.List<Integer> msgs = new java.util.ArrayList<>();
        msgs.add(0x8000 + 1);                                  // 最可能 ✓（QQNT 就是它 ✓）
        for (int i = 0; i <= 40; i++) if (i != 1) msgs.add(0x8000 + i);
        for (int i = 0; i <= 40; i++) msgs.add(0x0400 + i);
        int tries = 0;
        for (int uid : new int[]{1, 0, 2, 3}) {
            for (int m : msgs) {
                Ext.INSTANCE.PostMessageW(h(hostHwnd), m, w(uid), l(0x0201));   // lParam = WM_LBUTTONDOWN ✓
                tries++;
                sleep(35);
                if (SwNativeOps.isWindowVisible(mainHwnd)) {
                    out.add("★命中：msg=0x" + Integer.toHexString(m) + " uid=" + uid + " → 主窗口已可见 ✓（第 " + tries + " 次）");
                    LOG.info("[测试台] 托盘回调消息命中：msg=0x{} uid={} ✓", Integer.toHexString(m), uid);
                    return out;
                }
            }
        }
        out.add("枚举完 " + tries + " 次未命中 ✗（主窗口仍 visible=" + SwNativeOps.isWindowVisible(mainHwnd) + "）");
        return out;
    }

    /** **按 pid + 类名关键字找窗口** ✓（探针用：找 explorer 的 `Shell_TrayWnd` 任务栏 ✓） */
    public static int findWindowByClassOfPid(int pid, String classContains) {
        final int[] found = {0};
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            if (pidOfHwnd(hwnd) != pid) return true;
            String cls = className(hwnd);
            if (cls != null && classContains != null && cls.contains(classContains)) {
                found[0] = hwndValue(hwnd);
                return false;
            }
            return true;
        }, null);
        return found[0];
    }

    /** **在屏幕坐标上发一次真实左键点击** ✓（探针/托盘图标点击用 ✓；会挪一下鼠标 ✓） */
    public static void clickScreen(int x, int y) {
        Ext.INSTANCE.SetCursorPos(x, y);
        sleep(50);
        Ext.INSTANCE.mouse_event(0x0002, 0, 0, 0, null);   // LEFTDOWN
        sleep(30);
        Ext.INSTANCE.mouse_event(0x0004, 0, 0, 0, null);   // LEFTUP
        LOG.info("[测试台] 已在屏幕 ({},{}) 发真实左键点击 ✓", x, y);
    }

    /** **全局**按类名找窗口 ✓（不需要 pid：任务栏 `Shell_TrayWnd` 属 explorer ✓ 直接找就行 ✓） */
    public static int findWindowByClassGlobal(String classContains) {
        final int[] found = {0};
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            String cls = className(hwnd);
            if (cls != null && classContains != null && cls.contains(classContains)) {
                found[0] = hwndValue(hwnd);
                return false;
            }
            return true;
        }, null);
        return found[0];
    }

    /**
     * **托盘唤出（正解 ✓ 用户 2026-10-15 实测 + 我自跑探针实证 ✓）**.
     *
     * <p>原理 ✓：Win11 任务栏（explorer 的 `Shell_TrayWnd` ✓）是**原生 XAML** ✓，
     * 托盘图标就是 **UIA 元素** ✓（名字是应用名 ✓ 例如"微信" ✓），
     * 且它**支持 `InvokePattern.Invoke()`** ✓ —— 于是可以：
     * 找到任务栏 ✓ → 按名字找到该图标元素 ✓ → **Invoke** ✓ → 应用**自己**把窗口收回来 ✓✓。
     * <p>优点 ✓（探针实证）：**零坐标** ✓、**不动鼠标** ✓、**无动效、无副作用** ✓、窗口状态由应用自己恢复 ✓。
     * <p>对比 ✗：微信自绘标题栏的按钮**没有几何** ✓ 且 Invoke 是空操作 ✗（所以那里只能双击×2 ✓）；
     * 而**任务栏**是 XAML ✓ 两者都成立 ✓ —— 差别就在这 ✓。
     *
     * @param nameKeyword 托盘图标的名字关键字（"微信" ✓ / 也可用英文名 ✓）
     * @param verifyHwnd  用来**自证**的窗口（调用后检查它是否变可见 ✓；0 = 不校验 ✓）
     * @return true = 已调用且（若给了 verifyHwnd）确认窗口已可见 ✓
     */
    public static boolean trayIconActivateByUia(String nameKeyword, int verifyHwnd) {
        try {
            int tray = findWindowByClassGlobal("Shell_TrayWnd");
            if (tray == 0) {
                LOG.info("[唤起] 没找到任务栏 Shell_TrayWnd ✗（非 Win11 或 explorer 异常 ✓）");
                return false;
            }
            String hit = UiaOps.invokeButtonExact(tray, null, nameKeyword);
            if (hit == null) {
                LOG.info("[唤起] 任务栏里没找到/没能调用托盘图标「{}」✗", nameKeyword);
                return false;
            }
            LOG.info("[唤起] 托盘唤出：已用 UIA 调用任务栏图标「{}」✓", hit);
            if (verifyHwnd == 0) return true;
            sleep(500);
            boolean vis = SwNativeOps.isWindowVisible(verifyHwnd);
            LOG.info("[唤起] 托盘唤出校验：hwnd=0x{} visible={} {}", Integer.toHexString(verifyHwnd), vis,
                    vis ? "✓ 成功" : "✗ 窗口仍未可见");
            return vis;
        } catch (Throwable t) {
            LOG.warn("[唤起] 托盘唤出异常: {}", t.getMessage());
            return false;
        }
    }

    /**
     * **探针：枚举 tray 图标的 uid，并找出 uid ↔ 账号窗口 的对应关系** ✓（我自己跑 ✓）.
     *
     * <p>为什么需要 ✓（用户 2026-10-15 提出的真问题 ✓）：
     * ①QQNT 曾用 `uid=3` 唤成功 ✓ 现在同一套失效 ✗ —— 账号多了、图标可能不止一个 ✓ uid 会变 ✓；
     * ②更根本的是 ✓：同一个应用**多开**时，托盘上多个图标**名字完全一样** ✗（微信全是"微信" ✓），
     * 所以"调一次图标"根本无法指定账号 ✗ —— 唯一的解是**把 uid 与账号窗口建立起映射** ✓✓。
     *
     * <p>做法 ✓：逐 uid 发一次托盘点击消息 ✓，然后**对比哪些窗口从不可见变成可见** ✓ ——
     * 变成可见的那个 hwnd 就是这个 uid 负责的账号窗口 ✓（**自己验证** ✓ 不需要用户点 ✓）。
     *
     * @return 每个 uid 一行结果（含"唤出了哪个 hwnd" ✓）
     */
    public static java.util.List<String> probeTrayUidMapping(int pid, int maxUid) {
        java.util.List<String> out = new java.util.ArrayList<>();
        if (pid == 0) return out;
        int host = trayHostByPid(pid);
        out.add("pid=" + pid + " Electron 托盘宿主 host=0x" + Integer.toHexString(host));
        if (host == 0) {
            out.add("该进程没有 Electron_NotifyIconHostWindow ✗（不是 Electron 或托盘没建）");
            return out;
        }
        // 先记录该进程所有顶层窗口的可见性快照 ✓
        final java.util.Map<Integer, String> before = new java.util.LinkedHashMap<>();
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            if (pidOfHwnd(hwnd) != pid) return true;
            int v = hwndValue(hwnd);
            String cls = className(hwnd);
            if (cls == null || cls.contains("MessageWindow") || cls.contains("NotifyIconHost")) return true;
            before.put(v, cls + "|" + Ext.INSTANCE.IsWindowVisible(hwnd));
            return true;
        }, null);
        out.add("候选窗口 " + before.size() + " 个（已记录可见性快照 ✓）");
        // ⚠️ 每轮都要**重新快照** ✗：否则 uid=3 唤出的窗口会一直算"新变可见" ✓
        //    实测踩到 ✓：uid=4..12 全都假报"唤出 0x20930" ✗（其实它从 uid=3 起就一直开着 ✓）
        final java.util.Map<Integer, Boolean> vis = new java.util.LinkedHashMap<>();
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            int v = hwndValue(hwnd);
            if (before.containsKey(v)) vis.put(v, Ext.INSTANCE.IsWindowVisible(hwnd));
            return true;
        }, null);
        for (int uid = 0; uid <= maxUid; uid++) {
            Ext.INSTANCE.PostMessageW(h(host), 0x8000 + 1, w(uid), l(0x0201));   // WM_APP+1 + LBUTTONDOWN ✓
            sleep(450);
            StringBuilder sb = new StringBuilder("uid=" + uid + " → ");
            boolean any = false;
            for (java.util.Map.Entry<Integer, String> e : before.entrySet()) {
                boolean nowVis = SwNativeOps.isWindowVisible(e.getKey());
                if (nowVis && !Boolean.TRUE.equals(vis.get(e.getKey()))) {
                    int[] r = SwNativeOps.getVisualRect(e.getKey());
                    sb.append("★唤出 hwnd=0x").append(Integer.toHexString(e.getKey()))
                      .append(" class=").append(e.getValue().split("\\|")[0])
                      .append(r == null ? "" : " rect=" + r[0] + "," + r[1] + " " + (r[2] - r[0]) + "x" + (r[3] - r[1]))
                      .append("  ");
                    any = true;
                }
            }
            // 本轮结束后更新快照 ✓（下一轮只报"新"变化 ✓）
            for (java.util.Map.Entry<Integer, String> e : before.entrySet()) {
                vis.put(e.getKey(), SwNativeOps.isWindowVisible(e.getKey()));
            }
            if (!any) sb.append("（无窗口变为可见 ✓）");
            out.add(sb.toString());
        }
        return out;
    }

    /**
     * **数一数任务栏里有几个同名托盘图标** ✓（决定能不能用"托盘唤出" ✓）.
     *
     * <p>为什么必须有它 ✗（用户 2026-10-15 实测 + 我探针实证 ✓）：
     * 微信**多开**时，任务栏上多个图标的 `name` **全都是「微信」** ✗（探针输出：`[#16] name=微信`、`[#17] name=微信` ✓）
     * → 托盘唤出**无法指定是哪个账号** ✗（调一次弹 A ✓、再调又弹 B ✗）。
     * 而**双击×2 作用在"我们指定的那个 hwnd"上** ✓ → **天然按账号精确** ✓。
     * <p>⇒ 规则 ✓：**同名图标恰好 1 个 → 用托盘 ✓（最自然 ✓）；2 个及以上 → 用双击×2 ✓（按账号精确 ✓）**。
     *
     * @return 同名图标个数 ✓（找不到任务栏返回 -1 ✓）
     */
    public static int countTrayIcons(String nameKeyword) {
        try {
            int tray = findWindowByClassGlobal("Shell_TrayWnd");
            if (tray == 0) return -1;
            java.util.List<String> hits = UiaOps.listByClassKeyword(tray, 4000, nameKeyword);
            if (hits == null) return -1;
            int n = 0;
            for (String s : hits) if (s.startsWith("name=") || s.contains("name=" + nameKeyword)) n++;
            LOG.info("[唤起] 任务栏里名字含「{}」的图标数 = {}（1 → 托盘可用 ✓；≥2 → 改用双击×2 ✓）", nameKeyword, n);
            return n;
        } catch (Throwable t) {
            LOG.warn("[唤起] 数托盘图标失败: {}", t.getMessage());
            return -1;
        }
    }

    // ==================== 第三轮新增小件（微信自己的通道 ✓） ====================

    /** 模拟 **Ctrl+Alt+W**（微信默认「打开/隐藏微信」热键 ✓） */
    private static void hotkeyCtrlAltW() {
        final byte VK_CONTROL = 0x11, VK_MENU = 0x12, VK_W = 0x57, KEYUP = 2;
        Ext.INSTANCE.keybd_event(VK_CONTROL, (byte) 0, 0, null);
        Ext.INSTANCE.keybd_event(VK_MENU, (byte) 0, 0, null);
        Ext.INSTANCE.keybd_event(VK_W, (byte) 0, 0, null);
        sleep(40);
        Ext.INSTANCE.keybd_event(VK_W, (byte) 0, KEYUP, null);
        Ext.INSTANCE.keybd_event(VK_MENU, (byte) 0, KEYUP, null);
        Ext.INSTANCE.keybd_event(VK_CONTROL, (byte) 0, KEYUP, null);
    }

    /**
     * **找目标进程托盘图标的屏幕矩形** ✓（`Shell_NotifyIconGetRect` ✓）.
     * <p>做法：把该进程每个顶层窗口都当作"托盘图标宿主"试一遍 ✓、图标 id 试 0~20 ✓ ——
     * 谁返回 `S_OK(0)` 谁就是 ✓（免得去猜类名 ✗）。
     *
     * @return {left, top, right, bottom}；找不到返回 null ✓
     */
    private static int[] findTrayIconRect(int targetHwnd) {
        final int pid = pidOf(targetHwnd);
        if (pid == 0) return null;
        final List<Integer> hwnds = new ArrayList<>();
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            if (pidOfHwnd(hwnd) == pid) hwnds.add(hwndValue(hwnd));
            return true;
        }, null);
        for (int h : hwnds) {
            for (int uid = 0; uid <= 20; uid++) {
                Shell32.NOTIFYICONIDENTIFIER id = new Shell32.NOTIFYICONIDENTIFIER();
                id.hWnd = h(h);
                id.uID = uid;
                id.guidItem = new com.sun.jna.platform.win32.Guid.GUID();
                WinDef.RECT r = new WinDef.RECT();
                int hr = Shell32.INSTANCE.Shell_NotifyIconGetRect(id, r);
                if (hr == 0) {                      // S_OK ✓
                    LOG.info("[测试台] 找到托盘图标：宿主 hwnd=0x{} uid={} rect={},{},{}x{}",
                            Integer.toHexString(h), uid, r.left, r.top, r.right - r.left, r.bottom - r.top);
                    return new int[]{r.left, r.top, r.right, r.bottom};
                }
            }
        }
        return null;
    }

    // ==================== 新增小步骤（专治"大灰框" ✓ 框架/非客户区重画） ====================

    /**
     * **重画"框架"（非客户区）** ✓ —— `RDW_FRAME` 专管标题栏/边框那一圈 ✓.
     * <p>为什么加它 ✗：老 `redraw()` 用的是 `RDW_INVALIDATE|UPDATENOW|ALLCHILDREN` ✓，
     * 只保证**客户区**能重画 ✓；而用户看到的"**大灰框**"恰好是**非客户区**没重画 ✓ → 必须带 `RDW_FRAME` ✓。
     */
    private static boolean redrawFrame(int hwnd) {
        Ext.INSTANCE.InvalidateRect(h(hwnd), null, true);
        return Ext.INSTANCE.RedrawWindow(h(hwnd), null, null,
                RDW_FRAME | RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN);
    }

    /**
     * **1px 轻推再复位** ✓（用户 2026-10-14：手动拖一下灰框就消失 ✓）.
     * <p>`SWP_NOCOPYBITS` 关键 ✓：让系统**不要**把旧像素复制过来（否则又会把灰框搬过来 ✓）。
     * 净位移为 0 ✓ —— 视觉上不动，但系统被迫重算了框架并重画 ✓。
     */
    private static void nudge(int hwnd) {
        int[] r = SwNativeOps.getVisualRect(hwnd);
        if (r == null) return;
        int x = r[0], y = r[1], w0 = r[2] - r[0], h0 = r[3] - r[1];
        Ext.INSTANCE.SetWindowPos(h(hwnd), null, x + 1, y, w0, h0,
                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOCOPYBITS);
        sleep(30);
        Ext.INSTANCE.SetWindowPos(h(hwnd), null, x, y, w0, h0,
                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOCOPYBITS);
    }

    // ==================== 托盘唤醒（正式业务也用这一条 ✓ 用户 2026-10-14 实测唯一可用 ✓） ====================

    /** Electron 托盘消息：`kMessageNotifyIcon = WM_APP + 1` ✓ */
    private static final int WM_NOTIFY_ICON = 0x8000 + 1;
    private static final int WM_LBUTTONDOWN = 0x0201;

    /**
     * **托盘唤醒**（正式链路用的公开入口 ✓）.
     *
     * <p>实测结论（用户 2026-10-14）：25 种方式里**只有它可用且最丝滑** ✓ ——
     * 把"点一下托盘图标"这条消息交还给程序自己 ✓，窗口自己回来 ✓ 不会冻结 ✓
     * 也没有微信那种"先蒙一圈颜色、要拖动才消失"的副作用 ✓。
     *
     * @param uid Electron 托盘图标的 id（QQNT = 3 ✓）
     * @return 是否成功把消息投递出去（找不到托盘宿主就 false ✓）
     */
    public static boolean trayActivate(int hwnd, int uid) {
        int host = trayHost(hwnd);
        if (host == 0) {
            LOG.info("[唤起] 目标进程没有 Electron_NotifyIconHostWindow（hwnd=0x{}）", Integer.toHexString(hwnd));
            return false;
        }
        boolean ok = Ext.INSTANCE.PostMessageW(h(host), WM_NOTIFY_ICON, w(uid), l(WM_LBUTTONDOWN));
        LOG.info("[唤起] 托盘唤醒 → host=0x{}, uid={}, LBUTTONDOWN, ok={}", Integer.toHexString(host), uid, ok);
        return ok;
    }

    /** 该窗口所属进程是否有 Electron 托盘宿主（判断能不能用托盘唤醒 ✓） */
    public static boolean hasElectronTray(int hwnd) {
        return trayHost(hwnd) != 0;
    }

    /**
     * **按进程 id 托盘唤醒** —— 用于「窗口已关闭、主窗口 hwnd 已销毁」的情况 ✓（用户 2026-10-14 实测必需 ✓）.
     *
     * <p>为什么必须有这一条 ✗：QQNT 关闭窗口后，我们存的主窗口 hwnd **已经作废** ✓
     * （Electron 销毁了那个 BrowserWindow ✓），而**进程还活着、托盘宿主也在** ✓ ——
     * 测试台里能成功，正是因为它是**按 pid** 找托盘的 ✓。
     */
    public static boolean trayActivateByPid(int pid, int uid) {
        int host = trayHostByPid(pid);
        if (host == 0) {
            LOG.info("[唤起] pid={} 没有 Electron_NotifyIconHostWindow（可能不是 Electron 托盘，或托盘还没创建）", pid);
            return false;
        }
        boolean ok = Ext.INSTANCE.PostMessageW(h(host), WM_NOTIFY_ICON, w(uid), l(WM_LBUTTONDOWN));
        LOG.info("[唤起] 托盘唤醒(按 pid={}) → host=0x{}, uid={}, LBUTTONDOWN, ok={}",
                pid, Integer.toHexString(host), uid, ok);
        return ok;
    }

    /** 该进程是否有 Electron 托盘宿主 ✓（按 pid ✓） */
    public static boolean hasElectronTrayByPid(int pid) {
        return trayHostByPid(pid) != 0;
    }

    /**
     * 在该 pid 里找**真正的主窗口**（可见的顶层窗口里面积最大者 ✓）.
     * <p>用途：按托盘唤醒之后，QQNT 会重新创建/显示它的主窗口 ✓ —— 把那个**新的** hwnd 找回来 ✓
     * （旧 hwnd 已作废 ✓ 不能再用 ✓）。
     *
     * @return 新的主窗口 hwnd；找不到返回 0 ✓
     */
    public static int findMainWindowOfPid(int pid) {
        if (pid == 0) return 0;
        final int[] best = {0};
        final long[] bestArea = {-1};
        final int[] bestHidden = {0};
        final long[] bestHiddenArea = {-1};
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            if (pidOfHwnd(hwnd) != pid) return true;
            int v = hwndValue(hwnd);
            String cls = className(hwnd);
            // 排除辅助窗口 ✓（探针实证：托盘宿主自报的矩形**比真主窗口还大** ✗ 会把它误选成主窗口 ✓）
            if (cls != null && (cls.contains("MessageWindow") || cls.contains("PowerMessage")
                    || cls.contains("IME") || cls.startsWith("SoPY") || cls.startsWith("Sogou")
                    || cls.startsWith("MSCTF"))) {
                return true;
            }
            int[] r = SwNativeOps.getVisualRect(v);
            if (r == null) return true;
            int w = Math.max(0, r[2] - r[0]), hh = Math.max(0, r[3] - r[1]);
            long area = (long) w * hh;
            if (area < 10000) return true;                      // 太小的辅助窗口跳过 ✓
            if (Ext.INSTANCE.IsWindowVisible(hwnd)) {
                if (area > bestArea[0]) { bestArea[0] = area; best[0] = v; }
            } else if (area > bestHiddenArea[0]) {
                bestHiddenArea[0] = area; bestHidden[0] = v;     // 收进托盘时它 visible=false ✓ 但仍可唤醒 ✓
            }
            return true;
        }, null);
        int picked = best[0] != 0 ? best[0] : bestHidden[0];
        if (picked != 0) {
            LOG.info("[唤起] pid={} 主窗口 = hwnd=0x{}（{}，面积 {}）", pid, Integer.toHexString(picked),
                    best[0] != 0 ? "可见 ✓" : "隐藏 ✓（收进托盘 ✓ 仍可唤醒）",
                    best[0] != 0 ? bestArea[0] : bestHiddenArea[0]);
        }
        return picked;
    }

    /**
     * **解冻连打**（画面冻住/白屏时用 ✓ 公开入口）：尺寸抖 ±1px + 重算框架 + 重画 + DwmFlush ✓.
     * <p>原理：Chromium 合成器主要在尺寸变化时重新出帧 ✓。
     */
    public static String unfreeze(int hwnd) {
        String j = jiggle(hwnd);
        framechange(hwnd);
        boolean rd = redraw(hwnd);
        Dwm.INSTANCE.DwmFlush();
        return j + "，重画=" + rd;
    }

    /** 托盘唤醒的公共流程 ✓；{@code maximize} / {@code doPlace} 决定"唤醒之后怎么摆" ✓ */
    private static String tray(int targetHwnd, int uid, boolean maximize, boolean doPlace, int[] a) {
        int host = trayHost(targetHwnd);
        if (host == 0) {
            return "没找到 Electron_NotifyIconHostWindow（该进程可能不是 Electron 托盘，或托盘还没创建）";
        }
        boolean ok = Ext.INSTANCE.PostMessageW(h(host), WM_NOTIFY_ICON, w(uid), l(WM_LBUTTONDOWN));
        StringBuilder sb = new StringBuilder();
        sb.append("托盘消息 → 0x").append(Integer.toHexString(host))
                .append(" (uid=").append(uid).append(", lParam=0x201) = ").append(ok).append(' ');
        // 唤醒后抬升 + 置前（**不硬拉** ✓）
        sleep(120);
        raise(targetHwnd);
        sb.append("抬升✓ 置前=").append(foreground(targetHwnd)).append(' ');
        if (maximize) {
            sb.append("最大化=").append(SwNativeOps.maximizeWindow(targetHwnd));
        } else if (doPlace) {
            sb.append(place(targetHwnd, a[A_W], a[A_H], a[A_DX], a[A_DY]));
        } else {
            sb.append("（未改几何 ✓）");
        }
        return sb.toString();
    }

    /** 找目标窗口**所属进程**里的托盘宿主窗口 ✓ */
    private static int trayHost(int targetHwnd) {
        return trayHostByPid(pidOf(targetHwnd));
    }

    /** 按 **pid** 找托盘宿主窗口（`Electron_NotifyIconHostWindow` ✓） */
    private static int trayHostByPid(final int wantPid) {
        if (wantPid == 0) return 0;
        final int[] found = {0};
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            if (pidOfHwnd(hwnd) != wantPid) return true;
            String cls = className(hwnd);
            if (cls != null && cls.contains("NotifyIconHost")) {
                found[0] = hwndValue(hwnd);
                return false;
            }
            return true;
        }, null);
        return found[0];
    }

    // ==================== 诊断 ====================

    private static String listWindows(int targetHwnd) {
        final int wantPid = pidOf(targetHwnd);
        final StringBuilder sb = new StringBuilder("进程 " + wantPid + " 的顶层窗口：\n");
        final int[] n = {0};
        Ext.INSTANCE.EnumWindows((hwnd, data) -> {
            if (pidOfHwnd(hwnd) != wantPid) return true;
            int v = hwndValue(hwnd);
            n[0]++;
            int[] r = SwNativeOps.getVisualRect(v);
            sb.append("  hwnd=0x").append(Integer.toHexString(v))
                    .append("  class=").append(className(hwnd))
                    .append("  visible=").append(Ext.INSTANCE.IsWindowVisible(hwnd))
                    .append(r == null ? "" : "  rect=" + r[0] + "," + r[1] + ","
                            + (r[2] - r[0]) + "x" + (r[3] - r[1]))
                    .append('\n');
            return true;
        }, null);
        sb.append("（共 ").append(n[0]).append(" 个）");
        LOG.info("[测试台] {}", sb.toString().replace('\n', ' '));
        return sb.toString();
    }

    private static String describe(int hwnd) {
        if (hwnd == 0) return "hwnd 为空";
        WinUser.WINDOWPLACEMENT wp = new WinUser.WINDOWPLACEMENT();
        wp.length = wp.size();
        boolean wpOk = Ext.INSTANCE.GetWindowPlacement(h(hwnd), wp);
        int[] r = SwNativeOps.getVisualRect(hwnd);
        int ex = Ext.INSTANCE.GetWindowLong(h(hwnd), -20);
        String s = "hwnd=0x" + Integer.toHexString(hwnd)
                + " class=" + className(h(hwnd))
                + " pid=" + pidOf(hwnd)
                + " visible=" + Ext.INSTANCE.IsWindowVisible(h(hwnd))
                + " enabled=" + Ext.INSTANCE.IsWindowEnabled(h(hwnd))
                + " 无响应(IsHungAppWindow)=" + Ext.INSTANCE.IsHungAppWindow(h(hwnd))
                + " showCmd=" + (wpOk ? wp.showCmd : -1) + "（1普通/2最小化/3最大化）"
                + " rect=" + (r == null ? "?" : r[0] + "," + r[1] + "," + (r[2] - r[0]) + "x" + (r[3] - r[1]))
                + " exStyle=0x" + Integer.toHexString(ex);
        LOG.info("[测试台] {}", s);
        return s;
    }

    // ==================== 小工具 ====================

    private static int pidOf(int hwnd) {
        IntByReference p = new IntByReference();
        Ext.INSTANCE.GetWindowThreadProcessId(h(hwnd), p);
        return p.getValue();
    }

    private static int pidOfHwnd(WinDef.HWND hwnd) {
        IntByReference p = new IntByReference();
        Ext.INSTANCE.GetWindowThreadProcessId(hwnd, p);
        return p.getValue();
    }

    /** JNA 的 HWND → 整数值（**必须走 nativeValue** ✓ 指针 hash 是错的 ✗） */
    private static int hwndValue(WinDef.HWND hwnd) {
        return (int) Pointer.nativeValue(hwnd.getPointer());
    }

    private static String className(WinDef.HWND hwnd) {
        char[] buf = new char[256];
        int n = Ext.INSTANCE.GetClassNameW(hwnd, buf, buf.length);
        return n <= 0 ? "?" : new String(buf, 0, n);
    }

    /** 在屏幕坐标处模拟一次左键单击（`mouse_event` —— 比 INPUT 结构体稳妥 ✓） */
    private static void clickAt(int x, int y) {
        Ext.INSTANCE.SetCursorPos(x, y);
        sleep(30);
        Ext.INSTANCE.mouse_event(0x0002, 0, 0, 0, null);   // MOUSEEVENTF_LEFTDOWN
        sleep(20);
        Ext.INSTANCE.mouse_event(0x0004, 0, 0, 0, null);   // MOUSEEVENTF_LEFTUP
    }

    private static WinDef.HWND h(int hwnd) {
        return new WinDef.HWND(Pointer.createConstant(hwnd));
    }

    private static WinDef.WPARAM w(int v) {
        return new WinDef.WPARAM(v);
    }

    /** `PostMessage` 的第 4 参是 LPARAM ✓（拿 WPARAM 顶上去类型不同、编译不过 ✓） */
    private static WinDef.LPARAM l(int v) {
        return new WinDef.LPARAM(v);
    }

    // ==================== JNA 声明 ====================

    interface Ext extends Library {
        Ext INSTANCE = Native.load("user32", Ext.class);

        boolean SetForegroundWindow(WinDef.HWND hWnd);

        boolean SetWindowPos(WinDef.HWND hWnd, WinDef.HWND after, int x, int y, int w, int h, int flags);

        boolean ShowWindow(WinDef.HWND hWnd, int cmd);

        boolean ShowWindowAsync(WinDef.HWND hWnd, int cmd);

        boolean IsWindowVisible(WinDef.HWND hWnd);

        boolean IsWindowEnabled(WinDef.HWND hWnd);

        boolean IsHungAppWindow(WinDef.HWND hWnd);

        void SwitchToThisWindow(WinDef.HWND hWnd, boolean altTab);

        boolean AllowSetForegroundWindow(int pid);

        int GetWindowThreadProcessId(WinDef.HWND hWnd, IntByReference pid);

        boolean AttachThreadInput(int attach, int attachTo, boolean attach2);

        WinDef.HWND SetFocus(WinDef.HWND hWnd);

        WinDef.HWND SetActiveWindow(WinDef.HWND hWnd);

        void keybd_event(byte vk, byte scan, int flags, Pointer extra);

        void mouse_event(int flags, int dx, int dy, int data, Pointer extra);

        boolean SetCursorPos(int x, int y);

        /**
         * ⚠️ 必须叫 **`PostMessageW`** ✗ 不能叫 `PostMessage` ——
         * user32 **只导出 `PostMessageA`/`PostMessageW`**，没有裸名 ✓
         * （用户实测 `UnsatisfiedLinkError: 找不到指定的程序` ✓ 就是踩了这个 ✓）。
         */
        boolean PostMessageW(WinDef.HWND hWnd, int msg, WinDef.WPARAM wp, WinDef.LPARAM lp);

        /** `SendMessageW`（同步 ✓）—— 发 `WM_NCPAINT` / `WM_NCACTIVATE` 强制重画非客户区要用 ✓ */
        boolean SendMessageW(WinDef.HWND hWnd, int msg, WinDef.WPARAM wp, WinDef.LPARAM lp);

        boolean GetWindowPlacement(WinDef.HWND hWnd, WinUser.WINDOWPLACEMENT pl);

        boolean SetWindowPlacement(WinDef.HWND hWnd, WinUser.WINDOWPLACEMENT pl);

        boolean InvalidateRect(WinDef.HWND hWnd, WinDef.RECT rect, boolean erase);

        boolean RedrawWindow(WinDef.HWND hWnd, WinDef.RECT rect, Pointer rgn, int flags);

        int GetClassNameW(WinDef.HWND hWnd, char[] buf, int max);

        int GetWindowLong(WinDef.HWND hWnd, int index);

        boolean EnumWindows(WinUser.WNDENUMPROC cb, Pointer data);

        boolean GetClientRect(WinDef.HWND hWnd, WinDef.RECT rect);

        boolean GetWindowRect(WinDef.HWND hWnd, WinDef.RECT rect);

        /** `SPI_SETFOREGROUNDLOCKTIMEOUT`（komorebi 配方：置 0 ✓） */
        boolean SystemParametersInfoW(int action, int param, IntByReference value, int winIni);

        boolean SystemParametersInfoW(int action, int param, com.sun.jna.ptr.PointerByReference value, int winIni);

        boolean GetCursorPos(int[] point);

        boolean ScreenToClient(WinDef.HWND hWnd, WinDef.POINT point);
    }

    /** `shell32`：找托盘图标矩形（`Shell_NotifyIconGetRect` ✓ 原生版托盘法的关键 ✓） */
    interface Shell32 extends Library {
        Shell32 INSTANCE = Native.load("shell32", Shell32.class);

        int Shell_NotifyIconGetRect(NOTIFYICONIDENTIFIER identifier, WinDef.RECT iconLocation);

        /** `NOTIFYICONIDENTIFIER`（`Shell_NotifyIconGetRect` 的入参 ✓） */
        class NOTIFYICONIDENTIFIER extends com.sun.jna.Structure {
            public WinDef.HWND hWnd;
            public int uID;
            public com.sun.jna.platform.win32.Guid.GUID guidItem;

            @Override
            protected List<String> getFieldOrder() {
                return java.util.List.of("hWnd", "uID", "guidItem");
            }
        }
    }

    /** `dwmapi`：`DwmFlush` ✓ + `DwmGetWindowAttribute`（检测 DWM 遮蔽/绘制区 ✓）
     *  ⚠️ 这两个函数返回的是 **HRESULT** ✗ 不是 BOOL ✓ —— 声明成 `boolean` 会得到无意义的值 ✗
     *  （实测日志里 `DwmFlush=false` ✓ 就是踩了这个 ✓）→ 一律用 `int`，`0`(S_OK) 才算成功 ✓。 */
    interface Dwm extends Library {
        Dwm INSTANCE = Native.load("dwmapi", Dwm.class);

        int DwmFlush();

        int DwmGetWindowAttribute(WinDef.HWND hWnd, int attr, Pointer value, int size);
    }

    /**
     * `kernel32` —— `GetCurrentThreadId` **在这里** ✓ 不在 user32 ✗
     * （同上，声明错就是 `UnsatisfiedLinkError` ✓）。
     */
    interface Kernel32 extends Library {
        Kernel32 INSTANCE = Native.load("kernel32", Kernel32.class);

        int GetCurrentThreadId();
    }
}
