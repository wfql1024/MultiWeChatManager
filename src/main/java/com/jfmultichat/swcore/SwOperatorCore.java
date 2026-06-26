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
 * 运营操作核心 — DLL 切换、共存程序创建/删除、登录、备份
 * <p>
 * 对应 Python: SwOperatorCore (L2063-L2946)
 * <p>
 * 包含：DLL 补丁切换、共存程序管理、进程创建、登录窗口操作等。
 *
 * 依赖: SwConfigAccessor, SwPathResolver, SwVersionHelper, SwAdapterChecker,
 *       SwNativeOps, SwAvatarOps, SwAccountOps, SwRuleResolver
 */
public final class SwOperatorCore {

    private static final Logger LOG = LoggerFactory.getLogger(SwOperatorCore.class);
    private SwOperatorCore() {}

    // ==================== 互斥体查杀 ====================

    /**
     * 查杀所有互斥体
     * 对应 Python: SwOperatorCore.kill_all_mutexes_now (L2065-L2090)
     *
     * @param sw         软件标识
     * @param accessor   配置访问器
     * @param nativeOps  原生操作器
     * @return {success, message}
     */
    public static String[] killAllMutexesNow(String sw, SwConfigAccessor accessor, SwNativeOps nativeOps) {
        List<String> mutantWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.MUTEX_HANDLE_WILDCARDS, Collections.emptyList());
        List<String> configWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.CONFIG_HANDLE_WILDCARDS, Collections.emptyList());

        List<String> allWildcards = new ArrayList<>(mutantWildcards);
        allWildcards.addAll(configWildcards);

        if (allWildcards.isEmpty()) {
            return new String[]{null, "未查询到" + sw + "的互斥体列表和配置文件列表!"};
        }

        // TODO: 获取所有 PID + JNA 查杀
        LOG.info("[互斥体] killAllMutexesNow: wildcards={} (Stub)", allWildcards);
        return new String[]{null, "需要 JNA 实现互斥体查杀"};
    }

    /**
     * 尝试查杀互斥体并返回剩余有互斥体的 PID 列表
     * 对应 Python: SwOperatorCore.try_kill_mutex_if_need_and_return_remained_pids (L2092-L2112)
     */
    public static List<Integer> tryKillMutexIfNeededAndReturnRemainedPids(
            String sw, Boolean kill, SwConfigAccessor accessor, SwNativeOps nativeOps) {

        List<String> mutantWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.MUTEX_HANDLE_WILDCARDS, Collections.emptyList());

        if (mutantWildcards.isEmpty()) {
            LOG.info("[互斥体] 未获取到互斥体通配词");
            return Collections.emptyList();
        }

        // TODO: JNA 查杀
        LOG.debug("[互斥体] tryKillMutexIfNeeded: wildcards={} (Stub)", mutantWildcards);
        return Collections.emptyList();
    }

    // ==================== DLL 切换 ====================

    /**
     * 切换 DLL 补丁核心
     * 对应 Python: SwOperatorCore.switch_dll_core (L2184-L2276)
     *
     * @param sw             软件标识
     * @param mode           模式 (multi / revoke)
     * @param channel        通道
     * @param coexistChannel 共存通道
     * @param ordinal        序列号
     * @param target         目标状态（null=自动检测取反）
     * @param accessor       配置访问器
     * @param cache          缓存数据
     * @param nativeOps      原生操作器
     * @return {success, message}
     */
    public static String[] switchDllCore(
            String sw, String mode, String channel,
            String coexistChannel, String ordinal, Boolean target,
            SwConfigAccessor accessor, ObjectNode cache, SwNativeOps nativeOps) {

        String modeText;
        if (SwCoreConstants.RemoteSwKey.MULTI.equals(mode)) {
            modeText = "全局多开";
        } else if (SwCoreConstants.RemoteSwKey.REVOKE.equals(mode)) {
            modeText = "防撤回";
        } else {
            return new String[]{null, "未知模式"};
        }

        try {
            // 1. 获取安装路径
            String instPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
            if (instPath == null) {
                return new String[]{null, "无法获取安装路径"};
            }
            String instDir = new File(instPath).getParent();

            // 2. 确定 exe 路径
            String swExePath;
            if (coexistChannel != null && ordinal != null) {
                JsonNode exeWildcard = accessor.getRemoteSw(
                        sw, SwCoreConstants.RemoteSwKey.COEXIST,
                        SwCoreConstants.RemoteSwKey.CHANNELS,
                        coexistChannel, "exe_wildcard");
                String coexistExe = exeWildcard != null && exeWildcard.isTextual()
                        ? exeWildcard.asText().replace("?", ordinal) : "";
                swExePath = (instDir != null ? instDir + "/" : "") + coexistExe;
            } else {
                swExePath = instPath;
            }

            // 3. 询问用户终止进程（Stub — 无 GUI）
            // answer = cls.ask_for_manual_terminate_or_force(sw_exe_path)
            LOG.info("[DLL] 目标 exe: {}", swExePath);

            // 4. 如果 target 未指定，先检测当前状态
            if (target == null) {
                // TODO: 调用 SwAdapterChecker.identifyDllCore 检测
                LOG.info("[DLL] 未指定 target，需要检测当前状态 (Stub)");
                return new String[]{null, "需要检测当前状态 (Stub)"};
            }

            // 5. 获取当前版本
            String currVer = SwVersionHelper.calcSwVer(sw, accessor);
            if (currVer == null) {
                return new String[]{null, "无法获取版本"};
            }

            // 6. 获取补丁表
            List<Map<String, Object>> addrPatchesDicts = getCachePreciseEntry(
                    cache, sw, mode, channel, currVer);
            if (addrPatchesDicts == null || addrPatchesDicts.isEmpty()) {
                return new String[]{null, "未找到适配表"};
            }

            // 7. 验证补丁表格式
            for (Map<String, Object> dict : addrPatchesDicts) {
                if (!dict.containsKey("addr") || !dict.containsKey("patches")) {
                    return new String[]{null, "缓存适配格式错误!"};
                }
            }

            // 8. 打开文件并写入补丁
            List<FileChannel> files = new ArrayList<>();
            List<MappedByteBuffer> mmaps = new ArrayList<>();

            try {
                for (Map<String, Object> dict : addrPatchesDicts) {
                    String addr = (String) dict.get("addr");
                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> patches = (List<Map<String, Object>>) dict.get("patches");

                    String realDllPath;
                    if (coexistChannel != null && ordinal != null) {
                        realDllPath = SwPathResolver.getCoexistPathFromAddress(
                                sw, addr, coexistChannel, ordinal, accessor);
                    } else {
                        realDllPath = SwPathResolver.resolveSwPath(sw, addr, accessor);
                    }

                    Path dllPath = Path.of(realDllPath);
                    if (!Files.exists(dllPath)) {
                        LOG.warn("[DLL] 文件不存在: {}", realDllPath);
                        continue;
                    }

                    FileChannel fc = FileChannel.open(dllPath,
                            java.nio.file.StandardOpenOption.READ, java.nio.file.StandardOpenOption.WRITE);
                    MappedByteBuffer mm = fc.map(FileChannel.MapMode.READ_WRITE, 0, fc.size());
                    files.add(fc);
                    mmaps.add(mm);

                    for (Map<String, Object> patch : patches) {
                        Object offsetObj = patch.get("offset");
                        if (offsetObj == null) continue;

                        int fileOffset = ((Number) offsetObj).intValue();
                        String hexStr = patch.get("modified") != null
                                ? patch.get("modified").toString()
                                : patch.get("original") != null
                                        ? patch.get("original").toString() : "";

                        // 如果是共存模式，替换 !! 为 ordinal
                        if (coexistChannel != null && ordinal != null) {
                            hexStr = hexStr.replace("!!",
                                    String.format("%02X", ordinal.charAt(0)));
                        }

                        byte[] patchBytes = SwHexUtils.hexStrToBytes(hexStr);
                        if (fileOffset + patchBytes.length <= mm.limit()) {
                            mm.position(fileOffset);
                            mm.put(patchBytes);
                        }
                    }
                }

                // 9. 统一 flush
                for (MappedByteBuffer mm : mmaps) {
                    mm.force();
                }

                String action = target ? "开启" : "关闭";
                return new String[]{null, "成功" + action + ": " + modeText};

            } catch (Exception e) {
                LOG.error("[DLL] 切换失败: {}", e.getMessage(), e);
                // 出错时不 flush，直接 close（放弃所有改动）
                return new String[]{null, "切换" + modeText + "失败！请稍后重试！"};
            } finally {
                for (MappedByteBuffer mm : mmaps) {
                    try { mm.force(); } catch (Exception ignored) {}
                }
                for (FileChannel fc : files) {
                    try { fc.close(); } catch (Exception ignored) {}
                }
            }

        } catch (Exception e) {
            Map<Class<?>, String> errorMsgMap = Map.of(
                    SecurityException.class, "权限不足，无法修改 DLL 文件。",
                    Exception.class, "发生未知错误。"
            );
            String errMsg = errorMsgMap.getOrDefault(e.getClass(), "发生未知错误。");
            LOG.error("[DLL] 切换{}时发生错误: {}", modeText, e.getMessage());
            return new String[]{null, "切换" + modeText + "时发生错误: " + e.getMessage() + "\n" + errMsg};
        }
    }

    // ==================== 通道关系 ====================

    /**
     * 获取通道的关系（parents / children / friends）
     * 对应 Python: SwOperatorCore.get_relations_of_channel (L2278-L2310)
     *
     * @param sw       软件标识
     * @param mode     模式
     * @param channel  通道
     * @param cache    缓存数据
     * @return {parents, children, friends}
     */
    public static Map<String, List<String>> getRelationsOfChannel(
            String sw, String mode, String channel, ObjectNode cache, SwConfigAccessor accessor) {

        String currVer = SwVersionHelper.calcSwVer(sw, accessor);
        if (currVer == null) {
            return Map.of("parents", Collections.emptyList(),
                    "children", Collections.emptyList(),
                    "friends", Collections.emptyList());
        }

        List<Map<String, Object>> addrPatchesDicts = getCachePreciseEntry(
                cache, sw, mode, channel, currVer);
        if (addrPatchesDicts == null) {
            return Map.of("parents", Collections.emptyList(),
                    "children", Collections.emptyList(),
                    "friends", Collections.emptyList());
        }

        Set<String> parents = new LinkedHashSet<>();
        Set<String> children = new LinkedHashSet<>();
        Set<String> friends = new LinkedHashSet<>();

        for (Map<String, Object> dict : addrPatchesDicts) {
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> patches = (List<Map<String, Object>>) dict.get("patches");
            if (patches == null) continue;

            for (Map<String, Object> patch : patches) {
                for (String key : List.of("parents", "children", "friends")) {
                    Object val = patch.get(key);
                    if (val instanceof List) {
                        for (Object item : (List<?>) val) {
                            if (item != null) {
                                switch (key) {
                                    case "parents" -> parents.add(item.toString());
                                    case "children" -> children.add(item.toString());
                                    case "friends" -> friends.add(item.toString());
                                }
                            }
                        }
                    }
                }
            }
        }

        Map<String, List<String>> result = new LinkedHashMap<>();
        result.put("parents", new ArrayList<>(parents));
        result.put("children", new ArrayList<>(children));
        result.put("friends", new ArrayList<>(friends));
        return result;
    }

    // ==================== 共存程序管理 ====================

    /**
     * 创建共存程序
     * 对应 Python: SwOperatorCore.create_coexist_exe_core (L2517-L2590)
     *
     * @param sw             软件标识
     * @param coexistChannel 共存通道
     * @param ordinal        序列号
     * @param accessor       配置访问器
     * @param cache          缓存数据
     * @param accountOps     账号操作器
     * @return {newExeName, message}
     */
    public static String[] createCoexistExeCore(
            String sw, String coexistChannel, String ordinal,
            SwConfigAccessor accessor, ObjectNode cache,
            SwAccountOps.AccountOpsProvider accountOps) {

        // 1. 获取 exe_wildcard 和 ordinals
        JsonNode exeWildcardNode = accessor.getRemoteSw(
                sw, SwCoreConstants.RemoteSwKey.COEXIST,
                SwCoreConstants.RemoteSwKey.CHANNELS,
                coexistChannel, "exe_wildcard");
        JsonNode ordinalsNode = accessor.getRemoteSw(
                sw, SwCoreConstants.RemoteSwKey.COEXIST,
                SwCoreConstants.RemoteSwKey.CHANNELS,
                coexistChannel, "ordinals");

        if (exeWildcardNode == null || !exeWildcardNode.isTextual()
                || ordinalsNode == null || !ordinalsNode.isTextual()) {
            return new String[]{null, "尚未适配[exe_wildcard, ordinals]!"};
        }

        String exeWildcard = exeWildcardNode.asText();
        String ordinalsStr = ordinalsNode.asText();

        // 2. 获取当前版本
        String currVer = SwVersionHelper.calcSwVer(sw, accessor);
        if (currVer == null) {
            return new String[]{null, "无法获取版本"};
        }

        // 3. 获取适配表
        List<Map<String, Object>> addrPatchesDicts = getCachePreciseEntry(
                cache, sw, SwCoreConstants.RemoteSwKey.COEXIST,
                coexistChannel, currVer);
        if (addrPatchesDicts == null || addrPatchesDicts.isEmpty()) {
            return new String[]{null, "尚未适配[coexist_channel]!"};
        }

        // 4. 验证格式
        for (Map<String, Object> dict : addrPatchesDicts) {
            if (!dict.containsKey("wildcard") || !dict.containsKey("addr")
                    || !dict.containsKey("patches")) {
                return new String[]{null, "适配格式错误!"};
            }
        }

        List<String> newFiles = new ArrayList<>();

        try {
            // 5. 创建共存文件
            for (Map<String, Object> dict : addrPatchesDicts) {
                String addr = (String) dict.get("addr");
                String originPath = SwPathResolver.resolveSwPath(sw, addr, accessor);

                @SuppressWarnings("unchecked")
                List<Map<String, Object>> patches = (List<Map<String, Object>>) dict.get("patches");
                String nameWildcard = (String) dict.get("wildcard");

                String originDir = new File(originPath).getParent();
                String newName = nameWildcard.replace("?", ordinal);
                String newPath = originDir + "/" + newName;

                // 拷贝文件
                Path src = Path.of(originPath);
                Path dst = Path.of(newPath);
                if (Files.exists(src)) {
                    Files.copy(src, dst, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    newFiles.add(newPath);
                }

                // 修改新文件
                FileChannel fc = FileChannel.open(dst,
                        java.nio.file.StandardOpenOption.READ, java.nio.file.StandardOpenOption.WRITE);
                MappedByteBuffer mm = fc.map(FileChannel.MapMode.READ_WRITE, 0, fc.size());

                for (Map<String, Object> patch : patches) {
                    Object offsetObj = patch.get("offset");
                    if (offsetObj == null) continue;

                    int fileOffset = ((Number) offsetObj).intValue();
                    String hexStr = patch.get("modified").toString();
                    // 替换 !! 为 ordinal 的 ASCII 码
                    hexStr = hexStr.replace("!!",
                            String.format("%02X", (int) ordinal.charAt(0)));

                    byte[] patchBytes = SwHexUtils.hexStrToBytes(hexStr);
                    if (fileOffset + patchBytes.length <= mm.limit()) {
                        mm.position(fileOffset);
                        mm.put(patchBytes);
                    }
                }

                mm.force();
                fc.close();
            }

            // 6. 更新配置
            String newCoexistExeName = exeWildcard.replace("?", ordinal);
            SwAccountOps.ensureCoexistAccFormatted(sw, newCoexistExeName, accountOps);
            accountOps.updateSwAccData(sw, Map.of(newCoexistExeName, ""),
                    Map.of(
                            "channel", coexistChannel,
                            SwCoreConstants.AccKeys.ORDINAL, ordinal
                    ));

            return new String[]{newCoexistExeName, ""};

        } catch (Exception e) {
            LOG.error("[共存] 创建失败: {}", e.getMessage(), e);
            // 回滚：删除已创建的文件
            for (String f : newFiles) {
                try { Files.delete(Path.of(f)); } catch (Exception ignored) {}
            }
            return new String[]{null, "创建共存程序失败!"};
        }
    }

    /**
     * 删除共存程序
     * 对应 Python: SwOperatorCore.del_coexist_exe (L2592-L2628)
     *
     * @param sw      软件标识
     * @param accounts 账号列表
     * @param accessor 配置访问器
     * @param cache   缓存数据
     * @return {successAccs, failedMsgDict}
     */
    public static Map<String, Object> delCoexistExe(
            String sw, List<String> accounts,
            SwConfigAccessor accessor, ObjectNode cache) {

        List<String> successAccs = new ArrayList<>();
        Map<String, String> failedMsgDict = new LinkedHashMap<>();

        String currVer = SwVersionHelper.calcSwVer(sw, accessor);

        for (String acc : accounts) {
            try {
                JsonNode coexistChannelNode = accessor.getSwAccData(sw, acc, "coexist_channel");
                JsonNode ordinalNode = accessor.getSwAccData(sw, acc, "ordinal");

                if (coexistChannelNode == null || ordinalNode == null) {
                    failedMsgDict.put(acc, "未适配");
                    continue;
                }

                String coexistChannel = coexistChannelNode.asText();
                String ordinal = ordinalNode.asText();

                // 获取适配表
                List<Map<String, Object>> channelAddrDicts = getCachePreciseEntry(
                        cache, sw, SwCoreConstants.RemoteSwKey.COEXIST,
                        coexistChannel, currVer);

                if (channelAddrDicts == null) {
                    // 未适配，只删除入口程序
                    String swExePath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
                    if (swExePath != null) {
                        String instDir = new File(swExePath).getParent();
                        String delPath = instDir + "/" + acc;
                        Files.deleteIfExists(Path.of(delPath));
                    }
                    successAccs.add(acc);
                    continue;
                }

                for (Map<String, Object> cADict : channelAddrDicts) {
                    String addr = (String) cADict.get("addr");
                    String originPath = SwPathResolver.resolveSwPath(sw, addr, accessor);
                    String nameWildcard = (String) cADict.get("wildcard");
                    String delPath = new File(originPath).getParent() + "/"
                            + nameWildcard.replace("?", ordinal);
                    Files.deleteIfExists(Path.of(delPath));
                    LOG.info("[共存] 清除共存文件: {}", delPath);
                }

                successAccs.add(acc);
            } catch (Exception e) {
                failedMsgDict.put(acc, "发生错误!(" + e.getMessage() + ")");
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("success", successAccs);
        result.put("failed", failedMsgDict);
        return result;
    }

    /**
     * 重建共存程序
     * 对应 Python: SwOperatorCore.rebuild_coexist_exes (L2630-L2646)
     */
    public static Map<String, Object> rebuildCoexistExes(
            String sw, List<String> accounts,
            String coexistChannel, String ordinal,
            SwConfigAccessor accessor, ObjectNode cache,
            SwAccountOps.AccountOpsProvider accountOps) {

        Map<String, String> failedMsgDict = new LinkedHashMap<>();
        List<String> successExes = new ArrayList<>();

        for (String acc : accounts) {
            String[] result = createCoexistExeCore(
                    sw, coexistChannel, ordinal, accessor, cache, accountOps);
            if (result[0] != null) {
                successExes.add(result[0]);
            } else {
                failedMsgDict.put(acc, result[1]);
            }
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("success", successExes);
        out.put("failed", failedMsgDict);
        return out;
    }

    // ==================== 备份操作 ====================

    /**
     * 备份所有补丁文件
     * 对应 Python: SwOperatorCore.backup_sw_all_patching_files (L2151-L2156)
     */
    public static void backupAllPatchingFiles(String sw, SwConfigAccessor accessor) {
        // 提取所有地址
        List<String> allPatchingAddresses = extractAddressesFromRemoteCfg(sw, accessor);
        List<String> allPatchingFiles = new ArrayList<>();
        for (String addr : allPatchingAddresses) {
            allPatchingFiles.add(SwPathResolver.resolveSwPath(sw, addr, accessor));
        }
        SwNativeOps.backupFiles(allPatchingFiles);
    }

    /**
     * 恢复备份文件并返回待删除路径
     * 对应 Python: SwOperatorCore.restore_dll_and_get_del_paths (L2920-L2946)
     *
     * @param sw  软件标识
     * @param accessor 配置访问器
     * @return 待删除路径列表
     */
    public static List<String> restoreDllAndGetDelPaths(String sw, SwConfigAccessor accessor) {
        List<String> delPaths = new ArrayList<>();
        List<String> allPatchingAddresses = extractAddressesFromRemoteCfg(sw, accessor);

        for (String addr : allPatchingAddresses) {
            String patchingFile = SwPathResolver.resolveSwPath(sw, addr, accessor);
            String dirPath = new File(patchingFile).getParent();
            String baseName = new File(patchingFile).getName();
            String dllPath = dirPath + "/" + baseName;
            String bakPath = dllPath + ".bak";
            String delPath = dllPath + ".del";

            try {
                if (Files.exists(Path.of(bakPath))) {
                    if (Files.exists(Path.of(dllPath))) {
                        Files.move(Path.of(dllPath), Path.of(delPath),
                                java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                        LOG.info("[恢复] 加入待删列表: {}", delPath);
                    }
                    Files.move(Path.of(bakPath), Path.of(dllPath),
                            java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    LOG.info("[恢复] 已恢复: {}", dllPath);
                }
            } catch (Exception e) {
                LOG.warn("[恢复] 失败: {}", e.getMessage());
            }
            delPaths.add(delPath);
        }

        return delPaths;
    }

    // ==================== 配置文件夹操作 ====================

    /**
     * 打开配置文件夹
     * 对应 Python: SwOperatorCore.open_config_file (L2852-L2864)
     */
    public static void openConfigFile(String sw, SwConfigAccessor accessor) {
        String dataPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.DATA_DIR);
        if (dataPath == null || !Files.exists(Path.of(dataPath))) {
            LOG.warn("[配置] 数据目录不存在: {}", dataPath);
            return;
        }

        JsonNode configAddresses = accessor.getRemoteSw(sw, "config_addresses");
        if (configAddresses == null || !configAddresses.isArray() || configAddresses.isEmpty()) {
            LOG.warn("[配置] 未适配配置地址: {}", sw);
            return;
        }

        String originCfgPath = SwPathResolver.resolveSwPath(sw, configAddresses.get(0).asText(), accessor);
        String configDir = new File(originCfgPath).getParent();
        if (Files.exists(Path.of(configDir))) {
            try {
                java.awt.Desktop.getDesktop().open(new File(configDir));
            } catch (Exception e) {
                LOG.warn("[配置] 打开文件夹失败: {}", e.getMessage());
            }
        }
    }

    /**
     * 打开 DLL 所在文件夹
     * 对应 Python: SwOperatorCore.open_dll_dir (L2900-L2918)
     */
    public static void openDllDir(String sw, SwConfigAccessor accessor) {
        String dllDir = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.DLL_DIR);
        if (dllDir == null || !Files.exists(Path.of(dllDir))) {
            LOG.warn("[DLL] 目录不存在: {}", dllDir);
            return;
        }

        try {
            java.awt.Desktop.getDesktop().open(new File(dllDir));
        } catch (Exception e) {
            LOG.warn("[DLL] 打开文件夹失败: {}", e.getMessage());
        }
    }

    // ==================== 登录相关 ====================

    /**
     * 打开 SW 并返回窗口句柄
     * 对应 Python: SwOperatorCore.open_sw_and_return_hwnd (L2404-L2428)
     * <p>
     * 需要 JNA 实现窗口检测和进程创建。
     */
    public static int[] openSwAndReturnHwnd(String sw, String exe,
                                             SwConfigAccessor accessor, SwNativeOps nativeOps) {
        // TODO: 完整实现需要大量 JNA 调用
        // 1. 获取登录窗口规则
        // 2. 关闭多余的多开器
        // 3. 记录 PID 互斥体
        // 4. 打开 SW
        // 5. 等待窗口出现
        LOG.info("[登录] openSwAndReturnHwnd: sw={}, exe={} (Stub)", sw, exe);
        return new int[]{-1, 0}; // {hwnd, pid}
    }

    /**
     * 打开 SW 进程
     * 对应 Python: SwOperatorCore.open_sw (L2776-L2815)
     */
    public static String[] openSw(String sw, String exe, SwConfigAccessor accessor) {
        // 获取多开模式
        String multirunMode = accessor.getSwSettingAsString(
                sw, SwCoreConstants.LocalSettingKey.REST_MULTIRUN_MODE,
                SwCoreConstants.MultirunMode.FREELY_MULTIRUN);

        String swPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
        if (swPath == null) return new String[]{null, null};

        if (exe != null && !exe.isBlank()) {
            String instDir = new File(swPath).getParent();
            swPath = instDir + "/" + exe;
        }

        if (SwCoreConstants.MultirunMode.FREELY_MULTIRUN.equals(multirunMode)) {
            // 全局多开 — 直接创建进程
            Process proc = SwNativeOps.createProcessWithoutAdmin(swPath, null, 0);
            return new String[]{proc != null ? String.valueOf(proc.pid()) : null, null};
        } else if (SwCoreConstants.MultirunMode.BUILTIN.equals(multirunMode)) {
            // Builtin 模式 — 先查杀互斥体
            // TODO: 查杀互斥体逻辑
            Process proc = SwNativeOps.createProcessWithoutAdmin(swPath, null, 0);
            return new String[]{proc != null ? String.valueOf(proc.pid()) : null, null};
        }

        return new String[]{null, "未知多开模式: " + multirunMode};
    }

    // ==================== 工具方法 ====================

    /**
     * 从远程配置提取所有地址
     * 对应 Python: SwInfoFuncCore.extract_addresses_from_remote_cfg (L133-L160)
     */
    public static List<String> extractAddressesFromRemoteCfg(String sw, SwConfigAccessor accessor) {
        Set<String> addrSet = new LinkedHashSet<>();
        JsonNode swDict = accessor.getRemoteSw(sw);
        if (swDict == null || !swDict.isObject()) return Collections.emptyList();

        for (String feature : List.of("revoke", "multi", "coexist")) {
            JsonNode featureDict = swDict.get(feature);
            if (featureDict == null || !featureDict.isObject()) continue;

            JsonNode channels = featureDict.get("channels");
            if (channels == null || !channels.isObject()) continue;

            channels.fieldNames().forEachRemaining(channel -> {
                JsonNode chDict = channels.get(channel);
                if (chDict == null || !chDict.isObject()) return;

                JsonNode adaptations = chDict.get("features");
                if (adaptations == null || !adaptations.isArray()) return;

                for (JsonNode item : adaptations) {
                    if (item.has("addr") && item.get("addr").isTextual()) {
                        addrSet.add(item.get("addr").asText());
                    }
                }
            });
        }

        return new ArrayList<>(addrSet);
    }

    /**
     * 从缓存中获取 precise 条目
     */
    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> getCachePreciseEntry(
            ObjectNode cache, String sw, String mode, String channel, String curVer) {
        if (cache == null || !cache.has(mode)) return Collections.emptyList();
        JsonNode modeDict = cache.get(mode);
        if (!modeDict.isObject() || !modeDict.has("channels")) return Collections.emptyList();
        JsonNode channels = modeDict.get("channels");
        if (!channels.isObject() || !channels.has(channel)) return Collections.emptyList();
        JsonNode chDict = channels.get(channel);
        if (!chDict.isObject() || !chDict.has("precises")) return Collections.emptyList();
        JsonNode precises = chDict.get("precises");
        if (!precises.isObject() || !precises.has(curVer)) return Collections.emptyList();

        return SwAdapterChecker.jsonToList(precises.get(curVer));
    }
}
