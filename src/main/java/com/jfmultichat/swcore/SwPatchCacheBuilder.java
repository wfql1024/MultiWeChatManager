package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 补丁适配缓存构建器 — 把远程配置里的 features 特征码扫描成"物化偏移"并写入 SwCache。
 * <p>
 * 对应 Python: SwInfoFuncCore._update_adaptation_from_remote_to_cache (L162-L286)
 * <p>
 * 三条闸门（必须严格照做）：
 * <ol>
 *   <li>所有规则在新版本都已弃用 → 删除该渠道该版本的缓存</li>
 *   <li>任一目标/规则扫描失败 → 不写缓存（保留旧缓存），记 [ERR]</li>
 *   <li>全部成功 → 写入缓存</li>
 * </ol>
 * <p>
 * 缓存结构（与旧版 sw_cache.json 一致）：
 * <pre>
 * {mode}.channels.{ch}.precise_ver_adaptations.{ver} = [
 *   { "addr": "%dll_dir%/Weixin.dll", "wildcard": "Weixi?.dll", "patches": [ ... ] }
 * ]
 * </pre>
 * 要点：
 * <ul>
 *   <li>{@code addr} 存的是<b>配置里的地址模板</b>（保留 {@code %变量%}），不是解析后的绝对路径</li>
 *   <li>{@code wildcard} 原样保留；缺省时写 null</li>
 *   <li>只有"有补丁的文件"才产出条目；目录只用于递归 {@code nested}，不产条目</li>
 * </ul>
 */
public final class SwPatchCacheBuilder {

