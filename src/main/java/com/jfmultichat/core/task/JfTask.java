package com.jfmultichat.core.task;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 一个"耗时任务"的状态（任务中心的一行）.
 *
 * <p>状态机：{@code RUNNING → CANCELLING → CANCELLED}｜{@code RUNNING → DONE}｜{@code RUNNING → FAILED}。
 * <p>⚠️ 取消是**协作式**的：{@link #requestCancel()} 只置标志 + 中断线程，
 * 真正停下要等流程跑到下一个 {@link TaskContext#checkpoint()}（Java 没有安全的强制杀线程）。
 */
public final class JfTask {

    public enum State {
        RUNNING, CANCELLING, DONE, FAILED, CANCELLED;

        public String zh() {
            switch (this) {
                case RUNNING:    return "进行中";
                case CANCELLING: return "正在停止";
                case DONE:       return "已完成";
                case FAILED:     return "失败";
                default:         return "已取消";
            }
        }
    }

    private final String id;
    private final String kind;      // login / multilaunch / detect …（给统计用）
    private final String title;     // 人话标题：登录 3 个账号
    private final String target;    // 目标说明：WeChat（可空）
    private final long startedAt = System.currentTimeMillis();
    private final AtomicBoolean cancelRequested = new AtomicBoolean(false);
    private final Thread thread = Thread.currentThread();

    private volatile State state = State.RUNNING;
    private volatile String phase = "准备中";
    /** 阶段"基名"（不带动态后缀）；显示 = phaseBase + phaseSuffix */
    private volatile String phaseBase = "准备中";
    /** 动态后缀，如"（等窗口 7s）"—— 只影响显示，不影响统计键 ✓ */
    private volatile String phaseSuffix = "";
    /** 阶段的**统计键**（可去掉序号，避免"开窗 1/3、开窗 2/3…"把统计碎成 N 条） */
    private volatile String phaseKey = "准备中";
    private volatile long phaseSince = System.currentTimeMillis();
    private final java.util.Map<String, Long> phaseMs = new java.util.concurrent.ConcurrentHashMap<>();
    /** 业务计数/度量（如"多开轮次""成功开窗""查杀超预算"）—— 流程自己上报，统计按 kind 聚合 */
    private final java.util.Map<String, Long> metrics = new java.util.concurrent.ConcurrentHashMap<>();
    private volatile int done = 0;
    private volatile int total = 0;
    private volatile String error;
    private volatile long finishedAt;

    JfTask(String id, String kind, String title, String target) {
        this.id = id;
        this.kind = kind;
        this.title = title;
        this.target = target == null ? "" : target;
    }

    // ==================== 状态 ====================

    public String getId()        { return id; }
    public String getKind()      { return kind; }
    public String getTitle()     { return title; }
    public String getTarget()    { return target; }
    public long getStartedAt()   { return startedAt; }
    public long getFinishedAt()  { return finishedAt; }
    public State getState()      { return state; }
    public String getPhase()     { return phase; }
    public int getDone()         { return done; }
    public int getTotal()        { return total; }
    public String getError()     { return error; }
    public boolean isCancelRequested() { return cancelRequested.get(); }
    /** 是否还在跑（用于 UI 判断要不要继续每秒刷新） */
    public boolean isActive()    { return state == State.RUNNING || state == State.CANCELLING; }

    /** 请求取消：置标志 + 中断线程（能打断 sleep / 阻塞 IO），返回是否"接下了这次请求" */
    public boolean requestCancel() {
        if (!isActive()) return false;
        cancelRequested.set(true);
        if (state == State.RUNNING) state = State.CANCELLING;
        try {
            thread.interrupt();
        } catch (Throwable ignore) {
            // 线程可能已结束，忽略
        }
        return true;
    }

    // ==================== 进度（由流程侧调用） ====================

    void setPhase(String display) {
        setPhase(display, display);
    }

    /**
     * @param display 给人看的阶段文字（**可以带序号**，如"账号 3/10：开窗"）
     * @param statKey 统计用的阶段键（**不带序号**，如"开窗"）——
     *                否则"开窗 1/3 / 开窗 2/3 / 开窗 3/3"会把阶段耗时统计碎成 N 条
     */
    void setPhase(String display, String statKey) {
        if (display == null || display.isBlank()) return;
        long now = System.currentTimeMillis();
        // 顺手把"上一阶段"的耗时累计起来 —— 统计里的"各阶段耗时"就是这么来的（零额外埋点）
        String prevKey = phaseKey;
        if (prevKey != null && !prevKey.isBlank() && phaseSince > 0 && now > phaseSince) {
            phaseMs.merge(prevKey, now - phaseSince, Long::sum);
        }
        phaseBase = display;
        phaseSuffix = "";
        phase = display;
        phaseKey = (statKey == null || statKey.isBlank()) ? display : statKey;
        phaseSince = now;
    }

    /**
     * 给当前阶段加一个**动态后缀**（例如"（等窗口 7s）"）.
     * <p>用途：等窗口/等关闭这类"一直没动静"的阶段，让界面每秒都在动 —— 但**不改统计键、不重置计时** ✓
     */
    void setPhaseSuffix(String suffix) {
        phaseSuffix = (suffix == null ? "" : suffix);
        phase = phaseBase + phaseSuffix;
    }

    /** 各阶段累计耗时（毫秒）；同一阶段名多次出现会累加（如"开窗"跑 3 个账号） */
    public java.util.Map<String, Long> getPhaseMs() { return phaseMs; }

    /** 业务计数/度量（统计里按 kind 汇总） */
    public java.util.Map<String, Long> getMetrics() { return metrics; }

    void addMetric(String key, long value) {
        if (key == null || key.isBlank()) return;
        metrics.merge(key, value, Long::sum);
    }

    /**
     * **覆盖式**写指标（不是累加）——用于"累计到当前"这类量，例如"时长 = 到最后一个成功开窗为止".
     * <p>为什么需要它：任务可能**中途被取消**（异常直接弹回边界，循环后的代码不会执行），
     * 每成功一步就覆盖一次，取消时也能留下"最后一次成功"的值 ✓。
     */
    void setMetric(String key, long value) {
        if (key == null || key.isBlank()) return;
        metrics.put(key, value);
    }

    void setProgress(int done, int total) {
        this.done = Math.max(0, done);
        this.total = Math.max(0, total);
    }

    void finish(State s, String err) {
        this.state = s;
        this.error = err;
        this.finishedAt = System.currentTimeMillis();
        // ⚠️ 故意**不覆盖 phase**：保留最后一个"真实阶段"
        //（原先把状态文字写进 phase，界面上会出现"已取消 / 已取消"这种重复 —— 用户 2026-10-12 指出）
    }

    // ==================== 序列化给前端 ====================

    public Map<String, Object> toMap() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", id);
        m.put("kind", kind);
        m.put("title", title);
        m.put("target", target);
        m.put("state", state.name());
        m.put("stateText", state.zh());
        m.put("phase", phase);
        m.put("done", done);
        m.put("total", total);
        m.put("startedAt", startedAt);
        m.put("finishedAt", finishedAt);
        m.put("elapsedMs", (finishedAt > 0 ? finishedAt : System.currentTimeMillis()) - startedAt);
        m.put("active", isActive());
        m.put("cancellable", isActive());
        if (!phaseMs.isEmpty()) m.put("phases", new LinkedHashMap<>(phaseMs));
        if (!metrics.isEmpty()) m.put("metrics", new LinkedHashMap<>(metrics));
        if (error != null) m.put("error", error);
        return m;
    }
}
