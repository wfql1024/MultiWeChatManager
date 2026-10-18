package com.jfmultichat.platform;

/**
 * **平台适配器** —— 让"不同平台的窗口行为差异"从业务代码里挪出来 ✓.
 *
 * <p>用户 2026-10-14 的想法（他自称不擅长设计模式 ✓）：希望有一个外部类（比如 {@code WeChatAdaptation}）能对方法做扩展 ✓，
 * 类里**没写**同名方法就走默认 ✓、**写了**就走适配 ✓ —— 目的：**业务方法不用被频繁维护和改动** ✓。
 *
 * <p>这在 Java 里正好就是 **接口 + default 方法** ✓✓：
 * <ul>
 *   <li>本接口的每个方法都有**默认实现**（= 现在已验证的通用做法 ✓）→ 适配类**只写它要改的那几个** ✓</li>
 *   <li>加载约定（见 {@link PlatformAdapters}）：`com.jfmultichat.platform.adapt.{平台id}Adaptation` ✓ ——
 *       **新增一个平台 = 丢一个新类进去** ✓ 注册表、业务代码、配置**都不用改** ✓✓</li>
 * </ul>
 *
 * <p>写适配类的三条注意事项 ✓：
 * <ol>
 *   <li>**能不改行为就不改** ✓ —— 默认实现都是实测过的（例如"保状态激活"：最小化才还原、否则只抬升 ✓）</li>
 *   <li>要调用底层就用 {@code swcore.SwNativeOps} / {@code swcore.WindowActivationOps} ✓（已有全套验证过的手法 ✓）</li>
 *   <li>适配器里**不要**做重活/阻塞 ✓（这些方法在切窗链路上被调用 ✓）</li>
 * </ol>
 */
public interface PlatformAdapter {

    /** 一次窗口操作的全部上下文（适配器按需取用 ✓） */
    final class Ctx {
        /** 平台 id（WeChat / Weixin / QQNT / QQ …） */
        public final String sw;
        /** 账号 id */
        public final String acc;
        /** 目标窗口句柄（**可能已作废** ✗ —— 例如 QQNT 关闭窗口后 Electron 销毁了它 ✓ 此时改按 {@link #pid} 走 ✓） */
        public final int hwnd;
        /** 该平台的**进程 id**（0 = 未知 ✓）—— 进程才是稳定身份 ✓（窗口会重生 ✓） */
        public final int pid;
        /** 调用的这一刻，窗口是否本来可见 ✓（"被藏进托盘"的判据之一 ✓） */
        public final boolean visibleBefore;
        /** 我们想摆成的物理像素矩形 {x,y,w,h}；null = 不改几何 ✓ */
        public final int[] rect;
        /** 这次是否要求它**最大化** ✓ */
        public final boolean wantMaximized;
        /** 适配器唤活之后，如果**主窗口重生了**，把新的 hwnd 写回这里 ✓（调用方负责更新绑定 ✓） */
        public int resolvedHwnd;

        public Ctx(String sw, String acc, int hwnd, int pid, boolean visibleBefore, int[] rect, boolean wantMaximized) {
            this.sw = sw;
            this.acc = acc;
            this.hwnd = hwnd;
            this.pid = pid;
            this.visibleBefore = visibleBefore;
            this.rect = rect;
            this.wantMaximized = wantMaximized;
            this.resolvedHwnd = hwnd;
        }
    }

    /**
     * **唤起窗口**（默认：保状态激活 ✓）.
     *
     * <p>默认实现 = 用户 2026-10-14 验证过的"**保状态激活**" ✓：
     * 最小化才 `SW_RESTORE` ✓，普通/最大化**只抬升 + 置前** ✓ —— 绝不 `SW_SHOWNORMAL` ✗
     * （那会把最大化抹掉 ✓ 曾导致"切回 A 后 A 变成普通窗口" ✗）。
     *
     * @return 是否至少做成了"抬升/恢复"这一步 ✓
     */
    default boolean activate(Ctx ctx) {
        // **统一模板（用户 2026-10-16 定）** ✓ —— 所有平台的唤起都按这个骨架走：
        //   ①**已经在桌面上**（含"只是最小化" ✓ —— 最小化窗口 `IsWindowVisible` 仍为 true ✓）
        //     → **直接置前** ✓（保状态激活：最小化才 `SW_RESTORE`，否则只抬升 + 置前 ✓）
        //     用户旧版实测 ✓："已打开的窗口哪怕只是最小化，都可以直接通过 hwnd 提到顶层、
        //     也可以直接改变位置和大小，**没有副作用**" ✓
        //   ②**不可见**（被收进托盘 / 被隐藏 ✓）→ 返回 false ✓，由各平台适配器走**它自己的通道** ✓
        //     （Electron：托盘消息 ✓；微信：托盘图标 UIA / 标题栏双击×2 ✓）
        int target = ctx.resolvedHwnd != 0 ? ctx.resolvedHwnd : ctx.hwnd;
        if (target == 0) return false;
        if (!com.jfmultichat.swcore.SwNativeOps.isWindowVisible(target)) {
            return false;                        // 在托盘里 → 绝不"乱动" ✗，交给适配器 ✓
        }
        return com.jfmultichat.swcore.SwNativeOps.restoreWindowAndActivate(ctx.sw, target);
    }

    /**
     * **摆位前的准备**（默认：该普通而它正最大化 → 先真还原 ✓）.
     *
     * <p>为什么必须存在这一步：对**最大化**窗口直接 `SetWindowPos` 是**无效的** ✗
     * （只改"还原矩形"，窗口视觉上仍最大化 ✓）。默认实现就是先 `SW_RESTORE` ✓。
     * <p>Electron 平台会覆盖它：先用**托盘唤醒**把它叫回来（而不是硬还原 ✓）。
     */
    default void beforePlace(Ctx ctx) {
        if (ctx.rect == null) return;
        if (com.jfmultichat.swcore.SwNativeOps.isMaximized(ctx.hwnd)) {
            com.jfmultichat.swcore.SwNativeOps.restoreWindowOnly(ctx.hwnd);
        }
    }

    /** 摆位后的收尾（默认：无 ✓）——画面冻住类问题的"解冻连打"就挂在这里 ✓ */
    default void afterPlace(Ctx ctx) {
        // 默认什么都不做 ✓
    }

    /**
     * **是否允许"外部强制摆位"**（默认允许 ✓）.
     *
     * <p>依据 ✓（用户 2026-10-15 指的那篇 [自建任务栏 qq关闭后再打开窗口，窗口卡死解决办法](https://misuseds.blog.csdn.net/article/details/166489064)
     * + 用户 2026-10-16 的实测补充 ✓）：
     * <ul>
     *   <li>**刚从托盘被唤醒**的 Electron 窗口 ✗ —— 文章明确"避免…外部强制显示操作"，搬运会把它弄冻 ✓
     *       → 这种情形不许摆位 ✗（见 {@code ElectronAdaptation}：`return ctx.visibleBefore;` ✓）</li>
     *   <li>**本来就在桌面上**的窗口（含最小化 ✓）—— 用户旧版实测：置前/改位置/改大小**都没有副作用** ✓
     *       → 照常摆位 ✓</li>
     * </ul>
     */
    default boolean allowExternalPlacement(Ctx ctx) {
        return true;
    }
}
