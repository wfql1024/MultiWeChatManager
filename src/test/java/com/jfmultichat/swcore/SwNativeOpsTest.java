package com.jfmultichat.swcore;

import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.HashSet;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 测试 SwNativeOps 的三种内存映射枚举方案 + 去子进程逻辑。
 * <p>
 * 测试 PID 固定为 32568（请根据实际情况调整）。
 */
class SwNativeOpsTest {

    private static final Logger LOG = LoggerFactory.getLogger(SwNativeOpsTest.class);
    private static final int TEST_PID = 32568;

    // ==================== 去子进程测试 ====================

    @Test
    void filterOutChildPids_shouldKeepOnlyRoot() {
        // 你提供的测试数据：[72740, 2228, 36704, 19408, 45892]
        // 只有 72740 是根进程
        List<Integer> input = List.of(72740, 2228, 36704, 19408, 45892);

        // 测试去子
        List<Integer> result = SwNativeOps.filterOutChildPids(input);
        System.out.println("[去子测试] 输入=" + input + " 结果=" + result);

        // 只保留 72740
        assertEquals(1, result.size(), "应该只保留 1 个根进程");
        assertEquals(72740, result.get(0), "应该保留 72740");
    }

    @Test
    void filterOutChildPids_emptyList() {
        List<Integer> result = SwNativeOps.filterOutChildPids(List.of());
        assertTrue(result.isEmpty());
    }

    @Test
    void filterOutChildPids_nonExistentPid() {
        // 传入一个不存在的 PID，应该保留（无法查询父进程时保留）
        List<Integer> result = SwNativeOps.filterOutChildPids(List.of(99999));
        // 不存在进程的父进程查询会失败，按逻辑应保留
        LOG.info("[去子测试] 不存在的 PID 99999 结果: {}", result);
    }

    // ==================== Psapi 方案 ====================

    @Test
    void enumerateByPsapi_shouldListModules() {
        List<String> modules = SwNativeOps.enumerateByPsapi(TEST_PID);
        LOG.info("[Psapi] PID={} 枚举到 {} 个模块", TEST_PID, modules.size());
        for (int i = 0; i < Math.min(modules.size(), 20); i++) {
            LOG.info("[Psapi]   [{}] {}", i, modules.get(i));
        }
    }

    // ==================== ToolHelp 方案 ====================

    @Test
    void enumerateByToolHelp_shouldListModules() {
        List<String> modules = SwNativeOps.enumerateByToolHelp(TEST_PID);
        LOG.info("[ToolHelp] PID={} 枚举到 {} 个模块", TEST_PID, modules.size());
        for (int i = 0; i < Math.min(modules.size(), 20); i++) {
            LOG.info("[ToolHelp]   [{}] {}", i, modules.get(i));
        }
    }

    // ==================== VirtualQueryEx 方案 ====================

    @Test
    void enumerateByVirtualQueryEx_shouldListAllMappedFiles() {
        List<String> paths = SwNativeOps.enumerateByVirtualQueryEx(TEST_PID);
        LOG.info("[VirtualQueryEx] PID={} 枚举到 {} 个映射文件", TEST_PID, paths.size());
        for (int i = 0; i < Math.min(paths.size(), 100); i++) {
            LOG.info("[VirtualQueryEx]   [{}] {}", i, paths.get(i));
        }
        if (paths.size() > 100) {
            LOG.info("[VirtualQueryEx]   ... and {} more", paths.size() - 100);
        }
    }

    // ==================== NtQueryVirtualMemory 方案（当前生产实现） ====================

    @Test
    void queryMemoryMapPaths_shouldFindWeixinConfigPath() {
        SwNativeOps ops = new SwNativeOps();
        List<String> exeWildcards = List.of("Weixin?.exe", "Weixi?.exe");
        String regex = "^(.*?)/all_users/config(?:/[^/]+)*$";

        List<String> results = ops.queryMemoryMapPaths("Weixin", exeWildcards, regex);

        LOG.info("[NtQM] queryMemoryMapPaths 结果数量: {}, 内容: {}", results.size(), results);

        if (results.isEmpty()) {
            LOG.warn("[NtQM] 未匹配到路径 — 请确认 Weixin 进程正在运行中");
        }
    }

    @Test
    void queryMemoryMapPaths_shouldFindVoipEngineDll() {
        SwNativeOps ops = new SwNativeOps();
        List<String> exeWildcards = List.of("Weixin?.exe", "Weixi?.exe");
        String regex = "(.*/[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+)/VoipEngine\\.dll$";

        List<String> results = ops.queryMemoryMapPaths("Weixin", exeWildcards, regex);

        LOG.info("[NtQM] VoipEngine.dll 匹配结果数量: {}, 内容: {}", results.size(), results);
    }

    @Test
    void queryMemoryMapPaths_emptyWildcards_returnsEmpty() {
        SwNativeOps ops = new SwNativeOps();
        List<String> results = ops.queryMemoryMapPaths(
                "NonExistentSw", List.of("NonExistent.exe"), ".*");
        assertNotNull(results);
        assertTrue(results.isEmpty());
    }

    @Test
    void queryMemoryMapPaths_invalidRegex_returnsEmpty() {
        SwNativeOps ops = new SwNativeOps();
        assertDoesNotThrow(() -> {
            List<String> results = ops.queryMemoryMapPaths(
                    "Weixin", List.of("Weixin?.exe"), "[invalid(regex");
            assertNotNull(results);
            assertTrue(results.isEmpty());
        });
    }

    // ==================== 三方案对比 ====================

    @Test
    void compareThreeEnumerationMethods() {
        List<String> psapi = SwNativeOps.enumerateByPsapi(TEST_PID);
        List<String> toolhelp = SwNativeOps.enumerateByToolHelp(TEST_PID);
        List<String> vqex = SwNativeOps.enumerateByVirtualQueryEx(TEST_PID);

        LOG.info("========== 三方案对比 PID={} ==========", TEST_PID);
        LOG.info("Psapi:          {} 个模块", psapi.size());
        LOG.info("ToolHelp:       {} 个模块", toolhelp.size());
        LOG.info("VirtualQueryEx: {} 个映射文件", vqex.size());

        assertEquals(psapi.size(), toolhelp.size(),
                "Psapi 和 ToolHelp 应返回相同数量的模块");
        assertTrue(vqex.size() >= psapi.size(),
                "VirtualQueryEx 应至少包含 Psapi 的所有模块");

        java.util.Set<String> psapiSet = java.util.Set.copyOf(psapi);
        java.util.Set<String> vqexSet = vqex.stream().collect(Collectors.toCollection(LinkedHashSet::new));
        vqexSet.removeAll(psapiSet);
        if (!vqexSet.isEmpty()) {
            LOG.info("VirtualQueryEx 独有文件 ({} 个):", vqexSet.size());
            Set<String> extTypes = vqexSet.stream()
                    .map(p -> p.substring(p.lastIndexOf('.') + 1).toLowerCase())
                    .collect(Collectors.toSet());
            LOG.info("  扩展类型: {}", extTypes);
            for (String p : vqexSet) {
                LOG.info("  {}", p);
            }
        } else {
            LOG.info("VirtualQueryEx 无独有文件（所有映射均为 exe/dll）");
        }
    }
}
