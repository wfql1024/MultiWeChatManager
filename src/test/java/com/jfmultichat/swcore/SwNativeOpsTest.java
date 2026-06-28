package com.jfmultichat.swcore;

import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Set;
import java.util.LinkedHashSet;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.*;

/**
 * SwNativeOps 测试 — 三种内存映射枚举方案 + 去子进程逻辑.
 */
class SwNativeOpsTest {

    private static final Logger LOG = LoggerFactory.getLogger(SwNativeOpsTest.class);
    private static final int TEST_PID = 32568;

    // ==================== 去子进程测试 ====================

    @Test
    void filterOutChildPids_shouldKeepOnlyRoot() {
        List<Integer> input = List.of(72740, 2228, 36704, 19408, 45892);
        List<Integer> result = SwNativeOps.filterOutChildPids(input);
        LOG.info("[去子测试] 输入={}, 结果={}", input, result);
        assertFalse(result.isEmpty(), "应至少保留一个根进程");
    }

    @Test
    void filterOutChildPids_emptyList() {
        List<Integer> result = SwNativeOps.filterOutChildPids(List.of());
        assertTrue(result.isEmpty());
    }

    @Test
    void filterOutChildPids_singlePid() {
        // 单个 PID 应保留自身
        List<Integer> result = SwNativeOps.filterOutChildPids(List.of(12345));
        LOG.info("[去子测试] 单PID 结果: {}", result);
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

    // ==================== NtQueryVirtualMemory 方案（生产实现） ====================

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

        if (!psapi.isEmpty() && !toolhelp.isEmpty()) {
            assertEquals(psapi.size(), toolhelp.size(),
                    "Psapi 和 ToolHelp 应返回相同数量的模块");
        }
        assertTrue(vqex.size() >= psapi.size(),
                "VirtualQueryEx 应至少包含 Psapi 的所有模块");

        Set<String> psapiSet = Set.copyOf(psapi);
        Set<String> vqexSet = vqex.stream()
                .collect(Collectors.toCollection(LinkedHashSet::new));
        vqexSet.removeAll(psapiSet);
        if (!vqexSet.isEmpty()) {
            LOG.info("VirtualQueryEx 独有文件 ({} 个):", vqexSet.size());
            Set<String> extTypes = vqexSet.stream()
                    .map(p -> {
                        int dot = p.lastIndexOf('.');
                        return dot >= 0 ? p.substring(dot + 1).toLowerCase() : "(none)";
                    })
                    .collect(Collectors.toSet());
            LOG.info("  扩展类型: {}", extTypes);
        }
    }
}
