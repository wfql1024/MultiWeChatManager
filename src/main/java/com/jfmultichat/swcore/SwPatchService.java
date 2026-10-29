package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.jfmultichat.core.task.TaskContext;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 补丁服务门面 —— 供 JS 桥调用的单一入口。
 * <p>
 * 把"识别状态 / 切换补丁 / 共存实例增删重建"这些动作收敛到一处：
 * <ul>
 *   <li>计划：{@link #getSwPatchPlan}（程序行）、{@link #getInstancePatchPlan}（共存账号行）</li>
 *   <li>动作：{@link #toggle}、{@link #createCoexist}、{@link #deleteCoexist}、{@link #rebuildCoexist}</li>
 * </ul>
 * 对应 Python: exe_manager_ui 里"补丁按钮 + 共存实例表"的行为。
 */
public final class SwPatchService {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private SwPatchService() {}

    // ==================== 计划（给界面渲染按钮） ====================

    /** 程序行：共存 / 多开 / 防撤 三组渠道 + 当前状态 */
    public static ObjectNode getSwPatchPlan(String sw, SwConfigAccessor acc) {
        return doGetSwPatchPlan(sw, acc);
    }

    private static ObjectNode doGetSwPatchPlan(String sw, SwConfigAccessor acc) {
        ObjectNode root = MAPPER.createObjectNode();
        String ver = SwVersionHelper.calcSwVer(sw, acc);
        root.put("version", ver == null ? "" : ver);
        TaskContext.checkpoint();
        // 实测（2026-10-23）：模式并行反而更慢 —— 192MB 全文件扫描是**内存带宽**瓶颈，
        // 同时跑 5~6 路只会互相拖慢（4.7s → 5.1s）。所以这里保持串行，靠渠道池控制并发。
        root.set(SwCoreConstants.RemoteSwKey.MULTI,
                buildChannels(sw, SwCoreConstants.RemoteSwKey.MULTI, null, null, true, acc));
        TaskContext.checkpoint();
        // 「共存」归共存账号表管（见 getCoexistPlan）；程序行只做 多开 / 防撤
        root.set("revoke",
                buildChannels(sw, SwCoreConstants.RemoteSwKey.REVOKE, null, null, true, acc));
        return root;
    }

    // ==================== 渠道启用/禁用（用户自选） ====================

    /** 某模式下被用户禁用的渠道 id 集合 */
    public static java.util.Set<String> disabledChannels(String sw, String mode, SwConfigAccessor acc) {
        java.util.Set<String> out = new java.util.LinkedHashSet<>();
        JsonNode n = acc.getSwSetting(sw, SwCoreConstants.LocalSettingKey.DISABLED_CHANNELS);
        if (n != null && n.isObject()) {
            JsonNode arr = n.get(mode);
            if (arr != null && arr.isArray()) arr.forEach(x -> out.add(x.asText()));
        }
        return out;
    }

    /** 启用/禁用某渠道（写本地配置，只改动该模式，不动其他模式） */
    public static void setChannelEnabled(String sw, String mode, String channel, boolean enabled,
                                         SwConfigAccessor acc) {
        java.util.Set<String> dis = disabledChannels(sw, mode, acc);
        // 关系传播（用户 2026-10-23 定）：
        //   启用子渠道 → 必然也启用它的 parents；禁用父渠道 → 连带禁用它的 children
        Map<String, List<String>> rel = SwOperatorCore.getRelationsOfChannel(sw, mode, channel,
                acc.getSwCache(), acc);
        if (enabled) {
            dis.remove(channel);
            for (String p : rel.getOrDefault("parents", List.of())) dis.remove(p);
        } else {
            dis.add(channel);
            for (String c : rel.getOrDefault("children", List.of())) dis.add(c);
        }

        java.util.Map<String, Object> all = new java.util.LinkedHashMap<>();
        JsonNode n = acc.getSwSetting(sw, SwCoreConstants.LocalSettingKey.DISABLED_CHANNELS);
        if (n != null && n.isObject()) {
            var it = n.fields();
            while (it.hasNext()) {
                var e = it.next();
                all.put(e.getKey(), MAPPER.convertValue(e.getValue(), Object.class));
            }
        }
        all.put(mode, new ArrayList<>(dis));
        // 必须走 updateSwSettings（putPOJO → 真正的 JSON 对象）；
        // saveAndCheckChanged 会 value.toString()，把 Map 写成字符串 → 读回来不是对象 → 禁用列表"丢失"
        Map<String, Object> kwargs = new java.util.HashMap<>();
        kwargs.put(SwCoreConstants.LocalSettingKey.DISABLED_CHANNELS, all);
        acc.updateSwSettings(sw, Map.of(), kwargs);
    }

    /**
     * 只返回某个模式的渠道计划（启用/禁用渠道后局部刷新用）。
     *
     * @param onlyChannel 启用后需要补扫的那个渠道；null = 不额外扫描，只读缓存
     */
    public static ObjectNode getModePlan(String sw, String mode, List<String> onlyChannels, SwConfigAccessor acc) {
        ObjectNode root = MAPPER.createObjectNode();
        root.put("mode", mode);
        boolean scan = onlyChannels != null && !onlyChannels.isEmpty();
        root.set("channels", buildChannels(sw, mode, null, null, scan, onlyChannels, acc));
        return root;
    }

    /** 启用某渠道时需要一并补扫的渠道：它自己 + 它的前置（用户定：启用子必然启用父） */
    public static List<String> channelsToScanOnEnable(String sw, String mode, String channel, SwConfigAccessor acc) {
        java.util.LinkedHashSet<String> out = new java.util.LinkedHashSet<>();
        out.add(channel);
        out.addAll(SwOperatorCore.getRelationsOfChannel(sw, mode, channel, acc.getSwCache(), acc)
                .getOrDefault("parents", List.of()));
        return new ArrayList<>(out);
    }

    /** 只构建 anti-revoke 缓存（共存表刷新 / 共存账号行扫描用；不碰多开） */
    public static void ensureRevokeCache(String sw, SwConfigAccessor acc) {
        buildChannels(sw, SwCoreConstants.RemoteSwKey.REVOKE, null, null, true, acc);
    }

    /** 兜底：即使拿不到共存索引，也把防撤渠道列表返回（状态未知），避免补丁列空白 */
    public static ObjectNode getRevokeChannelsUnknown(String sw, SwConfigAccessor acc) {
        ObjectNode root = MAPPER.createObjectNode();
        ArrayNode arr = root.putArray("revoke");
        JsonNode channels = acc.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.REVOKE,
                SwCoreConstants.RemoteSwKey.CHANNELS);
        if (channels != null && channels.isObject()) {
            var it = channels.fieldNames();
            while (it.hasNext()) {
                String id = it.next();
                JsonNode ch = channels.get(id);
                ObjectNode item = MAPPER.createObjectNode();
                item.put("id", id);
                item.put("alias", text(ch, SwCoreConstants.RemoteSwKey.ALIAS, id));
                item.put("introduce", text(ch, SwCoreConstants.RemoteSwKey.INTRODUCTION, ""));
                item.putArray(SwCoreConstants.RemoteSwKey.AUTHORS);
                item.put("state", "unknown");
                item.put("msg", "未知共存索引");
                arr.add(item);
            }
        }
        return root;
    }

    /** 共存表表头用：可用渠道 + 当前选中渠道（与程序行完全独立的一条加载路径） */
    public static ObjectNode getCoexistPlan(String sw, SwConfigAccessor acc) {
        ObjectNode root = MAPPER.createObjectNode();
        root.put("coexist_mode", selectedCoexistMode(sw, acc));
        root.set("channels", buildChannels(sw, SwCoreConstants.RemoteSwKey.COEXIST, null, null, true, acc));
        return root;
    }

    /** 共存账号行：只有防撤（作用在该实例的克隆 dll 上） */
    public static ObjectNode getInstancePatchPlan(
            String sw, String coexistChannel, String ordinal, SwConfigAccessor acc) {
        return doGetInstancePatchPlan(sw, coexistChannel, ordinal, acc);
    }

    private static ObjectNode doGetInstancePatchPlan(
            String sw, String coexistChannel, String ordinal, SwConfigAccessor acc) {
        ObjectNode root = MAPPER.createObjectNode();
        root.set("revoke",
                buildChannels(sw, SwCoreConstants.RemoteSwKey.REVOKE, coexistChannel, ordinal, false, acc));
        return root;
    }

    private static ArrayNode buildChannels(String sw, String mode,
                                           String coexistChannel, String ordinal, boolean allowScan,
                                           SwConfigAccessor acc) {
        return buildChannels(sw, mode, coexistChannel, ordinal, allowScan, null, acc);
    }

    /**
     * @param onlyChannels 只扫这些渠道（启用某渠道后按需补扫自己+前置）；null = 全部已启用渠道
     */
    private static ArrayNode buildChannels(String sw, String mode, String coexistChannel, String ordinal,
                                           boolean allowScan, List<String> onlyChannels, SwConfigAccessor acc) {
        ArrayNode arr = MAPPER.createArrayNode();
        JsonNode channels = acc.getRemoteSw(sw, mode, SwCoreConstants.RemoteSwKey.CHANNELS);
        if (channels == null || !channels.isObject()) return arr;

        // 禁用的渠道**不扫描**（列表仍然全部输出，前端按 enabled 区分）
        java.util.Set<String> disabled = disabledChannels(sw, mode, acc);
        List<String> scanList = new ArrayList<>();
        var ids = channels.fieldNames();
        while (ids.hasNext()) {
            String id = ids.next();
            if (disabled.contains(id)) continue;
            if (onlyChannels != null && !onlyChannels.contains(id)) continue;
            scanList.add(id);
        }

        SwAdapterChecker.ChannelsResult res;
        try {
            // 扫描只针对 scanList；**识别覆盖全部缓存渠道**（否则"启用某渠道"会让其它渠道显示成未知）
            res = SwAdapterChecker.identifyChannels(sw, mode, scanList, null, coexistChannel, ordinal,
                    false, allowScan, acc, acc.getSwCache());
        } catch (Exception e) {
            res = new SwAdapterChecker.ChannelsResult(null, "识别失败: " + e.getMessage(), false);
        }

        var names = channels.fieldNames();
        while (names.hasNext()) {
            TaskContext.checkpoint();
            String id = names.next();
            JsonNode ch = channels.get(id);
            ObjectNode item = MAPPER.createObjectNode();
            item.put("id", id);
            item.put("alias", text(ch, SwCoreConstants.RemoteSwKey.ALIAS, id));
            item.put("introduce", text(ch, SwCoreConstants.RemoteSwKey.INTRODUCTION, ""));
            ArrayNode authors = item.putArray(SwCoreConstants.RemoteSwKey.AUTHORS);
            JsonNode au = ch.get(SwCoreConstants.RemoteSwKey.AUTHORS);
            if (au != null && au.isArray()) au.forEach(a -> authors.add(a.asText()));

            boolean enabled = !disabled.contains(id);
            item.put("enabled", enabled);
            // 关系（前端 tooltip 显示"前置 / 后置 / 可共存"；互斥是默认行为，不强调）
            Map<String, List<String>> rel = SwOperatorCore.getRelationsOfChannel(sw, mode, id,
                    acc.getSwCache(), acc);
            for (String k : List.of("parents", "children", "friends")) {
                List<String> v = rel.getOrDefault(k, List.of());
                if (!v.isEmpty()) { ArrayNode arrRel = item.putArray(k); v.forEach(arrRel::add); }
            }
            SwAdapterChecker.DetectionResult r = res.channels.get(id);
            String state = (r == null || r.status == null) ? "unknown" : (r.status ? "on" : "off");
            item.put("state", state);
            item.put("msg", r == null ? "无适配" : r.message);
            arr.add(item);
        }
        return arr;
    }

    // ==================== 动作 ====================

    /** 切换某渠道补丁（target=null → 自动识别取反） */
    public static String toggle(String sw, String mode, String channel,
                                String coexistChannel, String ordinal, SwConfigAccessor acc) {
        TaskContext.checkpoint();   // 取消 = 一个字节都不写（写在 checkpoint 之后才开始）
        try {
            ObjectNode cache = acc.getSwCache();
            Boolean cur = channelStatus(sw, mode, channel, coexistChannel, ordinal, acc, cache);
            // 前置没适配没扫描 == 这个渠道没适配（用户 2026-10-23 定：照旧版）
            if (cur == null) return "无法识别当前状态（该渠道未适配），补丁未应用";
            boolean target = !cur;

            Map<String, List<String>> rel = SwOperatorCore.getRelationsOfChannel(sw, mode, channel, cache, acc);
            List<String> parents = rel.getOrDefault("parents", List.of());
            List<String> children = rel.getOrDefault("children", List.of());
            java.util.Set<String> friends = new java.util.HashSet<>(rel.getOrDefault("friends", List.of()));

            if (target) {
                // 前置必须可用（"前置没适配没扫描"= 本渠道没适配）
                for (String p : parents) {
                    if (channelStatus(sw, mode, p, coexistChannel, ordinal, acc, cache) == null) {
                        return "前置方案「" + p + "」未适配或未启用，补丁未应用";
                    }
                }
                // 同组其余渠道：跳过自己 / 可共存(friends) / 前置(parents)，其余全部关闭
                for (String other : enabledChannelIds(sw, mode, acc)) {
                    if (other.equals(channel) || friends.contains(other) || parents.contains(other)) continue;
                    if (!Boolean.TRUE.equals(channelStatus(sw, mode, other, coexistChannel, ordinal, acc, cache))) continue;
                    String[] r = SwOperatorCore.switchDllCore(sw, mode, other, coexistChannel, ordinal,
                            false, acc, cache, null);
                    if (r[0] == null) return "冲突方案「" + other + "」关闭失败: " + r[1];
                    TaskContext.checkpoint();
                }
                // 再依次开启前置
                for (String p : parents) {
                    String[] r = SwOperatorCore.switchDllCore(sw, mode, p, coexistChannel, ordinal,
                            true, acc, cache, null);
                    if (r[0] == null) return "前置方案「" + p + "」开启失败: " + r[1];
                    TaskContext.checkpoint();
                }
                String[] r = SwOperatorCore.switchDllCore(sw, mode, channel, coexistChannel, ordinal,
                        true, acc, cache, null);
                return r[1] == null ? "成功" : r[1];
            }

            // 关闭：先关后置（失败只忽略），再关自己
            for (String c : children) {
                try {
                    SwOperatorCore.switchDllCore(sw, mode, c, coexistChannel, ordinal, false, acc, cache, null);
                } catch (Exception ignored) { }
                TaskContext.checkpoint();
            }
            String[] r = SwOperatorCore.switchDllCore(sw, mode, channel, coexistChannel, ordinal,
                    false, acc, cache, null);
            return r[1] == null ? "成功" : r[1];
        } catch (Exception e) {
            return "操作失败: " + e.getMessage();
        }
    }

    /** 某渠道当前的三态状态（true=已打 / false=未打 / null=未知，如未适配） */
    private static Boolean channelStatus(String sw, String mode, String channel, String coexistChannel,
                                         String ordinal, SwConfigAccessor acc, ObjectNode cache) {
        try {
            SwAdapterChecker.ChannelsResult res = SwAdapterChecker.identifyChannels(
                    sw, mode, List.of(channel), coexistChannel, ordinal, false, false, acc, cache);
            SwAdapterChecker.DetectionResult r = res.channels == null ? null : res.channels.get(channel);
            return r == null ? null : r.status;
        } catch (Exception e) {
            return null;
        }
    }

    /** 已启用（未被用户禁用）的渠道 id 列表 */
    public static List<String> enabledChannelIds(String sw, String mode, SwConfigAccessor acc) {
        JsonNode channels = acc.getRemoteSw(sw, mode, SwCoreConstants.RemoteSwKey.CHANNELS);
        List<String> out = new ArrayList<>();
        if (channels == null || !channels.isObject()) return out;
        java.util.Set<String> dis = disabledChannels(sw, mode, acc);
        var it = channels.fieldNames();
        while (it.hasNext()) {
            String id = it.next();
            if (!dis.contains(id)) out.add(id);
        }
        return out;
    }

    /** 当前选中的共存渠道（未设置时取第一个渠道） */
    public static String selectedCoexistMode(String sw, SwConfigAccessor acc) {
        String v = acc.getSwSettingAsString(sw, SwCoreConstants.LocalSettingKey.COEXIST_MODE, null);
        if (v != null && !v.isBlank()) return v;
        JsonNode channels = acc.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.COEXIST,
                SwCoreConstants.RemoteSwKey.CHANNELS);
        if (channels != null && channels.isObject()) {
            var it = channels.fieldNames();
            if (it.hasNext()) return it.next();
        }
        return "";
    }

    public static void setSelectedCoexistMode(String sw, String channel, SwConfigAccessor acc) {
        acc.saveAndCheckChanged(sw, SwCoreConstants.LocalSettingKey.COEXIST_MODE, channel);
    }

    /**
     * 解析共存索引（渠道 + 序号）：优先用保存的渠道，匹配不上就遍历所有渠道找一个
     * `exe_wildcard` 能对上该账号名的（防止配置里残留了已失效/不存在的渠道）。
     *
     * @return {channel, ordinal}，都解析不到返回 null
     */
    public static String[] resolveCoexistIndex(String sw, String accId, String preferred,
                                               SwConfigAccessor acc) {
        JsonNode channels = acc.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.COEXIST,
                SwCoreConstants.RemoteSwKey.CHANNELS);
        if (channels == null || !channels.isObject()) return null;
        if (preferred != null && !preferred.isEmpty()) {
            String ord = deriveOrdinal(sw, accId, preferred, acc);
            if (ord != null) return new String[]{preferred, ord};
        }
        var it = channels.fieldNames();
        while (it.hasNext()) {
            String ch = it.next();
            String ord = deriveOrdinal(sw, accId, ch, acc);
            if (ord != null) return new String[]{ch, ord};
        }
        return null;
    }

    /**
     * 老数据可能没有 `channel` / `ordinal` 字段 → 从账号 id（克隆 exe 名）按 `exe_wildcard` 反推序号。
     * 例：exe_wildcard = "Weixi?.exe"、accId = "Weixi3.exe" → "3"。
     */
    public static String deriveOrdinal(String sw, String accId, String channel, SwConfigAccessor acc) {
        if (accId == null || channel == null || channel.isEmpty()) return null;
        JsonNode wc = acc.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.COEXIST,
                SwCoreConstants.RemoteSwKey.CHANNELS, channel, SwCoreConstants.RemoteSwKey.EXE_WILDCARD);
        if (wc == null || !wc.isTextual()) return null;
        String pat = wc.asText();
        int q = pat.indexOf('?');
        if (q < 0 || accId.length() != pat.length()) return null;
        if (!accId.substring(0, q).equalsIgnoreCase(pat.substring(0, q))) return null;
        if (!accId.substring(q + 1).equalsIgnoreCase(pat.substring(q + 1))) return null;
        return String.valueOf(accId.charAt(q));
    }

    /** 新建一个共存程序（自动取最小可用序号） */
    public static String createCoexist(String sw, String channel, SwConfigAccessor acc) {
        JsonNode ordinalsNode = acc.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.COEXIST,
                SwCoreConstants.RemoteSwKey.CHANNELS, channel, SwCoreConstants.RemoteSwKey.ORDINALS);
        JsonNode exeWildcardNode = acc.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.COEXIST,
                SwCoreConstants.RemoteSwKey.CHANNELS, channel, SwCoreConstants.RemoteSwKey.EXE_WILDCARD);
        if (ordinalsNode == null || !ordinalsNode.isTextual()
                || exeWildcardNode == null || !exeWildcardNode.isTextual()) {
            return "尚未适配[exe_wildcard, ordinals]";
        }
        String instPath = acc.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
        if (instPath == null) return "无法获取安装路径";
        String instDir = new File(instPath).getParent();

        String ordinal = null;
        for (char c : ordinalsNode.asText().toCharArray()) {
            String exe = exeWildcardNode.asText().replace("?", String.valueOf(c));
            if (instDir == null || !Files.exists(Path.of(instDir, exe))) {
                ordinal = String.valueOf(c);
                break;
            }
        }
        if (ordinal == null) return "没有可用的序号了";

        String[] r = SwOperatorCore.createCoexistExeCore(sw, channel, ordinal, acc, acc.getSwCache(), opsOf(acc));
        if (r[0] == null) return "创建失败: " + r[1];
        return "已创建 " + r[0];
    }

    /** 删除共存程序（文件 + 账号数据） */
    public static String deleteCoexist(String sw, String accId, SwConfigAccessor acc) {
        Map<String, Object> r = SwOperatorCore.delCoexistExe(sw, List.of(accId), acc, acc.getSwCache());
        @SuppressWarnings("unchecked")
        Map<String, String> failed = (Map<String, String>) r.get("failed");
        if (failed != null && failed.containsKey(accId)) {
            return "删除失败: " + failed.get(accId);
        }
        acc.clearSwAccData(sw, accId);
        return "已删除 " + accId;
    }

    /** 重建共存程序（按账号数据里记录的渠道/序号重新生产） */
    public static String rebuildCoexist(String sw, String accId, SwConfigAccessor acc) {
        JsonNode chNode = acc.getSwAccData(sw, accId, SwCoreConstants.AccKeys.COEXIST_CHANNEL);
        JsonNode ordNode = acc.getSwAccData(sw, accId, SwCoreConstants.AccKeys.ORDINAL);
        String channel = (chNode != null && chNode.isTextual()) ? chNode.asText() : null;
        if (channel == null || channel.isEmpty()) channel = selectedCoexistMode(sw, acc);
        String ordinal = (ordNode != null && ordNode.isTextual()) ? ordNode.asText() : null;
        if (ordinal == null || ordinal.isEmpty()) ordinal = deriveOrdinal(sw, accId, channel, acc);
        if (channel == null || ordinal == null) {
            return "未适配（未知共存索引）";
        }
        Map<String, Object> r = SwOperatorCore.rebuildCoexistExes(sw, List.of(accId),
                channel, ordinal, acc, acc.getSwCache(), opsOf(acc));
        Map<String, String> failed = castFailed(r.get("failed"));
        if (failed != null && failed.containsKey(accId)) {
            return "重建失败: " + failed.get(accId);
        }
        return "已重建 " + accId;
    }

    // ==================== 内部 ====================

    private static SwAccountOps.AccountOpsProvider opsOf(SwConfigAccessor acc) {
        return new SwAccountOps.AccountOpsProvider() {
            @Override
            public JsonNode getSwAccData(String sw, String... addr) {
                return acc.getSwAccData(sw, addr);
            }

            @Override
            public JsonNode getSwAccData(String sw, Map<String, Object> kwargs) {
                return acc.getSwAccData(sw, kwargs);
            }

            @Override
            public void updateSwAccData(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs) {
                acc.updateSwAccData(sw, frontAddr, kwargs);
            }
        };
    }

    @SuppressWarnings("unchecked")
    private static Map<String, String> castFailed(Object o) {
        return (o instanceof Map) ? (Map<String, String>) o : new LinkedHashMap<>();
    }

    private static String text(JsonNode node, String key, String def) {
        if (node == null) return def;
        JsonNode v = node.get(key);
        return v != null && v.isTextual() ? v.asText() : def;
    }
}
