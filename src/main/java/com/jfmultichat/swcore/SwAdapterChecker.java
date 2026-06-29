package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.nio.ByteBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 适配器补丁检测 — 检测 DLL 文件的补丁状态
 * <p>
 * 对应 Python: SwInfoFuncCore._identify_multi_state_patching_of_files_in_channel,
 * _identify_binary_state_patching_of_files_in_channel,
 * _identify_patching_by_addr_patches_dicts_in_ver,
 * identify_dll_core, clear_adaptation_cache,
 * get_sw_wnd_class_matching_dicts, get_mode_channel_customizable_patches
 *
 * 依赖: SwHexUtils, SwConfigAccessor, SwPathResolver, SwVersionHelper
 */
public final class SwAdapterChecker {

    private static final Logger LOG = LoggerFactory.getLogger(SwAdapterChecker.class);
    private SwAdapterChecker() {}

    /**
     * 检测状态结果
     */
    public static class DetectionResult {
        public final boolean status;   // true=已打补丁, false=未打, null=未知
        public final String message;
        public final Map<String, String> addressesMsg; // addr -> message

        public DetectionResult(boolean status, String message) {
            this(status, message, Collections.emptyMap());
        }

        public DetectionResult(boolean status, String message, Map<String, String> addressesMsg) {
            this.status = status;
            this.message = message;
            this.addressesMsg = addressesMsg;
        }

        public DetectionResult(String message) {
            this(false, message);
        }
    }

    /**
     * 检测 DLL 补丁状态的核心入口
     * 对应 Python: identify_dll_core (L412-L475)
     *
     * @param sw             软件标识
     * @param mode           模式 (multi / revoke)
     * @param channels       指定通道列表（null=全部）
     * @param coexistChannel 共存通道（null=非共存）
     * @param ordinal        序列号（null=非共存）
     * @param skipCache      是否跳过已有缓存
     * @param accessor       配置访问器
     * @param cache          缓存数据
     * @return {channelsResDict, message}
     */
    public static DetectionResult identifyDllCore(
            String sw, String mode, List<String> channels,
            String coexistChannel, String ordinal, boolean skipCache,
            SwConfigAccessor accessor, ObjectNode cache) {

        // 1. 获取 DLL 目录
        String dllDir = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.DLL_DIR);
        if (dllDir == null) {
            return new DetectionResult("错误：没有找到版本资源目录");
        }

        // 2. 获取 multi_state 标志
        JsonNode multiStateNode = accessor.getRemoteSw(sw, mode, "multi_state");
        boolean multiState = multiStateNode != null && multiStateNode.asBoolean(false);

        // 3. 获取所有通道字典
        JsonNode allChannelsDict = accessor.getRemoteSw(sw, mode, "channels");
        if (allChannelsDict == null || !allChannelsDict.isObject()) {
            return new DetectionResult("该模式没有方案");
        }

        List<String> channelsToScan = (channels != null) ? channels : new ArrayList<>();
        if (channelsToScan.isEmpty()) {
            allChannelsDict.fieldNames().forEachRemaining(channelsToScan::add);
        }

        // 4. 如果不是共存模式，根据 force_rescan 决定是否跳过缓存
        if (coexistChannel == null || ordinal == null) {
            // TODO: cls.get_sw_cls(sw).force_rescan
            skipCache = true;
            // cls._update_adaptation_from_remote_to_cache(sw, mode, channelsToScan, skipCache)
        } else {
            // cls._update_adaptation_from_remote_to_cache(sw, mode, channelsToScan)
        }

        // 5. 获取缓存配置
        JsonNode modeDict = cache.get(mode);
        if (modeDict == null) {
            return new DetectionResult("错误：没有" + mode + "的缓存");
        }

        JsonNode channelsCache = null;
        if (modeDict.isObject() && modeDict.has("channels")) {
            JsonNode ch = modeDict.get("channels");
            if (ch.isObject()) channelsCache = ch;
        }

