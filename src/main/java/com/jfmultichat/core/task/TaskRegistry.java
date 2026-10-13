package com.jfmultichat.core.task;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Consumer;

/**
 * 任务中心 —— 所有**耗时流程**的登记处（可见 + 可取消）.
 *
 * <p>用法（调用点只多一行包裹，核心方法不动）：
 * <pre>
 * TaskRegistry.get().submit("login", "登录 3 个账号", swId, () -&gt; {
 *     AccOperatorCore.loginOrigin(swId, accIds);   // ← 内部靠 TaskContext.checkpoint() 响应取消
 * });
 * </pre>
 *
 * <p>设计要点：
 * <ul>
 *   <li><b>协作式取消</b>：{@code cancel(id)} 只是"请求" + 中断线程；流程跑到下一个
 *       {@link TaskContext#checkpoint()} 才真正停下（Java 没有安全的强制杀线程）</li>
 *   <li><b>取消不回滚</b>：已经开出来的窗口/已经发出的点击留着不动（用户可自行关闭）</li>
 *   <li><b>完成的任务保留</b> 最近 {@link #KEEP_FINISHED} 条，供回看与统计</li>
 *   <li>变化时通知订阅者（前端面板靠它刷新；elapsed 由前端自己按 startedAt 每秒递增，服务端不推送心跳）</li>
 * </ul>
 */
public final class TaskRegistry {

    private static final Logger LOG = LoggerFactory.getLogger(TaskRegistry.class);

    /**
     * 已完成任务保留条数（超出后清最旧的已完成项）.
     * <p>2026-10-12：20 → **300** —— 任务中心有"进行中/已完成/已取消"三小栏、统计页要看列表，
     * 保留太少会"刚跑完就没了"；更久的历史仍在 {@code stats/task_stats.jsonl}（无上限追加）。
     */
    private static final int KEEP_FINISHED = 300;

    private static final TaskRegistry INSTANCE = new TaskRegistry();

    public static TaskRegistry get() { return INSTANCE; }

    private final Map<String, JfTask> tasks = new ConcurrentHashMap<>();
    private final List<Consumer<List<Map<String, Object>>>> listeners = new CopyOnWriteArrayList<>();
    private final AtomicInteger seq = new AtomicInteger();
    private final ExecutorService pool = Executors.newCachedThreadPool(r -> {
        Thread t = new Thread(r, "jf-task-" + System.nanoTime() % 1000);
        t.setDaemon(true);
        return t;
    });

    private TaskRegistry() {}

    // ==================== 提交 ====================

    /** 提交并**异步**执行一个任务体；返回任务（可拿 id） */
    public JfTask submit(String kind, String title, String target, Runnable body) {
        JfTask task = new JfTask(UUID.randomUUID().toString().substring(0, 8),
                kind, title, target);
        tasks.put(task.getId(), task);
        LOG.info("[任务] 开始 #{} {}（{}）", task.getId(), title, target == null ? "-" : target);
        pool.submit(() -> {
            TaskContext.bind(task);
            long t0 = System.currentTimeMillis();
            try {
                body.run();
                if (task.isCancelRequested()) task.finish(JfTask.State.CANCELLED, null);
                else task.finish(JfTask.State.DONE, null);
            } catch (TaskCancelledException ce) {
                task.finish(JfTask.State.CANCELLED, null);
            } catch (Throwable t) {
                task.finish(JfTask.State.FAILED, t.getMessage() == null ? t.toString() : t.getMessage());
                LOG.warn("[任务] 失败 #{} {}: {}", task.getId(), title, task.getError());
            } finally {
                TaskContext.unbind();
                Thread.interrupted();          // 清掉中断标志，避免污染池里复用的线程
                long ms = System.currentTimeMillis() - t0;
                if (task.getState() == JfTask.State.DONE) {
                    LOG.info("[任务] 完成 #{} {} 耗时 {}ms", task.getId(), title, ms);
                }
                // 统计与任务中心**同源**：任务边界天然就是计时区间 → 这里记一条（业务方法零侵入）
                TaskStats.get().record(task);
                // JFR 事件（用户 2026-10-12：开发中就用上 JFR）—— 未开录制时 commit() 几乎零开销
                try {
                    TaskJfrEvent ev = new TaskJfrEvent();
                    ev.kind = task.getKind();
                    ev.sw = task.getTarget();
                    ev.result = task.getState().name();
                    ev.durationMs = ms;
                    ev.lastPhase = task.getPhase();
                    ev.commit();
                } catch (Throwable ignore) {
                    // JFR 不可用也不影响功能
                }
                trimFinished();
                fireChanged();
            }
        });
        fireChanged();
        return task;
    }

    /** 便捷版：给任务体一个 ctx 参数（省一次 TaskContext.current()） */
    public JfTask submit(String kind, String title, String target, Consumer<JfTask> body) {
        return submit(kind, title, target, () -> body.accept(TaskContext.current()));
    }

    // ==================== 查询 / 取消 ====================

    public JfTask get(String id) { return id == null ? null : tasks.get(id); }

    /** 全部任务：进行中的在前，其次按开始时间倒序 */
    public List<Map<String, Object>> list() {
        List<JfTask> all = new ArrayList<>(tasks.values());
        all.sort(Comparator
                .comparing((JfTask t) -> !t.isActive())          // active 优先
                .thenComparing(Comparator.comparingLong(JfTask::getStartedAt).reversed()));
        List<Map<String, Object>> out = new ArrayList<>(all.size());
        for (JfTask t : all) out.add(t.toMap());
        return out;
    }

    public int activeCount() {
        int n = 0;
        for (JfTask t : tasks.values()) if (t.isActive()) n++;
        return n;
    }

    public boolean cancel(String id) {
        JfTask t = tasks.get(id);
        if (t == null) return false;
        boolean ok = t.requestCancel();
        LOG.info("[任务] 请求取消 #{} {} → {}", id, t.getTitle(), ok ? "已受理（等它到安全点）" : "该任务已结束");
        fireChanged();
        return ok;
    }

    public int cancelAll() {
        int n = 0;
        for (JfTask t : tasks.values()) if (t.requestCancel()) n++;
        LOG.info("[任务] 请求取消全部：{} 个", n);
        fireChanged();
        return n;
    }

    // ==================== 订阅（前端推送） ====================

    public void addListener(Consumer<List<Map<String, Object>>> l) {
        if (l != null) listeners.add(l);
    }

    /** 主动触发一次通知（前端首次加载时用） */
    public void fireChanged() {
        List<Map<String, Object>> snap = list();
        for (Consumer<List<Map<String, Object>>> l : listeners) {
            try {
                l.accept(snap);
            } catch (Throwable t) {
                LOG.warn("[任务] 通知订阅者失败: {}", t.getMessage());
            }
        }
    }

    // ==================== 内部 ====================

    private void trimFinished() {
        List<JfTask> finished = new ArrayList<>();
        for (JfTask t : tasks.values()) if (!t.isActive()) finished.add(t);
        if (finished.size() <= KEEP_FINISHED) return;
        finished.sort(Comparator.comparingLong(JfTask::getFinishedAt));
        for (int i = 0; i < finished.size() - KEEP_FINISHED; i++) {
            tasks.remove(finished.get(i).getId());
        }
    }
}
