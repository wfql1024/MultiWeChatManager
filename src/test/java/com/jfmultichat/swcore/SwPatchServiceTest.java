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
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 补丁开关链路测试：缓存 → 识别 → 写入 → 识别 → 撤销。
 * 用临时目录里的真实文件（带版本信息的 exe 副本）跑，不依赖平台安装。
 */
class SwPatchServiceTest {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final String SW = "TestSw";

    @TempDir
    Path tmp;

    @Test
    void toggle_onThenOff_restoresBytes() throws Exception {
        Path file = makeTarget();
        byte[] all = Files.readAllBytes(file);
        int offset = pickOffset(all, 8);
        byte[] original = java.util.Arrays.copyOfRange(all, offset, offset + 8);
        byte[] modified = new byte[8];
        java.util.Arrays.fill(modified, (byte) 0x90);

        String ver = SwVersionHelper.calcSwVer(SW, accessor(file));
        assertNotNull(ver, "应能读到版本号");

        ObjectNode cache = MAPPER.createObjectNode();
        var verArr = cache.putObject(SW).putObject("multirun").putObject("channels").putObject("default")
                .putObject("precise_ver_adaptations").putArray(ver);
        ObjectNode patchEntry = verArr.addObject();
        patchEntry.put("addr", file.toString().replace('\\', '/'));
        patchEntry.putNull("wildcard");
        ObjectNode patch = patchEntry.putArray("patches").addObject();
        patch.put("offset", offset);
        patch.put("original", toHex(original));
        patch.put("modified", toHex(modified));

        SwConfigAccessor acc = accessor(file, cache);

        String msg1 = SwPatchService.toggle(SW, "multirun", "default", null, null, acc);
        assertTrue(msg1.startsWith("成功开启"), "第一次应开启，实际: " + msg1);
        assertArrayEquals(modified, read(file, offset, 8), "文件应写入 modified");

        String msg2 = SwPatchService.toggle(SW, "multirun", "default", null, null, acc);
        assertTrue(msg2.startsWith("成功关闭"), "第二次应关闭，实际: " + msg2);
        assertArrayEquals(original, read(file, offset, 8), "撤销后应恢复 original");
    }

    @Test
    void plan_listsChannelsWithState() throws Exception {
        Path file = makeTarget();
        byte[] all = Files.readAllBytes(file);
        int offset = pickOffset(all, 8);
        byte[] original = java.util.Arrays.copyOfRange(all, offset, offset + 8);
        byte[] modified = new byte[8];
        java.util.Arrays.fill(modified, (byte) 0x90);
        String ver = SwVersionHelper.calcSwVer(SW, accessor(file));

        ObjectNode cache = MAPPER.createObjectNode();
        var verArr = cache.putObject(SW).putObject("multirun").putObject("channels").putObject("default")
                .putObject("precise_ver_adaptations").putArray(ver);
        ObjectNode patchEntry = verArr.addObject();
        patchEntry.put("addr", file.toString().replace('\\', '/'));
        patchEntry.putNull("wildcard");
        ObjectNode patch = patchEntry.putArray("patches").addObject();
        patch.put("offset", offset);
        patch.put("original", toHex(original));
        patch.put("modified", toHex(modified));

        ObjectNode plan = SwPatchService.getSwPatchPlan(SW, accessor(file, cache));
        assertTrue(plan.has("multirun"));
        assertEquals(1, plan.get("multirun").size());
        JsonNode item = plan.get("multirun").get(0);
        assertEquals("default", item.get("id").asText());
        assertEquals("off", item.get("state").asText(), "未打补丁时应为 off");
    }

