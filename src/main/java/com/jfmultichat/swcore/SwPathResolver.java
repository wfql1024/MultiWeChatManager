package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.FileInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * 路径解析器 — 解析补丁路径中的 %var% 引用
 * <p>
 * 对应 Python: SwInfoFuncCore.resolve_sw_path (L98-L119)
 * <p>
 * 示例: "%dll_dir%/WeChatWin.dll" -> "C:/WeChat/WeChatWin.dll"
 *
 * 依赖: SwConfigAccessor
 */
public final class SwPathResolver {

    private static final Logger LOG = LoggerFactory.getLogger(SwPathResolver.class);
    private SwPathResolver() {}

    private static final String PATH_VAR_PREFIX = "%";
    private static final String PATH_VAR_DELIM_LEFT = "%";
    private static final String PATH_VAR_DELIM_RIGHT = "%";

    /**
     * 解析补丁路径，将 %xxx% 变量替换为实际路径
     * 对应 Python: resolve_sw_path (L98-L119)
     *
     * @param sw    软件标识
     * @param addr  含变量的路径，如 "%dll_dir%/WeChatWin.dll"
     * @param accessor 配置访问器
     * @return 解析后的路径（使用 / 分隔符）
     */
    public static String resolveSwPath(String sw, String addr, SwConfigAccessor accessor) {
        String[] parts = addr.replace('\\', '/').split("/", -1);
        List<String> resolvedParts = new ArrayList<>();

        for (String part : parts) {
            if (part.isEmpty()) continue;

            if (part.startsWith("%") && part.endsWith("%") && part.length() > 2) {
                String varName = part.substring(1, part.length() - 1);
                try {
                    String resolved;
                    if ("inst_dir".equals(varName)) {
                        String instPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
                        if (instPath == null) {
                            throw new NoSuchElementException("INST_PATH 未定义");
                        }
                        resolved = new File(instPath).getParent().replace('\\', '/');
                    } else {
                        resolved = accessor.tryGetPathOf(sw, varName);
                    }
                    resolvedParts.add(resolved.trim().replaceAll("^[/\\\\]+|[/\\\\]+$", ""));
                } catch (NoSuchElementException e) {
                    throw new IllegalArgumentException("路径变量未定义: %" + varName + "%", e);
                } catch (Exception e) {
                    LOG.error("[路径解析] 变量 {} 解析失败: {}", varName, e.getMessage());
                    throw new IllegalArgumentException("路径变量解析失败: %" + varName + "%", e);
                }
            } else {
                resolvedParts.add(part);
            }
        }

        return String.join("/", resolvedParts);
    }

    /**
     * 从地址解析共存路径
     * 对应 Python: get_coexist_path_from_address (L122-L131)
     *
     * @param sw              软件标识
     * @param address         地址键
     * @param coexistChannel  共存通道
     * @param ordinal         序列号
     * @param accessor        配置访问器
     * @return 共存文件路径
     */
    public static String getCoexistPathFromAddress(
            String sw, String address, String coexistChannel, String ordinal,
            SwConfigAccessor accessor) {

        // 从远程配置获取通配符地址
        JsonNode wildcardDict = accessor.getRemoteSw(sw,
                SwCoreConstants.RemoteSwKey.COEXIST,
                SwCoreConstants.RemoteSwKey.CHANNELS,
                coexistChannel,
                "patch_wildcard");

        String wildcardAddr = "";
        if (wildcardDict != null && wildcardDict.isObject() && wildcardDict.has(address)) {
            JsonNode addrNode = wildcardDict.get(address);
            if (addrNode != null && addrNode.isTextual()) {
                wildcardAddr = addrNode.asText();
            }
        }

        // 解析路径变量
        String coexistPatchWildcard = resolveSwPath(sw, wildcardAddr, accessor);

        // 替换 ? 为 ordinal
        return coexistPatchWildcard.replace("?", ordinal).replace('\\', '/');
    }

    /**
     * 检查路径是否为有效的 %var% 引用
     */
    public static boolean isPathVariable(String part) {
        return part.startsWith("%") && part.endsWith("%") && part.length() > 2;
    }

    /**
     * 从 %var% 引用中提取变量名
     */
    public static String extractVariableName(String varRef) {
        if (!isPathVariable(varRef)) return null;
        return varRef.substring(1, varRef.length() - 1);
    }
}
