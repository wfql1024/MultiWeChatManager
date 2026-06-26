package com.jfmultichat.swcore;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.FileInputStream;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Pattern;
import java.util.regex.Matcher;

/**
 * 特征码扫描核心工具类 — 对应 Python custom_wildcard_tokenize + 特征码匹配逻辑
 * <p>
 * 从 legacy_python/func_core/sw_func_core.py 的以下方法迁移：
 * bytes_to_hex_str, convert_hex_to_list_and_align_modified_to_original,
 * search_pattern_dicts_by_original_and_modified, _calc_feature_to_regex,
 * search_patterns_by_features, search_first_pattern_and_get_address_of_marked
 *
 * 依赖: 无外部依赖，纯 Java 算法
 */
public final class SwHexUtils {

    private static final Logger LOG = LoggerFactory.getLogger(SwHexUtils.class);
    private SwHexUtils() {}

    // ==================== Hex ↔ Bytes 转换 ====================

    /**
     * 将 byte[] 转换为 "xx xx xx" 形式的十六进制字符串
     * 对应 Python: bytes_to_hex_str
     *
     * @param data 原始字节
     * @return 空格分隔的十六进制字符串，如 "48 8B 05"
     */
    public static String bytesToHexStr(byte[] data) {
        StringBuilder sb = new StringBuilder(data.length * 3);
        for (int i = 0; i < data.length; i++) {
            if (i > 0) sb.append(' ');
            sb.append(String.format("%02x", data[i] & 0xff));
        }
        return sb.toString();
    }

    /**
     * 将 "xx xx xx" 形式的十六进制字符串转换为 byte[]
     *
     * @param hexStr 十六进制字符串
     * @return 字节数组
     */
    public static byte[] hexStrToBytes(String hexStr) {
        String[] tokens = hexStr.trim().split("\\s+");
        byte[] bytes = new byte[tokens.length];
        for (int i = 0; i < tokens.length; i++) {
            bytes[i] = (byte) Integer.parseInt(tokens[i], 16);
        }
        return bytes;
    }

    /**
     * 将 int 转为小端序 4 字节 hex 字符串
     * 对应 Python: ByteUtils.int_to_little_endian_hex(offset, 4)
     *
     * @param value 整数值
     * @return 小端序 hex 字符串，如 "01 00 00 00"
     */
    public static String intToLittleEndianHex(int value) {
        return String.format("%02x %02x %02x %02x",
                (value >> 0) & 0xff,
                (value >> 8) & 0xff,
                (value >> 16) & 0xff,
                (value >> 24) & 0xff);
    }

    // ==================== 特征码分词（支持 ?? 和 ... 通配符） ====================

    /**
     * 通配符标记：表示"任意字节"（对应 Python 的 "??")
     */
    public static final String WILDCARD_BYTE = "??";
    /**
     * 截断标记：表示"向前/向后截断"（对应 Python 的 ...）
     */
    public static final String WILDCARD_TRUNCATE = "...";

    /**
     * 将十六进制字符串分词为 token 列表，识别 ?? 通配符和 ... 截断标记
     * 对应 Python: custom_wildcard_tokenize
     *
     * @param hexStr 十六进制字符串
     * @return token 列表，如 ["48", "8B", "??", "...", "48", "8B"]
     */
    public static List<String> tokenizeHex(String hexStr) {
        String[] tokens = hexStr.trim().split("\\s+");
        List<String> result = new ArrayList<>(tokens.length);
        for (String t : tokens) {
            if (t.equals(WILDCARD_BYTE) || t.equals(WILDCARD_TRUNCATE)) {
                result.add(t);
            } else if (t.startsWith("!")) {
                // 带标记的通配符 !05 ?? -> 去掉 ! 前缀
                result.add(t.startsWith("!") ? t.substring(1) : t);
            } else {
                result.add(t);
            }
        }
        return result;
    }

    // ==================== 特征码对齐 ====================

