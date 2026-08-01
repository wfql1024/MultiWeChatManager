package com.jfmultichat.core.event;

import java.util.Map;

/**
 * 账号数据变更事件 — 任何账号数据更新操作完成后发布.
 * <p>
 * UI 订阅者据此定向推送 JS，仅刷新受影响的行/格，避免整表重渲染。
 *
 * @param swId       软件标识
 * @param accountId  账号 ID
 * @param changed    本次更新的字段 key → 新值
 */
public record AccountDataChangedEvent(String swId, String accountId, Map<String, Object> changed) {
}
