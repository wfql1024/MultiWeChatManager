package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * 总入口 Facade — 组合所有子模块，提供统一的 SW 信息操作接口
 * <p>
 * 对应 Python: SwInfoFuncCore (L50-L2061) 的主类入口
 * <p>
 * 这是所有子模块的统一门面，前端/JsBridge 通过此类访问所有 SW 操作能力。
 * <p>
 * 使用方式:
 * <pre>
 *   SwConfigAccessor accessor = new SwConfigAccessor(myProvider);
 *   SwNativeOps nativeOps = new SwNativeOps(); // 需 JNA
 *   SwPathDetective detective = new SwPathDetective(nativeOps);
 *   SwInfoFuncCore core = new SwInfoFuncCore(accessor, nativeOps, detective);
 * </pre>
 *
 * 依赖: 所有其他 swcore 模块
 */
public final class SwInfoFuncCore {

    private static final Logger LOG = LoggerFactory.getLogger(SwInfoFuncCore.class);
    private SwInfoFuncCore() {
        throw new UnsupportedOperationException("SwInfoFuncCore requires a Provider");
    }

    private final SwConfigAccessor accessor;
    private final SwNativeOps nativeOps;
    private final SwPathDetective pathDetective;
    private final SwAccountOps.AccountOpsProvider accountOps;

    // ==================== 构造函数 ====================

    /**
     * 创建 SwInfoFuncCore 实例
     *
     * @param accessor    配置访问器
     * @param nativeOps   原生操作器（可为 null，部分功能不需要 JNA）
     * @param pathDetective 路径探测（可为 null）
     * @param accountOps  账号操作器
     */
    public SwInfoFuncCore(SwConfigAccessor accessor, SwNativeOps nativeOps,
                          SwPathDetective pathDetective,
                          SwAccountOps.AccountOpsProvider accountOps) {
        this.accessor = accessor;
        this.nativeOps = nativeOps != null ? nativeOps : new SwNativeOps();
        this.pathDetective = pathDetective != null ? pathDetective : new SwPathDetective(null);
        this.accountOps = accountOps;
    }

    // ==================== 静态便捷方法 ====================

    /**
     * 获取软件类（占位）
     * 对应 Python: get_sw_cls (L57-L59)
     */
    public static Class<?> getSwCls(String sw) {
        // TODO: 返回 GlobalMembers.root_class.sw_classes[sw]
        return Object.class;
    }

    // ==================== 路径解析 ====================

    /**
     * 解析补丁路径
     * 对应 Python: resolve_sw_path (L98-L119)
     */
    public String resolveSwPath(String sw, String addr) {
        return SwPathResolver.resolveSwPath(sw, addr, accessor);
    }

    /**
     * 获取共存路径
     * 对应 Python: get_coexist_path_from_address (L122-L131)
     */
    public String getCoexistPathFromAddress(String sw, String address,
                                             String coexistChannel, String ordinal) {
        return SwPathResolver.getCoexistPathFromAddress(
                sw, address, coexistChannel, ordinal, accessor);
    }

    // ==================== 路径探测 ====================

    /**
     * 检测路径
     * 对应 Python: try_detect_path (L1668-L1707)
     *
     * @param sw       软件标识
     * @param pathType 路径类型
     * @return {success, changed, result}
     */
    public String[] detectPath(String sw, String pathType) {
        List<SwPathDetective.PathEntry> paths = pathDetective.detectAll(sw, pathType, accessor);
        for (SwPathDetective.PathEntry entry : paths) {
            if (SwAdapterChecker.isValidSwPath(pathType, sw, entry.path, accessor)) {
                String standardized = Path.of(entry.path).toAbsolutePath().toString().replace('\\', '/');
                boolean changed = accessor.saveAndCheckChanged(sw, pathType, standardized);
                LOG.info("[路径] 通过探测获得结果: {}", standardized);
                return new String[]{String.valueOf(true), String.valueOf(changed), standardized};
            }
        }
        return new String[]{String.valueOf(false), String.valueOf(false), ""};
    }