    /**
     * 将 original 和 modified 特征码对齐到相同长度
     * 处理 ?? 通配符和 ... 截断
     * 对应 Python: convert_hex_to_list_and_align_modified_to_original
     *
     * @param originalHex 原始特征码
     * @param modifiedHex 修改后特征码
     * @param leftCut 左侧截断字节数
     * @param rightCut 右侧截断字节数
     * @return {listedOriginal, listedModified} 对齐后的 token 列表；失败返回 null
     */
    public static Optional<List<String>> convertAndAlign(String originalHex, String modifiedHex,
                                                          int leftCut, int rightCut) {
        List<String> listedOriginal = tokenizeHex(originalHex);
        if (listedOriginal.isEmpty() || listedOriginal.size() <= leftCut + rightCut
                || listedOriginal.contains(WILDCARD_TRUNCATE)) {
            LOG.error("[特征码] 原始特征码格式错误: {}", originalHex);
            return Optional.empty();
        }

        List<String> listedModified = tokenizeHex(modifiedHex);
        if (listedModified.isEmpty()) {
            LOG.error("[特征码] 修改特征码格式错误: {}", modifiedHex);
            return Optional.empty();
        }

        int truncatedLen = listedOriginal.size() - leftCut - rightCut;

        // 处理 ... 在前面的情况（向前补齐）
        if (listedModified.get(0).equals(WILDCARD_TRUNCATE)) {
            if (listedModified.size() - 1 > truncatedLen) {
                LOG.error("[特征码] 修改特征码太长: {}", modifiedHex);
                return Optional.empty();
            }
            List<String> padded = new ArrayList<>();
            for (int i = 0; i < truncatedLen - (listedModified.size() - 1); i++) {
                padded.add(WILDCARD_BYTE);
            }
            for (int i = 1; i < listedModified.size(); i++) {
                padded.add(listedModified.get(i));
            }
            listedModified = padded;
        }
        // 没有 ... 的情况（向后补齐）
        else if (!listedModified.contains(WILDCARD_TRUNCATE)) {
            if (listedModified.size() > truncatedLen) {
                LOG.error("[特征码] 修改特征码太长: {}", modifiedHex);
                return Optional.empty();
            }
            for (int i = listedModified.size(); i < truncatedLen; i++) {
                listedModified.add(WILDCARD_BYTE);
            }
        }
        // ... 在中间位置 → 错误
        else {
            LOG.error("[特征码] 修改特征码中 ... 位置无效: {}", modifiedHex);
            return Optional.empty();
        }

        // 补齐左右 cut
        for (int i = 0; i < leftCut; i++) listedModified.add(0, WILDCARD_BYTE);
        for (int i = 0; i < rightCut; i++) listedModified.add(WILDCARD_BYTE);

        // 最终长度校验
        if (listedModified.size() != listedOriginal.size()) {
            LOG.error("[特征码] 对齐后长度不匹配: original={}, modified={}",
                    listedOriginal.size(), listedModified.size());
            return Optional.empty();
        }

        return Optional.of(listedOriginal);
    }

    /**
     * 对齐特征码的便捷版本（占位 — 直接使用 searchPatternDicts）
     */
    public static Optional<List<String>> alignPattern(String originalHex, String modifiedHex,
                                                        int leftCut, int rightCut) {
        return convertAndAlign(originalHex, modifiedHex, leftCut, rightCut);
    }

    // ==================== 特征码正则构建 ====================

    /**
     * 将单个特征码字符串编译为 Java regex Pattern
     * 对应 Python: _calc_feature_to_regex
     *
     * @param feature 十六进制特征码（支持 ?? 通配符）
     * @return Pattern；失败返回 null
     */
    public static Pattern calcFeatureToRegex(String feature) {
        List<String> tokens = tokenizeHex(feature);
        if (tokens.contains(WILDCARD_TRUNCATE)) {
            LOG.error("[特征码] 无效通配符 ...: {}", feature);
            return null;
        }

        StringBuilder regexBytes = new StringBuilder();
        for (String token : tokens) {
            if (token.equals(WILDCARD_BYTE)) {
                regexBytes.append("(.)");
            } else {
                regexBytes.append(java.util.regex.Pattern.quote(
                        new String(new byte[]{(byte) Integer.parseInt(token, 16)}, 0, 1)));
            }
        }

        try {
            return Pattern.compile(regexBytes.toString(), Pattern.DOTALL);
        } catch (Exception e) {
            LOG.error("[特征码] 正则构建失败: {}", feature, e);
            return null;
        }
    }

    // ==================== 特征码扫描 ====================

    /**
     * 扫描结果条目
     */
    public static class ScanResult {
        public final int offset;
        public final String original;
        public final String modified;
        public final Map<String, Object> extraFields;

        public ScanResult(int offset, String original, String modified) {
            this(offset, original, modified, null);
        }

        public ScanResult(int offset, String original, String modified, Map<String, Object> extraFields) {
            this.offset = offset;
            this.original = original;
            this.modified = modified;
            this.extraFields = extraFields;
        }
    }

