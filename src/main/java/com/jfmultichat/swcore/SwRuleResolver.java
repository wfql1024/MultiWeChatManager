package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.ByteBuffer;
import java.util.*;

/**
 * 规则解析器 — 解析补丁规则字典并返回扫描结果
 * <p>
 * 对应 Python: SwInfoFuncCore._resolve_simple_rule, _resolve_custom_rule,
 * _resolve_jmp_offset_rule, _resolve_relation_rule, resolve_rule_dict_and_return_res_dicts
 * 以及 SwHexUtils.search_pattern_dicts_by_original_and_modified,
 * search_first_pattern_and_get_address_of_marked
 *
 * 依赖: SwHexUtils (特征码扫描), Jackson (JSON 解析)
 */
public final class SwRuleResolver {

    private static final Logger LOG = LoggerFactory.getLogger(SwRuleResolver.class);
    private SwRuleResolver() {}

    // ==================== 规则类型常量 ====================

    public static final String RULE_TYPE_SIMPLE = "simple";
    public static final String RULE_TYPE_CUSTOM = "custom";
    public static final String RULE_TYPE_JMP_OFFSET = "jmp_offset";
    public static final String RULE_TYPE_RELATION = "relation";

    // ==================== 规则解析入口 ====================

    /**
     * 解析规则字典并返回结果字典列表
     * 对应 Python: resolve_rule_dict_and_return_res_dicts (L1300-L1339)
     *
     * @param curSwVer    当前软件版本
     * @param mm          文件映射 ByteBuffer
     * @param featureRule 特征规则字典（含 type + ver_adaptations）
     * @return 结果字典列表；版本不兼容返回 null；格式错误抛出异常
     */
    public static List<Map<String, Object>> resolveRuleDictAndReturnResDicts(
            String curSwVer, ByteBuffer mm, JsonNode featureRule) {

        JsonNode patchingVersDict = featureRule.get("ver_adaptations");
        if (patchingVersDict == null || !patchingVersDict.isObject()) {
            return Collections.emptyList();
        }

        // 找到兼容版本
        String compatibleVer = findCompatibleVersion(curSwVer, patchingVersDict);
        if (compatibleVer == null) {
            LOG.warn("[规则] 当前版本 {} 无本条规则的适配版本!", curSwVer);
            return null; // null 表示规则已弃用
        }

        JsonNode verRuleDict = patchingVersDict.get(compatibleVer);
        if (verRuleDict == null) {
            LOG.warn("[规则] 当前版本 {} 对应的适配版本 {} 已弃用本条规则!", curSwVer, compatibleVer);
            return null;
        }

        String ruleType = featureRule.has("type") ? featureRule.get("type").asText() : "";
        List<Map<String, Object>> innerResults;

        switch (ruleType) {
            case RULE_TYPE_SIMPLE ->
                    innerResults = resolveSimpleRule(mm, verRuleDict);
            case RULE_TYPE_CUSTOM ->
                    innerResults = resolveCustomRule(mm, verRuleDict);
            case RULE_TYPE_JMP_OFFSET ->
                    innerResults = resolveJmpOffsetRule(mm, verRuleDict);
            case RULE_TYPE_RELATION ->
                    innerResults = resolveRelationRule(verRuleDict);
            default ->
                    throw new IllegalArgumentException("未知规则类型: " + ruleType);
        }

        // 将 featureRule 中除 type/ver_adaptations 外的额外节点复制到每个结果
        for (Map<String, Object> result : innerResults) {
            featureRule.fieldNames().forEachRemaining(key -> {
                if (!"type".equals(key) && !"ver_adaptations".equals(key)) {
                    result.put(key, jsonNodeToObject(featureRule.get(key)));
                }
            });
        }

        return innerResults;
    }

    // ==================== 版本兼容查找 ====================

    /**
     * 从版本字典中找到与目标版本最兼容的版本
     * 策略：精确匹配 > 次高版本匹配 > 最低版本匹配
     * 对应 Python: VersionUtils.pkg_find_compatible_version
     *
     * @param targetVer 目标版本，如 "8.0.47"
     * @param versDict  版本字典（JsonNode 的 fieldNames）
     * @return 兼容版本号；无则 null
     */
    public static String findCompatibleVersion(String targetVer, JsonNode versDict) {
        if (versDict == null || !versDict.isObject()) return null;

        // 精确匹配
        if (versDict.has(targetVer)) return targetVer;

        List<String> versions = new ArrayList<>();
        versDict.fieldNames().forEachRemaining(versions::add);
        if (versions.isEmpty()) return null;

        // 按版本号降序排列
        versions.sort(SwVersionHelper::compareVersionDesc);

        // 找第一个 <= target 的版本
        for (String v : versions) {
            if (SwVersionHelper.compareVersionDesc(v, targetVer) <= 0) {
                return v;
            }
        }

        // 全部比 target 新，取最低版本
        return versions.get(versions.size() - 1);
    }

