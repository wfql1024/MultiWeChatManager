package com.jfmultichat.swcore;

import org.junit.jupiter.api.Test;

import java.nio.ByteBuffer;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 特征码分词/对齐的回归测试。
 * <p>
 * 覆盖两个曾导致线上扫描全挂的问题：
 * <ul>
 *   <li>尾部 {@code ...} 的语义（= 其余不变），曾被判成"位置无效"</li>
 *   <li>{@code !!} 占位被分词器吃掉（曾经变成 {@code !} 再 parseInt 崩掉）</li>
 * </ul>
 */
class SwHexUtilsTest {

    @Test
    void tokenizeWildcard_trailingTruncate_dropsMarker() {
        assertEquals(List.of("90", "E9"), SwHexUtils.tokenizeWildcard("90 E9 ..."));
        assertEquals(List.of("E9", "BE", "00"), SwHexUtils.tokenizeWildcard("E9 BE 00 ..."));
    }

    @Test
    void tokenizeWildcard_leadingTruncate_keepsMarkerToken() {
        assertEquals(List.of("...", "2E", "78", "6D", "6C"),
                SwHexUtils.tokenizeWildcard("... 2E 78 6D 6C"));
    }

    @Test
    void tokenizeWildcard_keepsBangBang() {
        assertEquals(List.of("57", "00", "65", "00", "!!"),
                SwHexUtils.tokenizeWildcard("57 00 65 00 !! ..."));
    }

    @Test
    void tokenizeWildcard_rejectsHalfWildcard() {
        assertNull(SwHexUtils.tokenizeWildcard("5? 00"));
    }

    @Test
    void search_trailingTruncate_keepsOriginalTail() {
        byte[] data = {0x11, 0x22, 0x33, 0x44, 0x55, 0x66};
        List<SwHexUtils.ScanResult> res = SwHexUtils.searchPatternDicts(
                ByteBuffer.wrap(data), "11 22 33 44 55 66", "90 E9 ...", 0, 0);
        assertNotNull(res, "对齐应成功");
        assertEquals(1, res.size());
        assertEquals(0, res.get(0).offset);
        assertEquals("90 e9 33 44 55 66", res.get(0).modified, "尾部应保留原字节");
    }

    @Test
    void search_bangBang_staysAsPlaceholder() {
        byte[] data = {0x57, 0x00, 0x65, 0x00, 0x41, 0x42};
        List<SwHexUtils.ScanResult> res = SwHexUtils.searchPatternDicts(
                ByteBuffer.wrap(data), "57 00 65 00 41 42", "57 00 65 00 !! ...", 0, 0);
        assertNotNull(res);
        assertFalse(res.isEmpty());
        assertTrue(res.get(0).modified.contains("!!"),
                "缓存里的 modified 必须保留 !! 占位，供共存创建时替换序号；实际: " + res.get(0).modified);
    }
}
