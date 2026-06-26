package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;

/**
 * PID/互斥体操作 — 管理进程与互斥体的映射关系
 * <p>
 * 对应 Python: SwInfoFuncCore.record_sw_pid_mutex_dict_when_start_login,
 * get_pids_has_mutex_from_record, set_pid_mutex_all_values_to_false,
 * update_has_mutex_from_pid_mutex, SwOperatorCore.try_kill_mutex_if_need_and_return_remained_pids,
 * SwOperatorCore.kill_all_mutexes_now
 * <p>
 * 注意: 互斥体查杀需要 JNA/native 调用，此处提供数据管理和 Stub 实现。
 *
 * 依赖: SwConfigAccessor, SwAccountOps
 */
public final class SwPidMutexOps {

    private static final Logger LOG = LoggerFactory.getLogger(SwPidMutexOps.class);
    private SwPidMutexOps() {}

    private static final String RELAY_KEY = SwCoreConstants.AccKeys.RELAY;
    private static final String PID_MUTEX_KEY = SwCoreConstants.AccKeys.PID_MUTEX;

    /**
     * 在平台登录前，存储 PID 和互斥体的映射关系字典
     * 对应 Python: record_sw_pid_mutex_dict_when_start_login (L799-L824)
     *
     * @param sw            软件标识
     * @param allHasMutex   是否默认所有进程都有互斥体
     * @param accessor      配置访问器
     * @param pidProvider   提供 PID 列表的函数
     * @param accountOps    账号操作器
     */
    public static void recordPidMutexDictWhenStartLogin(
            String sw, boolean allHasMutex,
            SwConfigAccessor accessor,
            SwAccountOps.AccountOpsProvider accountOps,
            SwConfigAccessor.Provider configProvider) {

        // 获取所有 SW 进程 PID
        List<Integer> pids = getPids(sw, accessor, configProvider);
        Map<String, Boolean> pidMutexDict = new LinkedHashMap<>();

        if (allHasMutex) {
            LOG.info("[互斥体] 将所有进程设为含有互斥体: true");
            for (int pid : pids) {
                pidMutexDict.put(String.valueOf(pid), true);
            }
        } else {
            // 从记录中获取已有互斥体的 PID
            List<Integer> pidsWithMutex = tryKillMutexAndReturnRemainedPids(
                    sw, accessor, configProvider, accountOps);
            for (int pid : pids) {
                pidMutexDict.put(String.valueOf(pid), pidsWithMutex.contains(pid));
            }
        }

        LOG.info("[互斥体] 登录前所有互斥体: {}", pidMutexDict);

        // 保存到账号数据的 relay.pid_mutex 节点
        accountOps.updateSwAccData(sw, Map.of(RelayKey(), ""),
                Map.of(PidMutexKey(), pidMutexDict));
    }

    /**
     * 从记录中获取所有有互斥体的 PID 列表
     * 对应 Python: get_pids_has_mutex_from_record (L826-L832)
     *
     * @param sw         软件标识
     * @param accountOps 账号操作器
     * @return PID 列表
     */
    public static List<Integer> getPidsHasMutexFromRecord(
            String sw, SwAccountOps.AccountOpsProvider accountOps) {

        JsonNode hasMutexDict = accountOps.getSwAccData(sw, RelayKey(), PidMutexKey());
        if (hasMutexDict == null || !hasMutexDict.isObject()) {
            return Collections.emptyList();
        }

        List<Integer> result = new ArrayList<>();
        hasMutexDict.fieldNames().forEachRemaining(key -> {
            JsonNode val = hasMutexDict.get(key);
            if (val != null && val.asBoolean(false)) {
                try {
                    result.add(Integer.parseInt(key));
                } catch (NumberFormatException e) {
                    // 跳过非数字 key
                }
            }
        });
        return result;
    }

    /**
     * 将所有 PID 的互斥体标记设为 false
     * 对应 Python: set_pid_mutex_all_values_to_false (L834-L849)
     *
     * @param sw         软件标识
     * @param accountOps 账号操作器
     * @return true 如果成功
     */
    public static boolean setPidMutexAllValuesToFalse(
            String sw, SwAccountOps.AccountOpsProvider accountOps) {

        JsonNode pidMutexData = accountOps.getSwAccData(sw, RelayKey(), PidMutexKey());
        if (pidMutexData == null || !pidMutexData.isObject()) {
            return false;
        }

        Map<String, Object> updates = new LinkedHashMap<>();
        pidMutexData.fieldNames().forEachRemaining(key -> {
            updates.put(key, false);
        });

        if (!updates.isEmpty()) {
            accountOps.updateSwAccData(sw, Map.of(RelayKey(), PidMutexKey()), updates);
        }
        return true;
    }