    /**
     * 版本字符串降序比较
     * @return negative if a > b, zero if equal, positive if a < b
     */
    public static int compareVersionDesc(String a, String b) {
        return -compareVersionAsc(a, b);
    }

    /**
     * 版本字符串升序比较
     * @return negative if a < b, zero if equal, positive if a > b
     */
    public static int compareVersionAsc(String a, String b) {
        String[] pa = a.split("\\.");
        String[] pb = b.split("\\.");
        int maxLen = Math.max(pa.length, pb.length);
        for (int i = 0; i < maxLen; i++) {
            int va = i < pa.length ? parseIntSafe(pa[i]) : 0;
            int vb = i < pb.length ? parseIntSafe(pb[i]) : 0;
            if (va != vb) return Integer.compare(va, vb);
        }
        return 0;
    }

    private static int parseIntSafe(String s) {
        try { return Integer.parseInt(s); } catch (NumberFormatException e) { return 0; }
    }

    // ==================== Simple 规则 ====================

    /**
     * 解析 simple 类型规则
     * 对应 Python: _resolve_simple_rule (L1147-L1164)
     */
    private static List<Map<String, Object>> resolveSimpleRule(ByteBuffer mm, JsonNode ruleDict) {
        String original = ruleDict.get("original").asText();
        String modified = ruleDict.get("modified").asText();
        int leftCut = ruleDict.has("left_cut") ? ruleDict.get("left_cut").asInt() : 0;
        int rightCut = ruleDict.has("right_cut") ? ruleDict.get("right_cut").asInt() : 0;

        List<SwHexUtils.ScanResult> results = SwHexUtils.searchPatternDicts(
                mm, original, modified, leftCut, rightCut);
        if (results == null) return Collections.emptyList();

        List<Map<String, Object>> out = new ArrayList<>();
        for (SwHexUtils.ScanResult r : results) {
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("offset", r.offset);
            entry.put("original", r.original);
            entry.put("modified", r.modified);
            // 补充额外节点（排除 basic 四个字段）
            for (String key : Set.of("original", "modified", "left_cut", "right_cut")) {
                // skipped
            }
            out.add(entry);
        }
        return out;
    }

    // ==================== Custom 规则 ====================

    /**
     * 解析 custom 类型规则 — 同 simple，但标记 customizable=true
     * 对应 Python: _resolve_custom_rule (L1177-L1197)
     */
    private static List<Map<String, Object>> resolveCustomRule(ByteBuffer mm, JsonNode ruleDict) {
        String original = ruleDict.get("original").asText();
        String modified = ruleDict.get("modified").asText();
        int leftCut = ruleDict.has("left_cut") ? ruleDict.get("left_cut").asInt() : 0;
        int rightCut = ruleDict.has("right_cut") ? ruleDict.get("right_cut").asInt() : 0;

        List<SwHexUtils.ScanResult> results = SwHexUtils.searchPatternDicts(
                mm, original, modified, leftCut, rightCut);
        if (results == null) return Collections.emptyList();

        List<Map<String, Object>> out = new ArrayList<>();
        for (SwHexUtils.ScanResult r : results) {
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("offset", r.offset);
            entry.put("original", r.original);
            entry.put("modified", r.modified);
            entry.put("customizable", true);
            out.add(entry);
        }
        return out;
    }

    // ==================== JMP Offset 规则 ====================

