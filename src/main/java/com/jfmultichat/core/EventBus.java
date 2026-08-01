package com.jfmultichat.core;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

/**
 * 轻量事件总线（观察者模式）— 数据更新与 UI 刷新解耦.
 * <p>
 * 发布方与订阅方通过强类型事件间接联系，互不依赖。
 * 事件发布与订阅为线程安全；publish 在调用方线程同步分发，
 * 耗时订阅者自行起后台线程，UI 推送走 JsBridge.pushToJs（内部 Platform.runLater）。
 */
public final class EventBus {

    private static final Logger LOG = LoggerFactory.getLogger(EventBus.class);
    private static final EventBus INSTANCE = new EventBus();

    private final Map<Class<?>, List<Consumer<?>>> subscribers = new ConcurrentHashMap<>();

    private EventBus() {
    }

    public static EventBus getInstance() {
        return INSTANCE;
    }

    /** 订阅某类型事件，handler 收到事件后处理 */
    public <T> void subscribe(Class<T> type, Consumer<T> handler) {
        subscribers.computeIfAbsent(type, k -> new CopyOnWriteArrayList<>()).add(handler);
    }

    /** 发布事件，同步分发给所有订阅者；单个订阅者异常不影响其它订阅者 */
    @SuppressWarnings("unchecked")
    public <T> void publish(T event) {
        Class<?> type = event.getClass();
        List<Consumer<?>> list = subscribers.get(type);
        if (list == null || list.isEmpty()) return;
        for (Consumer<?> h : list) {
            try {
                ((Consumer<T>) h).accept(event);
            } catch (Exception e) {
                LOG.warn("[EventBus] 订阅者异常 {}", type.getSimpleName(), e);
            }
        }
    }
}
