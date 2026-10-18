package com.jfmultichat.platform.adapt;

import com.jfmultichat.platform.PlatformAdapter;
import com.jfmultichat.swcore.SwNativeOps;
import com.jfmultichat.swcore.WindowActivationOps;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * **Electron 系平台**的公共适配（QQNT、以及将来任何 Electron 客户端 ✓）.
 *
 * <p>依据（用户 2026-10-14 实测 ✓ + 联网资料 ✓）：Electron 窗口被系统判定为「不在屏幕上」时
 * **Chromium 渲染器会停住** ✓（界面在、点不动 ✓）；而 25 种唤起手法里**只有"托盘唤醒"可用且最丝滑** ✓ ——
 * 把「点一下托盘图标」这条消息交还给程序自己 ✓（{@code WM_APP+1} + {@code WM_LBUTTONDOWN} ✓）。
 *
 * <p>所以本类只做两件与通用不同的事 ✓：
 * <ol>
 *   <li>{@link #activate}：**先用托盘唤醒** ✓（而不是靠 `ShowWindow`/硬拉 —— 那些正是把它弄冻的原因 ✗）；
 *       托盘不可用时才退回默认的"保状态激活" ✓</li>
 *   <li>{@link #beforePlace}：Electron 窗口若正最大化，**也先走托盘唤醒**把它叫活 ✓ 再还原 ✓
 *       （避免"对冻结窗口直接 {@code SW_RESTORE} + {@code SetWindowPos}"这种最容易出白屏的组合 ✗）</li>
 * </ol>
 */
public class ElectronAdaptation implements PlatformAdapter {

    private static final Logger LOG = LoggerFactory.getLogger(ElectronAdaptation.class);

    /** 托盘图标 id ✓（Electron 侧同一进程内第几个托盘图标；QQNT 是 3 ✓ 子类可改 ✓） */
    protected int trayIconId() {
        return 1;
    }

    @Override
    public boolean activate(Ctx ctx) {
        // **统一模板（用户 2026-10-16 定）** ✓：已经开着的窗口（含只是最小化 ✓）由父类**直接置前** ✓
        //   —— 用户旧版实测：这种情形用 hwnd 提顶层/改位置大小**都没有副作用** ✓
        //   注意 ✗：绝不能在"已可见"时去发托盘消息 ✓（托盘是**切换**语义 → 会把它又切回去/切进坏状态 ✗）
        if (PlatformAdapter.super.activate(ctx)) {
            LOG.info("[适配] {} 窗口已可见（含最小化 ✓）→ 直接置前 ✓（不碰托盘 ✗）", ctx.sw);
            return true;
        }
        // 走到这里 = 窗口**不可见**（在托盘里 ✓ 或已被 Electron 销毁 ✓）→ 走它自己的通道 ✓
        // 优先按 pid 走 ✓（用户实测：QQNT 关闭后主窗口 hwnd 会被 Electron 销毁 ✗，但进程/托盘还在 ✓）
        if (ctx.pid != 0 && WindowActivationOps.hasElectronTrayByPid(ctx.pid)) {
            boolean ok = WindowActivationOps.trayActivateByPid(ctx.pid, trayIconId());
            if (ok) {
                afterWake(ctx);
                return true;
            }
        }
        if (ctx.hwnd != 0 && WindowActivationOps.hasElectronTray(ctx.hwnd)) {
            boolean ok = WindowActivationOps.trayActivate(ctx.hwnd, trayIconId());
            if (ok) {
                // 同样**不做外部推拉** ✗（文章口径 ✓）
                return true;
            }
        }
        LOG.info("[适配] {} 托盘唤醒未成功 ✓", ctx.sw);
        return false;
    }

    /**
     * 唤活之后收尾 ✓：QQNT 会把主窗口**重新创建**出来 ✓ —— 这时旧 hwnd 已作废 ✗，
     * 必须**找回新的主窗口** ✓ 写进 {@code ctx.resolvedHwnd} ✓（调用方据此更新绑定 ✓），再轻轻抬升 ✓。
     */
    protected void afterWake(Ctx ctx) {
        // ⚠️⚠️ 依据用户给的文章 ✓（[自建任务栏 qq关闭后再打开窗口，窗口卡死解决办法](https://misuseds.blog.csdn.net/article/details/166489064)）：
        //   "发对托盘那条消息之后，主窗口**自己回到屏幕上**，**没有再被外部强制显示**" ✓
        //   → 所以我**只读不碰** ✗：只把重生后的主窗口 hwnd **记下来**（供绑定/跟随 ✓），
        //     **绝不** raiseToTop / SetForegroundWindow / SetWindowPos ✓（那些是外部强制 ✗ → 会让它"出来但卡住" ✓ 用户实测 ✓）
        int fresh = WindowActivationOps.findMainWindowOfPid(ctx.pid);
        if (fresh != 0) {
            ctx.resolvedHwnd = fresh;
            LOG.info("[适配] {} 唤活后主窗口 = 0x{}（**不做任何外部强制** ✓ 让它自己回到屏幕 ✓）",
                    ctx.sw, Integer.toHexString(fresh));
        } else {
            LOG.info("[适配] {} 唤活后暂时没找到主窗口（可能还在创建 ✓）", ctx.sw);
        }
    }

    // ⚠️ 这里**故意不再覆盖** `beforePlace` / `allowExternalPlacement` ✗（2026-10-16 用户实测纠正 ✓）：
    //   用户定的窗口切换流程是**两步** ✓：①唤起（激活）②**调整窗口状态** ✓
    //   —— 即使目标是"已关闭、在托盘里"的窗口 ✓，②也必须照做 ✓
    //   （否则就会像用户实测那样：QQNT 只恢复成自己原来的最大化 ✗ 而没有变成上一个窗口的位置尺寸 ✓）
    //   之前我按文章口径把它**整体禁掉** ✗ → 就是把②也一起禁了 ✓ 属于**扩大化** ✗。
    //   唯一要禁的是"**再发一次托盘消息**" ✗（那才是卡住的元凶 ✓）—— 那只存在于旧 beforePlace 里，已删 ✓。

    @Override
    public void afterPlace(Ctx ctx) {
        // ⚠️ 这里**只做诊断，不做任何外部操作** ✗（用户给的文章 ✓：
        //    Electron 窗口"出来但卡住"就是被外部强制操作搞的 ✗ —— 尺寸抖动/抬升也属此类 ✓）
        try {
            int target = ctx.resolvedHwnd != 0 ? ctx.resolvedHwnd : ctx.hwnd;
            if (target != 0 && !SwNativeOps.isWindowVisible(target)) {
                LOG.info("[适配] {} 唤出后仍不可见 → **不做外部强制** ✗（避免把它推进卡住状态 ✓）"
                        + "，交由下一次托盘点击或用户手动处理 ✓", ctx.sw);
            }
        } catch (Throwable t) {
            LOG.debug("[适配] afterPlace 收尾失败: {}", t.getMessage());
        }
    }
}
