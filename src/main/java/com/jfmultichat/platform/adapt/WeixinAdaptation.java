package com.jfmultichat.platform.adapt;

import com.jfmultichat.platform.PlatformAdapter;
import com.jfmultichat.swcore.SwNativeOps;
import com.jfmultichat.swcore.WindowActivationOps;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * **新版微信（平台 id = {@code Weixin}）适配** —— 原生客户端（**不是 Electron** ✗）.
 *
 * <p>⚠️ 名字澄清（用户 2026-10-14 亲自纠正 ✓）：
 * **有"蒙一圈颜色"副作用的是新版微信 = `Weixin`** ✓；`WeChat` 是**旧版**微信 ✓。
 * （我最初把文件建成 `WeChatAdaptation` ✗ 已按用户指正改成 `WeixinAdaptation` ✓；
 * 旧版 `WeChat` 没有专属适配类 → 自动走**默认适配器** ✓，这正合本机制的设计 ✓。）
 *
 * <p>痛点 ✓：微信窗口收进托盘后要唤起，老做法（在 (8,8) 处**模拟双击**标题区 ✓）虽能把窗口叫出来 ✓，
 * 但会**先蒙上一圈颜色、拖动窗口才消失** ✗ —— 那是合成点击留下的"被按住"视觉态 ✓。
 * 所以本类改成**阶梯式**（能用轻的就别用重的 ✓）：
 * <ol>
 *   <li>窗口**本来可见** → 默认的"保状态激活" ✓（最小化才还原、否则只抬升 + 置前 ✓ 零副作用 ✓）</li>
 *   <li>窗口**不可见**（在托盘里）→ 先试**温和三连** ✓：`ShowWindowAsync(SW_SHOW)` → `ShowWindowAsync(SW_RESTORE)` → 抬升 → 置前；
 *       等一小会儿看是否可见 ✓ —— 成功就**没有颜色残留** ✓</li>
 *   <li>仍不可见 → 才用**老办法**（合成双击 ✓）兜底 ✓ —— 有颜色残留但至少窗口能出来 ✓</li>
 * </ol>
 */
public class WeixinAdaptation implements PlatformAdapter {

    private static final Logger LOG = LoggerFactory.getLogger(WeixinAdaptation.class);

    @Override
    public boolean activate(Ctx ctx) {
        if (ctx.hwnd == 0) return false;
        // ⚠️ **托盘图标是「切换」语义** ✗（与 QQNT 同 ✓）：窗口已可见时若再去点它 ✓
        //    会把这个窗口**收起来** ✗ → 所以只在**不可见**时才走托盘 ✓
        if (SwNativeOps.isWindowVisible(ctx.hwnd)) {
            SwNativeOps.raiseToTop(ctx.hwnd);
            SwNativeOps.tryForeground(ctx.hwnd);
            LOG.info("[适配] Weixin 窗口已可见 → 只抬升+置前（不点托盘 ✗ 免得被切回去 ✓）");
            return true;
        }
        // ① **托盘唤出** ✓ —— 但**只在"同名托盘图标恰好 1 个"时可用** ✓
        //    为什么 ✗：探针实证微信多开时任务栏上多个图标的 name **全是「微信」** ✗
        //    → 无法指定账号 ✓（调一次弹 A、再调又弹 B ✗ 用户实测 ✓）
        //    而**双击×2 作用在我们指定的 hwnd 上** ✓ → 天然按账号精确 ✓
        int iconCount = WindowActivationOps.countTrayIcons("微信");
        if (iconCount == 1) {
            if (WindowActivationOps.trayIconActivateByUia("微信", ctx.hwnd)) {
                LOG.info("[适配] Weixin 托盘唤出成功（UIA 调任务栏图标 ✓ 最自然 ✓）");
                return true;
            }
        } else {
            LOG.info("[适配] Weixin 任务栏「微信」图标数={} → 跳过托盘（多开时图标同名 ✗ 无法指定账号 ✓）"
                    + "，改用标题栏双击×2 ✓", iconCount);
        }
        // ② 兜底：**标题栏双击 ×2** —— 用户三方案实测对比后**胜出**的那条 ✓（最自然无副作用 ✓）
        //    （托盘唤不到时用它：例如图标被移出任务栏/被折叠且 Invoke 不生效 ✓）
        String r = WindowActivationOps.weixinWakeByTitleBarDoubleClick(ctx.hwnd);
        LOG.info("[适配] Weixin 标题栏双击唤醒（兜底）: {}", r);
        return true;
    }
}
