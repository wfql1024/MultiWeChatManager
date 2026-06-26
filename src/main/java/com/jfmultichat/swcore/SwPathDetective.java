package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * 路径探测 — 三级策略探测软件路径
 * <p>
 * 对应 Python: SwInfoFuncCore._get_sw_path_by_register,
 * _get_sw_path_by_memo_and_regex, _guess_sw_path,
 * _get_sw_install_path_from_process, _get_sw_dll_dir_by_files,
 * _get_sw_data_dir_from_other_sw
 *
 * 三级策略:
 * 1. reg (注册表) — 从 Windows 注册表读取路径
 * 2. regex (内存映射正则) — 通过进程内存映射文件匹配正则表达式
 * 3. addr (猜测) — 从已知系统目录拼接 sub_path
 */
public final class SwPathDetective {

    private static final Logger LOG = LoggerFactory.getLogger(SwPathDetective.class);
    private SwPathDetective() {
        throw new UnsupportedOperationException("SwPathDetective requires a NativeOps");
    }

    /**
     * 路径条目（值 + 是否为目录）
     */
    public static class PathEntry {
        public final String path;
        public final boolean isDir;

        public PathEntry(String path, boolean isDir) {
            this.path = path;
            this.isDir = isDir;
        }

        @Override
        public String toString() {
            return path + (isDir ? "/" : "");
        }
    }

    private final NativeOps nativeOps;

    public SwPathDetective(NativeOps nativeOps) {
        this.nativeOps = nativeOps;
    }

    // ==================== 统一探测入口 ====================

    /**
     * 探测指定 SW 的指定路径类型的所有候选
     * 按优先级: reg > regex > addr (猜测)
     * 对应 Python: try_detect_path (L1668-L1707)
     *
     * @param sw       软件标识
     * @param pathType 路径类型 (inst_path / data_dir / dll_dir)
     * @param accessor 配置访问器
     * @return 候选路径列表（去重）
     */
    public List<PathEntry> detectAll(String sw, String pathType, SwConfigAccessor accessor) {
        Set<String> seen = new LinkedHashSet<>();

        // 1. 进程查询（仅 inst_path）
        if ("inst_path".equals(pathType)) {
            List<PathEntry> procResults = queryByProcess(sw, accessor);
            for (PathEntry e : procResults) {
                String normalized = normalizePath(e.path, e.isDir);
                if (normalized != null) seen.add(normalized);
            }
        }

        // 2. 注册表查询
        List<PathEntry> regResults = queryByRegister(sw, pathType, accessor);
        for (PathEntry e : regResults) {
            String normalized = normalizePath(e.path, e.isDir);
            if (normalized != null) seen.add(normalized);
        }

        // 3. 内存映射正则查询
        List<PathEntry> regexResults = queryByMemoryRegex(sw, pathType, accessor);
        for (PathEntry e : regexResults) {
            String normalized = normalizePath(e.path, e.isDir);
            if (normalized != null) seen.add(normalized);
        }

        // 3. 猜测 (addr)
        List<PathEntry> guessResults = queryByGuess(sw, pathType, accessor);
        for (PathEntry e : guessResults) {
            String normalized = normalizePath(e.path, e.isDir);
            if (normalized != null) seen.add(normalized);
        }

        // 4. 其他 SW 推断（仅 data_dir）
        if ("data_dir".equals(pathType)) {
            List<PathEntry> otherResults = queryFromOtherSw(sw, accessor);
            for (PathEntry e : otherResults) {
                String normalized = normalizePath(e.path, true);
                if (normalized != null) seen.add(normalized);
            }
        }

        // 5. DLL 目录特殊处理
        if ("dll_dir".equals(pathType)) {
            List<PathEntry> dllByFiles = queryDllDirByFiles(sw, accessor);
            for (PathEntry e : dllByFiles) {
                String normalized = normalizePath(e.path, true);
                if (normalized != null) seen.add(normalized);
            }
        }

        List<PathEntry> seenList = new ArrayList<>();
        for (String p : seen) {
            // Default: treat as directory
            seenList.add(new PathEntry(p, true));
        }
        return seenList;
    }

