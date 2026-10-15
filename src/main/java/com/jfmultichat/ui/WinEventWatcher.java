package com.jfmultichat.ui;

import com.sun.jna.Native;
import com.sun.jna.platform.win32.Kernel32;
import com.sun.jna.platform.win32.User32;
import com.sun.jna.platform.win32.WinDef;
import com.sun.jna.platform.win32.WinNT;
import com.sun.jna.platform.win32.WinUser;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;

/**
 * **Windows 事件钩子监听器**（`SetWinEventHook`）—— 侧栏"跟随外部窗口"的事件来源.
 *
 * <p>为什么用钩子而不是轮询（用户 2026-10-13：旧版 5ms 轮询"太耗资源、延迟大、不跟手"）：
 * <ul>
 *   <li>官方文档（{@code SetWinEventHook}）：{@code WINEVENT_OUTOFCONTEXT} 时**回调不映射进目标进程** →
 *       **不需要注入、不需要 DLL** ✓；事件跨进程排队且**保证有序** ✓</li>
 *   <li>官方文档同时明确：**调用 SetWinEventHook 的那个线程必须有消息循环**，
 *       且**事件就投递在那个线程上** ✓ → 所以这里单独起一条 daemon 线程装钩子 + 跑消息泵 ✓</li>
 *   <li>空闲时**零开销**（没有事件就阻塞在 {@code GetMessage} 上）✓ 事件来了立刻到 ✓ 拖动跟手 ✓</li>
 * </ul>
 *
 * <p>⚠️ 官方警告：钩子回调**可能重入**（处理一个事件时又触发新事件）。
 * 因此回调里**只做三件事**：过滤、写 volatile 字段、`seq++` —— **绝不做任何重活**（更不碰 UI）✓；
 * 真正的几何计算与窗口移动交给 JavaFX 侧按帧消费（见 {@code FloatingSidebar} 的 AnimationTimer）✓。
 */
public final class WinEventWatcher {

    // ---- 关心的系统事件（值取自 Winuser.h；见 MS Learn "Event Constants"）----
    /** 前台窗口变化（决定侧栏跟谁） */
    public static final int EVENT_SYSTEM_FOREGROUND = 0x0003;
    /** 窗口开始最小化 */
    public static final int EVENT_SYSTEM_MINIMIZESTART = 0x0016;
    /** 窗口还原（最小化结束） */
    public static final int EVENT_SYSTEM_MINIMIZEEND = 0x0017;
    /** 对象销毁（窗口被关掉） */
    public static final int EVENT_OBJECT_DESTROY = 0x8001;
    /** 对象位置/形状/尺寸变化（顶层窗口移动、改大小；官方：不为子对象逐个发） */
    public static final int EVENT_OBJECT_LOCATIONCHANGE = 0x800B;

    private static final int WINEVENT_OUTOFCONTEXT = 0x0000;
    /**
     * ⚠️ **刻意不加** {@code WINEVENT_SKIPOWNPROCESS}（用户 2026-10-14）.
     *
     * <p>先前跳过了本进程 ✓ → 于是**我们自己的主窗口**永远不会有前台事件 ✗ →
     * 切到主窗口时侧栏只能靠 JavaFX 的焦点"监听"来补 ✗ → 而那个监听与钩子事件**两个来源打架** ✓
     * → 表现就是用户看到的"侧栏闪着跟了一下主窗口，然后又跟回平台窗口" ✗✓。
     * <p>现在**只留钩子这一个来源** ✓：本进程的前台事件也照收 ✓（忽略侧栏自己那个窗口即可 ✓）。
     */
    private static final int WINEVENT_SKIPOWNPROCESS_DISABLED = 0x0002;   // 保留常量以便需要时恢复，但不参与组合
    private static final int OBJID_WINDOW = 0;          // 只关心"窗口对象"本身
    private static final int CHILDID_SELF = 0;          // 只关心对象自身（不是它的某个子项）
    private static final int WM_QUIT = 0x0012;

    private static final Logger LOG = LoggerFactory.getLogger(WinEventWatcher.class);

    /** user32 里 JNA 没暴露的一个小函数：给某线程的消息队列投 WM_QUIT（用来让消息泵优雅退出） */
    private interface User32MsgExt extends com.sun.jna.Library {
        User32MsgExt INSTANCE = Native.load("user32", User32MsgExt.class);

        boolean PostThreadMessageW(int idThread, int msg, WinDef.WPARAM wParam, WinDef.LPARAM lParam);
    }

    private final Thread thread;
    private volatile boolean running;
    private volatile int threadId;

    /** 回调对象必须**长期持有引用**（否则被 GC 掉，钩子就再也不回调了） */
    private final WinUser.WinEventProc callback = this::onWinEvent;
    private final List<WinNT.HANDLE> hooks = new ArrayList<>();

    // ---- 回调只写这几个字段（读侧是 JavaFX 线程）----
    /** 当前前台窗口（0 = 未知） */
    private volatile int foregroundHwnd;
    /** 最近一次事件涉及的窗口与事件号（供诊断/过滤） */
    private volatile int lastEventHwnd;
    private volatile int lastEvent;
    /** 事件序号：**每到一次我们关心的事件就 +1** —— JavaFX 侧靠它判断"这帧要不要重算" */
    private volatile long seq;

    public WinEventWatcher() {
        this.thread = new Thread(this::run, "win-event-watch");
        this.thread.setDaemon(true);
    }