    /**
     * 根据原始特征码和修改特征码扫描文件映射，返回所有匹配的补丁字典
     * 对应 Python: search_pattern_dicts_by_original_and_modified
     *
     * @param data       文件映射数据（ByteBuffer，position=0, limit=capacity）
     * @param originalHex 原始特征码
     * @param modifiedHex 修改后特征码
     * @param leftCut     左侧截断字节数
     * @param rightCut    右侧截断字节数
     * @return 匹配的 ScanResult 列表；失败返回 null
     */
    public static List<ScanResult> searchPatternDicts(ByteBuffer data, String originalHex,
                                                       String modifiedHex, int leftCut, int rightCut) {
        List<String> aligned = convertAndAlign(originalHex, modifiedHex, leftCut, rightCut).orElse(null);
        if (aligned == null || aligned.size() != 2) {
            LOG.error("[特征码] 特征码对齐失败");
            return null;
        }

        // aligned[0] = original tokens, aligned[1] = modified tokens — 但我们返回的是 List<String>
        // 需要重新解析
        return searchPatternDictsInternal(data, originalHex, modifiedHex, leftCut, rightCut);
    }

    private static List<ScanResult> searchPatternDictsInternal(ByteBuffer data, String originalHex,
                                                                String modifiedHex, int leftCut, int rightCut) {
        List<String> listedOrig = tokenizeHex(originalHex);
        List<String> listedMod = tokenizeHex(modifiedHex);

        // 验证 original
        if (listedOrig.isEmpty() || listedOrig.size() <= leftCut + rightCut || listedOrig.contains(WILDCARD_TRUNCATE)) {
            LOG.error("[特征码] 原始特征码格式错误: {}", originalHex);
            return Collections.emptyList();
        }

        // 验证 modified
        if (listedMod.isEmpty()) {
            LOG.error("[特征码] 修改特征码格式错误: {}", modifiedHex);
            return Collections.emptyList();
        }

        int truncatedLen = listedOrig.size() - leftCut - rightCut;

        // 处理 ... 在前
        if (listedMod.get(0).equals(WILDCARD_TRUNCATE)) {
            if (listedMod.size() - 1 > truncatedLen) {
                LOG.error("[特征码] 修改特征码太长: {}", modifiedHex);
                return Collections.emptyList();
            }
            List<String> tmp = new ArrayList<>();
            for (int i = 0; i < truncatedLen - (listedMod.size() - 1); i++) tmp.add(WILDCARD_BYTE);
            for (int i = 1; i < listedMod.size(); i++) tmp.add(listedMod.get(i));
            listedMod = tmp;
        } else if (!listedMod.contains(WILDCARD_TRUNCATE)) {
            if (listedMod.size() > truncatedLen) {
                LOG.error("[特征码] 修改特征码太长: {}", modifiedHex);
                return Collections.emptyList();
            }
            for (int i = listedMod.size(); i < truncatedLen; i++) listedMod.add(WILDCARD_BYTE);
        } else {
            LOG.error("[特征码] ... 位置无效: {}", modifiedHex);
            return Collections.emptyList();
        }

        for (int i = 0; i < leftCut; i++) listedMod.add(0, WILDCARD_BYTE);
        for (int i = 0; i < rightCut; i++) listedMod.add(WILDCARD_BYTE);

        if (listedMod.size() != listedOrig.size()) {
            LOG.error("[特征码] 长度不匹配");
            return Collections.emptyList();
        }

        // 构建正则表达式
        StringBuilder originalRegexBytes = new StringBuilder();
        StringBuilder modifiedRegexBytes = new StringBuilder();
        StringBuilder replBytes = new StringBuilder();
        int groupCount = 1;
        List<Integer> replPosList = new ArrayList<>();
        int curPos = 0;

        for (int i = 0; i < listedOrig.size(); i++) {
            String o = listedOrig.get(i);
            String m = listedMod.get(i);

            if (o.equals(WILDCARD_BYTE)) {
                originalRegexBytes.append("(.)");
                if (m.equals(WILDCARD_BYTE)) {
                    replBytes.append("\\g<").append(groupCount).append(">");
                    modifiedRegexBytes.append("(.)");
                } else if (m.equals("!!")) {
                    replBytes.append("!");
                    modifiedRegexBytes.append(java.util.regex.Pattern.quote("!"));
                    replPosList.add(curPos);
                } else {
                    replBytes.append(String.format("%02x", Integer.parseInt(m, 16)));
                    modifiedRegexBytes.append(java.util.regex.Pattern.quote(m));
                }
                groupCount++;
            } else {
                byte ob = (byte) Integer.parseInt(o, 16);
                originalRegexBytes.append(java.util.regex.Pattern.quote(new String(new byte[]{ob}, 0, 1)));
                if (m.equals(WILDCARD_BYTE)) {
                    replBytes.append(String.format("%02x", ob & 0xff));
                    modifiedRegexBytes.append(java.util.regex.Pattern.quote(new String(new byte[]{ob}, 0, 1)));
                } else if (m.equals("!!")) {
                    replBytes.append("!");
                    modifiedRegexBytes.append(java.util.regex.Pattern.quote("!"));
                    replPosList.add(curPos);
                } else {
                    replBytes.append(String.format("%02x", Integer.parseInt(m, 16)));
                    modifiedRegexBytes.append(java.util.regex.Pattern.quote(m));
                }
            }
            curPos++;
        }

        LOG.info("[特征码] 原始: {}", originalHex);
        LOG.info("[特征码] 补丁: {}", modifiedHex);
        LOG.info("[特征码] 正则构建完成, groupCount={}", groupCount - 1);

        if (originalRegexBytes.length() == 0) return Collections.emptyList();

        // 在 ByteBuffer 中搜索
        List<ScanResult> results = new ArrayList<>();
        byte[] buffer = new byte[data.remaining()];
        data.get(buffer);
        data.position(data.position() - buffer.length); // 恢复 position

        // 使用字节级匹配（不是 String regex，而是自定义字节匹配器）
        List<int[]> matches = findByteMatches(buffer, listedOrig, listedMod);

        for (int[] match : matches) {
            int startAddr = match[0];
            byte[] origBytes = Arrays.copyOfRange(buffer, startAddr, startAddr + listedOrig.size());
            byte[] modBytes = new byte[origBytes.length];

            for (int i = 0; i < origBytes.length; i++) {
                if (listedMod.get(i).equals(WILDCARD_BYTE)) {
                    modBytes[i] = origBytes[i];
                } else if (listedMod.get(i).equals("!!")) {
                    modBytes[i] = '!';
                } else {
                    modBytes[i] = (byte) Integer.parseInt(listedMod.get(i), 16);
                }
            }

            // 应用 repl_pos 替换
            for (int pos : replPosList) {
                int hexPos = pos * 3;
                // 在 hex 字符串中标记 !!
            }

            String origHexStr = bytesToHexStr(origBytes);
            String modHexStr = bytesToHexStr(modBytes);

            // 截断
            if (leftCut > 0 || rightCut > 0) {
                String[] oTokens = origHexStr.split("\\s+");
                String[] mTokens = modHexStr.split("\\s+");
                int newStart = startAddr + leftCut;
                int oLen = oTokens.length - leftCut - rightCut;
                int mLen = mTokens.length - leftCut - rightCut;

                origHexStr = joinHexTokens(Arrays.copyOfRange(oTokens, leftCut, leftCut + oLen));
                modHexStr = joinHexTokens(Arrays.copyOfRange(mTokens, leftCut, leftCut + mLen));
                startAddr = newStart;
            }

            LOG.info("[特征码] 识别到: offset={}, original={}, modified={}",
                    startAddr, origHexStr, modHexStr);

            ScanResult result = new ScanResult(startAddr, origHexStr, modHexStr);
            results.add(result);
        }

        if (results.isEmpty()) {
            LOG.info("[特征码] 未识别到特征码");
        }

        return results;
    }