    /**
     * 规范化路径：去除引号、统一分隔符、追加 exe 名等
     */
    private String normalizePath(String rawPath, boolean isDir) {
        if (rawPath == null || rawPath.isBlank()) return null;
        String path = rawPath.replace('\\', '/').strip();
        // 去除首尾引号
        if ((path.startsWith("\"") && path.endsWith("\"")) ||
                (path.startsWith("'") && path.endsWith("'"))) {
            path = path.substring(1, path.length() - 1).replace('\\', '/');
        }
        return path;
    }

    // ==================== 2. 注册表查询 ====================

    /**
     * 通过进程枚举获取安装路径
     * 对应 Python: _get_sw_install_path_from_process (L935-L943)
     * <p>
     * 原理：枚举所有运行中的进程，匹配远程配置中的 exe 名称，
     * 直接取其 exe 路径即为安装路径。
     */
    public List<PathEntry> queryByProcess(String sw, SwConfigAccessor accessor) {
        if (nativeOps == null) {
            LOG.debug("[路径] 进程查询未启用（需要 JNA）");
            return Collections.emptyList();
        }

        // 获取远程配置中的 exe 名称（如 WeChat.exe）
        JsonNode exeNode = accessor.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.EXECUTABLE);
        LOG.info("[路径进程] sw={}, exeNode={}", sw, exeNode);
        if (exeNode == null || !exeNode.isTextual()) return Collections.emptyList();
        String exeName = exeNode.asText();