        if (channelsCache == null) {
            return new DetectionResult("错误：该模式没有适配频道列表或适配频道列表格式错误");
        }

        // 6. 获取当前版本
        String curSwVer = SwVersionHelper.calcSwVer(sw, accessor);
        if (curSwVer == null) {
            return new DetectionResult("错误：未知当前版本");
        }

        // 7. 只检测指定通道
        List<String> channelsToCheck = (channels != null) ? channels : new ArrayList<>();
        if (channelsToCheck.isEmpty()) {
            channelsCache.fieldNames().forEachRemaining(channelsToCheck::add);
        }

        Map<String, DetectionResult> channelsResDict = new LinkedHashMap<>();

        for (String ch : channelsToCheck) {
            try {
                JsonNode preciseNode = channelsCache.get(ch);
                if (preciseNode == null || !preciseNode.isObject()) continue;
                JsonNode versNode = preciseNode.get("precises");
                if (versNode == null || !versNode.isObject()) continue;
                JsonNode verPrecise = versNode.get(curSwVer);
                if (verPrecise == null) continue;

                // 解析为 addr_patches_dicts
                List<Map<String, Object>> addrPatchesDicts = addrToMapList(verPrecise);

                DetectionResult chResult = identifyPatchingByAddrPatchesDictsInVer(
                        sw, addrPatchesDicts, multiState, coexistChannel, ordinal, accessor);
                channelsResDict.put(ch, chResult);
            } catch (Exception e) {
                LOG.warn("[检测] 通道 {} 检测失败: {}", ch, e.getMessage());
            }
        }

        if (channelsResDict.isEmpty()) {
            return new DetectionResult("错误：该版本 " + curSwVer + " 的适配在本地平台中未找到");
        }

