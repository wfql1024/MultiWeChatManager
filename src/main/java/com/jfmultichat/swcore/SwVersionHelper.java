package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 版本计算器 — 从 EXE/DLL 文件提取软件版本号
 * <p>
 * 对应 Python: SwInfoFuncCore.calc_sw_ver (L676-L691)
 * <p>
 * 策略：先从 inst_path 读取文件版本，失败则从 patch_addresses[0] 读取。
 * Windows 文件版本通过 VerQueryValue 获取（需要 JNA 或 native 调用）。
 * 此处提供纯 Java 回退方案（文件名解析）。

 * 依赖: SwConfigAccessor
 */
public final class SwVersionHelper {

    private static final Logger LOG = LoggerFactory.getLogger(SwVersionHelper.class);
    private SwVersionHelper() {}

    /**
     * 计算软件当前版本
     * 对应 Python: calc_sw_ver (L676-L691)
     *
     * @param sw       软件标识
     * @param accessor 配置访问器
     * @return 版本号字符串，如 "8.0.47"；失败返回 null
     */
    public static String calcSwVer(String sw, SwConfigAccessor accessor) {
        try {
            // 1. 从 inst_path 获取文件版本
            String execPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
            if (execPath != null && !execPath.isBlank()) {
                String version = getFileVersion(execPath);
                if (version != null) return version;
            }

            // 2. 从 patch_addresses[0] 获取文件版本
            JsonNode patchAddresses = accessor.getRemoteSw(sw,
                    SwCoreConstants.RemoteSwKey.PATCH_ADDRESSES);
            if (patchAddresses != null && patchAddresses.isArray() && patchAddresses.size() > 0) {
                String firstAddr = patchAddresses.get(0).asText();
                String patchPath = SwPathResolver.resolveSwPath(sw, firstAddr, accessor);
                String version = getFileVersion(patchPath);
                if (version != null) return version;
            }

            return null;
        } catch (Exception e) {
            LOG.error("[版本] 从 dll 文件处获取失败: {}", e.getMessage());
            return null;
        }
    }

    /**
     * 从文件路径获取版本号
     * <p>
     * Windows 平台：优先使用 native 方式（VerQueryValue）。
     * 回退方案：从文件名中解析版本号（如 WeChat_8.0.47.61.exe）。
     *
     * @param filePath 文件路径
     * @return 版本号字符串；失败返回 null
     */
    public static String getFileVersion(String filePath) {
        if (filePath == null || filePath.isBlank()) return null;

        Path path = Path.of(filePath);
        if (!Files.exists(path)) return null;

        // 1. 优先读 Windows 文件版本资源（真实程序版本）
        String winVer = getWindowsFileVersion(filePath);
        if (winVer != null) return winVer;

        // 2. 回退：从文件名解析版本号（如 WeChat_8.0.47.61.exe）
        String fileName = path.getFileName().toString().toLowerCase();

        // 模式 1: WeChat_8.0.47.61.exe
        // 模式 2: WeChatSetup-8.0.47.61.exe
        // 模式 3: 8.0.47.61.dll
        List<String> patterns = Arrays.asList(
                "(?i)[^a-z_]?([0-9]+\\.[0-9]+\\.[0-9]+\\.?[0-9]*)",
                "(?i)v?([0-9]+\\.[0-9]+\\.[0-9]+\\.?[0-9]*)"
        );

        for (String pattern : patterns) {
            try {
                Pattern regex = Pattern.compile(pattern);
                // 去掉扩展名
                String baseName = fileName;
                int dotIdx = baseName.lastIndexOf('.');
                if (dotIdx > 0) baseName = baseName.substring(0, dotIdx);

                Matcher matcher = regex.matcher(baseName);
                if (matcher.find()) {
                    String version = matcher.group(1);
                    // 验证版本号格式
                    String[] parts = version.split("\\.");
                    boolean valid = parts.length >= 2;
                    for (String part : parts) {
                        try {
                            Integer.parseInt(part);
                        } catch (NumberFormatException e) {
                            valid = false;
                            break;
                        }
                    }
                    if (valid) return version;
                }
            } catch (Exception e) {
                // 继续尝试下一个模式
            }
        }

        // 无法从文件名解析，返回 null
        LOG.debug("[版本] 无法从文件名解析版本: {}", fileName);
        return null;
    }