    private static final Logger LOG = LoggerFactory.getLogger(SwPatchCacheBuilder.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** 强制重扫标记（对应 Python 的 sw_cls.force_rescan） */
    private static final Set<String> FORCE_RESCAN = ConcurrentHashMap.newKeySet();

    /**
     * 缓存根：**平台节点**（与旧版 SwCache.json 一致：{@code {"Weixin": {"anti-revoke": ...}}}）。
     * 老版本曾把 mode 直接放顶层（扁平结构），读取时做兼容。
     */
    public static ObjectNode platformRoot(ObjectNode cache, String sw) {
        JsonNode n = cache.get(sw);
        if (n instanceof ObjectNode o) return o;
        return cache.putObject(sw);
    }

    /** 只读版：没有平台节点时返回 null（不创建） */
    public static ObjectNode platformNodeIfPresent(ObjectNode cache, String sw) {
        JsonNode n = cache == null ? null : cache.get(sw);
        return (n instanceof ObjectNode o) ? o : null;
    }

    /** 缓存里"精确版本适配"的键名（与远程配置一致） */
    public static final String KEY_PRECISE = "precise_ver_adaptations";
    /** 旧 Java 端口用过的键名，仅用于读取兼容 */
    public static final String KEY_PRECISE_LEGACY = "precises";

    /** 小于该大小直接读进内存，避免为扫描建映射 */
    private static final long MMAP_THRESHOLD = 32L * 1024 * 1024;

    private SwPatchCacheBuilder() {}

    // ==================== 强制重扫 ====================

    public static void setForceRescan(String sw, boolean on) {
        if (on) FORCE_RESCAN.add(sw);
        else FORCE_RESCAN.remove(sw);
    }

    public static boolean isForceRescan(String sw) {
        return FORCE_RESCAN.contains(sw);
    }

    // ==================== 结果类型 ====================

    public enum Status { OK, SKIPPED, DISABLED, FAILED }

    public static final class ChannelResult {
        public final Status status;
        public final String message;
        public final int ruleHits;
        public final List<String> failures;

        ChannelResult(Status status, String message, int ruleHits, List<String> failures) {
            this.status = status;
            this.message = message;
            this.ruleHits = ruleHits;
            this.failures = failures == null ? Collections.emptyList() : failures;
        }

        @Override
        public String toString() {
            return status + (failures.isEmpty() ? "" : " " + failures);
        }
    }

    public static final class BuildResult {
        public final boolean ok;
        public final Map<String, ChannelResult> channels;
        public final String message;

        BuildResult(boolean ok, Map<String, ChannelResult> channels, String message) {
            this.ok = ok;
            this.channels = channels;
            this.message = message;
        }
    }

    // ==================== 入口 ====================

    /**
     * 按远程配置刷新缓存。
     *
     * @param channels  只处理指定渠道；null = 全部
     * @param skipCache true = 缓存已存在且格式合法时跳过扫描（对应 Python 的 skip_cache）
     */
    public static BuildResult build(String sw, String mode, List<String> channels,
                                    boolean skipCache, SwConfigAccessor accessor) {
        return build(sw, mode, channels, skipCache, accessor, accessor.getSwCache());
    }

    public static BuildResult build(String sw, String mode, List<String> channels,
                                    boolean skipCache, SwConfigAccessor accessor, ObjectNode cache) {
        return build(sw, mode, channels, skipCache, true, accessor, cache);
    }

    /**
     * @param allowScan false = **只查缓存**，缓存里没有就当作"无适配"，绝不扫描
     *                  （共存账号行的状态查询走这条，扫描由显式动作触发）
     */
    public static BuildResult build(String sw, String mode, List<String> channels,
                                    boolean skipCache, boolean allowScan,
                                    SwConfigAccessor accessor, ObjectNode cache) {
        JsonNode channelsDict = accessor.getRemoteSw(sw, mode, SwCoreConstants.RemoteSwKey.CHANNELS);
        if (channelsDict == null || !channelsDict.isObject()) {
            return new BuildResult(false, Collections.emptyMap(), "该模式没有方案");
        }
        String curVer = SwVersionHelper.calcSwVer(sw, accessor);
        if (curVer == null) {
            return new BuildResult(false, Collections.emptyMap(), "错误：未知当前版本");
        }

        List<String> toUpdate = new ArrayList<>();
        if (channels == null || channels.isEmpty()) {
            channelsDict.fieldNames().forEachRemaining(toUpdate::add);
        } else {
            toUpdate.addAll(channels);
        }

        Map<String, ChannelResult> results = new java.util.concurrent.ConcurrentHashMap<>();
        Map<String, ObjectNode> perChannel = new LinkedHashMap<>();
        for (String ch : toUpdate) {
            // 以现有缓存为起点（否则 hasValidCache 看不到旧数据，永远重扫）
            JsonNode existing = null;
            if (cache != null) synchronized (MERGE_LOCK) {
                existing = cache.path(sw).path(mode).path(SwCoreConstants.RemoteSwKey.CHANNELS).path(ch);
                if (existing.isMissingNode()) {
                    // 兼容老扁平结构
                    existing = cache.path(mode).path(SwCoreConstants.RemoteSwKey.CHANNELS).path(ch);
                }
            }
            perChannel.put(ch, existing != null && existing.isObject()
                    ? ((ObjectNode) existing).deepCopy() : MAPPER.createObjectNode());
        }

        // 关系（parents/children/friends）与"扫描是否成功"无关 → 每轮都写进渠道节点的 relations 字段。
        // 之前关系藏在 patch_rules 里，只有扫到适配才会进缓存；无适配的渠道就丢了关系（用户 2026-10-23 指出）
        for (String ch : toUpdate) {
            ObjectNode relNode = relationsOfChannel(channelsDict.get(ch), curVer);
            if (relNode != null) perChannel.get(ch).set("relations", relNode);
        }

        List<java.util.concurrent.Future<?>> futures = new ArrayList<>();
        for (String channel : toUpdate) {
            futures.add(CHANNEL_POOL.submit(() -> {
                try {
                    results.put(channel, buildChannel(sw, mode, channel, curVer, channelsDict,
                            skipCache, allowScan, accessor, perChannel.get(channel)));
                } catch (Exception e) {
                    LOG.error("[缓存] 渠道 {} 构建异常: {}", channel, e.getMessage(), e);
                    results.put(channel, new ChannelResult(Status.FAILED, "构建异常: " + e.getMessage(), 0,
                            List.of(String.valueOf(e.getMessage()))));
                }
            }));
        }
        for (java.util.concurrent.Future<?> f : futures) {
            try {
                f.get();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new com.jfmultichat.core.task.TaskCancelledException();
            } catch (Exception ignored) {
                // 单个渠道的异常已在任务内记录
            }
        }

        // 合并各渠道的临时节点到真实缓存（合并是单线程的，避免并发写同一个 JSON 树）
        if (cache != null) {
            synchronized (MERGE_LOCK) {
                ObjectNode plat = platformRoot(cache, sw);
                ObjectNode chRoot = ensureObject(plat, mode, SwCoreConstants.RemoteSwKey.CHANNELS);
                for (String ch : toUpdate) {
                    ObjectNode node = perChannel.get(ch);
                    if (node != null && node.size() > 0) chRoot.set(ch, node);
                }
                // 清掉"扁平结构"遗留的顶层 mode 节点（老版本的错误结构，会跨平台串数据）
                if (!sw.equals(mode) && cache.get(mode) instanceof ObjectNode) {
                    cache.remove(mode);
                }
                accessor.setSwCache(cache);
            }
        }
        long nOk = results.values().stream().filter(r -> r.status == Status.OK).count();
        long nSkip = results.values().stream().filter(r -> r.status == Status.SKIPPED).count();
        long nDis = results.values().stream().filter(r -> r.status == Status.DISABLED).count();
        long nFail = results.values().stream().filter(r -> r.status == Status.FAILED).count();
        String summary = "[缓存] {} {} 本轮扫描：新扫描 {} / 缓存命中 {} / 该版本弃用 {} / 失败 {}";
        if (nFail > 0) LOG.warn(summary, sw, mode, nOk, nSkip, nDis, nFail);
        else LOG.info(summary, sw, mode, nOk, nSkip, nDis, nFail);
        boolean ok = results.values().stream().noneMatch(r -> r.status == Status.FAILED);
        return new BuildResult(ok, results, ok ? "成功" : "存在失败的渠道");
    }

    /**
     * 取某渠道在指定版本下的关系集合（parents/children/friends）。
     *
     * <p>支持两种配置写法（新写法优先）：
     * <ol>
     *   <li>渠道级：{@code channels.<ch>.relation.ver_adaptations.<ver> = {parents|children|friends}}</li>
     *   <li>规则级（旧）：{@code features[].patch_rules[]} 里 {@code type=relation} 且带同名 ver_adaptations</li>
     * </ol>
     * 关系本身与"能不能扫到补丁"无关，所以必须在扫描之外单独取。
     *
     * @return 三个键的 ObjectNode（只放非空项）；全空返回 null
     */
    static ObjectNode relationsOfChannel(JsonNode chDict, String curVer) {
        if (chDict == null || !chDict.isObject()) return null;
        java.util.LinkedHashSet<String> parents = new java.util.LinkedHashSet<>();
        java.util.LinkedHashSet<String> children = new java.util.LinkedHashSet<>();
        java.util.LinkedHashSet<String> friends = new java.util.LinkedHashSet<>();

        // 1) 渠道级 relation
        JsonNode rel = chDict.get("relation");
        if (rel != null && rel.isObject()) {
            collectRelations(rel.get("ver_adaptations"), curVer, parents, children, friends);
        }

        // 2) 规则级（旧写法，向后兼容）
        JsonNode features = chDict.get("features");
        if (features != null && features.isArray()) {
            for (JsonNode feature : features) {
                JsonNode rules = feature.get("patch_rules");
                if (rules == null || !rules.isArray()) continue;
                for (JsonNode rule : rules) {
                    if (!"relation".equals(rule.path("type").asText())) continue;
                    collectRelations(rule.get("ver_adaptations"), curVer, parents, children, friends);
                }
            }
        }

        if (parents.isEmpty() && children.isEmpty() && friends.isEmpty()) return null;
        ObjectNode out = MAPPER.createObjectNode();
        if (!parents.isEmpty()) { ArrayNode a = out.putArray("parents"); parents.forEach(a::add); }
        if (!children.isEmpty()) { ArrayNode a = out.putArray("children"); children.forEach(a::add); }
        if (!friends.isEmpty()) { ArrayNode a = out.putArray("friends"); friends.forEach(a::add); }
        return out;
    }

    private static void collectRelations(JsonNode versDict, String curVer,
                                         java.util.Set<String> parents,
                                         java.util.Set<String> children,
                                         java.util.Set<String> friends) {
        if (versDict == null || !versDict.isObject()) return;
        String ver = SwRuleResolver.findCompatibleVersion(curVer, versDict);
        if (ver == null) return;
        JsonNode body = versDict.get(ver);
        if (body == null || !body.isObject()) return;
        for (String key : List.of("parents", "children", "friends")) {
            JsonNode arr = body.get(key);
            if (arr == null || !arr.isArray()) continue;
            for (JsonNode n : arr) {
                String v = n.asText();
                switch (key) {
                    case "parents" -> parents.add(v);
                    case "children" -> children.add(v);
                    default -> friends.add(v);
                }
            }
        }
    }

    // ==================== 单渠道 ====================

    private static ChannelResult buildChannel(String sw, String mode, String channel, String curVer,
                                              JsonNode channelsDict, boolean skipCache, boolean allowScan,
                                              SwConfigAccessor accessor, ObjectNode chCache) {
        JsonNode chDict = channelsDict.get(channel);
        if (chDict == null || !chDict.isObject()) {
            return new ChannelResult(Status.FAILED, "渠道配置缺失", 0, List.of("渠道 " + channel + " 不存在"));
        }

        if (chCache == null) {
            return new ChannelResult(Status.FAILED, "缓存结构异常", 0, List.of("无法创建缓存节点"));
        }

        // 1) 远程预烘焙的精确适配 → 直接抄进缓存
        JsonNode preciseDict = chDict.has(KEY_PRECISE) ? chDict.get(KEY_PRECISE) : chDict.get(KEY_PRECISE_LEGACY);
        if (preciseDict != null && preciseDict.isObject()) {
            JsonNode baked = preciseDict.get(curVer);
            if (baked != null && baked.isArray()) {
                ensureObject(chCache, KEY_PRECISE).set(curVer, baked.deepCopy());
                LOG.debug("[缓存] {}/{} 使用远程预烘焙适配 ({})", sw, channel, curVer);
                return new ChannelResult(Status.OK, "使用预烘焙适配", 0, List.of());
            }
        }

        // 2) 已有合法缓存 → 跳过
        if (skipCache && hasValidCache(chCache, curVer)) {
            LOG.debug("[缓存] {}/{} 已存在缓存，跳过扫描", sw, channel);
            return new ChannelResult(Status.SKIPPED, "已存在缓存", 0, List.of());
        }
        // 2.5) 只查缓存（共存账号行查询走这条）：没有缓存就当"无适配"，不扫描
        if (!allowScan) {
            return new ChannelResult(Status.SKIPPED, "仅查缓存（该渠道无适配）", 0, List.of());
        }

        // 3) 扫描 features
        JsonNode features = chDict.get(SwCoreConstants.RemoteSwKey.FEATURES);
        if (features == null || !features.isArray() || features.isEmpty()) {
            return new ChannelResult(Status.FAILED, "未配置 features", 0,
                    List.of("渠道 " + channel + " 没有特征列表"));
        }

        List<ObjectNode> entries = new ArrayList<>();
        ScanStats stats = new ScanStats();
        scanFeatures(sw, curVer, accessor, features, "", entries, stats);

        // 闸门一：没有任何一条规则产出列表 → 该版本规则已全部弃用 → 删缓存
        // （与 Python 一致：channel_disabled 优先于 channel_failed）
        if (!stats.sawRuleList) {
            removeVersion(chCache, curVer);
            LOG.info("[缓存] {}/{} 该版本全部规则已弃用，删除缓存", sw, channel);
            return new ChannelResult(Status.DISABLED, "该版本规则已全部弃用", 0, List.of());
        }

        // 闸门二：任一失败 → 不写缓存
        if (!stats.failures.isEmpty()) {
            // 每个渠道一行太吵（每次扫描都会重扫失败渠道）→ 明细降 DEBUG，结论看本轮汇总
            LOG.debug("[缓存] {}/{} 扫描失败，保留旧缓存: {}", sw, channel, stats.failures);
            return new ChannelResult(Status.FAILED, "扫描失败", stats.ruleHits, stats.failures);
        }

        // 闸门三：全部成功 → 写缓存
        if (entries.isEmpty()) {
            LOG.warn("[缓存] {}/{} 没有产出任何目标", sw, channel);
            return new ChannelResult(Status.FAILED, "没有产出任何目标", 0,
                    List.of("所有 feature 都被跳过"));
        }

        ArrayNode arr = MAPPER.createArrayNode();
        for (ObjectNode entry : entries) arr.add(entry);
        ensureObject(chCache, KEY_PRECISE).set(curVer, arr);
        LOG.info("[缓存] {}/{} 写入缓存成功：{} 个目标 / {} 条补丁", sw, channel, entries.size(), stats.ruleHits);
        return new ChannelResult(Status.OK, "写入缓存成功", stats.ruleHits, List.of());
    }

    // ==================== 递归扫描 ====================

    private static final class ScanStats {
        int ruleHits;
        boolean sawRuleList;
        final List<String> failures = new ArrayList<>();
    }

    /**
     * 扫描一组 features，只产出"有补丁的文件"条目。
     *
     * @param templateBase 地址模板前缀（顶层为 ""；nested 为父级 addr 模板）
     */
    private static void scanFeatures(String sw, String curVer, SwConfigAccessor accessor,
                                     JsonNode features, String templateBase,
                                     List<ObjectNode> out, ScanStats stats) {
        for (JsonNode feature : features) {
            String addr = text(feature, SwCoreConstants.RemoteSwKey.ADDR);
            if (addr == null || addr.isBlank()) {
                stats.failures.add("存在无地址的补丁模式");
                continue;
            }
            boolean isDir = addr.endsWith("/");
            // 缓存里存"配置模板"（保留 %变量%），不是解析后的绝对路径
            String template = joinPath(templateBase, addr, isDir);

            JsonNode rules = feature.get(SwCoreConstants.RemoteSwKey.PATCH_RULES);
            List<JsonNode> ruleList = new ArrayList<>();
            if (rules != null && rules.isArray()) {
                for (JsonNode r : rules) ruleList.add(r);
            }

            if (isDir) {
                // 目录不产缓存条目（无补丁），只把 nested 的子项按模板拼进来
                for (JsonNode rule : ruleList) {
                    String type = text(rule, SwCoreConstants.RemoteSwKey.TYPE);
                    if (!"nested".equals(type)) {
                        LOG.warn("[缓存] 目录目标的非 nested 规则被忽略: {} / {}", template, type);
                        continue;
                    }
                    JsonNode children = rule.get(SwCoreConstants.RemoteSwKey.FEATURES);
                    if (children == null || !children.isArray()) {
                        stats.failures.add(template + " 的 nested 缺少 features");
                        continue;
                    }
                    scanFeatures(sw, curVer, accessor, children, template, out, stats);
                }
                continue;
            }

            Path file;
            try {
                file = Path.of(SwPathResolver.resolveSwPath(sw, template, accessor));
            } catch (IllegalArgumentException e) {
                stats.failures.add(template + " 路径解析失败: " + e.getMessage());
                continue;
            }
            if (!Files.isRegularFile(file)) {
                stats.failures.add(template + " 文件不存在");
                continue;
            }

            ByteBuffer mm = null;
            try {
                mm = mapReadOnly(file);
                List<Map<String, Object>> patches = new ArrayList<>();
                boolean addrFailed = false;

                // 先挑出可扫描的规则（nested 在文件目标上无意义）
                List<JsonNode> effectiveRules = new ArrayList<>();
                for (JsonNode rule : ruleList) {
                    if ("nested".equals(text(rule, SwCoreConstants.RemoteSwKey.TYPE))) {
                        LOG.warn("[缓存] 文件目标的 nested 规则被忽略: {}", template);
                        continue;
                    }
                    effectiveRules.add(rule);
                }

                // 多条规则并行扫描（同一 ByteBuffer 只读共享；byte[] 只复制一次）
                List<RuleOutcome> outcomes = resolveRules(curVer, mm, effectiveRules);

                for (int i = 0; i < outcomes.size(); i++) {
                    RuleOutcome oc = outcomes.get(i);
                    String type = text(effectiveRules.get(i), SwCoreConstants.RemoteSwKey.TYPE);
                    if (oc.error != null) {
                        stats.failures.add(template + " 规则解析异常: " + oc.error);
                        addrFailed = true;
                        break;
                    }
                    if (oc.patches == null) {
                        // 该版本已弃用这条规则
                        stats.sawRuleList = true;
                        continue;
                    }
                    stats.sawRuleList = true;
                    if (oc.patches.isEmpty()) {
                        stats.failures.add(template + " 特征码未命中 (类型 " + type + ")");
                        addrFailed = true;
                        break;
                    }
                    patches.addAll(oc.patches);
                    stats.ruleHits += oc.patches.size();
                }

                if (addrFailed || patches.isEmpty()) {
                    if (!addrFailed) {
                        stats.failures.add(template + " 没有产出可用的补丁");
                    }
                    continue;
                }

                ObjectNode entry = baseEntry(feature, template);
                entry.set("patches", MAPPER.valueToTree(patches));
                out.add(entry);
            } catch (IOException e) {
                stats.failures.add(template + " 读取失败: " + e.getMessage());
            } finally {
                unmap(mm);
            }
        }
    }

    /** 构造缓存条目：addr（模板）+ 其余原样字段（wildcard 缺省写 null）；patches 由调用方填 */
    private static ObjectNode baseEntry(JsonNode feature, String template) {
        ObjectNode entry = MAPPER.createObjectNode();
        entry.put(SwCoreConstants.RemoteSwKey.ADDR, template);
        feature.fieldNames().forEachRemaining(key -> {
            if (SwCoreConstants.RemoteSwKey.PATCH_RULES.equals(key)
                    || SwCoreConstants.RemoteSwKey.ADDR.equals(key)) return;
            entry.set(key, feature.get(key).deepCopy());
        });
        if (!entry.has(SwCoreConstants.RemoteSwKey.WILDCARD)) {
            entry.putNull(SwCoreConstants.RemoteSwKey.WILDCARD);
        }
        return entry;
    }

    // ==================== 规则并行扫描 ====================

    /** 单条规则的扫描结果：patches=null 表示该版本弃用；error 非空表示解析异常 */
    private static final class RuleOutcome {
        final List<Map<String, Object>> patches;
        final String error;

        RuleOutcome(List<Map<String, Object>> patches, String error) {
            this.patches = patches;
            this.error = error;
        }
    }

    /** 规则级并行池（守护线程；同一文件的多个规则共享只读 ByteBuffer） */
    private static final java.util.concurrent.ExecutorService RULE_POOL =
            java.util.concurrent.Executors.newFixedThreadPool(
                    Math.max(2, Math.min(4, Runtime.getRuntime().availableProcessors())),
                    r -> {
                        Thread t = new Thread(r, "patch-scan");
                        t.setDaemon(true);
                        return t;
                    });

    /** 渠道级并行池（与规则池分开，避免"渠道任务等规则任务"互相占满） */
    private static final java.util.concurrent.ExecutorService CHANNEL_POOL =
            java.util.concurrent.Executors.newFixedThreadPool(3, r -> {
                Thread t = new Thread(r, "patch-chan");
                t.setDaemon(true);
                return t;
            });

    /**
     * 缓存树写入锁：**只保护 JSON 树的合并**（毫秒级），扫描本身不持锁。
     * 这样不同模式（多开 / 防撤 / 共存）可以真正并行扫描，又不会并发写坏同一棵 ObjectNode。
     */
    static final Object MERGE_LOCK = new Object();

    /** 按规则顺序返回结果（并行执行，顺序 = 配置顺序，保证"后可覆盖前"） */
    private static List<RuleOutcome> resolveRules(String curVer, ByteBuffer mm, List<JsonNode> rules) {
        List<RuleOutcome> out = new ArrayList<>(rules.size());
        if (rules.isEmpty()) return out;
        if (rules.size() == 1) {
            out.add(resolveOne(curVer, mm, rules.get(0)));
            return out;
        }

        com.jfmultichat.core.task.JfTask task = com.jfmultichat.core.task.TaskContext.current();
        List<java.util.concurrent.Future<RuleOutcome>> futures = new ArrayList<>(rules.size());
        for (JsonNode rule : rules) {
            futures.add(RULE_POOL.submit(() -> {
                // 取消对整个任务生效：所有 worker 共享同一个 task 的取消标记
                if (task != null && (task.isCancelRequested() || Thread.currentThread().isInterrupted())) {
                    throw new com.jfmultichat.core.task.TaskCancelledException();
                }
                return resolveOne(curVer, mm, rule);
            }));
        }
        for (java.util.concurrent.Future<RuleOutcome> f : futures) {
            try {
                out.add(f.get());
            } catch (java.util.concurrent.ExecutionException e) {
                Throwable cause = e.getCause();
                if (cause instanceof com.jfmultichat.core.task.TaskCancelledException ce) throw ce;
                out.add(new RuleOutcome(null,
                        cause == null ? e.getMessage() : cause.getMessage()));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new com.jfmultichat.core.task.TaskCancelledException();
            }
        }
        return out;
    }

    private static RuleOutcome resolveOne(String curVer, ByteBuffer mm, JsonNode rule) {
        try {
            return new RuleOutcome(SwRuleResolver.resolveRuleDictAndReturnResDicts(curVer, mm, rule), null);
        } catch (Exception e) {
            return new RuleOutcome(null, e.getMessage());
        }
    }

    // ==================== 缓存节点操作 ====================

    private static boolean hasValidCache(ObjectNode chCache, String curVer) {
        JsonNode node = chCache.get(KEY_PRECISE);
        if (node == null) node = chCache.get(KEY_PRECISE_LEGACY);
        if (node == null || !node.isObject()) return false;
        JsonNode verNode = node.get(curVer);
        if (verNode == null || !verNode.isArray() || verNode.isEmpty()) return false;
        for (JsonNode entry : verNode) {
            if (!entry.isObject()) return false;
            if (!entry.has("patches") || !entry.get("patches").isArray()) return false;
            if (!entry.has(SwCoreConstants.RemoteSwKey.ADDR)
                    || !entry.get(SwCoreConstants.RemoteSwKey.ADDR).isTextual()) return false;
        }
        return true;
    }

    private static void removeVersion(ObjectNode chCache, String curVer) {
        for (String key : new String[]{KEY_PRECISE, KEY_PRECISE_LEGACY}) {
            JsonNode node = chCache.get(key);
            if (node instanceof ObjectNode obj) obj.remove(curVer);
        }
    }

    private static ObjectNode ensureObject(ObjectNode root, String... path) {
        ObjectNode cur = root;
        for (String key : path) {
            JsonNode next = cur.get(key);
            ObjectNode nextObj;
            if (next instanceof ObjectNode existing) {
                nextObj = existing;
            } else {
                nextObj = cur.putObject(key);
            }
            cur = nextObj;
        }
        return cur;
    }

    // ==================== 文件映射 ====================

    private static ByteBuffer mapReadOnly(Path file) throws IOException {
        long size = Files.size(file);
        if (size <= MMAP_THRESHOLD) {
            return ByteBuffer.wrap(Files.readAllBytes(file));
        }
        try (FileChannel ch = FileChannel.open(file, StandardOpenOption.READ)) {
            return ch.map(FileChannel.MapMode.READ_ONLY, 0, size);
        }
    }

    /** 释放直接映射（Windows 上映射未解除会导致文件被占用；同进程内改完立刻要读时必须调用） */
    public static void unmap(ByteBuffer buf) {
        if (buf == null || !buf.isDirect()) return;
        try {
            Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
            var field = unsafeClass.getDeclaredField("theUnsafe");
            field.setAccessible(true);
            Object unsafe = field.get(null);
            var cleaner = unsafeClass.getMethod("invokeCleaner", ByteBuffer.class);
            cleaner.invoke(unsafe, buf);
        } catch (Throwable ignored) {
            // 退化为等待 GC
        }
    }

    // ==================== 小工具 ====================

    private static String text(JsonNode node, String key) {
        if (node == null) return null;
        JsonNode v = node.get(key);
        return v != null && v.isTextual() ? v.asText() : null;
    }

    private static String joinPath(String base, String rel, boolean isDir) {
        String r = rel.replace('\\', '/');
        while (r.startsWith("/")) r = r.substring(1);
        boolean trailing = r.endsWith("/");
        while (r.endsWith("/")) r = r.substring(0, r.length() - 1);

        String joined;
        if (base == null || base.isEmpty()) {
            joined = r;
        } else {
            String b = base.replace('\\', '/');
            while (b.endsWith("/")) b = b.substring(0, b.length() - 1);
            joined = r.isEmpty() ? b : b + "/" + r;
        }
        return (isDir || trailing) ? joined + "/" : joined;
    }
}