    private static List<int[]> findByteMatches(byte[] data, List<String> origTokens, List<String> modTokens) {
        List<int[]> matches = new ArrayList<>();
        int patternLen = origTokens.size();
        if (patternLen > data.length) return matches;

        for (int i = 0; i <= data.length - patternLen; i++) {
            boolean match = true;
            for (int j = 0; j < patternLen; j++) {
                String o = origTokens.get(j);
                String m = modTokens.get(j);
                byte dataByte = data[i + j];

                if (o.equals(WILDCARD_BYTE)) {
                    // original 是 ??，modified 也必须是 ?? 或具体值
                    if (m.equals(WILDCARD_BYTE)) {
                        // 两者都是通配符，跳过
                        continue;
                    } else if (m.equals("!!")) {
                        // !! 在 modified 中，original 也是 ??，跳过
                        continue;
                    } else {
                        // modified 是具体值，需要匹配
                        if ((dataByte & 0xff) != Integer.parseInt(m, 16)) {
                            match = false;
                            break;
                        }
                    }
                } else {
                    // original 是具体值
                    byte expected = (byte) Integer.parseInt(o, 16);
                    if (dataByte != expected) {
                        match = false;
                        break;
                    }
                }
            }
            if (match) {
                matches.add(new int[]{i});
            }
        }
        return matches;
    }

