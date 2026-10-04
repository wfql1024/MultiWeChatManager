package com.jfmultichat.swcore;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * {@link SwAccountOps#resolveInstDir} 测试。
 *
 * <p>回归点：共存 exe 扫描以安装目录为基准，而 {@code inst_path} 既有"主程序 exe 路径"也有
 * "安装目录"两种存法；只取父目录会扫描到上一级目录，导致共存账号全部漏掉
 * （实测：WeChat 的 inst_path 存的是目录，只取父目录时共存账号为 0，修好后取到 WeCha1.exe/WeCha2.exe）。
 */
class SwAccountOpsTest {

    @Test
    void takesParentWhenGivenExePath(@TempDir Path dir) throws Exception {
        Path exe = Files.createFile(dir.resolve("App.exe"));

        assertEquals(dir.toString(), SwAccountOps.resolveInstDir(exe.toString()));
    }

    @Test
    void usesDirectoryItselfWhenGivenDirectory(@TempDir Path dir) {
        assertEquals(dir.toString(), SwAccountOps.resolveInstDir(dir.toString()));
    }

    @Test
    void returnsNullForBlankInput() {
        assertNull(SwAccountOps.resolveInstDir(null));
        assertNull(SwAccountOps.resolveInstDir(""));
        assertNull(SwAccountOps.resolveInstDir("   "));
    }
}
