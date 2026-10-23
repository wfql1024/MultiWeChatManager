package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * SwPatchCacheBuilder 测试 —— 扫描 → 物化 → 写缓存 的三条闸门与 nested 拼接。
 * <p>
 * 用临时目录 + 真实的带版本信息的可执行文件（复制一份到临时目录），
 * 这样 SwVersionHelper.calcSwVer 能读到版本号，不依赖 mock。
 */
class SwPatchCacheBuilderTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final String SW = "TestSw";

    @TempDir
    Path tmp;

    // ==================== 测试用例 ====================

    @Test
    void build_writesCacheWithPatches() throws Exception {
        TestEnv env = new TestEnv(tmp);
        env.setVersionedExe();
        byte[] pattern = env.pickPattern(0x200, 8);
        env.remote = env.config(env.exePath().toString(), env.simpleRule(pattern, fill(0x90, 8)));

        SwPatchCacheBuilder.BuildResult result =
                SwPatchCacheBuilder.build(SW, "multirun", null, false, env.accessor(), env.cache());

        assertTrue(result.ok, "构建应成功: " + result.message + " / " + result.channels);
        assertEquals(SwPatchCacheBuilder.Status.OK, result.channels.get("default").status);
        assertTrue(result.channels.get("default").ruleHits > 0, "应至少命中一条补丁");

        JsonNode entries = env.cacheEntry("multirun", "default");
        assertNotNull(entries, "缓存应写入");
        assertTrue(entries.isArray() && !entries.isEmpty());
        JsonNode first = entries.get(0);
        assertEquals(env.exePath().toString().replace('\\', '/'), first.get("addr").asText());
        assertTrue(first.has("wildcard"));
        assertTrue(first.get("patches").isArray() && !first.get("patches").isEmpty());
        assertTrue(first.get("patches").get(0).has("offset"));
    }

    @Test
    void build_secondCall_skipsWhenCacheValid() throws Exception {
        TestEnv env = new TestEnv(tmp);
        env.setVersionedExe();
        byte[] pattern = env.pickPattern(0x300, 8);
        env.remote = env.config(env.exePath().toString(), env.simpleRule(pattern, fill(0x90, 8)));

        SwPatchCacheBuilder.build(SW, "multirun", null, false, env.accessor(), env.cache());
        SwPatchCacheBuilder.BuildResult second =
                SwPatchCacheBuilder.build(SW, "multirun", null, true, env.accessor(), env.cache());

        assertEquals(SwPatchCacheBuilder.Status.SKIPPED, second.channels.get("default").status,
                "缓存合法时应跳过扫描");
    }

    @Test
    void build_scanFailure_keepsCacheEmpty() throws Exception {
        TestEnv env = new TestEnv(tmp);
        env.setVersionedExe();
        // 故意用一段几乎不可能出现的特征码
        String missing = "DE AD BE EF DE AD BE EF DE AD";
        env.remote = env.config(env.exePath().toString(), env.simpleRule(hexToBytes(missing), fill(0x90, 10)));

        SwPatchCacheBuilder.BuildResult result =
                SwPatchCacheBuilder.build(SW, "multirun", null, false, env.accessor(), env.cache());

        assertFalse(result.ok, "扫描失败时整体结果应为失败");
        assertEquals(SwPatchCacheBuilder.Status.FAILED, result.channels.get("default").status);
        assertFalse(result.channels.get("default").failures.isEmpty(), "应带失败原因");
        assertNull(env.cacheEntry("multirun", "default"), "失败时不得写缓存");
    }

    @Test
    void build_allRulesDeprecated_disablesChannel() throws Exception {
        TestEnv env = new TestEnv(tmp);
        env.setVersionedExe();
        // 版本值显式为 null → 规则已弃用
        ObjectNode rule = MAPPER.createObjectNode();
        rule.put("type", "simple");
        ObjectNode vers = rule.putObject("ver_adaptations");
        vers.putNull(env.version());
        env.remote = env.config(env.exePath().toString(), rule);

        SwPatchCacheBuilder.BuildResult result =
                SwPatchCacheBuilder.build(SW, "multirun", null, false, env.accessor(), env.cache());

        assertEquals(SwPatchCacheBuilder.Status.DISABLED, result.channels.get("default").status,
                "全部规则弃用应判为 DISABLED");
        assertNull(env.cacheEntry("multirun", "default"), "弃用时应删除该版本缓存");
    }

    @Test
    void build_dirFeature_nestedChild_joinsDst() throws Exception {
        TestEnv env = new TestEnv(tmp);
        env.setVersionedExe();

        Path pack = Files.createDirectories(tmp.resolve("pack"));
        byte[] pattern = env.pickPattern(0x400, 8);
        Path nodeDll = pack.resolve("node.dll");
        Files.copy(env.exePath(), nodeDll, StandardCopyOption.REPLACE_EXISTING);

        ObjectNode child = MAPPER.createObjectNode();
        child.put("addr", "node.dll");
        child.put("wildcard", "nod?.dll");
        child.putArray("patch_rules").add(env.simpleRule(pattern, fill(0x90, 8)));

        ObjectNode nested = MAPPER.createObjectNode();
        nested.put("type", "nested");
        nested.putArray("features").add(child);

        ObjectNode dirFeature = MAPPER.createObjectNode();
        dirFeature.put("addr", pack.toString().replace('\\', '/') + "/");
        dirFeature.put("wildcard", "pac?/");
        dirFeature.putArray("patch_rules").add(nested);

        ObjectNode ch = MAPPER.createObjectNode();
        ch.put("alias", "共存");
        ch.putArray("features").add(dirFeature);
        ObjectNode remote = MAPPER.createObjectNode();
        ObjectNode sw = remote.putObject(SW);
        ObjectNode mode = sw.putObject("coexist");
        mode.put("alias", "共存");
        mode.putObject("channels").set("default", ch);
        env.remote = remote;

        SwPatchCacheBuilder.BuildResult result =
                SwPatchCacheBuilder.build(SW, "coexist", null, false, env.accessor(), env.cache());

        assertTrue(result.ok, "目录 + nested 应构建成功: " + result.message + " / " + result.channels);
        JsonNode entries = env.cacheEntry("coexist", "default");
        assertNotNull(entries);
        assertEquals(1, entries.size(), "目录本身不产条目，只有子文件产条目");

        JsonNode childEntry = entries.get(0);
        assertEquals(pack.resolve("node.dll").toString().replace('\\', '/'), childEntry.get("addr").asText());
        assertEquals("nod?.dll", childEntry.get("wildcard").asText());
        assertFalse(childEntry.get("patches").isEmpty());
    }

    @Test
    void scanner_findsPatternInRealFile() throws Exception {
        // 回归测试：曾因 convertAndAlign 返回值误判导致扫描恒失败
        TestEnv env = new TestEnv(tmp);
        env.setVersionedExe();
        byte[] pat = env.pickPattern(0x200, 8);
        java.nio.ByteBuffer buf = java.nio.ByteBuffer.wrap(Files.readAllBytes(env.exePath()));
        List<SwHexUtils.ScanResult> res = SwHexUtils.searchPatternDicts(
                buf, toHex(pat), toHex(fill(0x90, 8)), 0, 0);
        assertNotNull(res, "对齐成功时不应返回 null");
        assertFalse(res.isEmpty(), "文件里真实存在的特征码必须能命中");
    }

    @Test
    void build_keepsAddrTemplate() throws Exception {
        // 缓存里必须保留配置模板（%变量%），不能替成解析后的绝对路径
        TestEnv env = new TestEnv(tmp);
        env.setVersionedExe();
        byte[] pattern = env.pickPattern(0x280, 8);
        env.remote = env.config("%inst_dir%/fake.exe", env.simpleRule(pattern, fill(0x90, 8)));

        SwPatchCacheBuilder.BuildResult result =
                SwPatchCacheBuilder.build(SW, "multirun", null, false, env.accessor(), env.cache());

        assertTrue(result.ok, "构建应成功: " + result.channels);
        JsonNode entries = env.cacheEntry("multirun", "default");
        assertNotNull(entries);
        assertEquals("%inst_dir%/fake.exe", entries.get(0).get("addr").asText());
    }

    // ==================== 测试环境 ====================
    private static final class TestEnv {
        private final Path dir;
        private final Map<String, String> settings = new HashMap<>();
        private final ObjectNode cacheNode = MAPPER.createObjectNode();
        private ObjectNode remote;
        private String cachedVersion;

        TestEnv(Path dir) {
            this.dir = dir;
        }

        void setVersionedExe() throws Exception {
            // 找一个带版本信息的系统程序作为"目标文件"
            Path source = Path.of(System.getenv("SystemRoot") + "/System32/notepad.exe");
            if (!Files.isRegularFile(source)) {
                source = Path.of(System.getProperty("java.home"), "bin", "java.exe");
            }
            assertTrue(Files.isRegularFile(source), "找不到可用的带版本信息的 exe");
            Path target = dir.resolve("fake.exe");
            Files.copy(source, target, StandardCopyOption.REPLACE_EXISTING);
            settings.put("inst_path", target.toString());
        }

        Path exePath() {
            return Path.of(settings.get("inst_path"));
        }

        String version() {
            if (cachedVersion == null) {
                cachedVersion = SwVersionHelper.calcSwVer(SW, accessor());
            }
            assertNotNull(cachedVersion, "应能读到版本号");
            return cachedVersion;
        }

        /** 在文件 offset 附近找一段高熵字节（至少 3 种取值），避免命中补零区 */
        byte[] pickPattern(int offset, int len) throws Exception {
            byte[] all = Files.readAllBytes(exePath());
            for (int start = offset; start + len <= all.length; start++) {
                java.util.Set<Integer> distinct = new java.util.HashSet<>();
                for (int i = 0; i < len; i++) distinct.add(all[start + i] & 0xFF);
                if (distinct.size() >= 3) {
                    byte[] out = new byte[len];
                    System.arraycopy(all, start, out, 0, len);
                    return out;
                }
            }
            throw new IllegalStateException("找不到合适的特征码");
        }

        ObjectNode simpleRule(byte[] original, byte[] modified) {
            ObjectNode rule = MAPPER.createObjectNode();
            rule.put("type", "simple");
            ObjectNode vers = rule.putObject("ver_adaptations");
            ObjectNode body = vers.putObject(version());
            body.put("original", toHex(original));
            body.put("modified", toHex(modified));
            return rule;
        }

        ObjectNode config(String addr, ObjectNode rule) {
            ObjectNode feature = MAPPER.createObjectNode();
            feature.put("addr", addr.replace('\\', '/'));
            feature.putArray("patch_rules").add(rule);

            ObjectNode channel = MAPPER.createObjectNode();
            channel.put("alias", "多开");
            channel.putArray("features").add(feature);

            ObjectNode remoteRoot = MAPPER.createObjectNode();
            ObjectNode sw = remoteRoot.putObject(SW);
            ObjectNode mode = sw.putObject("multirun");
            mode.put("alias", "多开");
            mode.putObject("channels").set("default", channel);
            return remoteRoot;
        }

        JsonNode cacheEntry(String mode, String channel) {
            // 缓存结构：{sw: {mode: {channels: {ch: {precise_ver_adaptations: {ver: [...]}}}}}}
            JsonNode node = cacheNode.path(SW).path(mode).path("channels").path(channel)
                    .path(SwPatchCacheBuilder.KEY_PRECISE).path(version());
            return node.isMissingNode() || node.isNull() ? null : node;
        }

        ObjectNode cache() {
            return cacheNode;
        }

        SwConfigAccessor accessor() {
            return new SwConfigAccessor(new SwConfigAccessor.Provider() {
                @Override
                public JsonNode getRemoteSw(String sw, String... addr) {
                    JsonNode cur = remote == null ? null : remote.get(sw);
                    for (String key : addr) {
                        if (cur == null) return null;
                        cur = cur.get(key);
                    }
                    return cur;
                }

                @Override
                public JsonNode getRemoteSw(String sw, Map<String, Object> kwargs) {
                    return null;
                }

                @Override
                public JsonNode getSwSetting(String sw, String... addr) {
                    return null;
                }

                @Override
                public JsonNode getSwSetting(String sw, Map<String, Object> kwargs) {
                    for (String key : kwargs.keySet()) {
                        String value = settings.get(key);
                        if (value != null) return MAPPER.getNodeFactory().textNode(value);
                    }
                    return null;
                }

                @Override
                public void updateSwSettings(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs) {
                }

                @Override
                public JsonNode getSwAccData(String sw, String... addr) {
                    return null;
                }

                @Override
                public JsonNode getSwAccData(String sw, Map<String, Object> kwargs) {
                    return null;
                }

                @Override
                public void updateSwAccData(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs) {
                }

                @Override
                public void clearSwAccData(String sw, String... addr) {
                }

                @Override
                public ObjectNode getSwCache() {
                    return cacheNode;
                }

                @Override
                public void setSwCache(ObjectNode data) {
                    // 同一个对象，无需复制
                }

                @Override
                public boolean saveAndCheckChanged(String sw, String key, Object value) {
                    return false;
                }

                @Override
                public JsonNode fetchOrSetDefault(String sw, String key, String enumCls) {
                    return null;
                }
            });
        }
    }

    // ==================== 小工具 ====================

    private static byte[] fill(int value, int len) {
        byte[] out = new byte[len];
        java.util.Arrays.fill(out, (byte) value);
        return out;
    }

    private static byte[] hexToBytes(String hex) {
        String[] parts = hex.trim().split("\\s+");
        byte[] out = new byte[parts.length];
        for (int i = 0; i < parts.length; i++) out[i] = (byte) Integer.parseInt(parts[i], 16);
        return out;
    }

    private static String toHex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            if (sb.length() > 0) sb.append(' ');
            sb.append(String.format("%02X", b));
        }
        return sb.toString();
    }
}