    /** 开钩子（幂等：已在跑就什么都不做） */
    public synchronized void start() {
        if (running) return;
        running = true;
        thread.start();
        LOG.info("[侧栏] WinEvent 监听线程已启动");
    }

    /** 关钩子：让消息泵退出并卸载全部钩子（幂等） */
    public synchronized void stop() {
        if (!running) return;
        running = false;
        int tid = threadId;
        if (tid != 0) {
            User32MsgExt.INSTANCE.PostThreadMessageW(tid, WM_QUIT, new WinDef.WPARAM(0), new WinDef.LPARAM(0));
        }
        LOG.info("[侧栏] WinEvent 监听线程已请求退出");
    }

    public boolean isRunning() {
        return running;
    }

    /** 事件序号（JavaFX 侧每帧读一次即可：没变就什么都不用算 ✓） */
    public long getSeq() {
        return seq;
    }

    public int getForegroundHwnd() {
        return foregroundHwnd;
    }

    public int getLastEventHwnd() {
        return lastEventHwnd;
    }

    public int getLastEvent() {
        return lastEvent;
    }

    // ==================== 内部：线程 + 消息泵 ====================

    private void run() {
        threadId = Kernel32.INSTANCE.GetCurrentThreadId();
        try {
            hook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND);
            hook(EVENT_SYSTEM_MINIMIZESTART, EVENT_SYSTEM_MINIMIZEEND);   // 合并成一个区间装一次
            hook(EVENT_OBJECT_DESTROY, EVENT_OBJECT_DESTROY);
            hook(EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_LOCATIONCHANGE);
            // 装钩子那一刻的前台窗口也要拿到（否则要等到用户切一次窗口才有值）
            foregroundHwnd = hwndToInt(User32.INSTANCE.GetForegroundWindow());
            seq++;
            LOG.info("[侧栏] 钩子已装载（{} 个），当前前台窗口=0x{}", hooks.size(),
                    Integer.toHexString(foregroundHwnd));
        } catch (Throwable t) {
            LOG.error("[侧栏] 装载 WinEvent 钩子失败", t);
        }

        // 消息泵：官方要求装钩子的线程必须有消息循环；没事件时阻塞在这里 → 空闲零 CPU ✓
        WinUser.MSG msg = new WinUser.MSG();
        while (running) {
            int r;
            try {
                r = User32.INSTANCE.GetMessage(msg, null, 0, 0);
            } catch (Throwable t) {
                LOG.warn("[侧栏] GetMessage 异常，退出消息泵: {}", t.getMessage());
                break;
            }
            if (r == 0 || r == -1) break;                 // 0 = WM_QUIT；-1 = 出错
            User32.INSTANCE.TranslateMessage(msg);
            User32.INSTANCE.DispatchMessage(msg);
        }

        // 退出前卸载钩子
        for (WinNT.HANDLE h : hooks) {
            try {
                User32.INSTANCE.UnhookWinEvent(h);
            } catch (Throwable ignore) {
                // 退出阶段失败无所谓
            }
        }
        hooks.clear();
        LOG.info("[侧栏] WinEvent 监听线程已退出");
    }

    private void hook(int eventMin, int eventMax) {
        WinNT.HANDLE h = User32.INSTANCE.SetWinEventHook(
                eventMin, eventMax,
                null,                                   // OUTOFCONTEXT → 不需要 DLL
                callback,
                0, 0,                                   // 所有进程、所有线程
                WINEVENT_OUTOFCONTEXT);                 // **不跳过本进程**（要看得见我们自己的主窗口 ✓）
        if (h == null) {
            LOG.warn("[侧栏] SetWinEventHook 失败: 事件区间 0x{}-0x{}",
                    Integer.toHexString(eventMin), Integer.toHexString(eventMax));
        } else {
            hooks.add(h);
        }
    }

    /**
     * 钩子回调（**在监听线程上执行，且可能重入** → 这里只做过滤 + 写字段）.
     *
     * <p>⚠️ 签名必须与 JNA 的 {@code WinUser.WinEventProc#callback} **完全一致**（数值参数是
     * {@link WinDef.DWORD} / {@link WinDef.LONG} 包装类型，不是 int ✗）—— 否则方法引用编译不过 ✓。
     */
    private void onWinEvent(WinNT.HANDLE hook, WinDef.DWORD event, WinDef.HWND hwnd,
                            WinDef.LONG idObject, WinDef.LONG idChild,
                            WinDef.DWORD idEventThread, WinDef.DWORD dwmsEventTime) {
        int ev = event == null ? 0 : event.intValue();
        int obj = idObject == null ? 0 : idObject.intValue();
        int child = idChild == null ? 0 : idChild.intValue();
        // 对象类事件只为"窗口对象自身"处理（过滤掉子对象/光标等噪声）
        if (ev >= EVENT_OBJECT_DESTROY && (obj != OBJID_WINDOW || child != CHILDID_SELF)) {
            return;
        }
        int h = hwndToInt(hwnd);
        if (h == 0) return;
        lastEvent = ev;
        lastEventHwnd = h;
        if (ev == EVENT_SYSTEM_FOREGROUND) {
            foregroundHwnd = h;
        }
        seq++;
    }

    private static int hwndToInt(WinDef.HWND hwnd) {
        if (hwnd == null) return 0;
        try {
            return com.jfmultichat.swcore.SwNativeOps.hwndToInt(hwnd);
        } catch (Throwable t) {
            return 0;
        }
    }
}
