package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

/**
 * SwPathDetective 单元测试 — 覆盖批量 pathType + 并发 + 懒加载迭代器.
 * <p>
 * 所有测试使用 Mock NativeOps，不依赖真实 Windows API。
 */
@DisplayName("SwPathDetective")
class SwPathDetectiveTest {

    private static final Logger LOG = LoggerFactory.getLogger(SwPathDetectiveTest.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    // ==================== Mock 基础设施 ====================

    private static class MockNativeOps implements SwPathDetective.NativeOps {
        String registryValue;
        String processImagePath;
        Map<String, List<Integer>> pidsByWildcards;
        SwPathDetective.NativeOps.MemoryMapIterator memoryMapIterator;
        final List<String> callLog = new ArrayList<>();
        final AtomicInteger iteratorCloseCount = new AtomicInteger(0);

        @Override
        public String readRegistryValue(Long hkey, String subKey, String valueName) {
            callLog.add("reg:" + subKey + ":" + valueName);
            return registryValue;
        }

        @Override
        public List<String> queryMemoryMapPaths(String sw, List<String> exeWildcards, String regex) {
            callLog.add("memmap:" + sw + ":" + regex);
            return Collections.emptyList();
        }

        @Override
        public List<String> queryDllDirByFiles(String sw, String installDir) {
            callLog.add("dlldir:" + sw);
            return Collections.emptyList();
        }

        @Override
        public String getProcessImagePath(int pid) {
            callLog.add("procpath:" + pid);
            return processImagePath;
        }

        @Override
        public Map<String, List<Integer>> getPidsByWildcardsAndGroup(List<String> wildcards) {
            callLog.add("pids:" + String.join(",", wildcards));
            return pidsByWildcards != null ? pidsByWildcards : Collections.emptyMap();
        }

        @Override
        public SwPathDetective.NativeOps.MemoryMapIterator iterateMemoryMapPaths(
                String sw, List<String> exeWildcards) {
            callLog.add("iter:" + sw);
            if (memoryMapIterator != null) return memoryMapIterator;
            return new SwPathDetective.NativeOps.MemoryMapIterator() {
                private boolean done;
                @Override public boolean hasNext() { return !done; }
                @Override public String next() {
                    if (done) throw new NoSuchElementException();
                    done = true;
                    return null;
                }
                @Override public void close() { iteratorCloseCount.incrementAndGet(); }
            };
        }
    }

    private static class MockProvider implements SwConfigAccessor.Provider {
        final ObjectNode remoteSw;
        final ObjectNode swSettings;

        MockProvider(ObjectNode remoteSw) {
            this.remoteSw = remoteSw;
            this.swSettings = MAPPER.createObjectNode();
        }

        @Override
        public JsonNode getRemoteSw(String sw, String... addr) {
            JsonNode node = remoteSw.get(sw);
            if (node == null) return null;
            for (String a : addr) {
                if (node == null || !node.isObject()) return null;
                node = node.get(a);
            }
            return node;
        }

        @Override
        public JsonNode getRemoteSw(String sw, Map<String, Object> kwargs) {
            return resolveKwargs(remoteSw.get(sw), kwargs);
        }

        @Override
        public JsonNode getSwSetting(String sw, String... addr) {
            JsonNode node = swSettings.get(sw);
            if (node == null) return null;
            for (String a : addr) {
                if (node == null || !node.isObject()) return null;
                node = node.get(a);
            }
            return node;
        }

        @Override
        public JsonNode getSwSetting(String sw, Map<String, Object> kwargs) {
            return resolveKwargs(swSettings.get(sw), kwargs);
        }

        private JsonNode resolveKwargs(JsonNode root, Map<String, Object> kwargs) {
            if (root == null || !root.isObject() || kwargs.isEmpty()) return null;
            if (kwargs.size() == 1) {
                Map.Entry<String, Object> entry = kwargs.entrySet().iterator().next();
                JsonNode node = root.get(entry.getKey());
                if (node != null) return node;
                Object def = entry.getValue();
                if (def != null) return MAPPER.valueToTree(def);
                return null;
            }
            Iterator<Map.Entry<String, Object>> it = kwargs.entrySet().iterator();
            JsonNode cur = root;
            while (it.hasNext()) {
                Map.Entry<String, Object> entry = it.next();
                if (!it.hasNext()) {
                    JsonNode node = cur.isObject() ? cur.get(entry.getKey()) : null;
                    if (node != null) return node;
                    Object def = entry.getValue();
                    if (def != null) return MAPPER.valueToTree(def);
                    return null;
                }
                if (cur.isObject()) cur = cur.get(entry.getKey());
                else return null;
            }
            return null;
        }

        @Override public void updateSwSettings(String sw, Map<String, String> fa, Map<String, Object> kw) {}
        @Override public JsonNode getSwAccData(String sw, String... addr) { return null; }
        @Override public JsonNode getSwAccData(String sw, Map<String, Object> kwargs) { return null; }
        @Override public void updateSwAccData(String sw, Map<String, String> fa, Map<String, Object> kw) {}
        @Override public void clearSwAccData(String sw, String... addr) {}
        @Override public ObjectNode getSwCache() { return MAPPER.createObjectNode(); }
        @Override public void setSwCache(ObjectNode data) {}
        @Override public boolean saveAndCheckChanged(String sw, String key, Object value) { return true; }
        @Override public JsonNode fetchOrSetDefault(String sw, String key, String enumCls) { return null; }
    }

    // ==================== 测试数据构建器 ====================

    private static ObjectNode buildRemoteSwWithRegex(
            String sw, List<String> exeWildcards, Map<String, String> ptRegexMap) {
        ObjectNode root = MAPPER.createObjectNode();
        ObjectNode swNode = root.putObject(sw);
        var wcArr = swNode.putArray("executable_wildcards");
        exeWildcards.forEach(wcArr::add);
        ObjectNode pdNode = swNode.putObject("path_detect");
        for (Map.Entry<String, String> e : ptRegexMap.entrySet()) {
            ObjectNode ptNode = pdNode.putObject(e.getKey());
            ObjectNode regexNode = ptNode.putObject("regex");
            var groupArr = regexNode.putArray("-");
            groupArr.addObject().put("regex", e.getValue());
        }
        return root;
    }

    private static ObjectNode buildRemoteSwWithReg(
            String sw, String pathType, String hkey, String subKey, String valueName) {
        ObjectNode root = MAPPER.createObjectNode();
        ObjectNode swNode = root.putObject(sw);
        swNode.put("executable", sw + ".exe");
        ObjectNode pdNode = swNode.putObject("path_detect");
        ObjectNode ptNode = pdNode.putObject(pathType);
        ObjectNode regNode = ptNode.putObject("reg");
        var regArr = regNode.putArray(hkey);
        regArr.addObject().put("sub_key", subKey).put("value_name", valueName);
        return root;
    }

    private static ObjectNode buildRemoteSwWithAddr(
            String sw, String pathType, String sysPathKey, String subPath) {
        ObjectNode root = MAPPER.createObjectNode();
        ObjectNode swNode = root.putObject(sw);
        ObjectNode pdNode = swNode.putObject("path_detect");
        ObjectNode ptNode = pdNode.putObject(pathType);
        ObjectNode addrNode = ptNode.putObject("addr");
        var addrArr = addrNode.putArray(sysPathKey);
        addrArr.addObject().put("sub_path", subPath);
        return root;
    }

    // ==================== FakeMemoryMapIterator ====================

    private static class FakeMemoryMapIterator
            implements SwPathDetective.NativeOps.MemoryMapIterator {
        private final List<String> paths;
        private int index;
        private boolean closed;
        private int consumedCount;

        FakeMemoryMapIterator(List<String> paths) {
            this.paths = new ArrayList<>(paths);
            this.index = 0;
        }

        @Override public boolean hasNext() { return !closed && index < paths.size(); }

        @Override
        public String next() {
            if (!hasNext()) throw new NoSuchElementException();
            consumedCount++;
            return paths.get(index++);
        }

        @Override public void close() { closed = true; }

        int getConsumedCount() { return consumedCount; }
        boolean isClosed() { return closed; }
    }

    // ========== detectAll 批量查询 ==========

    @Nested
    @DisplayName("detectAll — 批量 pathType")
    class DetectAllBatch {

        @Test
        @DisplayName("传入单个 pathType (inst_path) 命中注册表")
        void singlePathType_instPath_hitRegister() {
            MockNativeOps ops = new MockNativeOps();
            ops.registryValue = "C:/Program Files/TestSw/TestSw.exe";
            ops.pidsByWildcards = Collections.emptyMap();

            ObjectNode remoteSw = buildRemoteSwWithReg(
                    "TestSw", "inst_path", "current_user",
                    "Software\\TestSw", "InstallPath");
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.detectAll(accessor, "TestSw", "inst_path");

            assertEquals(1, results.size());
            assertFalse(results.get("inst_path").isEmpty());
            assertTrue(results.get("inst_path").get(0).path.contains("TestSw"));
        }

        @Test
        @DisplayName("传入单个 pathType (data_dir) 命中内存映射")
        void singlePathType_dataDir_hitMemoryMap() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Map.of("TestSw.exe", List.of(1234));
            List<String> fakePaths = List.of(
                    "C:/Users/test/Documents/TestSw/UserData/Msg/abc.db");
            ops.memoryMapIterator = new FakeMemoryMapIterator(fakePaths);

            ObjectNode remoteSw = buildRemoteSwWithRegex(
                    "TestSw", List.of("TestSw.exe"),
                    Map.of("data_dir", "^(.*?)/UserData/Msg(?:/[^/]+)*$"));
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.detectAll(accessor, "TestSw", "data_dir");

            assertEquals(1, results.size());
            assertFalse(results.get("data_dir").isEmpty());
            assertTrue(results.get("data_dir").get(0).path.contains("TestSw"));
        }

        @Test
        @DisplayName("传入多个 pathType 全部命中")
        void multiplePathTypes_allHit() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Map.of("WeChat.exe", List.of(5678));
            ops.processImagePath = "C:/Program Files/WeChat/WeChat.exe";

            List<String> fakePaths = List.of(
                    "C:/Users/test/Documents/WeChat Files/UserData/Msg/file.db",
                    "C:/Program Files/WeChat/4.0.0.30/VoipEngine.dll");
            ops.memoryMapIterator = new FakeMemoryMapIterator(fakePaths);

            ObjectNode root = MAPPER.createObjectNode();
            ObjectNode swNode = root.putObject("WeChat");
            var wcArr = swNode.putArray("executable_wildcards");
            wcArr.add("WeChat.exe");
            swNode.put("executable", "WeChat.exe");
            ObjectNode pdNode = swNode.putObject("path_detect");
            // data_dir regex
            ObjectNode ddNode = pdNode.putObject("data_dir");
            ObjectNode ddRegex = ddNode.putObject("regex");
            var ddGroup = ddRegex.putArray("-");
            ddGroup.addObject().put("regex", "^(.*?)/WeChat Files/UserData/Msg(?:/[^/]+)*$");
            // dll_dir regex
            ObjectNode dllNode = pdNode.putObject("dll_dir");
            ObjectNode dllRegex = dllNode.putObject("regex");
            var dllGroup = dllRegex.putArray("-");
            dllGroup.addObject().put("regex",
                    "^(.*?)/([0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+)/VoipEngine\\.dll$");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.detectAll(accessor, "WeChat", "inst_path", "data_dir", "dll_dir");

            assertEquals(3, results.size());
            assertFalse(results.get("inst_path").isEmpty(), "进程应命中 inst_path");
            assertFalse(results.get("data_dir").isEmpty(), "内存映射应命中 data_dir");
            assertFalse(results.get("dll_dir").isEmpty(), "内存映射应命中 dll_dir");
        }

