package com.jfmultichat.bridge;

import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 远程配置候选 URL 组装测试。
 *
 * <p>回归点：用户把"远程配置源"清空后（{@code remote_*_urls = []}），
 * 下载候选曾变成 **0 个** 导致远程配置永远下载失败；
 * 内置 URL 必须始终作为兜底追加。
 */
class JsBridgeUrlTest {

    private static final String[] BUILTIN = {
            "https://gitee.com/wfraw/remote_sw_v10",
            "https://raw.githubusercontent.com/wfraw/remote_sw_v10"
    };

    @Test
    void emptyUserUrlsFallsBackToBuiltins() {
        List<String> merged = JsBridge.mergeUrls(Collections.emptyList(), BUILTIN);

        assertEquals(Arrays.asList(BUILTIN), merged);
    }

    @Test
    void nullUserUrlsFallsBackToBuiltins() {
        List<String> merged = JsBridge.mergeUrls(null, BUILTIN);

        assertEquals(Arrays.asList(BUILTIN), merged);
    }

    @Test
    void userUrlsComeFirstAndDuplicatesAreRemoved() {
        List<String> merged = JsBridge.mergeUrls(
                Arrays.asList(" https://my.example/remote_sw ", "", BUILTIN[0]),
                BUILTIN);

        assertEquals(Arrays.asList("https://my.example/remote_sw", BUILTIN[0], BUILTIN[1]), merged);
    }

    @Test
    void missingBuiltinsStillKeepsUserUrls() {
        List<String> merged = JsBridge.mergeUrls(Arrays.asList("https://my.example/a"), null);

        assertEquals(1, merged.size());
        assertTrue(merged.contains("https://my.example/a"));
    }
}
