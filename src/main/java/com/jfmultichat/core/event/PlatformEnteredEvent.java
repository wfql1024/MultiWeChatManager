package com.jfmultichat.core.event;

/**
 * 平台页面进入事件 — 前端进入/切换平台时发布.
 * <p>
 * 订阅者据此自动触发该平台需要的数据加载/维护（登录态、PID、互斥体等）。
 */
public record PlatformEnteredEvent(String swId) {
}