    /**
     * 读取 Windows 可执行文件的版本资源（VerQueryValue）.
     *
     * <p>与旧版 Python `file_utils.get_file_version` **同一来源**：`win32api.GetFileVersionInfo(path,'\\')`
     * 的 `FileVersionMS/LS`，也就是资源管理器"详细信息"里的**文件版本**（不是产品版本）。
     * 这条逻辑一度缺失（原实现只从文件名抠版本号，真实文件名如 `WeChat.exe` 抠不出来 → 版本列常年为空）。
     *
     * <p>取值顺序：文件版本 → 产品版本（仅当文件版本明显是垃圾值时，如抖音的 `29622.0.0.0`）→ null（交给调用方回退文件名解析）。
     * 非 Windows、无版本资源、JNA 不可用等一律返回 null，只降级不抛错。
     *
     * @param filePath 文件绝对路径
     * @return 形如 {@code 3.9.12.55} 的版本号；取不到返回 null
     */
    public static String getWindowsFileVersion(String filePath) {
        try {
            com.sun.jna.platform.win32.VerRsrc.VS_FIXEDFILEINFO info =
                    com.sun.jna.platform.win32.VersionUtil.getFileVersionInfo(filePath);
            if (info == null) return null;
            String fileVer = formatFixedVersion(info.dwFileVersionMS.longValue(),
                    info.dwFileVersionLS.longValue());
            if (isPlausibleVersion(fileVer)) return fileVer;
            String prodVer = formatFixedVersion(info.dwProductVersionMS.longValue(),
                    info.dwProductVersionLS.longValue());
            if (isPlausibleVersion(prodVer)) return prodVer;
            return null;
        } catch (Throwable t) {   // JNA 缺失 / 非 Windows / 文件无版本资源
            LOG.debug("[版本] 读取文件版本资源失败: {} - {}", filePath, t.getMessage());
            return null;
        }
    }

    /** 把 VS_FIXEDFILEINFO 的 MS/LS 拼成 a.b.c.d（HIWORD=高位、LOWORD=低位，与旧版 Python 一致） */
    private static String formatFixedVersion(long ms, long ls) {
        return ((ms >> 16) & 0xFFFF) + "." + (ms & 0xFFFF) + "."
                + ((ls >> 16) & 0xFFFF) + "." + (ls & 0xFFFF);
    }

    /**
     * 版本号是否像"真实版本"：排除全零，以及 {@code 29622.0.0.0} 这类把构建号塞进主版本位的垃圾值
     * （抖音聊天的文件版本就是这种，其产品版本 1.1.32.0 才是可读的）。
     */
    private static boolean isPlausibleVersion(String v) {
        if (v == null || "0.0.0.0".equals(v)) return false;
        String[] p = v.split("\\.");
        if (p.length != 4) return false;
        try {
            int major = Integer.parseInt(p[0]);
            int minor = Integer.parseInt(p[1]);
            int build = Integer.parseInt(p[2]);
            int rev = Integer.parseInt(p[3]);
            if (major == 0) return false;
            // x.0.0.0 且 x 很大 → 不是语义化版本，是构建号
            return !(minor == 0 && build == 0 && rev == 0 && major >= 1000);
        } catch (NumberFormatException e) {
            return false;
        }
    }

    /**
     * 从版本文件夹列表中获取最新版本文件夹
     * 对应 Python: file_utils.get_newest_full_version_dir
     *
     * @param versionFolders 版本文件夹路径列表
     * @return 最新版本文件夹；为空列表返回 null
     */
    public static String getNewestFullVersionDir(List<String> versionFolders) {
        if (versionFolders == null || versionFolders.isEmpty()) return null;
        if (versionFolders.size() == 1) return versionFolders.get(0);

        String newest = versionFolders.get(0);
        for (int i = 1; i < versionFolders.size(); i++) {
            String candidate = versionFolders.get(i);
            if (compareVersionDesc(candidate, newest) > 0) {
                newest = candidate;
            }
        }
        return newest;
    }

    /**
     * 降序比较两个路径中的版本号
     * @return positive if a > b
     */
    public static int compareVersionDesc(String a, String b) {
        // 提取路径中的版本号部分
        String verA = extractVersionFromPath(a);
        String verB = extractVersionFromPath(b);
        if (verA == null) return -1;
        if (verB == null) return 1;
        return SwRuleResolver.compareVersionDesc(verA, verB);
    }

    /**
     * 从路径中提取版本号
     */
    private static String extractVersionFromPath(String path) {
        Path p = Path.of(path);
        String name = p.getFileName().toString();
        // 去除前导非数字字符
        int start = 0;
        while (start < name.length() && !Character.isDigit(name.charAt(start))) start++;
        if (start >= name.length()) return null;
        int end = start;
        while (end < name.length() && (Character.isDigit(name.charAt(end)) || name.charAt(end) == '.')) end++;
        return name.substring(start, end);
    }
}