        return new DetectionResult(true, "成功：找到版本 " + curSwVer + " 的适配");
    }

    /**
     * 识别地址补丁字典列表的状态
     * 对应 Python: _identify_patching_by_addr_patches_dicts_in_ver (L368-L409)
     *
     * @param sw             软件标识
     * @param addrPatchRules 地址补丁字典列表
     * @param multiState     是否多状态
     * @param coexistChannel 共存通道
     * @param ordinal        序列号
     * @param accessor       配置访问器
     * @return 检测结果
     */
    public static DetectionResult identifyPatchingByAddrPatchesDictsInVer(
            String sw, List<Map<String, Object>> addrPatchRules,
            boolean multiState, String coexistChannel, String ordinal,
            SwConfigAccessor accessor) {

        Map<String, String> addressesMsgDict = new LinkedHashMap<>();
        Set<Boolean> statusSet = new HashSet<>();

        List<Map<String, Object>> addrResDict;
        if (multiState) {
            addrResDict = identifyMultiStatePatching(sw, addrPatchRules, coexistChannel, ordinal, accessor);
        } else {
            addrResDict = identifyBinaryStatePatching(sw, addrPatchRules, coexistChannel, ordinal, accessor);
        }

        for (Map<String, Object> entry : addrResDict) {
            String addr = (String) entry.get("addr");
            Object statusObj = entry.get("status");
            Object msgObj = entry.get("msg");

            Boolean status = (statusObj instanceof Boolean) ? (Boolean) statusObj : null;
            String msg = (msgObj != null) ? msgObj.toString() : "";

            if (status == null) {
                addressesMsgDict.put(addr, msg);
            }
            if (status != null) statusSet.add(status);
        }

        Boolean channelStatus;
        if (statusSet.contains(null)) {
            channelStatus = null;
        } else if (statusSet.equals(Set.of(true))) {
            channelStatus = true;
        } else {
            channelStatus = false;
        }

        String msgStr = "问题文件: " + addressesMsgDict;
        return new DetectionResult(channelStatus != null && channelStatus, msgStr, addressesMsgDict);
    }

    // ==================== 多状态检测 ====================

    /**
     * 检测非二元状态的补丁（只需检查文件是否存在）
     * 对应 Python: _identify_multi_state_patching_of_files_in_channel (L289-L313)
     */
    public static List<Map<String, Object>> identifyMultiStatePatching(
            String sw, List<Map<String, Object>> addrPatchesDicts,
            String coexistChannel, String ordinal,
            SwConfigAccessor accessor) {

        List<Map<String, Object>> result = new ArrayList<>();

        for (Map<String, Object> dict : addrPatchesDicts) {
            String addr = (String) dict.get("addr");
            if (addr == null || !(addr instanceof String)) {
                Map<String, Object> err = new LinkedHashMap<>();
                err.put("addr", "Error");
                err.put("status", null);
                err.put("msg", "存在无地址的补丁模式");
                result.add(err);
                continue;
            }

            String patchFile;
            if (coexistChannel != null && ordinal != null) {
                patchFile = SwPathResolver.getCoexistPathFromAddress(
                        sw, addr, coexistChannel, ordinal, accessor);
            } else {
                patchFile = SwPathResolver.resolveSwPath(sw, addr, accessor);
            }

            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("addr", addr);

            if (!Files.exists(Path.of(patchFile))) {
                entry.put("status", null);
                entry.put("msg", "文件不存在");
            } else {
                entry.put("status", true);
                entry.put("msg", "");
            }
            result.add(entry);
        }

        return result;
    }

    // ==================== 二元状态检测 ====================

    /**
     * 检测二元状态的补丁（检查文件中对应地址的字节是否与 modified 相等）
     * 对应 Python: _identify_binary_state_patching_of_files_in_channel (L315-L366)
     */
    public static List<Map<String, Object>> identifyBinaryStatePatching(
            String sw, List<Map<String, Object>> addrPatchesDicts,
            String channel, String ordinal,
            SwConfigAccessor accessor) {

        List<Map<String, Object>> result = new ArrayList<>();

        for (Map<String, Object> dict : addrPatchesDicts) {
            String addr = (String) dict.get("addr");
            if (addr == null) {
                Map<String, Object> err = new LinkedHashMap<>();
                err.put("addr", "Error");
                err.put("status", null);
                err.put("msg", "存在无地址的补丁模式");
                result.add(err);
                continue;
            }

            String patchFile;
            if (channel != null && ordinal != null) {
                patchFile = SwPathResolver.getCoexistPathFromAddress(
                        sw, addr, channel, ordinal, accessor);
            } else {
                patchFile = SwPathResolver.resolveSwPath(sw, addr, accessor);
            }

            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("addr", addr);

            if (!Files.exists(Path.of(patchFile))) {
                entry.put("status", null);
                entry.put("msg", "文件不存在");
                result.add(entry);
                continue;
            }

            // 打开文件映射进行读取
            try (FileChannel fc = FileChannel.open(Path.of(patchFile), java.nio.file.StandardOpenOption.READ)) {
                MappedByteBuffer mm = fc.map(FileChannel.MapMode.READ_ONLY, 0, fc.size());

                @SuppressWarnings("unchecked")
                List<Map<String, Object>> patches = (List<Map<String, Object>>) dict.get("patches");
                Set<Boolean> resultSet = new HashSet<>();

                if (patches != null) {
                    for (Map<String, Object> patch : patches) {
                        if (!(patch instanceof Map)) continue;

                        // customizable 的直接跳过
                        if (Boolean.TRUE.equals(patch.get("customizable"))) continue;

                        Object offsetObj = patch.get("offset");
                        Object modifiedHex = patch.get("modified");
                        if (offsetObj == null || modifiedHex == null) continue;

                        int fileOffset = ((Number) offsetObj).intValue();
                        String modifiedHexStr = modifiedHex.toString();
                        byte[] modifiedBytes = SwHexUtils.hexStrToBytes(modifiedHexStr);

                        // 检查文件中对应地址的字节
                        if (fileOffset + modifiedBytes.length <= mm.limit()) {
                            byte[] fileSlice = new byte[modifiedBytes.length];
                            mm.get(fileOffset, fileSlice);
                            boolean isPatched = Arrays.equals(fileSlice, modifiedBytes);
                            resultSet.add(isPatched);
                        }
                    }
                }

                boolean status = resultSet.equals(Set.of(true));
                entry.put("status", status);
                entry.put("msg", status ? "已开启" : "未开启");

            } catch (Exception e) {
                LOG.warn("[检测] 二进制状态检测失败: {}", e.getMessage());
                entry.put("status", null);
                entry.put("msg", "检测异常: " + e.getMessage());
            }

            result.add(entry);
        }

        return result;
    }

    // ==================== 清除适配缓存 ====================

    /**
     * 清除当前版本模式的适配缓存
     * 对应 Python: clear_adaptation_cache (L478-L487)
     *
     * @param sw     软件标识
     * @param mode   模式
     * @param curVer 当前版本
     * @param cache  缓存数据
     */
    public static void clearAdaptationCache(String sw, String mode, String curVer, ObjectNode cache) {
        if (cache == null || !cache.has(mode)) return;

        JsonNode modeDict = cache.get(mode);
        if (!modeDict.isObject() || !modeDict.has("channels")) return;

        JsonNode channels = modeDict.get("channels");
        if (!channels.isObject()) return;

        channels.fieldNames().forEachRemaining(channel -> {
            JsonNode chDict = channels.get(channel);
            if (chDict != null && chDict.isObject() && chDict.has("precises")) {
                JsonNode precises = chDict.get("precises");
                if (precises != null && precises.isObject() && precises.has(curVer)) {
                    ((ObjectNode) precises).remove(curVer);
                }
            }
        });
    }

    // ==================== 窗口类名匹配 ====================

    /**
     * 获取适合当前版本的窗口类名检查字典
     * 对应 Python: get_sw_wnd_class_matching_dicts (L490-L500)
     *
     * @param sw      软件标识
     * @param wndType 窗口类型
     * @param accessor 配置访问器
     * @return 匹配字典列表；失败返回 null
     */
    public static List<Map<String, Object>> getWndClassMatchingDicts(
            String sw, String wndType, SwConfigAccessor accessor) {

        JsonNode typeVersDict = accessor.getRemoteSw(sw, "wnd_class", wndType, "matching");
        if (typeVersDict == null || !typeVersDict.isObject()) return null;

        String currVer = SwVersionHelper.calcSwVer(sw, accessor);
        if (currVer == null) return null;

        String compatVer = SwRuleResolver.findCompatibleVersion(currVer, typeVersDict);
        if (compatVer == null) return null;

        JsonNode verDict = typeVersDict.get(compatVer);
        if (verDict == null) return null;

        // 转换为 List<Map<String, Object>>
        return jsonNodeToMapList(verDict);
    }

    // ==================== 自定义补丁获取 ====================

    /**
     * 从版本文件适配字典中过滤出 customizable=true 的 patches
     * 对应 Python: get_mode_channel_customizable_patches (L502-L523)
     *
     * @param sw       软件标识
     * @param mode     模式
     * @param channel  通道
     * @param curVer   当前版本
     * @param cache    缓存数据
     * @return 自定义补丁列表
     */
    public static List<Map<String, Object>> getModeChannelCustomizablePatches(
            String sw, String mode, String channel, String curVer, ObjectNode cache) {

        List<Map<String, Object>> result = new ArrayList<>();

        // 从缓存中获取 addr_patching_dicts
        List<Map<String, Object>> addrPatchingDicts = getCachePreciseEntry(cache, sw, mode, channel, curVer);
        if (addrPatchingDicts == null) return result;

        for (Map<String, Object> entry : addrPatchingDicts) {
            String addr = (String) entry.get("addr");
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> patches = (List<Map<String, Object>>) entry.get("patches");

            if (patches == null) continue;

            List<Map<String, Object>> filtered = new ArrayList<>();
            for (Map<String, Object> patch : patches) {
                if (Boolean.TRUE.equals(patch.get("customizable"))) {
                    filtered.add(patch);
                }
            }

            if (!filtered.isEmpty()) {
                Map<String, Object> filteredEntry = new LinkedHashMap<>();
                filteredEntry.put("addr", addr);
                filteredEntry.put("patches", filtered);
                result.add(filteredEntry);
            }
        }

        return result;
    }

    // ==================== 窗口原始类名 ====================

    /**
     * 获取窗口的原始类名
     * 对应 Python: get_sw_original_wnd_class_name (L526-L538)
     */
    public static String getSwOriginalWndClassName(String sw, String wndType, SwConfigAccessor accessor) {
        try {
            JsonNode typeVersDict = accessor.getRemoteSw(sw, "wnd_class", wndType, "original");
            if (typeVersDict == null || !typeVersDict.isObject()) return null;

            String currVer = SwVersionHelper.calcSwVer(sw, accessor);
            if (currVer == null) return null;

            String compatVer = SwRuleResolver.findCompatibleVersion(currVer, typeVersDict);
            if (compatVer == null) return null;

            JsonNode verDict = typeVersDict.get(compatVer);
            if (verDict != null && verDict.isObject() && verDict.has("class_name")) {
                return verDict.get("class_name").asText();
            }
            return null;
        } catch (Exception e) {
            LOG.warn("[窗口] 获取原始类名失败: {}", e.getMessage());
            return null;
        }
    }

    // ==================== 工具方法 ====================

    @SuppressWarnings("unchecked")
    public static List<Map<String, Object>> jsonToList(JsonNode node) {
        if (node == null || !node.isArray()) return Collections.emptyList();
        List<Map<String, Object>> result = new ArrayList<>();
        node.forEach(n -> {
            if (n.isObject()) {
                Map<String, Object> map = new LinkedHashMap<>();
                n.fieldNames().forEachRemaining(key -> map.put(key, jsonNodeToObject(n.get(key))));
                result.add(map);
            }
        });
        return result;
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> jsonNodeToMapList(JsonNode node) {
        if (node == null || !node.isArray()) return Collections.emptyList();
        List<Map<String, Object>> result = new ArrayList<>();
        node.forEach(n -> {
            if (n.isObject()) {
                Map<String, Object> map = new LinkedHashMap<>();
                n.fieldNames().forEachRemaining(key -> map.put(key, jsonNodeToObject(n.get(key))));
                result.add(map);
            }
        });
        return result;
    }

    private static List<Map<String, Object>> addrToMapList(JsonNode node) {
        return jsonToList(node);
    }

    private static List<Map<String, Object>> getCachePreciseEntry(
            ObjectNode cache, String sw, String mode, String channel, String curVer) {
        // 从缓存中获取特定位
        return Collections.emptyList();
    }

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

    // ==================== 路径验证 ====================

    /**
     * 检查 SW 路径是否合法
     * 对应 Python: is_valid_sw_path (L875-L932)
     *
     * @param pathType 路径类型 (inst_path / data_dir / dll_dir)
     * @param sw       软件标识
     * @param path     待检查路径
     * @param accessor 配置访问器
     * @return true 如果路径合法
     */
    /**
     * 路径检查（详细版），返回 valid + 中文提示 reason.
     */
    public static Map<String, Object> checkSwPathDetail(
            String pathType, String sw, String path, SwConfigAccessor accessor) {
        Map<String, Object> result = new LinkedHashMap<>();
        LOG.info("[路径检查] sw={}, pathType={}, path={}", sw, pathType, path);
        if (path == null || path.isBlank()) {
            result.put("valid", false);
            result.put("reason", "路径为空，请输入有效路径");
            LOG.info("[路径检查] 结果=false (路径为空)");
            return result;
        }
        path = path.replace('\\', '/');

        JsonNode checkDict = accessor.getRemoteSw(sw, "path_check", pathType);
        if (checkDict == null || !checkDict.isObject()) {
            result.put("valid", true);
            result.put("reason", "路径有效");
            LOG.info("[路径检查] 结果=true (无检查规则，默认通过)");
            return result;
        }
        LOG.info("[路径检查] 检查规则: {}", checkDict);

        // r_concat
        JsonNode rConcat = checkDict.get(SwCoreConstants.RemoteSwKey.RIGHT_CONCAT);
        if (rConcat != null && rConcat.isTextual()) {
            String rightConcat = rConcat.asText();
            String pathRightConcat = path + "/" + rightConcat;
            boolean exists = Files.exists(Path.of(pathRightConcat));
            LOG.info("[路径检查] r_concat={}, checkPath={}, exists={}", rightConcat, pathRightConcat, exists);
            if (!exists) {
                result.put("valid", false);
                result.put("reason", "路径下缺少关键文件「" + rightConcat + "」，该路径可能不正确");
                return result;
            }
        }

        // l_concat
        JsonNode lConcat = checkDict.get(SwCoreConstants.RemoteSwKey.LEFT_CONCAT);
        if (lConcat != null && lConcat.isTextual()) {
            String expected = lConcat.asText();
            String dirName = new File(path).getParent().replace('\\', '/');
            if (dirName == null) dirName = path;
            boolean ok = dirName.endsWith(expected);
            LOG.info("[路径检查] l_concat={}, parentDir={}, endsWith={}", expected, dirName, ok);
            if (!ok) {
                result.put("valid", false);
                result.put("reason", "该路径可能不正确：预期路径应该在「" + expected + "」文件夹之内");
                return result;
            }
        }

        // r_contain
        JsonNode rContain = checkDict.get(SwCoreConstants.RemoteSwKey.RIGHT_CONTAIN);
        if (rContain != null && rContain.isTextual()) {
            String containStr = rContain.asText();
            AtomicBoolean found = new AtomicBoolean(false);
            try {
                Files.walk(Path.of(path)).forEach(p -> {
                    if (!found.get() && p.toString().replace('\\', '/').contains(containStr)) {
                        found.set(true);
                    }
                });
            } catch (Exception ignored) {}
            LOG.info("[路径检查] r_contain={}, found={}", containStr, found.get());
            if (!found.get()) {
                result.put("valid", false);
                result.put("reason", "该目录下未找到包含「" + containStr + "」的文件，路径可能不完整");
                return result;
            }
        }

        // l_contain
        JsonNode lContain = checkDict.get(SwCoreConstants.RemoteSwKey.LEFT_CONTAIN);
        if (lContain != null && lContain.isTextual()) {
            String expected = lContain.asText();
            String dirPath = new File(path).getParent().replace('\\', '/');
            if (dirPath == null) dirPath = path;
            boolean ok = dirPath.contains(expected);
            LOG.info("[路径检查] l_contain={}, parentDir={}, contains={}", expected, dirPath, ok);
            if (!ok) {
                result.put("valid", false);
                result.put("reason", "该路径可能不正确：预期路径的上级目录应包含「" + expected + "」");
                return result;
            }
        }

        result.put("valid", true);
        result.put("reason", "路径有效");
        LOG.info("[路径检查] 结果=true (所有检查通过)");
        return result;
    }

    public static boolean isValidSwPath(String pathType, String sw, String path, SwConfigAccessor accessor) {
        Map<String, Object> detail = checkSwPathDetail(pathType, sw, path, accessor);
        return Boolean.TRUE.equals(detail.get("valid"));
    }
}