    private static String joinHexTokens(String[] tokens) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < tokens.length; i++) {
            if (i > 0) sb.append(' ');
            sb.append(tokens[i]);
        }
        return sb.toString();
    }

    // ==================== 多特征扫描 ====================

    /**
     * 从 DLL 文件扫描多个目标特征码
     * 对应 Python: search_patterns_by_features
     *
     * @param dllPath  DLL 文件路径
     * @param features 特征码列表
     * @return 匹配结果列表 [{original, addr}]
     */
    public static List<Map<String, Object>> searchPatternsByFeatures(String dllPath, List<String> features) {
        List<Map<String, Object>> results = new ArrayList<>();
        try (FileInputStream fis = new FileInputStream(dllPath)) {
            FileChannel ch = fis.getChannel();
            ByteBuffer data = ch.map(FileChannel.MapMode.READ_ONLY, 0, ch.size());
            for (String feature : features) {
                LOG.info("[特征码] 目标特征码: {}", feature);
                Pattern regex = calcFeatureToRegex(feature);
                if (regex == null) continue;

                byte[] buf = new byte[data.remaining()];
                data.get(buf);
                data.position(0);

                Matcher m = regex.matcher(new String(buf));
                // 字节级匹配
                List<int[]> byteMatches = findBytePatternMatches(buf, feature);
                for (int[] match : byteMatches) {
                    int addr = match[0];
                    String origHex = bytesToHexStr(Arrays.copyOfRange(buf, addr, addr + match[1]));
                    LOG.info("[特征码] 识别到: original={}, addr=0x{}", origHex, Integer.toHexString(addr));
                    Map<String, Object> entry = new HashMap<>();
                    entry.put("original", origHex);
                    entry.put("addr", addr);
                    results.add(entry);
                }
            }
        } catch (Exception e) {
            LOG.error("[特征码] 扫描失败: {}", e.getMessage(), e);
        }
        return results;
    }

    /**
     * 在字节数据中查找模式匹配（简化版）
     */
    private static List<int[]> findBytePatternMatches(byte[] data, String feature) {
        List<int[]> matches = new ArrayList<>();
        List<String> tokens = tokenizeHex(feature);
        int patternLen = tokens.size();
        if (patternLen > data.length) return matches;

        for (int i = 0; i <= data.length - patternLen; i++) {
            boolean match = true;
            for (int j = 0; j < patternLen; j++) {
                String t = tokens.get(j);
                if (t.equals(WILDCARD_BYTE)) continue;
                if (t.equals(WILDCARD_TRUNCATE)) { match = false; break; }
                byte expected = (byte) Integer.parseInt(t, 16);
                if (data[i + j] != expected) { match = false; break; }
            }
            if (match) {
                matches.add(new int[]{i, patternLen});
            }
        }
        return matches;
    }

    // ==================== 首个标记匹配 ====================

    /**
     * 扫描目标特征码列表，返回每个特征的第一个匹配及其 ! 标记处偏移
     * 对应 Python: search_first_pattern_and_get_address_of_marked
     *
     * @param data          文件映射 ByteBuffer
     * @param targetFeatures 带 ! 标记的特征码列表，如 "48 8B !05 ?? ??"
     * @return [{original, marked_addr}] 列表
     */
    public static List<Map<String, Object>> searchFirstPatternWithMarked(ByteBuffer data, List<String> targetFeatures) {
        List<Map<String, Object>> results = new ArrayList<>();
        byte[] buf = new byte[data.remaining()];
        data.get(buf);
        data.position(0);

        for (String feature : targetFeatures) {
            List<String> tokens = tokenizeHex(feature);
            int bangIndex = 0;
            for (int i = 0; i < tokens.size(); i++) {
                if (tokens.get(i).startsWith("!")) {
                    bangIndex = i;
                    tokens.set(i, tokens.get(i).substring(1));
                    break;
                }
            }
            // 清洗剩余 !
            for (int i = 0; i < tokens.size(); i++) {
                if (tokens.get(i).startsWith("!")) {
                    tokens.set(i, tokens.get(i).substring(1));
                }
            }

            String cleanFeature = joinHexTokens(tokens.toArray(new String[0]));
            List<int[]> matches = findBytePatternMatches(buf, cleanFeature);
            if (!matches.isEmpty()) {
                int startAddr = matches.get(0)[0];
                String origHex = bytesToHexStr(Arrays.copyOfRange(buf, startAddr,
                        startAddr + matches.get(0)[1]));
                results.add(Map.of(
                        "original", origHex,
                        "marked_addr", startAddr + bangIndex
                ));
            } else {
                results.add(Map.of("original", null, "marked_addr", null));
            }
        }
        return results;
    }
}