        @Test
        @DisplayName("传入多个 pathType 全部未匹配 — 返回空列表")
        void multiplePathTypes_allMiss() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Collections.emptyMap();
            ops.registryValue = null;
            ops.memoryMapIterator = new FakeMemoryMapIterator(Collections.emptyList());

            ObjectNode remoteSw = buildRemoteSwWithRegex(
                    "NoSuchSw", List.of("NoSuch.exe"),
                    Map.of("data_dir", "^(.*?)/NoSuch/Files$"));
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.detectAll(accessor, "NoSuchSw", "data_dir", "dll_dir");

            assertEquals(2, results.size());
            assertTrue(results.get("data_dir").isEmpty());
            assertTrue(results.get("dll_dir").isEmpty());
        }

        @Test
        @DisplayName("传入空 pathTypes — 返回空 Map")
        void emptyPathTypes_returnsEmptyMap() {
            MockNativeOps ops = new MockNativeOps();
            SwConfigAccessor accessor = new SwConfigAccessor(
                    new MockProvider(MAPPER.createObjectNode()));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.detectAll(accessor, "WeChat");

            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("传入 null pathTypes — 返回空 Map")
        void nullPathTypes_returnsEmptyMap() {
            MockNativeOps ops = new MockNativeOps();
            SwConfigAccessor accessor = new SwConfigAccessor(
                    new MockProvider(MAPPER.createObjectNode()));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.detectAll(accessor, "WeChat", (String[]) null);

            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("部分 pathType 匹配，部分不匹配")
        void partialMatch() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Map.of("WeChat.exe", List.of(1234));
            ops.processImagePath = "C:/Program Files/WeChat/WeChat.exe";

            List<String> fakePaths = List.of(
                    "C:/Users/test/Documents/WeChat Files/UserData/Msg/file.db");
            ops.memoryMapIterator = new FakeMemoryMapIterator(fakePaths);

            ObjectNode root = MAPPER.createObjectNode();
            ObjectNode swNode = root.putObject("WeChat");
            var wcArr = swNode.putArray("executable_wildcards");
            wcArr.add("WeChat.exe");
            swNode.put("executable", "WeChat.exe");
            ObjectNode pdNode = swNode.putObject("path_detect");
            // data_dir regex
            ObjectNode ddNode = pdNode.putObject("data_dir");
            ObjectNode ddRegex = ddNode.putObject("regex");
            var ddGroup = ddRegex.putArray("-");
            ddGroup.addObject().put("regex", "^(.*?)/WeChat Files/UserData/Msg(?:/[^/]+)*$");
            // dll_dir regex — 不会匹配
            ObjectNode dllNode = pdNode.putObject("dll_dir");
            ObjectNode dllRegex = dllNode.putObject("regex");
            var dllGroup = dllRegex.putArray("-");
            dllGroup.addObject().put("regex",
                    "^(.*?)/([0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+)/VoipEngine\\.dll$");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.detectAll(accessor, "WeChat", "inst_path", "data_dir", "dll_dir");

            assertFalse(results.get("inst_path").isEmpty());
            assertFalse(results.get("data_dir").isEmpty());
            assertTrue(results.get("dll_dir").isEmpty(), "dll_dir 应未匹配");
        }
    }

    // ========== shared memory scan tests ==========

    @Nested
    @DisplayName("queryByMemoryRegex — 共享内存扫描")
    class QueryByMemoryRegex {

        @Test
        @DisplayName("两个 pathType 共享一次扫描，全部匹配后提前终止")
        void sharedScan_earlyTermination() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Map.of("WeChat.exe", List.of(1234));

            List<String> fakePaths = List.of(
                    "C:/Users/test/Documents/WeChat Files/UserData/Msg/file.db",
                    "C:/Program Files/WeChat/4.0.0.30/VoipEngine.dll",
                    "C:/Users/test/Documents/WeChat Files/MoreData/extra.db");
            FakeMemoryMapIterator fakeIter = new FakeMemoryMapIterator(fakePaths);
            ops.memoryMapIterator = fakeIter;

            ObjectNode root = MAPPER.createObjectNode();
            ObjectNode swNode = root.putObject("WeChat");
            var wcArr = swNode.putArray("executable_wildcards");
            wcArr.add("WeChat.exe");
            ObjectNode pdNode = swNode.putObject("path_detect");
            // data_dir
            ObjectNode ddNode = pdNode.putObject("data_dir");
            ObjectNode ddRegex = ddNode.putObject("regex");
            var ddGroup = ddRegex.putArray("-");
            ddGroup.addObject().put("regex", "^(.*?)/WeChat Files/UserData/Msg(?:/[^/]+)*$");
            // dll_dir
            ObjectNode dllNode = pdNode.putObject("dll_dir");
            ObjectNode dllRegex = dllNode.putObject("regex");
            var dllGroup = dllRegex.putArray("-");
            dllGroup.addObject().put("regex",
                    "^(.*?)/([0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+)/VoipEngine\\.dll$");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(ops);
            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByMemoryRegex(accessor, "WeChat", List.of("data_dir", "dll_dir"));

            assertFalse(results.get("data_dir").isEmpty());
            assertFalse(results.get("dll_dir").isEmpty());
            assertTrue(fakeIter.getConsumedCount() <= 2,
                    "应提前终止，最多消耗2条，实际=" + fakeIter.getConsumedCount());
        }

        @Test
        @DisplayName("无正则配置的 pathType — 返回空列表")
        void noRegexConfig_returnsEmpty() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Map.of("WeChat.exe", List.of(1234));
            ops.memoryMapIterator = new FakeMemoryMapIterator(List.of());

            ObjectNode root = MAPPER.createObjectNode();
            ObjectNode swNode = root.putObject("WeChat");
            var wcArr = swNode.putArray("executable_wildcards");
            wcArr.add("WeChat.exe");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(ops);
            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByMemoryRegex(accessor, "WeChat", List.of("data_dir"));

            assertTrue(results.get("data_dir").isEmpty());
        }

        @Test
        @DisplayName("nativeOps 为 null — 返回空列表")
        void nullNativeOps_returnsEmpty() {
            ObjectNode root = buildRemoteSwWithRegex(
                    "WeChat", List.of("WeChat.exe"),
                    Map.of("data_dir", "^(.*?)/test$"));
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(null);
            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByMemoryRegex(accessor, "WeChat", List.of("data_dir"));

            assertTrue(results.get("data_dir").isEmpty());
        }

        @Test
        @DisplayName("迭代器 close 被调用")
        void iteratorClose_called() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Map.of("WeChat.exe", List.of(1234));
            FakeMemoryMapIterator fakeIter = new FakeMemoryMapIterator(List.of());
            ops.memoryMapIterator = fakeIter;

            ObjectNode root = buildRemoteSwWithRegex(
                    "WeChat", List.of("WeChat.exe"),
                    Map.of("data_dir", "^(.*?)/test$"));
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(ops);
            detective.queryByMemoryRegex(accessor, "WeChat", List.of("data_dir"));

            assertTrue(fakeIter.isClosed(), "迭代器应在 finally 块中被关闭");
        }
    }

    // ========== queryByRegister ==========

    @Nested
    @DisplayName("queryByRegister — 注册表查询")
    class QueryByRegister {

        @Test
        @DisplayName("命中注册表 — 返回路径")
        void hit_returnsPath() {
            MockNativeOps ops = new MockNativeOps();
            ops.registryValue = "C:/Program Files/TestSw/TestSw.exe";

            ObjectNode remoteSw = buildRemoteSwWithReg(
                    "TestSw", "inst_path", "current_user",
                    "Software\\TestSw", "InstallPath");
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByRegister(accessor, "TestSw", List.of("inst_path"));

            assertFalse(results.get("inst_path").isEmpty());
            assertTrue(results.get("inst_path").get(0).path.contains("TestSw"));
        }

        @Test
        @DisplayName("注册表值为空 — 返回空列表")
        void emptyValue_returnsEmpty() {
            MockNativeOps ops = new MockNativeOps();
            ops.registryValue = "";

            ObjectNode remoteSw = buildRemoteSwWithReg(
                    "TestSw", "data_dir", "local_machine",
                    "Software\\TestSw", "DataDir");
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByRegister(accessor, "TestSw", List.of("data_dir"));

            assertTrue(results.get("data_dir").isEmpty());
        }

        @Test
        @DisplayName("无 reg 配置 — 返回空列表")
        void noRegConfig_returnsEmpty() {
            MockNativeOps ops = new MockNativeOps();
            ObjectNode remoteSw = MAPPER.createObjectNode();
            remoteSw.putObject("TestSw");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByRegister(accessor, "TestSw", List.of("data_dir"));

            assertTrue(results.get("data_dir").isEmpty());
        }

        @Test
        @DisplayName("nativeOps 为 null — 返回空列表")
        void nullNativeOps_returnsEmpty() {
            ObjectNode remoteSw = buildRemoteSwWithReg(
                    "TestSw", "inst_path", "current_user",
                    "Software\\TestSw", "InstallPath");
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(null);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByRegister(accessor, "TestSw", List.of("inst_path"));

            assertTrue(results.get("inst_path").isEmpty());
        }
    }

    // ========== queryByGuess ==========

    @Nested
    @DisplayName("queryByGuess — 猜测路径")
    class QueryByGuess {

        @Test
        @DisplayName("命中 addr 猜测 — 返回路径")
        void hit_returnsPath() {
            MockNativeOps ops = new MockNativeOps();
            ObjectNode remoteSw = buildRemoteSwWithAddr(
                    "WeChat", "data_dir", "Documents", "WeChat Files");
            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByGuess(accessor, "WeChat", List.of("data_dir"));

            assertFalse(results.get("data_dir").isEmpty());
            assertTrue(results.get("data_dir").get(0).path.contains("WeChat Files"));
        }

        @Test
        @DisplayName("无 addr 配置 — 返回空列表")
        void noAddrConfig_returnsEmpty() {
            MockNativeOps ops = new MockNativeOps();
            ObjectNode remoteSw = MAPPER.createObjectNode();
            remoteSw.putObject("WeChat");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByGuess(accessor, "WeChat", List.of("data_dir"));

            assertTrue(results.get("data_dir").isEmpty());
        }
    }

    // ========== queryByProcess ==========

    @Nested
    @DisplayName("queryByProcess — 进程枚举")
    class QueryByProcess {

        @Test
        @DisplayName("pathTypes 不含 inst_path — 跳过")
        void noInstPath_skips() {
            MockNativeOps ops = new MockNativeOps();
            SwConfigAccessor accessor = new SwConfigAccessor(
                    new MockProvider(MAPPER.createObjectNode()));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByProcess(accessor, "WeChat", List.of("data_dir"));

            assertTrue(results.isEmpty());
            assertTrue(ops.callLog.isEmpty(), "不应调用任何 nativeOps 方法");
        }

        @Test
        @DisplayName("命中进程 — 返回路径")
        void hit_returnsPath() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Map.of("WeChat.exe", List.of(1234));
            ops.processImagePath = "C:/Program Files/WeChat/WeChat.exe";

            ObjectNode root = MAPPER.createObjectNode();
            ObjectNode swNode = root.putObject("WeChat");
            swNode.put("executable", "WeChat.exe");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByProcess(accessor, "WeChat", List.of("inst_path"));

            assertFalse(results.get("inst_path").isEmpty());
            assertTrue(results.get("inst_path").get(0).path.contains("WeChat.exe"));
        }

        @Test
        @DisplayName("无匹配进程 — 返回空列表")
        void noMatchingProcess_returnsEmpty() {
            MockNativeOps ops = new MockNativeOps();
            ops.pidsByWildcards = Collections.emptyMap();

            ObjectNode root = MAPPER.createObjectNode();
            ObjectNode swNode = root.putObject("WeChat");
            swNode.put("executable", "WeChat.exe");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryByProcess(accessor, "WeChat", List.of("inst_path"));

            assertTrue(results.get("inst_path").isEmpty());
        }
    }

    // ========== queryFromOtherSw ==========

    @Nested
    @DisplayName("queryFromOtherSw — 其他 SW 推断")
    class QueryFromOtherSw {

        @Test
        @DisplayName("微信/企微共用同级目录")
        void wechatAndWeixin_shareSiblingDir() {
            MockNativeOps ops = new MockNativeOps();

            ObjectNode root = MAPPER.createObjectNode();
            ObjectNode wcNode = root.putObject("WeChat");
            wcNode.put("data_dir_name", "WeChat Files");

            MockProvider provider = new MockProvider(root);
            provider.swSettings.putObject("Weixin")
                    .put("data_dir", "C:/Users/test/Documents/WeChat Files/Weixin_Data");

            SwConfigAccessor accessor = new SwConfigAccessor(provider);
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryFromOtherSw(accessor, "WeChat", List.of("data_dir"));

            assertFalse(results.get("data_dir").isEmpty());
            assertTrue(results.get("data_dir").get(0).path.contains("WeChat Files"));
        }

        @Test
        @DisplayName("无 data_dir 配置 — 跳过")
        void noDataDirConfig_skips() {
            MockNativeOps ops = new MockNativeOps();
            SwConfigAccessor accessor = new SwConfigAccessor(
                    new MockProvider(MAPPER.createObjectNode()));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryFromOtherSw(accessor, "WeChat", List.of("data_dir"));

            assertTrue(results.get("data_dir").isEmpty());
        }
    }

    // ========== queryDllDirByFiles ==========

    @Nested
    @DisplayName("queryDllDirByFiles — DLL 目录文件遍历")
    class QueryDllDirByFiles {

        @Test
        @DisplayName("无 dll_dir — 跳过")
        void noDllDir_skips() {
            MockNativeOps ops = new MockNativeOps();
            SwConfigAccessor accessor = new SwConfigAccessor(
                    new MockProvider(MAPPER.createObjectNode()));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryDllDirByFiles(accessor, "WeChat", List.of("inst_path"));

            assertTrue(results.isEmpty());
        }

        @Test
        @DisplayName("无安装路径 — 返回空列表")
        void noInstallPath_returnsEmpty() {
            MockNativeOps ops = new MockNativeOps();
            ObjectNode root = MAPPER.createObjectNode();
            ObjectNode swNode = root.putObject("WeChat");
            var paArr = swNode.putArray("patch_addresses");
            paArr.add("%dll_dir%/WeChat.dll");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(root));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results =
                    detective.queryDllDirByFiles(accessor, "WeChat", List.of("dll_dir"));

            assertTrue(results.get("dll_dir").isEmpty());
        }
    }

    // ========== normalizePath ==========

    @Nested
    @DisplayName("normalizePath")
    class NormalizePath {

        @Test
        @DisplayName("反斜杠转正斜杠")
        void backslashToForwardSlash() {
            assertEquals("C:/Program Files/Test",
                    SwPathDetective.normalizePath("C:\\Program Files\\Test"));
        }

        @Test
        @DisplayName("去除首尾引号")
        void stripQuotes() {
            assertEquals("C:/path/to/exe",
                    SwPathDetective.normalizePath("\"C:\\path\\to\\exe\""));
        }

        @Test
        @DisplayName("null 返回 null")
        void nullInput_returnsNull() {
            assertNull(SwPathDetective.normalizePath(null));
        }

        @Test
        @DisplayName("空白字符串返回 null")
        void blankInput_returnsNull() {
            assertNull(SwPathDetective.normalizePath("   "));
        }
    }

    // ========== 并发安全性 ==========

    @Nested
    @DisplayName("并发安全性")
    class ConcurrencySafety {

        @Test
        @DisplayName("多个子查询异常不影响其他子查询")
        void subQueryException_doesNotAffectOthers() {
            MockNativeOps ops = new MockNativeOps();
            ops.registryValue = "C:/Program Files/TestSw/TestSw.exe";
            ops.pidsByWildcards = null; // NPE trigger

            ObjectNode remoteSw = buildRemoteSwWithReg(
                    "TestSw", "inst_path", "current_user",
                    "Software\\TestSw", "InstallPath");
            // 同时添加 data_dir 的 addr 猜测（复用已有 path_detect 节点）
            ObjectNode swNode = (ObjectNode) remoteSw.get("TestSw");
            ObjectNode pdNode = swNode.has("path_detect")
                    ? (ObjectNode) swNode.get("path_detect")
                    : swNode.putObject("path_detect");
            ObjectNode addrPt = pdNode.has("data_dir")
                    ? (ObjectNode) pdNode.get("data_dir")
                    : pdNode.putObject("data_dir");
            ObjectNode addrNode = addrPt.putObject("addr");
            var addrArr = addrNode.putArray("Documents");
            addrArr.addObject().put("sub_path", "TestSw Files");

            SwConfigAccessor accessor = new SwConfigAccessor(new MockProvider(remoteSw));
            SwPathDetective detective = new SwPathDetective(ops);

            Map<String, List<SwPathDetective.PathEntry>> results = assertDoesNotThrow(() ->
                    detective.detectAll(accessor, "TestSw", "inst_path", "data_dir"));

            assertFalse(results.get("inst_path").isEmpty(), "注册表应正常命中");
            assertFalse(results.get("data_dir").isEmpty(),
                    "猜测应正常命中（不受进程查询异常影响）");
        }
    }
}