        // 获取 exe 通配符列表
        List<String> wildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());
        if (wildcards.isEmpty()) wildcards = List.of(exeName);

        // 通过 JNA 枚举进程
        Map<String, List<Integer>> namePids = nativeOps.getPidsByWildcardsAndGroup(wildcards);
        if (namePids.isEmpty()) {
            LOG.debug("[路径] 未找到匹配的进程: sw={}, exe={}", sw, exeName);
            return Collections.emptyList();
        }

        List<PathEntry> results = new ArrayList<>();
        for (Map.Entry<String, List<Integer>> entry : namePids.entrySet()) {
            String name = entry.getKey();
            List<Integer> pids = entry.getValue();
            // 取第一个进程的 exe 路径
            if (!pids.isEmpty()) {
                try {
                    String exePath = nativeOps.getProcessImagePath(pids.get(0));
                    if (exePath != null && !exePath.isBlank()) {
                        String normalized = normalizePath(exePath, false);
                        if (normalized != null) {
                            results.add(new PathEntry(normalized, false));
                            LOG.info("[路径进程] 通过进程枚举获取安装路径: sw={}, exe={}, path={}",
                                    sw, name, exePath);
                        }
                    }
                } catch (Exception e) {
                    LOG.debug("[路径进程] 获取进程路径失败: pid={}", pids.get(0), e);
                }
            }
        }

        LOG.info("[路径] 进程查询得到 {} 个候选: sw={}", results.size(), sw);
        return results;
    }

    // ==================== 3. 注册表查询 ====================

    /**
     * 通过 Windows 注册表查询路径
     * 对应 Python: _get_sw_path_by_register (L1049-L1085)
     *
     * RemoteSwConfig 格式:
     * {
     *   "path_detect": {
     *     "inst_path": {
     *       "reg": {
     *         "current_user": [
     *           {"sub_key": "Software\\Tencent\\WeChat", "value_name": "InstallPath"}
     *         ],
     *         "local_machine": [
     *           {"sub_key": "SOFTWARE\\...\\Uninstall\\WeChat", "value_name": "InstallLocation"},
     *           {"sub_key": "SOFTWARE\\...\\Uninstall\\WeChat", "value_name": "DisplayIcon", "is_dir": false}
     *         ]
     *       }
     *     }
     *   }
     * }
     */
    public List<PathEntry> queryByRegister(String sw, String pathType, SwConfigAccessor accessor) {
        if (nativeOps == null) {
            LOG.debug("[路径] 注册表查询未启用（需要 JNA）");
            return Collections.emptyList();
        }

        JsonNode regDict = accessor.getRemoteSw(sw, "path_detect", pathType, "reg");
        if (regDict == null || !regDict.isObject()) {
            return Collections.emptyList();
        }

        // 获取 exe 名（用于 is_dir=false 时拼接）
        String exeName = null;
        if ("inst_path".equals(pathType)) {
            JsonNode exeNode = accessor.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.EXECUTABLE);
            if (exeNode != null && exeNode.isTextual()) {
                exeName = exeNode.asText();
            }
        }

        // 根键映射
        Map<String, Long> hkeyMap = Map.of(
                "classes_root", 0x80000000L,  // HKEY_CLASSES_ROOT
                "current_user", 0x80000001L,  // HKEY_CURRENT_USER
                "local_machine", 0x80000002L, // HKEY_LOCAL_MACHINE
                "users", 0x80000003L,         // HKEY_USERS
                "current_config", 0x80000005L // HKEY_CURRENT_CONFIG
        );

        List<PathEntry> results = new ArrayList<>();
        List<String> hkeyNames = new ArrayList<>();
        regDict.fieldNames().forEachRemaining(hkeyNames::add);
        for (String hkeyName : hkeyNames) {
            Long hkeyValue = hkeyMap.get(hkeyName);
            if (hkeyValue == null) continue;

            JsonNode regList = regDict.get(hkeyName);
            if (regList == null || !regList.isArray()) continue;

            for (JsonNode regEntry : regList) {
                if (!regEntry.isObject()) continue;
                String subKey = regEntry.has("sub_key") ? regEntry.get("sub_key").asText() : null;
                String valueName = regEntry.has("value_name") ? regEntry.get("value_name").asText() : null;
                boolean isDir = regEntry.has("is_dir") ? regEntry.get("is_dir").asBoolean(true) : true;
                String suffix = regEntry.has("suffix") ? regEntry.get("suffix").asText() : null;

                if (subKey == null || valueName == null) continue;

                try {
                    String value = nativeOps.readRegistryValue(hkeyValue, subKey, valueName);
                    if (value == null || value.isBlank()) continue;

                    // 如果 is_dir=false，需要从值中提取路径
                    String path = value.replace('\\', '/').strip();
                    if (!isDir) {
                        // 例如 DisplayIcon = "C:\Program Files\WeChat\WeChat.exe"
                        // 取父目录
                        path = new File(path).getParent();
                        if (path == null) path = value;
                        // 拼接 exe 名
                        if (exeName != null && !exeName.isBlank()) {
                            path = path + "/" + exeName;
                        }
                    }

                    // 处理 suffix
                    if (suffix != null && !suffix.isBlank()) {
                        path = path + "/" + suffix.replace('\\', '/');
                    }

                    results.add(new PathEntry(path, isDir));
                    LOG.info("[路径注册表] sw={}, pathType={}, value={}, result={}",
                            sw, pathType, valueName, path);
                } catch (Exception e) {
                    LOG.debug("[路径注册表] 读取失败: hkey={}, subKey={}, valueName={}",
                            hkeyName, subKey, valueName, e);
                }
            }
        }

        LOG.info("[路径] 注册表查询得到 {} 个候选: sw={}, pathType={}",
                results.size(), sw, pathType);
        return results;
    }

    // ==================== 2. 内存映射正则查询 ====================

    /**
     * 通过进程内存映射 + 正则表达式匹配路径
     * 对应 Python: _get_sw_path_by_memo_and_regex (L1087-L1118)
     *
     * RemoteSwConfig 格式:
     * {
     *   "path_detect": {
     *     "data_dir": {
     *       "regex": {
     *         "-": [
     *           {"regex": "^(.*?)/[A-Za-z0-9_-]+/Msg(?:/[^/]+)*$"}
     *         ]
     *       }
     *     }
     *   }
     * }
     */
    public List<PathEntry> queryByMemoryRegex(String sw, String pathType, SwConfigAccessor accessor) {
        if (nativeOps == null) {
            LOG.debug("[路径] 内存映射查询未启用（需要 JNA）");
            return Collections.emptyList();
        }

        JsonNode regexDict = accessor.getRemoteSw(sw, "path_detect", pathType, "regex");
        if (regexDict == null || !regexDict.isObject()) {
            return Collections.emptyList();
        }

        // 获取 exe 通配符列表
        List<String> exeWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());

        List<PathEntry> results = new ArrayList<>();
        List<String> groupNames = new ArrayList<>();
        regexDict.fieldNames().forEachRemaining(groupNames::add);
        LOG.info("[路径内存映射] sw={}, groupNames={}", sw, groupNames);
        for (String groupName : groupNames) {
            JsonNode groupList = regexDict.get(groupName);
            if (groupList == null || !groupList.isArray()) continue;

            for (JsonNode regexEntry : groupList) {
                if (!regexEntry.isObject()) continue;
                String regexPattern = regexEntry.has("regex") ? regexEntry.get("regex").asText() : null;
                LOG.info("[路径内存映射] sw={}, exeWildcards={}, regexPattern={}", sw, exeWildcards, regexPattern);
                if (regexPattern == null || regexPattern.isBlank()) continue;

                try {
                    java.util.regex.Pattern pattern = java.util.regex.Pattern.compile(regexPattern);
                    List<String> matchedPaths = nativeOps.queryMemoryMapPaths(
                            sw, exeWildcards, regexPattern);
                    for (String path : matchedPaths) {
                        String normalized = normalizePath(path, "data_dir".equals(pathType) || "dll_dir".equals(pathType));
                        if (normalized != null) {
                            results.add(new PathEntry(normalized, "data_dir".equals(pathType) || "dll_dir".equals(pathType)));
                            LOG.info("[路径内存映射] sw={}, regex={}, matched={}", sw, regexPattern, path);
                        }
                    }
                } catch (Exception e) {
                    LOG.warn("[路径内存映射] 正则编译或查询失败: sw={}, pattern={}", sw, regexPattern, e);
                }
            }
        }

        LOG.info("[路径] 内存映射正则查询得到 {} 个候选: sw={}, pathType={}",
                results.size(), sw, pathType);
        return results;
    }

    // ==================== 3. 猜测路径 (addr) ====================

    /**
     * 通过 path_detect.addr 猜测路径
     * 对应 Python: _guess_sw_path (L1018-L1047)
     */
    public List<PathEntry> queryByGuess(String sw, String pathType, SwConfigAccessor accessor) {
        JsonNode addrDict = accessor.getRemoteSw(sw, "path_detect", pathType, "addr");
        if (addrDict == null || !addrDict.isObject()) {
            return Collections.emptyList();
        }

        // 系统路径映射
        Map<String, String> sysPaths = new LinkedHashMap<>();
        sysPaths.put("~", System.getProperty("user.home"));
        sysPaths.put("Documents", guessDocumentsPath());
        sysPaths.put("ProgramFiles", System.getenv("ProgramFiles"));
        sysPaths.put("ProgramFiles(x86)", System.getenv("ProgramFiles(x86)"));
        sysPaths.put("appdata", System.getenv("APPDATA"));
        sysPaths.put("localappdata", System.getenv("LOCALAPPDATA"));
        sysPaths.put("programdata", System.getenv("ProgramData"));

        List<PathEntry> results = new ArrayList<>();
        boolean isDir = !"inst_path".equals(pathType);

        for (Map.Entry<String, String> entry : sysPaths.entrySet()) {
            String sysPathKey = entry.getKey();
            String sysPathValue = entry.getValue();
            if (sysPathValue == null || sysPathValue.isBlank()) continue;

            JsonNode addrList = addrDict.get(sysPathKey);
            if (addrList == null || !addrList.isArray()) continue;

            for (JsonNode addrNode : addrList) {
                if (!addrNode.isObject()) continue;
                JsonNode subPathNode = addrNode.get("sub_path");
                if (subPathNode == null || !subPathNode.isTextual()) continue;

                String subPath = subPathNode.asText().replace('\\', '/');
                String fullPath = (sysPathValue + "/" + subPath).replace('\\', '/');

                // 检查 is_dir 标志
                boolean nodeIsDir = addrNode.has("is_dir") ? addrNode.get("is_dir").asBoolean(true) : true;

                results.add(new PathEntry(fullPath, nodeIsDir));
            }
        }

        LOG.info("[路径] 猜测 {} 得到 {} 个候选: sw={}, pathType={}",
                isDir ? "目录" : "文件", results.size(), sw, pathType);
        return results;
    }

    // ==================== 4. 从其他 SW 推断数据目录 ====================

    /**
     * 通过其他同类软件的数据目录推断当前软件的数据目录
     * 对应 Python: _get_sw_data_dir_from_other_sw (L1709-L1733)
     */
    public List<PathEntry> queryFromOtherSw(String sw, SwConfigAccessor accessor) {
        JsonNode dataDirNameNode = accessor.getRemoteSw(sw, "data_dir_name");
        if (dataDirNameNode == null || !dataDirNameNode.isTextual()) return Collections.emptyList();
        String dataDirName = dataDirNameNode.asText();
        if (dataDirName.isBlank()) return Collections.emptyList();

        // 微信/企微共用同级目录
        if ("WeChat".equals(sw) || "Weixin".equals(sw)) {
            String otherKey = "WeChat".equals(sw) ? "Weixin" : "WeChat";
            String otherPath = accessor.tryGetPathOf(otherKey, SwCoreConstants.LocalSettingKey.DATA_DIR);
            if (otherPath != null) {
                return List.of(new PathEntry(
                        new File(otherPath).getParent() + "/" + dataDirName, true));
            }
        }

        // QQ/TIM 共用同一数据目录
        if ("QQNT".equals(sw) || "TIM".equals(sw) || "QQ".equals(sw)) {
            for (String otherKey : List.of("QQNT", "TIM", "QQ")) {
                if (otherKey.equals(sw)) continue;
                String otherPath = accessor.tryGetPathOf(otherKey, SwCoreConstants.LocalSettingKey.DATA_DIR);
                if (otherPath != null) {
                    return List.of(new PathEntry(otherPath, true));
                }
            }
        }

        return Collections.emptyList();
    }

    // ==================== 5. DLL 目录文件遍历 ====================

    /**
     * 通过文件遍历方式获取 DLL 目录
     * 对应 Python: _get_sw_dll_dir_by_files (L1735-L1770)
     */
    public List<PathEntry> queryDllDirByFiles(String sw, SwConfigAccessor accessor) {
        String installPath = accessor.tryGetPathOf(sw, SwCoreConstants.LocalSettingKey.INST_PATH);
        if (installPath == null || installPath.isBlank()) return Collections.emptyList();

        String installDir = new File(installPath).getParent();
        if (installDir == null) return Collections.emptyList();

        // 从远程配置获取 patch_addresses 中 %dll_dir%/ 开头的条目
        JsonNode patchAddrs = accessor.getRemoteSw(sw, "patch_addresses");
        if (patchAddrs == null || !patchAddrs.isArray()) return Collections.emptyList();

        List<PathEntry> results = new ArrayList<>();
        Set<String> seenDirs = new LinkedHashSet<>();

        for (JsonNode addrNode : patchAddrs) {
            if (!addrNode.isTextual()) continue;
            String addr = addrNode.asText().replace('\\', '/');
            if (!addr.startsWith("%dll_dir%/")) continue;

            String rest = addr.substring("%dll_dir%/".length());
            if (rest.contains("/")) continue; // 不能有子目录

            String dllName = rest; // 如 "WeChat.dll"

            // 遍历安装目录查找包含 dllName 的目录
            try {
                Files.walk(Path.of(installDir)).filter(Files::isDirectory).forEach(dir -> {
                    try {
                        if (Files.exists(dir.resolve(dllName))) {
                            String dirPath = dir.toString().replace('\\', '/');
                            if (seenDirs.add(dirPath)) {
                                results.add(new PathEntry(dirPath, true));
                            }
                        }
                    } catch (Exception ignored) {}
                });
            } catch (IOException e) {
                LOG.warn("[DLL目录] 遍历失败: {}", e.getMessage());
            }
        }

        LOG.info("[路径] DLL 目录文件遍历得到 {} 个候选: sw={}", results.size(), sw);
        return results;
    }

    // ==================== 工具方法 ====================

    private String guessDocumentsPath() {
        try {
            Path docs = Path.of(System.getProperty("user.home"), "Documents");
            if (Files.exists(docs)) return docs.toString().replace('\\', '/');
        } catch (Exception ignored) {}
        return null;
    }

    // ==================== 路径探测提供者接口 ====================

    /**
     * 原生操作提供者接口 — 实现 native 操作
     */
    public interface NativeOps {
        /** 读取注册表值 */
        String readRegistryValue(Long hkey, String subKey, String valueName);

        /** 通过内存映射 + 正则查询路径 */
        List<String> queryMemoryMapPaths(String sw, List<String> exeWildcards, String regex);

        /** 通过文件遍历获取 DLL 目录 */
        List<String> queryDllDirByFiles(String sw, String installDir);

        /** 通过进程枚举获取 exe 路径 */
        String getProcessImagePath(int pid);

        /** 通过通配符获取进程 PID 并按名称分组 */
        Map<String, List<Integer>> getPidsByWildcardsAndGroup(List<String> executableWildcards);
    }
}
