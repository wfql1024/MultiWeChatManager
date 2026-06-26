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

        // 尝试从文件名解析版本号
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

        // 无法从文件名解析，返回 null（需要 JNA 调用 VerQueryValue）
        LOG.debug("[版本] 无法从文件名解析版本: {}", fileName);
        return null;
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
