package com.jfmultichat.core.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 任务统计 —— **统计与任务中心同源**（用户 2026-10-12 定）.
 *
 * <p>核心思想：任务的启停边界**天然**就是计时区间，所以统计不需要在业务方法里塞 stopwatch、
 * 也不需要写进核心逻辑 —— 只要在任务结束时记一条（由 {@link TaskRegistry} 统一调用）。
 * 业务里的"业务指标"由流程自己用 {@link TaskContext#metric} 上报，统计层只做聚合。
 *
 * <p><b>口径对齐旧版</b>（{@code legacy_python/data_access/setting.py::StatisticData}）：
 * <ul>
 *   <li>旧版按 {@code (sw, mode, main_key, sub_key)} 存 {@code 最短,次数,平均,最长}，样本是**单次值**；</li>
 *   <li>旧版"平台平均"的样本 = {@code (全部窗口开完的总时长) / 应开窗数}
 *       （{@code acc_func_core.py:315}），即"每次运行的单窗平均用时"；</li>
 *   <li>旧版**丢弃异常样本**：手动登录 &gt;20s、自动登录 &gt;60s、刷新 &gt;2s 不记（{@code setting.py:352-357}）。</li>
 * </ul>
 * 本类照此实现，并额外给出"累计口径"的平均 = {@code Σ总时长 / Σ应开窗数}（用户 2026-10-12 明确要求）。
 */
public final class TaskStats {

    private static final Logger LOG = LoggerFactory.getLogger(TaskStats.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** 统计条目 schema 版本（将来上传给分析端时用来兼容） */
    public static final int SCHEMA = 1;

    private static final TaskStats INSTANCE = new TaskStats();
    public static TaskStats get() { return INSTANCE; }

    /**
     * "派生统计"配置：kind → {时长键, 轮次键}.
     * <p>口径（用户 2026-10-12 定）：
     * <ul>
     *   <li><b>轮次</b> = 流程进行到第几轮（登录=尝试开第几个窗口，成功/失败/超时/中途取消都算）</li>
     *   <li><b>时长</b> = 从开始到**最后一次成功**为止（覆盖式记录，取消也保留）</li>
     *   <li>单次值 = 时长 ÷ 轮次 → 单次统计显示 **末次 / 最短 / 最长**；总平均 = **Σ时长 ÷ Σ轮次**</li>
     * </ul>
     */
    private static final Map<String, String[]> DERIVED = new LinkedHashMap<>();
    static {
        DERIVED.put("login", new String[]{"开窗时长ms", "开窗轮次"});
        DERIVED.put("login_coexist", new String[]{"开窗时长ms", "开窗轮次"});
        DERIVED.put("multilaunch", new String[]{"多开时长ms", "开实例数"});
    }

    /** 异常样本上限（毫秒/单位）——对齐旧版：自动登录 60s、手动登录 20s、刷新 2s 之外的不记 */
    private static final Map<String, Long> PER_UNIT_CAP_MS = new LinkedHashMap<>();
    static {
        PER_UNIT_CAP_MS.put("login", 60_000L);
        PER_UNIT_CAP_MS.put("login_coexist", 60_000L);
        PER_UNIT_CAP_MS.put("multilaunch", 60_000L);
        PER_UNIT_CAP_MS.put("refresh", 2_000L);
    }

    /** kind → 聚合 */
    private final Map<String, KindAgg> byKind = new ConcurrentHashMap<>();
    private final List<Map<String, Object>> recent = new ArrayList<>();
    private static final int KEEP_RECENT = 200;

    private TaskStats() {}

    /** 单个指标的聚合（sum/count/min/max/avg） */
    public static final class MetricAgg {
        long sum, count, min = Long.MAX_VALUE, max;

        void add(long v) {
            sum += v;
            count++;
            if (v < min) min = v;
            if (v > max) max = v;
        }

        Map<String, Object> toMap() {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("sum", sum);
            m.put("count", count);
            m.put("avg", count > 0 ? sum / count : 0);
            m.put("min", count > 0 ? min : 0);
            m.put("max", max);
            return m;
        }
    }

    /** 一条任务的聚合（按 kind） */
    public static final class KindAgg {
        public long count, success, failed, cancelled, totalMs, maxMs;
        /** 各阶段累计耗时（按阶段名合并 —— "查杀/启动/等窗口/点击"各花了多久） */
        final Map<String, Long> phases = new ConcurrentHashMap<>();
        /** 业务指标（流程用 TaskContext.metric 上报），按 key 聚合 */
        final Map<String, MetricAgg> metrics = new ConcurrentHashMap<>();

        Map<String, Object> toMap(String kind) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("kind", kind);
            m.put("count", count);
            m.put("success", success);
            m.put("failed", failed);
            m.put("cancelled", cancelled);
            m.put("avgMs", count > 0 ? totalMs / count : 0);
            m.put("maxMs", maxMs);
            m.put("phases", new LinkedHashMap<>(phases));
            Map<String, Object> ms = new LinkedHashMap<>();
            for (Map.Entry<String, MetricAgg> e : metrics.entrySet()) ms.put(e.getKey(), e.getValue().toMap());
            m.put("metrics", ms);
            return m;
        }
    }

    /** 任务结束时调用一次（由 TaskRegistry 统一调用，业务方法不关心） */
    public synchronized void record(JfTask t) {
        long ms = Math.max(0, (t.getFinishedAt() > 0 ? t.getFinishedAt() : System.currentTimeMillis())
                - t.getStartedAt());
        String kind = t.getKind() == null ? "unknown" : t.getKind();

        // 异常样本丢弃（对齐旧版：超过阈值的一次不统计，免得把平均/最长带偏）
        Map<String, Long> metrics = t.getMetrics();
        String[] dk = DERIVED.get(kind);
        Long cap = PER_UNIT_CAP_MS.get(kind);
        if (dk != null && cap != null) {
            Long dur = metrics.get(dk[0]);
            Long cnt = metrics.get(dk[1]);
            if (dur != null && cnt != null && cnt > 0) {
                long perUnit = dur / cnt;
                if (perUnit > cap) {
                    LOG.info("[统计] 丢弃异常样本：{} 单次平均 {}ms > 上限 {}ms（旧版同规则）", kind, perUnit, cap);
                    return;
                }
            }
        }

        KindAgg agg = byKind.computeIfAbsent(kind, k -> new KindAgg());
        agg.count++;
        agg.totalMs += ms;
        if (ms > agg.maxMs) agg.maxMs = ms;
        switch (t.getState()) {
            case DONE:       agg.success++;   break;
            case FAILED:     agg.failed++;    break;
            case CANCELLED:  agg.cancelled++; break;
            default:         break;
        }
        // 阶段耗时与业务指标一并累计（同源：都挂在任务上，不需要额外埋点）
        t.getPhaseMs().forEach((k, v) -> agg.phases.merge(k, v, Long::sum));
        metrics.forEach((k, v) -> agg.metrics.computeIfAbsent(k, x -> new MetricAgg()).add(v));

        ObjectNode line = MAPPER.createObjectNode();
        line.put("schema", SCHEMA);
        line.put("ts", System.currentTimeMillis());
        line.put("id", t.getId());
        line.put("kind", kind);
        line.put("sw", t.getTarget());                 // 只到平台级，不含账号明文
        line.put("ms", ms);
        line.put("result", t.getState().name());
        line.put("phase", t.getPhase());
        line.put("title", t.getTitle());
        if (!t.getPhaseMs().isEmpty()) line.set("phases", MAPPER.valueToTree(t.getPhaseMs()));
        if (!metrics.isEmpty()) line.set("metrics", MAPPER.valueToTree(metrics));

        Map<String, Object> row = MAPPER.convertValue(line, Map.class);
        synchronized (recent) {
            recent.add(row);
            while (recent.size() > KEEP_RECENT) recent.remove(0);
        }
        appendLine(line);
    }

    /** 内存聚合快照（给"任务与统计"页） */
    public synchronized List<Map<String, Object>> summary() {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map.Entry<String, KindAgg> e : byKind.entrySet()) {
            Map<String, Object> m = e.getValue().toMap(e.getKey());
            Map<String, Object> derived = derivedSummary(e.getKey());
            if (derived != null) m.put("derived", derived);
            out.add(m);
        }
        return out;
    }

    /**
     * 派生统计（**真算出来的数**，不是摆算式）.
     * <ul>
     *   <li>{@code lastPerUnitMs} / {@code minPerUnitMs} / {@code maxPerUnitMs} —— 单次统计的 **末次 / 最短 / 最长**
     *       （每次运行的单窗平均用时里取）</li>
     *   <li>{@code avgPerUnitMs} = <b>Σ时长 ÷ Σ轮次</b> —— 总平均 ✓</li>
     *   <li>{@code totalDurationMs} / {@code totalCount} —— 分子分母原值（可选展示）</li>
     * </ul>
     */
    private Map<String, Object> derivedSummary(String kind) {
        String[] keys = DERIVED.get(kind);
        if (keys == null) return null;
        long sumDur = 0, sumCnt = 0, runs = 0;
        long minSample = Long.MAX_VALUE, maxSample = 0, lastSample = 0;
        synchronized (recent) {
            for (Map<String, Object> row : recent) {
                if (!kind.equals(row.get("kind"))) continue;
                Object mo = row.get("metrics");
                if (!(mo instanceof Map)) continue;
                @SuppressWarnings("unchecked")
                Map<String, Object> mm = (Map<String, Object>) mo;
                Object d = mm.get(keys[0]);
                Object c = mm.get(keys[1]);
                if (!(d instanceof Number) || !(c instanceof Number)) continue;
                long dur = ((Number) d).longValue();
                long cnt = ((Number) c).longValue();
                if (cnt <= 0) continue;
                long sample = dur / cnt;
                sumDur += dur;
                sumCnt += cnt;
                runs++;
                lastSample = sample;                      // recent 是追加序 → 最后一条就是"末次"
                if (sample < minSample) minSample = sample;
                if (sample > maxSample) maxSample = sample;
            }
        }
        if (runs == 0) return null;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("durationKey", keys[0]);
        out.put("countKey", keys[1]);
        out.put("runs", runs);
        out.put("totalDurationMs", sumDur);
        out.put("totalCount", sumCnt);
        out.put("avgPerUnitMs", sumCnt > 0 ? sumDur / sumCnt : 0);   // 总平均 = Σ时长 ÷ Σ轮次
        out.put("lastPerUnitMs", lastSample);                        // 末次
        out.put("minPerUnitMs", minSample);                          // 最短
        out.put("maxPerUnitMs", maxSample);                          // 最长
        return out;
    }

    /** 最近若干条明细（内存） */
    public List<Map<String, Object>> recent() {
        synchronized (recent) {
            return new ArrayList<>(recent);
        }
    }

    // ==================== 落盘（JSONL） ====================

    private void appendLine(ObjectNode line) {
        try {
            Path file = statsFile();
            if (file == null) return;
            Files.createDirectories(file.getParent());
            Files.write(file, (line.toString() + System.lineSeparator()).getBytes(StandardCharsets.UTF_8),
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (Throwable e) {
            LOG.warn("[统计] 落盘失败（不影响功能）: {}", e.getMessage());
        }
    }

    /** 用户数据目录下的 stats/task_stats.jsonl；目录还没就绪（如测试环境）时返回 null */
    private Path statsFile() {
        try {
            Path userDir = com.jfmultichat.config.ConfigManager.getInstance().getUserDataPath();
            if (userDir == null) return null;
            return userDir.resolve("stats").resolve("task_stats.jsonl");
        } catch (Throwable t) {
            return null;
        }
    }
}