    /**
     * 解析 jmp_offset 类型规则
     * 对应 Python: _resolve_jmp_offset_rule (L1199-L1298)
     * <p>
     * 该规则需要：先扫描 targets 特征码获取目标地址，然后在 original/modified 中
     * 用 !! 占位符填充跳转偏移量。
     */
    public static List<Map<String, Object>> resolveJmpOffsetRule(ByteBuffer mm, JsonNode ruleDict) {
        List<Map<String, Object>> resDicts = new ArrayList<>();

        // 1. 预处理 targets -> targetAddrs
        JsonNode targetsNode = ruleDict.get("targets");
        List<String> targetFeatures = new ArrayList<>();
        if (targetsNode != null && targetsNode.isArray()) {
            for (JsonNode t : targetsNode) {
                targetFeatures.add(t.asText());
            }
        }

        List<Map<String, Object>> targetResults = SwHexUtils.searchFirstPatternWithMarked(mm, targetFeatures);
        List<Integer> targetAddrs = new ArrayList<>();
        for (Map<String, Object> tr : targetResults) {
            targetAddrs.add((Integer) tr.get("marked_addr"));
        }

        if (targetAddrs.size() != targetFeatures.size()) {
            LOG.warn("[规则jmp_offset] target_features 数量与 target_addrs 数量不一致");
            return Collections.emptyList();
        }

        // 2. 扫描 original/modified
        String original = ruleDict.has("original") ? ruleDict.get("original").asText() : "";
        String modified = ruleDict.has("modified") ? ruleDict.get("modified").asText() : "";
        int leftCut = ruleDict.has("left_cut") ? ruleDict.get("left_cut").asInt() : 0;
        int rightCut = ruleDict.has("right_cut") ? ruleDict.get("right_cut").asInt() : 0;

        List<SwHexUtils.ScanResult> unfilledResults = SwHexUtils.searchPatternDicts(
                mm, original, modified, leftCut, rightCut);
        if (unfilledResults == null || unfilledResults.isEmpty()) {
            return Collections.emptyList();
        }

        // 3. 填充 !! 占位符
        int targetAddrIdx = 0;
        for (SwHexUtils.ScanResult unfilled : unfilledResults) {
            int startAddr = unfilled.offset;
            String origStr = unfilled.original;
            String expandedModified = unfilled.modified;

            String[] tokens = expandedModified.split("\\s+");
            int i = 0;
            boolean hasFailure = false;

            while (i < tokens.length) {
                if (!tokens[i].equals("!!")) {
                    i++;
                    continue;
                }

                // 找到连续 !! 块
                int j = i;
                while (j < tokens.length && tokens[j].equals("!!")) j++;
                int length = j - i;
                int relativePos = i;

                // 连续 !! 长度必须为 4
                if (length != 4) {
                    LOG.warn("[规则jmp_offset] !! 连续长度必须为 4，实际: {}", length);
                    return Collections.emptyList();
                }

                if (targetAddrIdx >= targetAddrs.size()) {
                    LOG.warn("[规则jmp_offset] 所有可用的 target_addr 用完仍有 !! 待填充");
                    return Collections.emptyList();
                }

                Integer targetAddr = targetAddrs.get(targetAddrIdx);
                targetAddrIdx++;

                if (targetAddr == null) {
                    LOG.warn("[规则jmp_offset] 某个目标特征未扫描到匹配串");
                    return Collections.emptyList();
                }

                // 计算跳转偏移: targetAddr - (startAddr + relativePos + 4)
                // 简化版：直接用地址差（暂不实现 PE FOA->VOA 转换）
                int nextInstrAddr = startAddr + relativePos + length;
                int offset = targetAddr - nextInstrAddr;
                String offsetHex = SwHexUtils.intToLittleEndianHex(offset);

                // 替换连续 !!
                String[] replaceParts = offsetHex.split("\\s+");
                if (replaceParts.length != 4) {
                    LOG.warn("[规则jmp_offset] 小端序地址字节长度不为 4");
                    return Collections.emptyList();
                }
                System.arraycopy(replaceParts, 0, tokens, i, 4);
                i = j;
            }

            if (hasFailure) continue;

            String filledModified = String.join(" ", tokens);
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("offset", startAddr);
            entry.put("original", origStr);
            entry.put("modified", filledModified);
            resDicts.add(entry);
        }

        // 4. 补充额外节点
        for (Map<String, Object> res : resDicts) {
            ruleDict.fieldNames().forEachRemaining(key -> {
                if (!Set.of("original", "modified", "left_cut", "right_cut", "targets").contains(key)) {
                    res.put(key, jsonNodeToObject(ruleDict.get(key)));
                }
            });
        }

        return resDicts;
    }

    // ==================== Relation 规则 ====================

    /**
     * 解析 relation 类型规则 — 不扫描文件，直接返回规则字典本身
     * 对应 Python: _resolve_relation_rule (L1166-L1175)
     */
    private static List<Map<String, Object>> resolveRelationRule(JsonNode ruleDict) {
        Map<String, Object> entry = new LinkedHashMap<>();
        ruleDict.fieldNames().forEachRemaining(key -> {
            entry.put(key, jsonNodeToObject(ruleDict.get(key)));
        });
        return Collections.singletonList(entry);
    }

    // ==================== 工具方法 ====================

    /**
     * 将 JsonNode 转换为 Java 对象
     */
    private static Object jsonNodeToObject(JsonNode node) {
        if (node == null || node.isNull()) return null;
        if (node.isTextual()) return node.asText();
        if (node.isInt()) return node.asInt();
        if (node.isLong()) return node.asLong();
        if (node.isDouble()) return node.asDouble();
        if (node.isBoolean()) return node.asBoolean();
        if (node.isArray()) {
            List<Object> list = new ArrayList<>();
            node.forEach(n -> list.add(jsonNodeToObject(n)));
            return list;
        }
        if (node.isObject()) {
            Map<String, Object> map = new LinkedHashMap<>();
            node.fieldNames().forEachRemaining(key -> map.put(key, jsonNodeToObject(node.get(key))));
            return map;
        }
        return node.asText();
    }
}
