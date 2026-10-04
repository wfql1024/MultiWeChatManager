package com.jfmultichat.config;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * {@link CryptoUtils} 远程配置加密格式测试。
 *
 * <p>加密格式为对外契约（已发布的 remote_configs/ 必须永远能被本类解开），因此这里同时覆盖：
 * <ul>
 *   <li>往返一致性</li>
 *   <li>key 的 ljust(16)[:16] 规则</li>
 *   <li>固定已知向量（格式一旦改动立刻失败）</li>
 *   <li>与历史 Python 版产物的兼容性（legacy_python 存在时才运行）</li>
 * </ul>
 */
class CryptoUtilsTest {

    /** 16 位密钥（Python 侧规则：15 随机字符 + '='） */
    private static final String KEY = "TestKey12345678";

    @Test
    void roundTripPreservesJsonText() throws Exception {
        String json = "{\n  \"app_name\": \"极峰多聊\",\n  \"list\": [1, 2, 3],\n  \"nested\": {\"cn\": \"中文\"}\n}";

        String encrypted = CryptoUtils.encryptAndAppendKey(json, KEY);

        assertTrue(encrypted.endsWith(" " + KEY), "密文末尾应追加 ' ' + key");
        assertEquals(json, CryptoUtils.decryptResponse(encrypted));
    }

    @Test
    void shortKeyIsRightPaddedWithSpaces() throws Exception {
        String json = "{\"a\":1}";

        // 短 key 加解密自洽
        assertEquals(json, CryptoUtils.decryptResponse(CryptoUtils.encryptAndAppendKey(json, "abc")));

        // 已知向量：3 位短 key 必须在解密侧同样右侧补空格后才能还原。
        // 注意：补齐后的 key 以空格结尾，而格式按“最后一个空格”切分，
        // 所以线上传输的 key 必须无尾随空格（生成规则 15 随机字符 + '=' 满足）。
        assertEquals("{\"k\":\"v\"}",
                CryptoUtils.decryptResponse("Dw4NDAsKCQgHBgUEAwIBADdkqjx6a9d1s8HTsbuE37A= abc"));
    }

    @Test
    void longKeyIsTruncatedToFirst16Chars() throws Exception {
        String json = "{\"a\":1}";

        // 20 位 key 与它的前 16 位等价
        String encrypted = CryptoUtils.encryptAndAppendKey(json, "0123456789ABCDEFGHIJ");

        assertEquals(json, CryptoUtils.decryptResponse(
                encrypted.substring(0, encrypted.lastIndexOf(' ')) + " 0123456789ABCDEF"));
    }

    /**
     * 固定已知向量：格式（IV 位置、key 规则、Base64/UTF-8 编码）一旦被改动，本用例立刻失败。
     */
    @Test
    void decryptsKnownAnswerVector() throws Exception {
        String vector = "AAECAwQFBgcICQoLDA0OD8YfQSxJJiKCeclMHZJ5VzdaDhfJauV3e6Nn14EcVN1r KATKey0000000000=";

        assertEquals("{\"k\":\"v\",\"cn\":\"JF\"}", CryptoUtils.decryptResponse(vector));
    }

    /**
     * 兼容性回归：直接解除历史 Python 版（legacy_python/remote_configs）产出的密文。
     *
     * <p>Python 侧以通用换行方式读取源文件（CRLF → LF），故比较前把源 JSON 也归一化为 LF。
     * legacy_python/ 不在版本控制中，缺失时跳过本用例。
     */
    @Test
    void decryptsLegacyPythonProducedConfig() throws Exception {
        Path encryptedPath = Path.of("legacy_python", "remote_configs", "remote_global_v1");
        Path sourcePath = Path.of("legacy_python", "scripts", "original_remote_global_v1.json");
        assumeTrue(Files.exists(encryptedPath) && Files.exists(sourcePath),
                "legacy_python 不在工作区，跳过 Python 兼容性校验");

        String plain = CryptoUtils.decryptResponse(Files.readString(encryptedPath, StandardCharsets.UTF_8));
        String expected = Files.readString(sourcePath, StandardCharsets.UTF_8).replace("\r\n", "\n");

        assertEquals(expected, plain);
    }

    /**
     * 当前发布产物自校验：{@code remote_configs/} 里的密文必须能还原出 {@code scripts/} 里的源 JSON
     * （对应“维护两个远程配置 json → 加密发布”的日常流程）。
     */
    @Test
    void publishedConfigsMatchTheirSources() throws Exception {
        assertPair(Path.of("scripts", "original_remote_global_v2.json"),
                Path.of("remote_configs", "remote_global_v2"), "remote_global_v2");
        assertPair(Path.of("scripts", "original_remote_sw_v10.json"),
                Path.of("remote_configs", "remote_sw_v10"), "remote_sw_v10");
    }

    /**
     * Python 工程（python 分支）侧发布产物自校验：同级 {@code ../MultiWeChatManager} 存在时才运行。
     */
    @Test
    void publishedLegacyConfigsMatchTheirSources() throws Exception {
        Path pythonRepo = Path.of("..", "MultiWeChatManager");
        assumeTrue(Files.isDirectory(pythonRepo), "同级 Python 工程不存在，跳过 legacy 发布产物校验");

        assertPair(pythonRepo.resolve("scripts").resolve("original_remote_global_v1.json"),
                pythonRepo.resolve("remote_configs").resolve("remote_global_v1"), "remote_global_v1");
        assertPair(pythonRepo.resolve("scripts").resolve("original_remote_sw_v9.json"),
                pythonRepo.resolve("remote_configs").resolve("remote_sw_v9"), "remote_sw_v9");
    }

    /**
     * 断言「源 JSON」与「加密产物」一致（加密前会做 CRLF → LF 归一化，故比较前同样归一化）。
     *
     * @param sourcePath    源 JSON 路径
     * @param encryptedPath 加密产物路径
     * @param label         用于断言消息的名称
     */
    private static void assertPair(Path sourcePath, Path encryptedPath, String label) throws Exception {
        assumeTrue(Files.exists(sourcePath) && Files.exists(encryptedPath),
                "缺少 " + label + "（尚未发布？），跳过校验");

        String plain = CryptoUtils.decryptResponse(Files.readString(encryptedPath, StandardCharsets.UTF_8));
        String expected = Files.readString(sourcePath, StandardCharsets.UTF_8).replace("\r\n", "\n");

        assertEquals(expected, plain, label + " 与 " + sourcePath + " 不一致");
    }
}
