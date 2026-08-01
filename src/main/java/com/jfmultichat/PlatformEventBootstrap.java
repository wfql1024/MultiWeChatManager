package com.jfmultichat;

import com.jfmultichat.acccore.AccInfoFuncCore;
import com.jfmultichat.bridge.JsBridge;
import com.jfmultichat.core.EventBus;
import com.jfmultichat.core.event.AccountDataChangedEvent;
import com.jfmultichat.core.event.PlatformEnteredEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Map;

/**
 * 平台事件装配 — 注册 EventBus 订阅者（应用启动时调用一次）.
 * <p>
 * 流 A: 平台进入 → 后台维护登录态数据（PID 解析 / 共存关联 / 互斥体回写 SwAccData）.
 * 流 B: 账号数据变更 → 定向推送 UI（仅刷新受影响的行/格，不整表重渲染）.
 */
public final class PlatformEventBootstrap {

    private static final Logger LOG = LoggerFactory.getLogger(PlatformEventBootstrap.class);

    private PlatformEventBootstrap() {
    }

    /** 应用启动时注册所有事件订阅者 */
    public static void install(JsBridge bridge) {
        // 流 A：平台进入 → 后台维护登录态数据
        EventBus.getInstance().subscribe(PlatformEnteredEvent.class, e ->
                JsBridge.runInBackground(() -> {
                    try {
                        String sw = e.swId();
                        Map<Integer, String> pidAccMap = AccInfoFuncCore.resolvePidAccountMap(sw);
                        if (pidAccMap == null) {
                            LOG.warn("[PlatformMaintenance] 数据路径不存在: {}", sw);
                            return;
                        }
                        pidAccMap = AccInfoFuncCore.associateCoexistAccounts(sw, pidAccMap);
                        List<String> allAccs = AccInfoFuncCore.getSwAllAccountsExisted(sw, null);
                        AccInfoFuncCore.updateAccLoginData(sw, pidAccMap, allAccs);
                        LOG.info("[PlatformMaintenance] 平台 {} 登录态数据维护完成, 账号数={}", sw, allAccs.size());
                    } catch (Exception ex) {
                        LOG.warn("[PlatformMaintenance] 维护失败: {}", e.swId(), ex);
                    }
                })
        );

        // 流 B：账号数据变更 → 定向推送 UI
        EventBus.getInstance().subscribe(AccountDataChangedEvent.class,
                e -> bridge.pushAccountDataChanged(e.swId(), e.accountId(), e.changed()));
    }
}
