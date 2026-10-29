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
    /** 单轮互斥体查杀的**默认总预算**（毫秒）：到点就停，避免整轮被个别会阻塞的命名管道句柄拖住 */
    public static final long DEFAULT_KILL_BUDGET_MS = 5000;

    public static String[] killAllMutexesNow(String sw, SwConfigAccessor accessor, SwNativeOps nativeOps) {
        return killAllMutexesNow(sw, accessor, nativeOps, DEFAULT_KILL_BUDGET_MS);
    }

    /**
     * @param budgetMs 本轮扫描的**总预算**（毫秒）；≤0 = 不限时。
     *                 超预算只影响"扫得全不全"，**不影响正确性** —— 查杀不存在的互斥体是空操作，
     *                 所以到点就停、先拿已命中的结果继续（用户 2026-10-12 探讨后定）。
     */
    public static String[] killAllMutexesNow(String sw, SwConfigAccessor accessor, SwNativeOps nativeOps,
                                             long budgetMs) {
        long tStart = System.currentTimeMillis();
        // ⚠️ 这里**故意不设任务阶段**：它只是上层流程（账号登录 / 批量多开）里的**一个子步骤**，
        //    由上层通过 TaskContext.phase("…") 统一负责。早先在这里设了"查杀互斥体"✗，
        //    结果把上层正在显示的"账号 3/10：开窗"覆盖掉、界面一直卡在"查杀互斥体"（用户 2026-10-12 实测指出）。
        com.jfmultichat.core.task.TaskContext.checkpoint();
        List<String> mutantWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.MUTEX_HANDLE_WILDCARDS, Collections.emptyList());
        List<String> configWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.CONFIG_HANDLE_WILDCARDS, Collections.emptyList());

        List<String> allWildcards = new ArrayList<>(mutantWildcards);
        allWildcards.addAll(configWildcards);

        if (allWildcards.isEmpty()) {
            return new String[]{null, "未查询到" + sw + "的互斥体列表和配置文件列表!"};
        }

        List<Integer> pids = allExePidsOf(sw, accessor, nativeOps);
        // **关键优化**（用户 2026-10-07）：先按"已知无互斥体"集合精简候选 ——
        // 之前只登记不过滤，导致每轮都要把所有实例的句柄逐个查名字，开得越多越慢。
        List<Integer> candidates = WinHandleOps.filterCleanedPids(pids);
        if (candidates.size() < pids.size()) {
            LOG.info("[互斥体] {} 枚举到 {} 个 pid，跳过 {} 个已知无互斥体的（长期缓存），本轮只扫 {} 个",
                    sw, pids.size(), pids.size() - candidates.size(), candidates);
        } else {
            LOG.info("[互斥体] {} 本轮按 exe 通配符枚举到 pid={}（通配词 {}）", sw, candidates, allWildcards);
        }
        if (candidates.isEmpty()) {
            return new String[]{Boolean.TRUE.toString(),
                    sw + "已经不含互斥体和文件锁!（全部进程都在免扫缓存里）"};
        }
        List<WinHandleOps.HandleRef> found = WinHandleOps.findHandles(candidates, allWildcards,
                budgetMs > 0 ? System.currentTimeMillis() + budgetMs : 0L);
        LOG.info("[互斥体] {} 本轮命中 {} 个：{}（预算 {}ms）", sw, found.size(), found,
                budgetMs > 0 ? budgetMs : -1);
        if (found.isEmpty()) {
            return new String[]{Boolean.TRUE.toString(), sw + "已经不含互斥体和文件锁!"};
        }
        int closed = WinHandleOps.closeHandles(found);
        for (WinHandleOps.HandleRef h : found) WinHandleOps.markPidsClean(Collections.singletonList(h.pid));
        LOG.info("[互斥体] {} 查杀耗时 {}ms（候选 {} 个 pid，命中 {} 个，关闭 {} 个）",
                sw, System.currentTimeMillis() - tStart, candidates.size(), found.size(), closed);
        if (closed > 0) {
            return new String[]{Boolean.TRUE.toString(),
                    sw + "已关闭互斥体和解锁文件!（命中 " + found.size() + " 个，关闭 " + closed + " 个）"};
        }
        return new String[]{Boolean.FALSE.toString(), sw + "关闭互斥体和解锁文件失败!"};
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
            LOG.info("[互斥体] 未获取到互斥体通配词，跳过查找");
            return Collections.emptyList();
        }

        List<Integer> pids = allExePidsOf(sw, accessor, nativeOps);
        List<WinHandleOps.HandleRef> before = WinHandleOps.findHandles(pids, mutantWildcards);
        if (Boolean.TRUE.equals(kill) && !before.isEmpty()) {
            WinHandleOps.closeHandles(before);
            before = WinHandleOps.findHandles(pids, mutantWildcards);      // 关完再查一遍（与 Python 一致）
        }
        List<Integer> pidsWithMutex = new ArrayList<>();
        for (WinHandleOps.HandleRef h : before) {
            if (!pidsWithMutex.contains(h.pid)) pidsWithMutex.add(h.pid);
        }
        LOG.info("[互斥体] tryKillMutexIfNeeded: kill={}, 仍有互斥体的 pid={}", kill, pidsWithMutex);
        return pidsWithMutex;
    }

    /**
     * 该平台"自己安装目录下"的全部进程 PID（通配符找 → 去子进程 → 去不在安装目录的）.
     * 批量多开要用它做"旧程序 / 现有程序"两次快照的差集。
     */
    public static List<Integer> allExePidsOf(String sw, SwConfigAccessor accessor, SwNativeOps nativeOps) {
        List<String> exeWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());
        if (exeWildcards.isEmpty()) return Collections.emptyList();
        List<Integer> pids = new ArrayList<>();
        nativeOps.getPidsByWildcardsAndGroup(exeWildcards).values().forEach(pids::addAll);
        pids = SwNativeOps.removeChildPids(pids);
        String instPath = accessor.tryGetPathOf(sw, "inst_path");
        if (instPath != null) {
            java.io.File parent = new java.io.File(instPath).getParentFile();
            if (parent != null) pids = SwNativeOps.removePidsNotInPath(pids, parent.getPath());
        }
        return pids;
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

            // 4. target 未指定 → 先识别当前状态，再取反
            if (target == null) {
                SwAdapterChecker.ChannelsResult res = SwAdapterChecker.identifyChannels(
                        sw, mode, java.util.Collections.singletonList(channel),
                        coexistChannel, ordinal, false, accessor, cache);
                SwAdapterChecker.DetectionResult chRes = res.channels.get(channel);
                if (chRes == null || chRes.status == null) {
                    return new String[]{null, "无法识别当前" + modeText + "状态，补丁未应用"};
                }
                target = !chRes.status;
                LOG.info("[DLL] 自动判定目标状态: {}", target);
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
                    // 首次修改前备份（不覆盖已有备份）
                    Path bakPath = Path.of(realDllPath + ".bak");
                    if (!Files.exists(bakPath)) {
                        try {
                            Files.copy(dllPath, bakPath);
                        } catch (Exception e) {
                            LOG.warn("[DLL] 备份失败: {}", e.getMessage());
                        }
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
                        String hexStr = target
                                ? (patch.get("modified") != null ? patch.get("modified").toString() : "")
                                : (patch.get("original") != null ? patch.get("original").toString() : "");
                        if (hexStr.isEmpty()) continue;

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

                // 9. 统一 flush，并立刻解除映射（否则同进程内紧接着的识别会读到旧页/被占用）
                for (MappedByteBuffer mm : mmaps) {
                    mm.force();
                    SwPatchCacheBuilder.unmap(mm);
                }

                String action = target ? "开启" : "关闭";
                return new String[]{null, "成功" + action + ": " + modeText};

            } catch (Exception e) {
                LOG.error("[DLL] 切换失败: {}", e.getMessage(), e);
                // 出错时不 flush，直接 close（放弃所有改动）
                return new String[]{null, "切换" + modeText + "失败！请稍后重试！"};
            } finally {
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

        // 缓存里渠道级 relations 优先（扫描成功与否都会写，见 SwPatchCacheBuilder.relationsOfChannel）
        JsonNode relNode = cache == null ? null
                : cache.path(sw).path(mode).path(SwCoreConstants.RemoteSwKey.CHANNELS)
                        .path(channel).get("relations");
        if (relNode != null && relNode.isObject()) {
            Map<String, List<String>> out = new LinkedHashMap<>();
            for (String key : List.of("parents", "children", "friends")) {
                List<String> list = new ArrayList<>();
                JsonNode arr = relNode.get(key);
                if (arr != null && arr.isArray()) arr.forEach(n -> list.add(n.asText()));
                out.put(key, list);
            }
            return out;
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

            // 6. 更新配置（updateSwAccData 只取 frontAddr 的第一个 value 作为账号 id）
            //    只记渠道；序号可从克隆 exe 名（exe_wildcard）反推，不再落库
            String newCoexistExeName = exeWildcard.replace("?", ordinal);
            SwAccountOps.ensureCoexistAccFormatted(sw, newCoexistExeName, accountOps);
            accountOps.updateSwAccData(sw, Map.of("acc", newCoexistExeName),
                    Map.of("channel", coexistChannel));

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
                JsonNode coexistChannelNode = accessor.getSwAccData(sw, acc,
                        SwCoreConstants.AccKeys.COEXIST_CHANNEL);
                JsonNode ordinalNode = accessor.getSwAccData(sw, acc, SwCoreConstants.AccKeys.ORDINAL);

                // 渠道/序号优先取账号数据；缺了就推导（序号可从克隆 exe 名反推）
                String coexistChannel = (coexistChannelNode != null && coexistChannelNode.isTextual())
                        ? coexistChannelNode.asText() : null;
                if (coexistChannel == null || coexistChannel.isEmpty()) {
                    coexistChannel = SwPatchService.selectedCoexistMode(sw, accessor);
                }
                String ordinal = (ordinalNode != null && ordinalNode.isTextual())
                        ? ordinalNode.asText() : null;
                if (ordinal == null || ordinal.isEmpty()) {
                    ordinal = SwPatchService.deriveOrdinal(sw, acc, coexistChannel, accessor);
                }

                if (coexistChannel == null || ordinal == null) {
                    failedMsgDict.put(acc, "未适配");
                    continue;
                }

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
     * **单个实例的完整启动流程（核心方法，多处复用）**：查杀互斥体/文件锁 → 以普通用户权限启动.
     *
     * <p>为什么抽出来：单点"登录"、批量多开的每一轮、（将来）账号登录流程、（将来）取登录窗口尺寸时
     * 自动开窗 —— 都要这一套，各自写一遍必然走形（之前批量里"先 kill 一次、openSw 内部又 kill 一次"
     * 就是重复劳动）。统一从这里走。
     *
     * @return {pid 字符串 或 null, 错误信息 或 null, 查杀结果说明}
     */
    public static String[] launchOneInstance(String sw, String exe, SwConfigAccessor accessor,
                                             SwNativeOps nativeOps) {
        return launchOneInstance(sw, exe, accessor, nativeOps, false);
    }

    /**
     * @param skipKill {@code true} = 调用方**刚刚已经查杀过**（如批量"先杀一次、再连开 N 个"），本轮不再重复扫描
     */
    public static String[] launchOneInstance(String sw, String exe, SwConfigAccessor accessor,
                                             SwNativeOps nativeOps, boolean skipKill) {
        String mutexMsg = "";
        // 启动**之前**先记下本平台现有的 pid：新窗口一旦开出来，就说明它们此刻都不含互斥体了
        // → 记进长期免扫缓存（用户 2026-10-07 的方案，解决"越开越慢"）
        List<Integer> prePids = allExePidsOf(sw, accessor, nativeOps);
        if (!skipKill && needsMutexKill(sw, accessor)) {
            String[] killed = killAllMutexesNow(sw, accessor, nativeOps);
            mutexMsg = killed[1] == null ? "" : killed[1];
        } else if (skipKill) {
            mutexMsg = "（调用方刚刚已查杀，本轮跳过）";
        }
        String[] launched = launchProcess(sw, exe, accessor);
        if (launched[0] != null && !"-1".equals(launched[0])) {
            WinHandleOps.markPidsClean(prePids);      // 启动前的进程此刻必然都无互斥体
            LOG.info("[登录] 单个实例启动: sw={}, pid={}, 查杀={}, 免扫缓存登记 {} 个旧 pid（缓存共 {} 个）",
                    sw, launched[0], mutexMsg, prePids.size(), WinHandleOps.killedPidCacheSize());
        } else {
            LOG.info("[登录] 单个实例启动: sw={}, pid={}, 查杀={}", sw, launched[0], mutexMsg);
        }
        return new String[]{launched[0], launched[1], mutexMsg};
    }

    /**
     * **这个平台要不要查杀互斥体**（= 是不是 builtin 多开）.
     *
     * <p>用户 2026-10-11 澄清的真相：{@code freely} 的含义是**程序目录下的 DLL 打过补丁**
     * （补丁把"创建互斥体"这段去掉了 ✓）→ 此时**任何情况下都不需要查杀** ✓；
     * 判定方式应当是**探测补丁状态**（旧版 {@code get_sw_multirun_mode} 就是先调
     * {@code check_if_sw_can_freely_multirun} ✓，只有探测不出来才回落到配置值 ✓）。
     *
     * <p>⚠️ 修（2026-10-11）：原来这里直接读 {@code rest_multirun_mode} 配置，而**前端从不写这个 key**
     * → 默认值 {@code freely_multirun} 永远生效 → **内部查杀一次都没跑过** ✓（日志里
     * {@code 查杀=,} 为空就是这个原因 ✓）。现在：
     * <ol>
     *   <li>配置**显式**写了 {@code freely_multirun} → 尊重它（用户手动选择）</li>
     *   <li>其它情况（含没写）→ 按 **builtin** 处理（要查杀）—— 与旧版"探测不出就当 builtin"一致，
     *       且查杀不存在的互斥体是无害空操作，比"漏查杀导致唤起老实例"安全得多</li>
     * </ol>
     * TODO（下一步）：接入补丁状态探测（{@code SwAdapterChecker} 里的 multi/bin 补丁识别），
     * 打过补丁的平台就完全跳过查杀（按平台缓存结果，补丁扫描不便宜）。
     */
    private static boolean needsMutexKill(String sw, SwConfigAccessor accessor) {
        String mode = accessor.getSwSettingAsString(
                sw, SwCoreConstants.LocalSettingKey.REST_MULTIRUN_MODE, "");
        boolean freely = SwCoreConstants.MultirunMode.FREELY_MULTIRUN.equals(mode);
        if (freely) LOG.info("[登录] {} 配置为 freely 多开（已打补丁），跳过互斥体查杀", sw);
        return !freely;
    }

    /** 只负责"降权启动"这一步（不含查杀），供 {@link #launchOneInstance} 与 {@link #openSw} 共用 */
    private static String[] launchProcess(String sw, String exe, SwConfigAccessor accessor) {
        String swPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
        if (swPath == null) return new String[]{null, null};

        if (exe != null && !exe.isBlank()) {
            String instDir = new File(swPath).getParent();
            swPath = instDir + "/" + exe;
        }
        int pid = SwNativeOps.createProcessWithoutAdmin(swPath, null, 0);
        if (pid == 0) {
            return new String[]{null, "启动失败: " + swPath};
        }
        // pid == -1：已通过 explorer.exe 代启（父进程是 explorer，拿不到目标 PID，但确实是启动了）
        return new String[]{String.valueOf(pid), null};
    }

    /**
     * 打开 SW 并返回**登录窗口句柄**
     * 对应 Python: SwOperatorCore.open_sw_and_return_hwnd (L2404-L2428)
     *
     * <p>流程（与旧版一致）：
     * ① 取登录窗口匹配规则（取不到 → 该平台未适配）
     * ② 记下**已经存在**的登录窗口（排除表：新窗口不能是它们）
     * ③ {@link #launchOneInstance}（查杀互斥体 + 降权启动）拿到新 pid
     * ④ **轮询等这个 pid 上出现唯一的登录窗口**（默认 20s）
     *
     * @return {hwnd, pid}；失败返回 {0, pid 或 0}
     */
    public static int[] openSwAndReturnHwnd(String sw, String exe,
                                            SwConfigAccessor accessor, SwNativeOps nativeOps) {
        SwInfoFuncCore infoCore = new SwInfoFuncCore(accessor, nativeOps, null, null);
        List<Map<String, Object>> rules = SwAdapterChecker.getWndClassMatchingDicts(sw, "login", accessor);
        if (rules == null || rules.isEmpty()) {
            LOG.warn("[登录] {} 没有登录窗口匹配规则（未适配），无法等窗口", sw);
            return new int[]{0, 0};
        }
        // 分步计时：这三步里最慢的一步就是"多号登录越开越慢"的真凶（用户 2026-10-07 要求查明）
        long t0 = System.currentTimeMillis();
        List<Integer> excluded = new ArrayList<>(infoCore.getLoginHwndsOfSw(sw));
        long t1 = System.currentTimeMillis();
        if (!excluded.isEmpty()) {
            LOG.info("[登录] 启动前已存在登录窗口 {}, 将排除它们", excluded);
        }
        String[] one = launchOneInstance(sw, exe, accessor, nativeOps);
        long t2 = System.currentTimeMillis();
        if (one[0] == null) {
            LOG.warn("[登录] 启动失败: {}", one[1]);
            return new int[]{0, 0};
        }
        int pid;
        try {
            pid = Integer.parseInt(one[0]);
        } catch (NumberFormatException e) {
            LOG.warn("[登录] 经 explorer 代启拿不到 PID，无法按 pid 等窗口: {}", one[0]);
            return new int[]{0, 0};
        }
        int hwnd = infoCore.waitHwndExclusivelyForPid(sw, pid, "login", excluded, 20);
        LOG.info("[登录] 开窗计时: 扫已存在登录窗 {}ms + 启动 {}ms + 等新窗口 {}ms",
                t1 - t0, t2 - t1, System.currentTimeMillis() - t2);
        return new int[]{hwnd, pid};
    }

    /**
     * **获取登录窗口尺寸（格式 `宽*高`）**.
     *
     * <p>对应 Python: `SwOperatorCore.get_login_size`（sw_func_core.py L2831）：
     * ① 已经有登录窗口 → 直接量；② 没有 → **自动开一个**，量完把那个窗口关掉（不留垃圾窗口）。
     *
     * @return {尺寸字符串 或 null, 错误信息 或 null}
     */
    public static String[] getLoginSize(String sw, SwConfigAccessor accessor) {
        SwInfoFuncCore infoCore = new SwInfoFuncCore(accessor, SwNativeOps.INSTANCE, null, null);
        List<Integer> loginHwnds = infoCore.getLoginHwndsOfSw(sw);
        boolean weOpened = false;
        if (loginHwnds == null || loginHwnds.isEmpty()) {
            // 没有登录窗口 → 自动开一个（与旧版一致）
            LOG.info("[登录] 没有登录窗口，自动打开一个来量尺寸");
            int[] opened = openSwAndReturnHwnd(sw, null, accessor, SwNativeOps.INSTANCE);
            if (opened[0] == 0) {
                return new String[]{null, "打开登录窗口失败或超时未检测到窗口（请确认该平台已适配窗口规则）"};
            }
            loginHwnds = Collections.singletonList(opened[0]);
            weOpened = true;
        }
        try {
            Map<String, Object> details = SwNativeOps.getHwndDetails(loginHwnds.get(0));
            int width = ((Number) details.getOrDefault("width", 0)).intValue();
            int height = ((Number) details.getOrDefault("height", 0)).intValue();
            if (width <= 0 || height <= 0) {
                return new String[]{null, "登录窗口尺寸读取失败（hwnd=" + loginHwnds.get(0) + "）"};
            }
            String size = width + "*" + height;
            LOG.info("[登录] 登录窗口尺寸: sw={}, hwnd={}, size={}", sw, loginHwnds.get(0), size);
            return new String[]{size, null};
        } finally {
            if (weOpened) {
                // 只关我们自己开出来的那个（用户已开着的登录窗口不动）
                SwNativeOps.tryCloseHwndsAndReturnRemained(new LinkedHashSet<>(loginHwnds));
            }
        }
    }

    /**
     * 打开 SW 进程（返回 {pid 字符串 或 null, 错误信息 或 null}）
     * 对应 Python: SwOperatorCore.open_sw (L2776-L2815)
     *
     * <p>实现统一收口到 {@link #launchOneInstance}（查杀互斥体 → 降权启动），避免两处各写一遍走形。
     */
    public static String[] openSw(String sw, String exe, SwConfigAccessor accessor) {
        String multirunMode = accessor.getSwSettingAsString(
                sw, SwCoreConstants.LocalSettingKey.REST_MULTIRUN_MODE,
                SwCoreConstants.MultirunMode.FREELY_MULTIRUN);
        if (!SwCoreConstants.MultirunMode.BUILTIN.equals(multirunMode)
                && !SwCoreConstants.MultirunMode.FREELY_MULTIRUN.equals(multirunMode)) {
            return new String[]{null, "未知多开模式: " + multirunMode};
        }
        String[] launched = launchOneInstance(sw, exe, accessor, SwNativeOps.INSTANCE);
        return new String[]{launched[0], launched[1]};
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
        if (cache == null) return Collections.emptyList();
        ObjectNode plat = SwPatchCacheBuilder.platformNodeIfPresent(cache, sw);
        JsonNode modeDict = plat != null ? plat.get(mode) : null;
        if (modeDict == null) modeDict = cache.get(mode);   // 兼容老扁平结构
        if (modeDict == null || !modeDict.isObject() || !modeDict.has("channels")) return Collections.emptyList();
        JsonNode channels = modeDict.get("channels");
        if (!channels.isObject() || !channels.has(channel)) return Collections.emptyList();
        JsonNode chDict = channels.get(channel);
        if (!chDict.isObject()) return Collections.emptyList();
        JsonNode precises = chDict.get(SwCoreConstants.RemoteSwKey.PRECISES);
        if (precises == null) precises = chDict.get(SwCoreConstants.RemoteSwKey.PRECISES_LEGACY);
        if (!precises.isObject() || !precises.has(curVer)) return Collections.emptyList();

        return SwAdapterChecker.jsonToList(precises.get(curVer));
    }
}
