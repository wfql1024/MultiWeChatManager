package com.jfmultichat.acccore;

import com.jfmultichat.config.ConfigManager;
import com.jfmultichat.core.task.TaskContext;
import com.jfmultichat.core.task.TaskRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Map;

/**
 * **启动全局扫描（一次性）**：进软件时当前平台照旧优先加载 ✓，
 * 其余平台由**后台线程**把必要信息（**pid / hwnd**）补进内存 ✓ ——
 * 这样用户点侧栏时就能**直接**看到所有已在线账号 ✓，不必先逐个去平台页面刷一遍 ✓（用户 2026-10-16 要求 ✓）。
 *
 * <p>走**任务中心** ✓（用户要求：这是耗时任务，运行中要显示在任务中心 ✓）：
 * {@code TaskRegistry.submit(...)} + 逐平台 {@code TaskContext.phase(...)} / {@code checkpoint()} ✓。
 *
 * <p>唯一写入点 ✓：扫描结果只经 {@link AccInfoFuncCore#refreshLiveWindows(String)} →
 * {@link AccRuntimeStore}（内存表 ✓）；每次写入会自动 bump 版本号 ✓
 * → 侧栏下一帧就会重建按钮列表 ✓，**不需要额外推送通道** ✓。
 */
public final class StartupAccountScan {

    private static final Logger LOG = LoggerFactory.getLogger(StartupAccountScan.class);

    private StartupAccountScan() {
    }

    /** 提交一次性启动扫描（本身**非阻塞** ✓ 任务体由任务中心开线程跑 ✓） */
    public static void submit() {
        List<String> sws;
        try {
            sws = ConfigManager.getInstance().getSwList();
        } catch (Throwable t) {
            LOG.warn("[启动扫描] 取平台列表失败，跳过: {}", t.getMessage());
            return;
        }
        if (sws == null || sws.isEmpty()) {
            LOG.info("[启动扫描] 没有已绑定平台，跳过 ✓");
            return;
        }
        final List<String> targets = sws;
        try {
            TaskRegistry.get().submit("startup-scan", "启动扫描：补齐各平台 PID/HWND", "后台一次性",
                    () -> run(targets));
            LOG.info("[启动扫描] 已提交任务中心：{} 个平台（{}）", targets.size(), String.join("/", targets));
        } catch (Throwable t) {
            LOG.warn("[启动扫描] 提交任务失败: {}", t.getMessage());
        }
    }

    private static void run(List<String> sws) {
        long t0 = System.currentTimeMillis();
        int hit = 0;
        for (int i = 0; i < sws.size(); i++) {
            String sw = sws.get(i);
            TaskContext.checkpoint();                                   // 可取消 ✓（协作式：跑到这里才停 ✓）
            TaskContext.phase("扫描 " + sw + "（" + (i + 1) + "/" + sws.size() + "）", "扫描 " + sw);
            try {
                Map<String, int[]> live = AccInfoFuncCore.refreshLiveWindows(sw);
                int n = live == null ? 0 : live.size();
                hit += n;
                LOG.info("[启动扫描] {}：命中 {} 个账号窗口（pid/hwnd 已写入内存 ✓）", sw, n);
            } catch (Throwable t) {
                LOG.warn("[启动扫描] {} 扫描失败: {}", sw, t.getMessage());
            }
            sleep(150);                                                 // 平台之间稍歇 ✓ 别与会话/进程扫描抢资源 ✓
        }
        LOG.info("[启动扫描] 全部完成：{} 个平台，共命中 {} 个窗口，耗时 {}ms",
                sws.size(), hit, System.currentTimeMillis() - t0);
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}
