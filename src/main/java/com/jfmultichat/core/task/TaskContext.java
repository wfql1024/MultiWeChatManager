package com.jfmultichat.core.task;

/**
 * 任务上下文 —— 给"流程内部"用的三件套：报阶段、报进度、**检查取消**.
 *
 * <p>它挂在**线程**上（{@link ThreadLocal}），由 {@link TaskRegistry} 在跑任务体时自动绑定/解绑 →
 * 所以业务方法的**签名一律不用改**，流程里只要在"安全点"调一下静态方法即可：
 * <pre>
 * for (String acc : accIds) {
 *     TaskContext.checkpoint();                 // ← 安全点（被取消就在这里抛出并弹回任务边界）
 *     TaskContext.phase("开窗 2/5");            // ← 人话进度（任务中心直接显示）
 *     ...
 * }
 * </pre>
 *
 * <p>⚠️ 安全点该放哪：**循环 / 阶段交界**（账号之间、开窗前、点击前、轮询里、批量每轮）。
 * 阻塞调用（sleep / 阻塞 IO / Future.get）不用手动加 —— {@code interrupt()} 会让它们自己抛
 * {@code InterruptedException}。真正无法中断的只有 **native 调用**那一段 → 那段要靠**各自的超时**兜。
 */
public final class TaskContext {

    private static final ThreadLocal<JfTask> CURRENT = new ThreadLocal<>();

    private TaskContext() {}

    // ==================== 绑定（仅 TaskRegistry 调用） ====================

    static void bind(JfTask task)   { CURRENT.set(task); }
    static void unbind()            { CURRENT.remove(); }

    /** 当前线程正在跑的任务；不在任务里时返回 null（此时所有方法都是空操作） */
    public static JfTask current()  { return CURRENT.get(); }

    public static boolean inTask()  { return CURRENT.get() != null; }

    // ==================== 流程侧 API ====================

    /**
     * **安全点**：被请求取消（或线程被中断）就抛出 {@link TaskCancelledException} 一路弹回任务边界.
     * <p>不在任务里时是空操作（探针/测试直接调业务方法也安全）。
     */
    public static void checkpoint() {
        JfTask t = CURRENT.get();
        if (t == null) return;
        if (t.isCancelRequested() || Thread.currentThread().isInterrupted()) {
            throw new TaskCancelledException();
        }
    }

    /** 报告"现在在干什么"（人话，直接显示在任务中心那一行）；**同时累计上一阶段耗时**（统计用） */
    public static void phase(String phase) {
        phase(phase, phase);
    }

    /**
     * @param display 给人看的阶段文字（**可以带序号**，如"账号 3/10：开窗"）
     * @param statKey 统计用的阶段键（**不带序号**，如"开窗"）
     *
     * <p>为什么要分两个：界面上要"精确到第几个子项"，而统计要"同类阶段合并成一条"。
     * 用一个字符串同时满足两边，结果是统计被序号碎成 N 条（2026-10-12 踩到）。
     */
    public static void phase(String display, String statKey) {
        JfTask t = CURRENT.get();
        if (t != null) t.setPhase(display, statKey);
    }

    /**
     * **一步一包裹**（推荐给新流程用）：自动 = 检查点 + 报阶段 + **计时**.
     *
     * <pre>
     * TaskContext.step("查杀互斥体", () -&gt; killAllMutexesNow(sw, accessor, ops));
     * TaskContext.step("等登录窗",   () -&gt; openSwAndReturnHwnd(sw, exe, accessor, ops));
     * </pre>
     *
     * 于是新流程**天然**具备：任务中心看得见阶段、可取消、统计里有"这一步花了多久"。
     * 不在任务里（探针/单测直调）时退化成"直接跑"，无副作用。
     */
    public static void step(String phase, Runnable body) {
        JfTask t = CURRENT.get();
        if (t == null) {
            body.run();
            return;
        }
        checkpoint();
        phase(phase);
        body.run();
    }

    /**
     * 给当前阶段加**动态后缀**（如 {@code "（等窗口 7s）"}）——只改显示，不动统计键、不重置计时.
     * <p>用在"等窗口出现 / 等窗口关闭"这类会静默几十秒的阶段，让界面每秒都在动。
     */
    public static void phaseSuffix(String suffix) {
        JfTask t = CURRENT.get();
        if (t != null) t.setPhaseSuffix(suffix);
    }

    /** 报告进度（如 2/5），任务中心会显示为 "2/5" */
    public static void progress(int done, int total) {
        JfTask t = CURRENT.get();
        if (t != null) t.setProgress(done, total);
    }

    /**
     * 记一个**业务计数/度量**（同一 key 累加）——统计里按流程聚合.
     *
     * <pre>
     * TaskContext.metric("多开轮次", 1);        // 每轮 +1
     * TaskContext.metric("成功开窗", okHwnds.size());
     * TaskContext.metric("查杀超预算", 1);
     * </pre>
     *
     * 这样"值得统计的业务指标"由**流程自己**上报，不需要统计层去猜、也不需要改统计代码。
     */
    public static void metric(String key, long value) {
        JfTask t = CURRENT.get();
        if (t != null) t.addMetric(key, value);
    }

    /**
     * **覆盖式**写指标（不是累加）：适合"累计到当前"的量.
     * <p>典型用法：每成功打开一个窗口就 {@code metricSet("开窗时长ms", 现在-开始)} ——
     * 这样即使**中途取消**（异常弹回边界、循环后的代码不执行），也能留下"最后一次成功"的时长 ✓。
     * <p>轮次这类计数用 {@code metricSet("开窗轮次", 已进行轮次)} 同样安全（每次覆盖，取消也保留）✓。
     */
    public static void metricSet(String key, long value) {
        JfTask t = CURRENT.get();
        if (t != null) t.setMetric(key, value);
    }
}