    /**
     * 获取路径
     * 对应 Python: detect_path_of_ (L653-L657)
     */
    public String detectPathOf(String sw, String pathType) {
        String[] result = detectPath(sw, pathType);
        if (Boolean.parseBoolean(result[0])) return result[2];
        return null;
    }

    /**
     * 尝试获取路径
     * 对应 Python: try_get_path_of_ (L659-L666)
     */
    public String tryGetPathOf(String sw, String pathType) {
        String saved = accessor.getSavedPathOf(sw, pathType);
        if (saved != null) return saved;
        return detectPathOf(sw, pathType);
    }

    // ==================== 版本计算 ====================

    /**
     * 计算软件版本
     * 对应 Python: calc_sw_ver (L676-L691)
     */
    public String calcSwVer(String sw) {
        return SwVersionHelper.calcSwVer(sw, accessor);
    }

    // ==================== 适配器检测 ====================

    /**
     * 检查 DLL 补丁状态
     * 对应 Python: identify_dll_core (L412-L475)
     *
     * @param sw             软件标识
     * @param mode           模式
     * @param channels       指定通道（null=全部）
     * @param coexistChannel 共存通道
     * @param ordinal        序列号
     * @param skipCache      是否跳过缓存
     * @param cache          缓存数据
     * @return {result, message}
     */
    public SwAdapterChecker.DetectionResult identifyDllCore(
            String sw, String mode, List<String> channels,
            String coexistChannel, String ordinal, boolean skipCache,
            ObjectNode cache) {

        return SwAdapterChecker.identifyDllCore(
                sw, mode, channels, coexistChannel, ordinal, skipCache,
                accessor, cache);
    }

    /**
     * 清除适配缓存
     * 对应 Python: clear_adaptation_cache (L478-L487)
     */
    public void clearAdaptationCache(String sw, String mode, ObjectNode cache) {
        String currVer = calcSwVer(sw);
        if (currVer != null) {
            SwAdapterChecker.clearAdaptationCache(sw, mode, currVer, cache);
        }
    }

    // ==================== 窗口类名 ====================

    /**
     * 获取窗口类名匹配字典
     * 对应 Python: get_sw_wnd_class_matching_dicts (L490-L500)
     */
    public List<Map<String, Object>> getWndClassMatchingDicts(String sw, String wndType) {
        return SwAdapterChecker.getWndClassMatchingDicts(sw, wndType, accessor);
    }

    /**
     * 获取窗口原始类名
     * 对应 Python: get_sw_original_wnd_class_name (L526-L538)
     */
    public String getSwOriginalWndClassName(String sw, String wndType) {
        return SwAdapterChecker.getSwOriginalWndClassName(sw, wndType, accessor);
    }

    /**
     * 获取自定义补丁
     * 对应 Python: get_mode_channel_customizable_patches (L502-L523)
     */
    public List<Map<String, Object>> getModeChannelCustomizablePatches(
            String sw, String mode, String channel, ObjectNode cache) {
        String currVer = calcSwVer(sw);
        if (currVer == null) return Collections.emptyList();
        return SwAdapterChecker.getModeChannelCustomizablePatches(sw, mode, channel, currVer, cache);
    }

    // ==================== 账号操作 ====================

    /**
     * 获取所有账号
     * 对应 Python: get_sw_all_accounts_existed (L587-L612)
     */
    public List<String> getSwAllAccountsExisted(String sw, String only) {
        String dataDir = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.DATA_DIR);
        String instPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
        List<String> excludedDirs = accessor.getRemoteSwAsList(sw, "excluded_dirs", Collections.emptyList());
        List<String> exeWildcards = accessor.getRemoteSwAsList(sw, "exe_wcs", Collections.emptyList());

