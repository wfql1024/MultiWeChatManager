package com.jfmultichat.swcore;

import java.nio.ByteBuffer;

/**
 * 最小 PE 解析 — 只做 FOA(文件偏移) → RVA 换算，供 jmp_offset 规则计算相对跳转。
 * <p>
 * 对应 Python: {@code MMap2PeFile}（legacy_python/utils/file_utils.py L496-580），
 * 只保留 foa_to_rva / calculate_jump_offset 两部分。
 */
public final class SwPeImage {

    private final int[] secStart;   // PointerToRawData
    private final int[] secEnd;     // PointerToRawData + SizeOfRawData
    private final int[] secVa;      // VirtualAddress
    private final int sizeOfHeaders;

    private SwPeImage(int[] secStart, int[] secEnd, int[] secVa, int sizeOfHeaders) {
        this.secStart = secStart;
        this.secEnd = secEnd;
        this.secVa = secVa;
        this.sizeOfHeaders = sizeOfHeaders;
    }

    /** 解析失败返回 null（调用方按"无法计算"处理） */
    public static SwPeImage parse(ByteBuffer buffer) {
        try {
            ByteBuffer b = buffer.duplicate();
            b.order(java.nio.ByteOrder.LITTLE_ENDIAN);
            if (b.capacity() < 0x40 || b.get(0) != 'M' || b.get(1) != 'Z') return null;

            int peOff = le32(b, 0x3C);
            if (peOff <= 0 || peOff + 24 > b.capacity()) return null;
            if (b.get(peOff) != 'P' || b.get(peOff + 1) != 'E'
                    || b.get(peOff + 2) != 0 || b.get(peOff + 3) != 0) return null;

            int coff = peOff + 4;
            int numSections = le16(b, coff + 2);
            int optSize = le16(b, coff + 16);
            int opt = coff + 20;
            if (numSections <= 0 || numSections > 96 || opt + 64 > b.capacity()) return null;

            int sizeOfHeaders = le32(b, opt + 60);
            int secTable = opt + optSize;
            if (secTable + numSections * 40 > b.capacity()) return null;

            int[] start = new int[numSections];
            int[] end = new int[numSections];
            int[] va = new int[numSections];
            for (int i = 0; i < numSections; i++) {
                int s = secTable + i * 40;
                va[i] = le32(b, s + 12);
                int rawSize = le32(b, s + 16);
                int rawPtr = le32(b, s + 20);
                start[i] = rawPtr;
                end[i] = rawPtr + Math.max(rawSize, 0);
            }
            return new SwPeImage(start, end, va, sizeOfHeaders);
        } catch (Exception e) {
            return null;
        }
    }

    /** 文件偏移 → 相对虚拟地址；不在任何节区（也不在头部）时返回 null */
    public Integer foaToRva(int foa) {
        for (int i = 0; i < secStart.length; i++) {
            if (foa >= secStart[i] && foa < secEnd[i]) {
                return foa - secStart[i] + secVa[i];
            }
        }
        if (sizeOfHeaders > 0 && foa < sizeOfHeaders) return foa;
        return null;
    }

    /**
     * 计算 jmp_offset 规则要填的 4 字节相对偏移。
     * <p>
     * 与 Python 一致：{@code (imageBase + targetRva) - (imageBase + patchRva + instrLen)}
     * → imageBase 抵消，实际就是 {@code targetRva - (patchRva + instrLen)}。
     *
     * @param targetFoa 目标地址（文件偏移）
     * @param patchFoa  补丁所在地址（文件偏移）
     * @param instrLen  指令长度（相对偏移起始位置 + 4）
     * @return 偏移值；任一侧无法换算返回 null
     */
    public Integer jumpOffset(int targetFoa, int patchFoa, int instrLen) {
        Integer targetRva = foaToRva(targetFoa);
        Integer patchRva = foaToRva(patchFoa);
        if (targetRva == null || patchRva == null) return null;
        return targetRva - (patchRva + instrLen);
    }

    // ==================== 小工具 ====================

    private static int le16(ByteBuffer b, int off) {
        return (b.get(off) & 0xFF) | ((b.get(off + 1) & 0xFF) << 8);
    }

    private static int le32(ByteBuffer b, int off) {
        return (b.get(off) & 0xFF)
                | ((b.get(off + 1) & 0xFF) << 8)
                | ((b.get(off + 2) & 0xFF) << 16)
                | ((b.get(off + 3) & 0xFF) << 24);
    }
}