    @Test
    void plan_listsAllChannels_evenWithoutAdaptation() throws Exception {
        Path file = makeTarget();
        ObjectNode remote = MAPPER.createObjectNode();
        ObjectNode sw = remote.putObject(SW);
        ObjectNode multirun = sw.putObject("multirun");
        multirun.put("alias", "多开");
        ObjectNode multiCh = multirun.putObject("channels");
        multiCh.putObject("default").put("alias", "多开");
        multiCh.putObject("default2").put("alias", "多开2");
        ObjectNode revoke = sw.putObject("anti-revoke");
        revoke.put("alias", "防撤");
        ObjectNode revCh = revoke.putObject("channels");
        revCh.putObject("silence").put("alias", "静默");
        revCh.putObject("bubble").put("alias", "气泡*");
        revCh.putObject("alert").put("alias", "通知*");
        ObjectNode coexist = sw.putObject("coexist");
        coexist.put("alias", "共存");
        ObjectNode coCh = coexist.putObject("channels");
        coCh.putObject("default").put("alias", "共存");

        ObjectNode plan = SwPatchService.getSwPatchPlan(SW, accessor(file, MAPPER.createObjectNode(), remote));

        assertEquals(2, plan.get("multirun").size(), "多开的所有渠道都要列出来");
        assertEquals(3, plan.get("revoke").size(), "防撤的所有渠道都要列出来");
        // 共存渠道从 getCoexistPlan 取（程序行不再包含共存）
        var coPlan = SwPatchService.getCoexistPlan(SW, accessor(file, MAPPER.createObjectNode(), remote));
        assertEquals(1, coPlan.get("channels").size(), "共存的渠道也要列出来");
        // 没有缓存/适配时状态应为 unknown，但仍要有条目
        assertEquals("unknown", plan.get("revoke").get(0).get("state").asText());
    }

    // ==================== 环境 ====================

    private Path makeTarget() throws Exception {
        Path source = Path.of(System.getenv("SystemRoot") + "/System32/notepad.exe");
        if (!Files.isRegularFile(source)) {
            source = Path.of(System.getProperty("java.home"), "bin", "java.exe");
        }
        Path target = tmp.resolve("target.exe");
        Files.copy(source, target, StandardCopyOption.REPLACE_EXISTING);
        return target;
    }

    private static int pickOffset(byte[] all, int len) {
        for (int start = 0x200; start + len <= all.length; start++) {
            java.util.Set<Integer> distinct = new java.util.HashSet<>();
            for (int i = 0; i < len; i++) distinct.add(all[start + i] & 0xFF);
            if (distinct.size() >= 3) return start;
        }
        throw new IllegalStateException("找不到合适特征码");
    }

    private static byte[] read(Path file, int offset, int len) throws Exception {
        byte[] all = Files.readAllBytes(file);
        return java.util.Arrays.copyOfRange(all, offset, offset + len);
    }

    private SwConfigAccessor accessor(Path file) {
        return accessor(file, MAPPER.createObjectNode());
    }

    private SwConfigAccessor accessor(Path file, ObjectNode cache) {
        ObjectNode remote = MAPPER.createObjectNode();
        ObjectNode sw = remote.putObject(SW);
        ObjectNode multirun = sw.putObject("multirun");
        multirun.put("alias", "多开");
        ObjectNode ch = multirun.putObject("channels").putObject("default");
        ch.put("alias", "多开");
        ch.putArray("features");
        return accessor(file, cache, remote);
    }

    private SwConfigAccessor accessor(Path file, ObjectNode cache, ObjectNode remote) {
        Map<String, String> settings = new HashMap<>();
        settings.put("inst_path", file.toString());
        settings.put("dll_dir", file.getParent().toString());

        return new SwConfigAccessor(new SwConfigAccessor.Provider() {
            @Override
            public JsonNode getRemoteSw(String sw, String... addr) {
                JsonNode cur = remote.get(sw);
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
                    String v = settings.get(key);
                    if (v != null) return MAPPER.getNodeFactory().textNode(v);
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
                return cache;
            }

            @Override
            public void setSwCache(ObjectNode data) {
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

    private static String toHex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            if (sb.length() > 0) sb.append(' ');
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