        return SwAccountOps.getSwAllAccountsExisted(
                sw, dataDir, excludedDirs, instPath, exeWildcards,
                accessor, accountOps, only);
    }

    /**
     * 获取当前登录账号 ID
     * 对应 Python: get_curr_wx_id_from_cfg_file (L540-L543)
     */
    public String getCurrLoginAccIdFromCfgFile(String sw) {
        // TODO: 需要 FuncTool.get_sw_func_impl(SwInfoFuncImpl, sw)
        LOG.debug("[账号] getCurrLoginAccIdFromCfgFile: sw={} (Stub)", sw);
        return null;
    }

    /**
     * 获取登录窗口句柄
     * 对应 Python: get_login_hwnds_of_sw (L545-L558)
     */
    public List<Integer> getLoginHwndsOfSw(String sw) {
        // TODO: 需要 JNA 枚举窗口
        List<Map<String, Object>> loginRules = getWndClassMatchingDicts(sw, "login");
        if (loginRules == null) return Collections.emptyList();
        LOG.debug("[窗口] getLoginHwndsOfSw: sw={}, rules={} (Stub)", sw, loginRules.size());
        return Collections.emptyList();
    }

    // ==================== 路径验证 ====================

    /**
     * 检查路径是否合法
     * 对应 Python: is_valid_sw_path (L875-L932)
     */
    public boolean isValidSwPath(String pathType, String sw, String path) {
        return SwAdapterChecker.isValidSwPath(pathType, sw, path, accessor);
    }

    // ==================== Logo / 图标 ====================

    /**
     * 获取平台 Logo
     * 对应 Python: get_sw_logo (L693-L744)
     */
    public String getSwLogo(String sw, String userDir, String instPath) {
        return SwAccountOps.getSwLogo(sw, userDir, instPath, accessor);
    }

    /**
     * 获取展示名
     * 对应 Python: get_sw_origin_display_name (L746-L758)
     */
    public String getSwOriginDisplayName(String sw) {
        return SwAccountOps.getSwOriginDisplayName(sw, accessor);
    }

    // ==================== 进程 PID ====================

    /**
     * 获取所有进程 PID 按名称分组
     * 对应 Python: get_sw_all_exe_pids_group_by_name (L761-L781)
     */
    public Map<String, List<Integer>> getSwAllExePidsGroupByName(String sw) {
        List<String> exeWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());
        String instPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
        String instDir = instPath != null ? new File(instPath).getParent() : "";

        Map<String, List<Integer>> namePidsDict = nativeOps.getPidsByWildcardsAndGroup(exeWildcards);

        // 过滤：移除子进程，过滤不在安装目录下的进程
        for (String name : new ArrayList<>(namePidsDict.keySet())) {
            List<Integer> pids = namePidsDict.get(name);
            pids = SwNativeOps.removeChildPids(pids);
            pids = SwNativeOps.removePidsNotInPath(pids, instDir);
            if (pids.isEmpty()) {
                namePidsDict.remove(name);
            } else {
                namePidsDict.put(name, pids);
            }
        }

        return namePidsDict;
    }

    /**
     * 获取所有进程 PID 列表
     * 对应 Python: get_sw_all_exe_pids (L783-L796)
     */
    public List<Integer> getSwAllExePids(String sw) {
        Map<String, List<Integer>> grouped = getSwAllExePidsGroupByName(sw);
        List<Integer> allPids = new ArrayList<>();
        grouped.values().forEach(allPids::addAll);
        allPids = SwNativeOps.removeChildPids(allPids);
        String instPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
        String instDir = instPath != null ? new File(instPath).getParent() : "";
        return SwNativeOps.removePidsNotInPath(allPids, instDir);
    }

    // ==================== 多开模式 ====================

    /**
     * 检查是否可以自由多开
     * 对应 Python: check_if_sw_can_freely_multirun (L626-L643)
     */
    public boolean checkIfSwCanFreelyMultirun(String sw) {
        SwAdapterChecker.DetectionResult result = identifyDllCore(
                sw, SwCoreConstants.RemoteSwKey.MULTI, null, null, null, true, null);

        if (result == null) {
            // 没有适配，检查是否原生支持多开
            Boolean nativeMultirun = accessor.getRemoteSwAsBoolean(
                    sw, SwCoreConstants.RemoteSwKey.MULTI, null);
            return Boolean.TRUE.equals(nativeMultirun);
        } else {
            // 检查是否有任何通道支持自由多开
            return true; // TODO: 检查 channels_res_dict
        }
    }

    /**
     * 获取多开模式
     * 对应 Python: get_sw_multirun_mode (L645-L651)
     */
    public String getSwMultirunMode(String sw) {
        if (checkIfSwCanFreelyMultirun(sw)) {
            return SwCoreConstants.MultirunMode.FREELY_MULTIRUN;
        }
        return accessor.getSwSettingAsString(
                sw, SwCoreConstants.LocalSettingKey.REST_MULTIRUN_MODE,
                SwCoreConstants.MultirunMode.BUILTIN);
    }

    // ==================== 共存模式 ====================

    /**
     * 识别可用的共存模式
     * 对应 Python: identity_and_get_available_coexist_mode (L614-L624)
     */
    public String[] identityAndGetAvailableCoexistMode(String sw) {
        return SwAccountOps.identityAndGetAvailableCoexistMode(sw, accessor, accountOps);
    }

    // ==================== 头像操作 ====================

    /**
     * 启动头像截取线程
     * 对应 Python: start_capt_thread (L2006-L2021)
     */
    public void startCaptThread(String sw, String period, int hwnd, int times, double gap) {
        SwAvatarOps.startCaptThread(sw, period, hwnd, times, gap, accessor, nativeOps);
    }

    /**
     * 启动复制当前头像线程
     * 对应 Python: start_thread_to_copy_curr_avatar (L2023-L2042)
     */
    public void startThreadToCopyCurrAvatar(String sw, int hwnd) {
        SwAvatarOps.startThreadToCopyCurrAvatar(sw, hwnd, accessor);
    }

    /**
     * 获取今天的截图头像列表
     * 对应 Python: get_today_capt_avatars (L2044-L2060)
     */
    public List<String> getTodayCaptAvatars(int pid) {
        return SwAvatarOps.getTodayCaptAvatars(pid);
    }

    // ==================== 关系查询 ====================

    /**
     * 获取通道关系
     * 对应 Python: get_relations_of_channel (L2278-L2310)
     */
    public Map<String, List<String>> getRelationsOfChannel(String sw, String mode, String channel,
                                                            ObjectNode cache) {
        return SwOperatorCore.getRelationsOfChannel(sw, mode, channel, cache, accessor);
    }

    // ==================== 静态工具方法（从 SwHexUtils 委托） ====================

    /**
     * 字节转 hex 字符串
     * 对应 Python: bytes_to_hex_str (L1358-L1361)
     */
    public static String bytesToHexStr(byte[] data) {
        return SwHexUtils.bytesToHexStr(data);
    }

    /**
     * 根据特征码搜索补丁字典
     * 对应 Python: search_pattern_dicts_by_original_and_modified (L1408-L1527)
     */
    public static List<SwHexUtils.ScanResult> searchPatternDicts(ByteBuffer data,
                                                                  String originalHex,
                                                                  String modifiedHex,
                                                                  int leftCut, int rightCut) {
        return SwHexUtils.searchPatternDicts(data, originalHex, modifiedHex, leftCut, rightCut);
    }

    /**
     * 搜索首个标记特征码
     * 对应 Python: search_first_pattern_and_get_address_of_marked (L1586-L1629)
     */
    public static List<Map<String, Object>> searchFirstPatternWithMarked(ByteBuffer data,
                                                                          List<String> targetFeatures) {
        return SwHexUtils.searchFirstPatternWithMarked(data, targetFeatures);
    }

    /**
     * 解析规则字典
     * 对应 Python: resolve_rule_dict_and_return_res_dicts (L1300-L1339)
     */
    public static List<Map<String, Object>> resolveRuleDict(ByteBuffer mm, String curSwVer,
                                                             JsonNode featureRule) {
        return SwRuleResolver.resolveRuleDictAndReturnResDicts(curSwVer, mm, featureRule);
    }
}
