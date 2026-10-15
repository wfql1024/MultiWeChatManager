package com.jfmultichat.platform.adapt;

/**
 * **QQNT 适配**（Electron ✓）.
 *
 * <p>用户 2026-10-14 实测：QQNT 关闭窗口后用 hwnd 直接唤起 → 界面出来了却卡住 ✓；
 * 25 种方式里**只有"托盘唤醒"可用且最丝滑** ✓（甚至没有微信那种"蒙一圈颜色、要拖动才消失"的副作用 ✓）。
 *
 * <p>本类**只改一个数字** ✓：QQNT 的托盘图标 id = **3** ✓（可用测试台「诊断 · 列窗口与类名」旁的
 * `Shell_NotifyIconGetRect` 思路核对；实测 3 有效 ✓）。其余全部继承
 * {@link ElectronAdaptation}（托盘唤醒 + 摆位前叫活 + 摆位后必要时解冻 ✓）。
 *
 * <p>要为自己定制的平台加适配：**在这个包里新建 `{平台id}Adaptation` 即可自动生效** ✓
 * （不需要改注册表 / 业务代码 / 配置 ✓ 见 {@code PlatformAdapters}）。
 */
public class QQNTAdaptation extends ElectronAdaptation {

    @Override
    protected int trayIconId() {
        return 3;
    }
}
