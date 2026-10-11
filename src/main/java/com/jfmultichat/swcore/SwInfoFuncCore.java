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
        List<SwPathDetective.PathEntry> entries =
                pathDetective.detectAll(accessor, sw, pathType).get(pathType);
        if (entries != null && !entries.isEmpty()) {
            SwPathDetective.PathEntry first = entries.get(0);
            if (SwAdapterChecker.isValidSwPath(pathType, sw, first.path, accessor)) {
                String standardized = Path.of(first.path).toAbsolutePath().toString().replace('\\', '/');
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
        List<String> exeWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());

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
     * **按窗口类型取本平台窗口句柄（取句柄的核心方法，多处复用）**.
     *
     * <p>链路（与 Python `get_login_hwnds_of_sw` 一致）：平台 pid 列表 → 每个 pid 的顶层窗口 →
     * 用 `wnd_class.<wndType>.matching` 的规则筛选 → **唯一命中**才算数（避免把别的窗口误当目标）。
     * 登录窗口校验、主窗口定位、登录窗口尺寸获取都走它，不再各写一套。
     *
     * @param wndType 窗口类型：{@code "login"} / {@code "main"}（见远程配置 wnd_class 的键）
     */
    public List<Integer> getHwndsOfSwByWndType(String sw, String wndType) {
        List<Map<String, Object>> rules = getWndClassMatchingDicts(sw, wndType);
        if (rules == null || rules.isEmpty()) {
            LOG.debug("[窗口] {} 的 {} 窗口规则为空，无法取句柄", sw, wndType);
            return new ArrayList<>();
        }
        // 平台 pid 列表（含去子进程 / 去非安装目录，与查杀互斥体同一份口径）
        List<Integer> pids = new ArrayList<>();
        Map<String, List<Integer>> grouped = getSwAllExePidsGroupByName(sw);
        if (grouped != null) {
            for (List<Integer> list : grouped.values()) {
                if (list != null) pids.addAll(list);
            }
        }
        List<Integer> result = new ArrayList<>();
        for (Integer pid : pids) {
            List<Integer> hwndsOfPid = nativeOps.getHwndsByPid(pid);
            for (Map<String, Object> rule : rules) {
                List<Integer> matched = SwNativeOps.filterHwndsByMatchingDict(hwndsOfPid, rule);
                if (matched.size() == 1) {
                    result.add(matched.get(0));
                    break;
                }
            }
        }
        LOG.info("[窗口] {} 的 {} 窗口命中 {} 个: {}", sw, wndType, result.size(), result);
        if (result.isEmpty()) {
            // 取不到就**把证据全打出来**（用户 2026-10-07：有的平台识别不到，需要一眼看出是哪一层断的）：
            // ① 规则有没有解析出来 ② 过滤后的 pid 列表 ③ **未过滤**的 pid 列表（含子进程/任意目录）
            // ④ 这些 pid 的每个窗口真实类名/标题/尺寸 —— 好对比"配置里的通配符"和"Win32 报的类名"
            logWindowDiagnosis(sw, wndType, rules, pids);
        }
        return result;
    }

    /** 取不到窗口时的诊断输出（只在失败时打，避免平时刷日志） */
    private void logWindowDiagnosis(String sw, String wndType,
                                    List<Map<String, Object>> rules, List<Integer> filteredPids) {
        try {
            String ver = SwVersionHelper.calcSwVer(sw, accessor);
            LOG.info("[窗口诊断] sw={}, 类型={}, calcSwVer={}, 规则={}", sw, wndType, ver, rules);
            LOG.info("[窗口诊断] 过滤后的 pid（去子进程/限安装目录）={}", filteredPids);

            List<String> exeWcs = accessor.getRemoteSwAsList(
                    sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());
            LOG.info("[窗口诊断] exe 通配词={}", exeWcs);
            Map<String, List<Integer>> rawGrouped = nativeOps.getPidsByWildcardsAndGroup(exeWcs);
            LOG.info("[窗口诊断] **未过滤**的 pid（按 exe 分组，含子进程/任意目录）={}", rawGrouped);

            List<Integer> allPids = new ArrayList<>(filteredPids);
            for (List<Integer> list : rawGrouped.values()) {
                if (list == null) continue;
                for (Integer pid : list) if (!allPids.contains(pid)) allPids.add(pid);
            }
            int printed = 0;
            for (Integer pid : allPids) {
                List<Integer> hwnds = nativeOps.getHwndsByPid(pid);
                for (Integer hwnd : hwnds) {
                    if (printed++ > 60) return;                       // 上限，别刷爆日志
                    Map<String, Object> d = SwNativeOps.getHwndDetails(hwnd);
                    LOG.info("[窗口诊断] pid={} hwnd=0x{} class=[{}] title=[{}] {}x{} visible={}",
                            pid, Integer.toHexString(hwnd), d.get("class"), d.get("title"),
                            d.get("width"), d.get("height"), d.get("visible"));
                }
            }
        } catch (Throwable t) {
            LOG.warn("[窗口诊断] 输出失败: {}", t.getMessage());
        }
    }

    /**
     * 获取登录窗口句柄
     * 对应 Python: get_login_hwnds_of_sw (L545-L558)
     */
    public List<Integer> getLoginHwndsOfSw(String sw) {
        return getHwndsOfSwByWndType(sw, "login");
    }

    /**
     * 获取主窗口句柄（登录完成后"等主窗口出现"用它校验）
     */
    public List<Integer> getMainHwndsOfSw(String sw) {
        return getHwndsOfSwByWndType(sw, "main");
    }

    /**
     * 取**某个 pid** 下符合某类型规则的窗口（可排除已知窗口）.
     * 供"启动平台后等登录窗口出现"使用（那里只能认这一个新 pid，不能全平台扫）。
     */
    public List<Integer> getHwndsByPidAndWndType(String sw, int pid, String wndType, List<Integer> exclude) {
        List<Map<String, Object>> rules = getWndClassMatchingDicts(sw, wndType);
        if (rules == null || rules.isEmpty() || pid <= 0) return new ArrayList<>();
        List<Integer> hwnds = nativeOps.getHwndsByPid(pid);
        if (exclude != null && !exclude.isEmpty()) hwnds.removeAll(exclude);
        for (Map<String, Object> rule : rules) {
            List<Integer> matched = SwNativeOps.filterHwndsByMatchingDict(hwnds, rule);
            if (matched.size() == 1) return matched;
        }
        return new ArrayList<>();
    }

    /**
     * 轮询等待"某 pid 上出现唯一的该类型窗口"（对应 Python: uiautomation_wait_hwnd_exclusively_by_pid_and_rules_dicts）.
     *
     * <p>性能要点（用户 2026-10-11 日志实测）：**只在"出现新窗口"时才做规则匹配** ✓。
     * 原先每轮轮询都对当前所有窗口跑一遍规则 ✗ —— 而新进程先冒出来的是各种辅助窗口 ✓（不匹配 ✓），
     * 于是每轮都要走 UIA 兜底 ✗（每个窗口约 143ms ✗）→ "等新窗口"从 ~1s 涨到 2.7~3.9s ✗。
     * 现在每个窗口**只匹配一次**（不匹配就记进 seen ✓，不再重复 ✓），其余轮询只做便宜的
     * `EnumWindows` 比对 ✓。
     *
     * @return hwnd；超时返回 0
     */
    public int waitHwndExclusivelyForPid(String sw, int pid, String wndType, List<Integer> exclude, int timeoutSec) {
        long deadline = System.currentTimeMillis() + Math.max(1, timeoutSec) * 1000L;
        Set<Integer> seen = new HashSet<>();          // 已"规则匹配过但不匹配"的窗口，不再重复匹配
        if (exclude != null) seen.addAll(exclude);
        List<Map<String, Object>> rules = getWndClassMatchingDicts(sw, wndType);
        while (System.currentTimeMillis() < deadline) {
            List<Integer> hwnds = nativeOps.getHwndsByPid(pid);
            List<Integer> fresh = new ArrayList<>();
            for (Integer h : hwnds) {
                if (h != null && !seen.contains(h)) fresh.add(h);
            }
            if (!fresh.isEmpty()) {
                for (Map<String, Object> rule : rules) {
                    List<Integer> matched = SwNativeOps.filterHwndsByMatchingDict(fresh, rule);
                    if (matched.size() == 1) {
                        LOG.info("[窗口] pid={} 的 {} 窗口已出现: hwnd={}", pid, wndType, matched.get(0));
                        return matched.get(0);
                    }
                }
                seen.addAll(fresh);                   // 这一批都不匹配 → 记住，之后不再重复匹配
            }
            try {
                Thread.sleep(200);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return 0;
            }
        }
        LOG.warn("[窗口] 等 pid={} 的 {} 窗口超时（{}s）", pid, wndType, timeoutSec);
        return 0;
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