    /**
     * 将 pid_mutex 记录中的情况加载回所有已登录账号
     * 对应 Python: update_has_mutex_from_pid_mutex (L851-L873)
     *
     * @param sw         软件标识
     * @param accountOps 账号操作器
     * @return {success, hasMutex}
     */
    public static boolean[] updateHasMutexFromPidMutex(
            String sw, SwAccountOps.AccountOpsProvider accountOps) {

        JsonNode swDict = accountOps.getSwAccData(sw);
        if (swDict == null || !swDict.isObject()) {
            return new boolean[]{false, false};
        }

        JsonNode pidMutexDictNode = accountOps.getSwAccData(sw, RelayKey(), PidMutexKey());
        if (pidMutexDictNode == null || !pidMutexDictNode.isObject()) {
            return new boolean[]{false, false};
        }

        java.util.concurrent.atomic.AtomicBoolean hasMutex = new java.util.concurrent.atomic.AtomicBoolean(false);

        // 遍历 swDict 中的所有账号
        swDict.fieldNames().forEachRemaining(acc -> {
            JsonNode accDetails = swDict.get(acc);
            if (accDetails != null && accDetails.isObject()) {
                JsonNode pidNode = accDetails.get("pid");
                if (pidNode != null) {
                    String pidKey = String.valueOf(pidNode.asLong());
                    Boolean accMutex = pidMutexDictNode.has(pidKey)
                            ? pidMutexDictNode.get(pidKey).asBoolean(true)
                            : true;
                    if (accMutex) hasMutex.set(true);
                    accountOps.updateSwAccData(sw, Map.of(acc, ""),
                            Map.of("has_mutex", accMutex));
                }
            }
        });

        return new boolean[]{true, hasMutex.get()};
    }

    // ==================== JNA Stub: 互斥体查杀 ====================

    /**
     * 尝试查杀互斥体并返回剩余有互斥体的 PID 列表
     * 对应 Python: SwOperatorCore.try_kill_mutex_if_need_and_return_remained_pids (L2092-L2112)
     * <p>
     * 需要 JNA 调用 Win32 FindFirstWinHandle / NtClose。
     * 此处返回空列表作为 Stub。
     *
     * @param sw            软件标识
     * @param accessor      配置访问器
     * @param configProvider 配置提供者
     * @param accountOps    账号操作器
     * @return 剩余有互斥体的 PID 列表
     */
    public static List<Integer> tryKillMutexAndReturnRemainedPids(
            String sw, SwConfigAccessor accessor,
            SwConfigAccessor.Provider configProvider,
            SwAccountOps.AccountOpsProvider accountOps) {

        // 获取互斥体通配符
        List<String> mutantWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.MUTEX_HANDLE_WILDCARDS, Collections.emptyList());

        if (mutantWildcards.isEmpty()) {
            LOG.info("[互斥体] 未获取到互斥体通配词，不进行查找");
            return Collections.emptyList();
        }

        // 获取所有 SW 进程 PID
        List<Integer> pids = getPids(sw, accessor, configProvider);
        LOG.debug("[互斥体] 当前所有进程: {}", pids);

        // TODO: 调用 JNA 查杀互斥体
        // handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards(pids, mutantWildcards)
        // handle_utils.pywinhandle_close_handles(handleInfos)

        LOG.debug("[互斥体] 查杀后剩余互斥体: (Stub — 需要 JNA)");
        return Collections.emptyList();
    }

    /**
     * 查杀所有互斥体
     * 对应 Python: SwOperatorCore.kill_all_mutexes_now (L2065-L2090)
     * <p>
     * 需要 JNA。此处返回 Stub。
     *
     * @return {success, message}
     */
    public static String[] killAllMutexesNow(
            String sw, SwConfigAccessor accessor,
            SwConfigAccessor.Provider configProvider) {

        List<String> mutantWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.MUTEX_HANDLE_WILDCARDS, Collections.emptyList());
        List<String> configWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.CONFIG_HANDLE_WILDCARDS, Collections.emptyList());

        List<String> allWildcards = new ArrayList<>(mutantWildcards);
        allWildcards.addAll(configWildcards);

        if (allWildcards.isEmpty()) {
            return new String[]{null, "未查询到" + sw + "的互斥体列表和配置文件列表!"};
        }

        List<Integer> pids = getPids(sw, accessor, configProvider);
        // TODO: JNA 查杀
        LOG.info("[互斥体] killAllMutexesNow: pids={}, wildcards={} (Stub)", pids, allWildcards);
        return new String[]{null, "需要 JNA 实现互斥体查杀"};
    }

    // ==================== 辅助方法 ====================

    private static List<Integer> getPids(String sw, SwConfigAccessor accessor,
                                          SwConfigAccessor.Provider configProvider) {
        // 获取所有 SW 进程 PID
        // 对应 Python: get_sw_all_exe_pids
        List<String> exeWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());

        if (exeWildcards.isEmpty()) return Collections.emptyList();

        // TODO: 需要 process_utils.psutil_get_pids_by_wildcards
        // 此处返回空列表作为 Stub
        LOG.debug("[PID] getSwAllExePids: exeWildcards={} (Stub)", exeWildcards);
        return Collections.emptyList();
    }

    private static String RelayKey() {
        return SwCoreConstants.AccKeys.RELAY;
    }

    private static String PidMutexKey() {
        return SwCoreConstants.AccKeys.PID_MUTEX;
    }
}
