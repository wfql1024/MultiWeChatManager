package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.regex.Pattern;

/**
 * 路径探测 — 三级策略探测软件路径，支持批量 pathType + 多线程并发.
 * <p>
 * 对应 Python: SwInfoFuncCore._get_sw_path_by_register,
 * _get_sw_path_by_memo_and_regex, _guess_sw_path,
 * _get_sw_install_path_from_process, _get_sw_dll_dir_by_files,
 * _get_sw_data_dir_from_other_sw
 *
 * <p>三级策略:
 * <ol>
 *   <li>reg  (注册表) — 从 Windows 注册表读取路径</li>
 *   <li>regex (内存映射正则) — 通过进程内存映射文件匹配正则表达式（多 pathType 共享一次扫描）</li>
 *   <li>addr (猜测) — 从已知系统目录拼接 sub_path</li>
 * </ol>
 *
 * <p>并发设计:
 * <ul>
 *   <li>detectAll 内部按子查询方法级别并发（内存映射、注册表、猜测等各自一个任务）</li>
 *   <li>每个子查询内部串行处理多个 pathType</li>
 *   <li>各子查询之间无共享可变状态，通过 ConcurrentHashMap 合并结果</li>
 *   <li>每个子查询有 30 秒超时保护</li>
 * </ul>
 */
public final class SwPathDetective {

    private static final Logger LOG = LoggerFactory.getLogger(SwPathDetective.class);

    /** 子查询超时时间（秒） */
    static final int SUB_QUERY_TIMEOUT_SECONDS = 30;

    private SwPathDetective() {
        throw new UnsupportedOperationException("SwPathDetective requires a NativeOps");
    }

    /**
     * 路径条目（值 + 是否为目录 + 来源列表）
     */
    public static class PathEntry {
        public final String path;
        public final boolean isDir;
        public final List<String> sources;

        public PathEntry(String path, boolean isDir) {
            this(path, isDir, Collections.emptyList());
        }

        public PathEntry(String path, boolean isDir, String source) {
            this(path, isDir, source != null ? List.of(source) : Collections.emptyList());
        }

        public PathEntry(String path, boolean isDir, List<String> sources) {
            this.path = path;
            this.isDir = isDir;
            this.sources = sources != null ? List.copyOf(sources) : Collections.emptyList();
        }

        /** 合并另一个来源 */
        public PathEntry withSource(String source) {
            List<String> merged = new ArrayList<>(this.sources);
            if (!merged.contains(source)) merged.add(source);
            return new PathEntry(this.path, this.isDir, merged);
        }

        @Override
        public String toString() {
            return path + (isDir ? "/" : "")
                    + (sources.isEmpty() ? "" : " [" + String.join(", ", sources) + "]");
        }
    }

    private final NativeOps nativeOps;

    public SwPathDetective(NativeOps nativeOps) {
        this.nativeOps = nativeOps;
    }

    // ==================== 统一探测入口 ====================

    /**
     * 探测指定 SW 的多个路径类型，并发执行各子查询，返回每个 pathType 的所有候选.
     * <p>
     * 并发粒度：子查询方法级别（内存映射 / 注册表 / 猜测 / 进程 / 其他SW / DLL遍历），
     * 每个子查询方法内部串行处理所有 pathType。
     * <p>
     * 内存映射查询中，多个 pathType 共享同一次进程内存扫描（懒加载迭代器），
     * 匹配到的 pathType 立即从待匹配集合中移除，全部匹配或遍历结束时停止。
     * <p>
     * 同一路径被多个来源发现时，通过 {@link PathEntry#withSource} 合并来源列表。
     *
     * @param accessor  配置访问器
     * @param sw        软件标识
     * @param pathTypes 路径类型 (inst_path / data_dir / dll_dir)，可变参数
     * @return Map: key = pathType, value = 候选路径列表（可能为空列表）
     */
    public Map<String, List<PathEntry>> detectAll(SwConfigAccessor accessor, String sw, String... pathTypes) {
        if (pathTypes == null || pathTypes.length == 0) {
            return Collections.emptyMap();
        }

        List<String> pts = Collections.unmodifiableList(Arrays.asList(pathTypes));
        Map<String, List<PathEntry>> results = Collections.synchronizedMap(new LinkedHashMap<>());
        for (String pt : pts) {
            results.put(pt, new ArrayList<>());
        }

        ExecutorService executor = Executors.newCachedThreadPool(r -> {
            Thread t = new Thread(r, "path-detect-" + sw);
            t.setDaemon(true);
            return t;
        });

        List<Future<?>> futures = new ArrayList<>();

        // ---- 子查询 1: 内存映射正则（共享一次扫描，处理所有有 regex 配置的 pathType） ----
        futures.add(executor.submit(() -> {
            LOG.info("[路径探测] 内存映射子查询启动: sw={}, pathTypes={}", sw, pts);
            try {
                Map<String, List<PathEntry>> memResults = queryByMemoryRegex(accessor, sw, pts);
                memResults.forEach((pt, entries) -> {
                    if (entries != null && !entries.isEmpty()) {
                        mergeEntries(results, pt, entries);
                    }
                });
            } catch (Exception e) {
                LOG.warn("[路径探测] 内存映射子查询异常: sw={}", sw, e);
            }
        }));

        // ---- 子查询 2: 注册表 ----
        futures.add(executor.submit(() -> {
            LOG.info("[路径探测] 注册表子查询启动: sw={}, pathTypes={}", sw, pts);
            try {
                Map<String, List<PathEntry>> regResults = queryByRegister(accessor, sw, pts);
                regResults.forEach((pt, entries) -> {
                    if (entries != null && !entries.isEmpty()) {
                        mergeEntries(results, pt, entries);
                    }
                });
            } catch (Exception e) {
                LOG.warn("[路径探测] 注册表子查询异常: sw={}", sw, e);
            }
        }));

        // ---- 子查询 3: 猜测 (addr) ----
        futures.add(executor.submit(() -> {
            LOG.info("[路径探测] 猜测子查询启动: sw={}, pathTypes={}", sw, pts);
            try {
                Map<String, List<PathEntry>> guessResults = queryByGuess(accessor, sw, pts);
                guessResults.forEach((pt, entries) -> {
                    if (entries != null && !entries.isEmpty()) {
                        mergeEntries(results, pt, entries);
                    }
                });
            } catch (Exception e) {
                LOG.warn("[路径探测] 猜测子查询异常: sw={}", sw, e);
            }
        }));

        // ---- 子查询 4: 进程枚举（仅 inst_path） ----
        if (pts.contains("inst_path")) {
            futures.add(executor.submit(() -> {
                LOG.info("[路径探测] 进程子查询启动: sw={}", sw);
                try {
                    Map<String, List<PathEntry>> procResults = queryByProcess(accessor, sw, pts);
                    procResults.forEach((pt, entries) -> {
                        if (entries != null && !entries.isEmpty()) {
                            mergeEntries(results, pt, entries);
                        }
                    });
                } catch (Exception e) {
                    LOG.warn("[路径探测] 进程子查询异常: sw={}", sw, e);
                }
            }));
        }

        // ---- 子查询 5: 其他 SW 推断（仅 data_dir） ----
        if (pts.contains("data_dir")) {
            futures.add(executor.submit(() -> {
                LOG.info("[路径探测] 其他SW子查询启动: sw={}", sw);
                try {
                    Map<String, List<PathEntry>> otherResults = queryFromOtherSw(accessor, sw, pts);
                    otherResults.forEach((pt, entries) -> {
                        if (entries != null && !entries.isEmpty()) {
                            mergeEntries(results, pt, entries);
                        }
                    });
                } catch (Exception e) {
                    LOG.warn("[路径探测] 其他SW子查询异常: sw={}", sw, e);
                }
            }));
        }

        // ---- 子查询 6: DLL 目录文件遍历（仅 dll_dir） ----
        if (pts.contains("dll_dir")) {
            futures.add(executor.submit(() -> {
                LOG.info("[路径探测] DLL目录子查询启动: sw={}", sw);
                try {
                    Map<String, List<PathEntry>> dllResults = queryDllDirByFiles(accessor, sw, pts);
                    dllResults.forEach((pt, entries) -> {
                        if (entries != null && !entries.isEmpty()) {
                            mergeEntries(results, pt, entries);
                        }
                    });
                } catch (Exception e) {
                    LOG.warn("[路径探测] DLL目录子查询异常: sw={}", sw, e);
                }
            }));
        }

        // ---- 等待所有子查询完成（带超时保护） ----
        for (Future<?> future : futures) {
            try {
                future.get(SUB_QUERY_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            } catch (TimeoutException e) {
                LOG.warn("[路径探测] 子查询超时 ({}s): sw={}", SUB_QUERY_TIMEOUT_SECONDS, sw);
            } catch (Exception e) {
                LOG.warn("[路径探测] 子查询执行异常: sw={}", sw, e);
            }
        }

        executor.shutdownNow();
        LOG.info("[路径探测] detectAll 完成: sw={}, totalCandidates={}", sw,
                results.values().stream().mapToInt(List::size).sum());
        return results;
    }

    /** 合并 entries 到 results，同一路径合并来源列表 */
    private void mergeEntries(Map<String, List<PathEntry>> results, String pathType, List<PathEntry> entries) {
        List<PathEntry> existing = results.get(pathType);
        if (existing == null) {
            results.put(pathType, new ArrayList<>(entries));
            return;
        }
        for (PathEntry entry : entries) {
            boolean merged = false;
            for (int i = 0; i < existing.size(); i++) {
                PathEntry e = existing.get(i);
                if (e.path.equals(entry.path)) {
                    // 合并来源
                    List<String> mergedSources = new ArrayList<>(e.sources);
                    for (String s : entry.sources) {
                        if (!mergedSources.contains(s)) mergedSources.add(s);
                    }
                    existing.set(i, new PathEntry(e.path, e.isDir, mergedSources));
                    merged = true;
                    break;
                }
            }
            if (!merged) {
                existing.add(entry);
            }
        }
        LOG.info("[路径探测] {} 合并后 {} 个候选: sw={}", pathType, existing.size(), pathType);
    }

    // ==================== 工具方法 ====================

    /**
     * 规范化路径：去除引号、统一分隔符.
     */
    /**
     * 统一路径规范化: 去引号、\ → /、盘符大写、去末尾分隔符.
     * <p>
     * 确保所有返回路径在存入 PathEntry 前经过此方法处理，
     * 避免 Windows 反斜杠在 JSON→JS 桥接中产生非法转义。
     */
    static String normalizePath(String rawPath) {
        if (rawPath == null || rawPath.isBlank()) return null;
        String path = rawPath.strip();
        // 去首尾引号
        if ((path.startsWith("\"") && path.endsWith("\""))
                || (path.startsWith("'") && path.endsWith("'"))) {
            path = path.substring(1, path.length() - 1);
        }
        // 统一分隔符为 /
        path = path.replace('\\', '/');
        // 盘符大写 (如 c: → C:)
        if (path.length() >= 2 && path.charAt(1) == ':') {
            path = Character.toUpperCase(path.charAt(0)) + path.substring(1);
        }
        // 去末尾多余 / (保留根路径如 C:/)
        while (path.endsWith("/") && path.length() > 3) {
            path = path.substring(0, path.length() - 1);
        }
        return path;
    }

    /**
     * 收集 pathType → regex 模式列表的映射.
     * 从远程配置 path_detect.{pathType}.regex 中提取所有正则表达式。
     *
     * @return Map: pathType → [(groupName, regexPattern), ...]，无配置的 pathType 不出现在 key 中
     */
    private Map<String, List<String[]>> collectRegexPatterns(
            SwConfigAccessor accessor, String sw, Collection<String> pathTypes) {
        Map<String, List<String[]>> result = new LinkedHashMap<>();
        for (String pt : pathTypes) {
            JsonNode regexDict = accessor.getRemoteSw(sw, "path_detect", pt, "regex");
            if (regexDict == null || !regexDict.isObject()) continue;

            List<String[]> patterns = new ArrayList<>();
            List<String> groupNames = new ArrayList<>();
            regexDict.fieldNames().forEachRemaining(groupNames::add);
            for (String groupName : groupNames) {
                JsonNode groupList = regexDict.get(groupName);
                if (groupList == null || !groupList.isArray()) continue;
                for (JsonNode regexEntry : groupList) {
                    if (!regexEntry.isObject()) continue;
                    String regexPattern = regexEntry.has("regex")
                            ? regexEntry.get("regex").asText() : null;
                    if (regexPattern != null && !regexPattern.isBlank()) {
                        patterns.add(new String[]{groupName, regexPattern});
                    }
                }
            }
            if (!patterns.isEmpty()) {
                result.put(pt, patterns);
            }
        }
        return result;
    }

    // ==================== 子查询 1: 内存映射正则（共享扫描） ====================

    /**
     * 通过进程内存映射 + 正则表达式匹配路径（多 pathType 共享一次内存扫描）.
     * <p>
     * 核心优化：使用懒加载迭代器逐条获取内存映射路径，每条路径立即与所有
     * 尚未匹配的 pathType 的正则进行匹配。一旦某个 pathType 匹配成功，
     * 将其从待匹配集合中移除。当所有 pathType 都已匹配或迭代器耗尽时停止。
     * <p>
     * 对应 Python: _get_sw_path_by_memo_and_regex (L1087-L1118)
     *
     * @param accessor  配置访问器
     * @param sw        软件标识
     * @param pathTypes 路径类型列表
     * @return Map: pathType → 匹配到的路径（未匹配则为 null）
     */
    Map<String, List<PathEntry>> queryByMemoryRegex(
            SwConfigAccessor accessor, String sw, Collection<String> pathTypes) {
        Map<String, List<PathEntry>> results = new LinkedHashMap<>();
        for (String pt : pathTypes) {
            results.put(pt, new ArrayList<>());
        }

        if (nativeOps == null) {
            LOG.debug("[路径内存映射] 未启用（需要 JNA）");
            return results;
        }

        // 1. 收集所有 pathType 的正则模式
        Map<String, List<String[]>> ptPatterns = collectRegexPatterns(accessor, sw, pathTypes);
        if (ptPatterns.isEmpty()) {
            LOG.debug("[路径内存映射] 无正则配置: sw={}", sw);
            return results;
        }

        // 2. 获取 exe 通配符列表
        List<String> exeWildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());

        LOG.info("[路径内存映射] 共享扫描启动: sw={}, pathTypes={}, exeWildcards={}",
                sw, ptPatterns.keySet(), exeWildcards);

        // 3. 编译所有正则（pathType → [(groupName, compiledPattern), ...]）
        Map<String, List<Object[]>> compiledPatterns = new LinkedHashMap<>();
        for (Map.Entry<String, List<String[]>> entry : ptPatterns.entrySet()) {
            List<Object[]> compiled = new ArrayList<>();
            for (String[] gnRegex : entry.getValue()) {
                try {
                    compiled.add(new Object[]{gnRegex[0], Pattern.compile(gnRegex[1])});
                } catch (Exception e) {
                    LOG.warn("[路径内存映射] 正则编译失败: sw={}, pattern={}",
                            sw, gnRegex[1], e);
                }
            }
            if (!compiled.isEmpty()) {
                compiledPatterns.put(entry.getKey(), compiled);
            }
        }

        if (compiledPatterns.isEmpty()) {
            return results;
        }

        // 4. 待匹配的 pathType 集合
        Set<String> pending = new HashSet<>(compiledPatterns.keySet());
        LOG.info("[路径内存映射] 待匹配: {}, 正则总数: {}",
                pending,
                compiledPatterns.values().stream().mapToInt(List::size).sum());

        // 5. 懒加载迭代器 — 逐条扫描内存映射路径
        NativeOps.MemoryMapIterator iterator = null;
        try {
            iterator = nativeOps.iterateMemoryMapPaths(sw, exeWildcards);
            int scannedCount = 0;
            while (iterator.hasNext() && !pending.isEmpty()) {
                String rawPath = iterator.next();
                scannedCount++;
                String normalized = normalizePath(rawPath);
                if (normalized == null) continue;

                // 对每个待匹配的 pathType 尝试匹配
                Iterator<String> pendingIter = new HashSet<>(pending).iterator();
                while (pendingIter.hasNext()) {
                    String pt = pendingIter.next();
                    List<Object[]> patterns = compiledPatterns.get(pt);
                    if (patterns == null) continue;

                    for (Object[] gnPat : patterns) {
                        Pattern pat = (Pattern) gnPat[1];
                        java.util.regex.Matcher matcher = pat.matcher(normalized);
                        if (matcher.find()) {
                            String captured = matcher.group(1);
                            if (captured != null && !captured.isBlank()) {
                                boolean isDir = !"inst_path".equals(pt);
                                String capturedPath = isDir
                                        ? captured.replace('\\', '/')
                                        : captured.replace('\\', '/');
                                results.get(pt).add(new PathEntry(
                                        capturedPath, isDir, "内存映射"));
                                pending.remove(pt);
                                LOG.info("[路径内存映射] 匹配成功: sw={}, pathType={}, "
                                                + "regexGroup={}, captured={}, scannedSoFar={}",
                                        sw, pt, gnPat[0], captured, scannedCount);
                                break; // 该 pathType 已匹配，跳出正则循环
                            }
                        }
                    }
                }
            }
            LOG.info("[路径内存映射] 扫描完成: sw={}, scannedCount={}, matched={}, pending={}",
                    sw, scannedCount,
                    compiledPatterns.size() - pending.size(), pending);
        } catch (Exception e) {
            LOG.warn("[路径内存映射] 扫描异常: sw={}", sw, e);
        } finally {
            if (iterator != null) {
                try { iterator.close(); } catch (Exception ignored) {}
            }
        }

        return results;
    }

    // ==================== 子查询 2: 注册表 ====================

    /**
     * 通过 Windows 注册表查询路径.
     * <p>
     * 对应 Python: _get_sw_path_by_register (L1049-L1085)
     * <p>
     * RemoteSwConfig 格式:
     * <pre>
     * "path_detect": {
     *   "inst_path": {
     *     "reg": {
     *       "current_user": [
     *         {"sub_key": "Software\\Tencent\\WeChat", "value_name": "InstallPath"}
     *       ],
     *       "local_machine": [
     *         {"sub_key": "SOFTWARE\\...\\Uninstall\\WeChat", "value_name": "InstallLocation"}
     *       ]
     *     }
     *   }
     * }
     * </pre>
     *
     * @param accessor  配置访问器
     * @param sw        软件标识
     * @param pathTypes 路径类型列表
     * @return Map: pathType → 路径（未匹配则为 null）
     */
    Map<String, List<PathEntry>> queryByRegister(
            SwConfigAccessor accessor, String sw, Collection<String> pathTypes) {
        Map<String, List<PathEntry>> results = new LinkedHashMap<>();
        for (String pt : pathTypes) {
            results.put(pt, new ArrayList<>());
        }

        if (nativeOps == null) {
            LOG.debug("[路径注册表] 未启用（需要 JNA）");
            return results;
        }

        // 获取 exe 名（用于 is_dir=false 时拼接）
        String exeName = null;
        if (pathTypes.contains("inst_path")) {
            JsonNode exeNode = accessor.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.EXECUTABLE);
            if (exeNode != null && exeNode.isTextual()) {
                exeName = exeNode.asText();
            }
        }

        // 根键映射
        Map<String, Long> hkeyMap = Map.of(
                "classes_root",   0x80000000L,  // HKEY_CLASSES_ROOT
                "current_user",   0x80000001L,  // HKEY_CURRENT_USER
                "local_machine",  0x80000002L,  // HKEY_LOCAL_MACHINE
                "users",          0x80000003L,  // HKEY_USERS
                "current_config", 0x80000005L   // HKEY_CURRENT_CONFIG
        );

        for (String pathType : pathTypes) {
            JsonNode regDict = accessor.getRemoteSw(sw, "path_detect", pathType, "reg");
            if (regDict == null || !regDict.isObject()) continue;

            List<String> hkeyNames = new ArrayList<>();
            regDict.fieldNames().forEachRemaining(hkeyNames::add);

            for (String hkeyName : hkeyNames) {
                Long hkeyValue = hkeyMap.get(hkeyName);
                if (hkeyValue == null) continue;

                JsonNode regList = regDict.get(hkeyName);
                if (regList == null || !regList.isArray()) continue;

                for (JsonNode regEntry : regList) {
                    if (!regEntry.isObject()) continue;
                    String subKey = regEntry.has("sub_key")
                            ? regEntry.get("sub_key").asText() : null;
                    String valueName = regEntry.has("value_name")
                            ? regEntry.get("value_name").asText() : null;
                    boolean isDir = !regEntry.has("is_dir")
                            || regEntry.get("is_dir").asBoolean(true);
                    String suffix = regEntry.has("suffix")
                            ? regEntry.get("suffix").asText() : null;

                    if (subKey == null || valueName == null) continue;

                    try {
                        String value = nativeOps.readRegistryValue(hkeyValue, subKey, valueName);
                        if (value == null || value.isBlank()) continue;

                        String path = value.replace('\\', '/').strip();
                        if (!isDir) {
                            path = new File(path).getParent();
                            if (path == null) path = value;
                            if (exeName != null && !exeName.isBlank()) {
                                path = path + "/" + exeName;
                            }
                        }
                        if (suffix != null && !suffix.isBlank()) {
                            path = path + "/" + suffix.replace('\\', '/');
                        }

                        results.get(pathType).add(new PathEntry(
                                normalizePath(path), isDir, "注册表"));
                        LOG.info("[路径注册表] 匹配: sw={}, pathType={}, value={}, result={}",
                                sw, pathType, valueName, path);
                    } catch (Exception e) {
                        LOG.debug("[路径注册表] 读取失败: hkey={}, subKey={}, valueName={}",
                                hkeyName, subKey, valueName, e);
                    }
                }
            }

            if (results.get(pathType).isEmpty()) {
                LOG.debug("[路径注册表] 未匹配: sw={}, pathType={}", sw, pathType);
            }
        }

        LOG.info("[路径注册表] 完成: sw={}, results={}", sw, results);
        return results;
    }

    // ==================== 子查询 3: 猜测路径 (addr) ====================

    /**
     * 通过 path_detect.addr 猜测路径.
     * <p>
     * 对应 Python: _guess_sw_path (L1018-L1047)
     *
     * @param accessor  配置访问器
     * @param sw        软件标识
     * @param pathTypes 路径类型列表
     * @return Map: pathType → 路径（未匹配则为 null）
     */
    Map<String, List<PathEntry>> queryByGuess(
            SwConfigAccessor accessor, String sw, Collection<String> pathTypes) {
        Map<String, List<PathEntry>> results = new LinkedHashMap<>();
        for (String pt : pathTypes) {
            results.put(pt, new ArrayList<>());
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

        for (String pathType : pathTypes) {
            if (!results.get(pathType).isEmpty()) continue;

            JsonNode addrDict = accessor.getRemoteSw(sw, "path_detect", pathType, "addr");
            if (addrDict == null || !addrDict.isObject()) continue;

            for (Map.Entry<String, String> sysEntry : sysPaths.entrySet()) {
                String sysPathKey = sysEntry.getKey();
                String sysPathValue = sysEntry.getValue();
                if (sysPathValue == null || sysPathValue.isBlank()) continue;

                JsonNode addrList = addrDict.get(sysPathKey);
                if (addrList == null || !addrList.isArray()) continue;

                for (JsonNode addrNode : addrList) {
                    if (!addrNode.isObject()) continue;
                    JsonNode subPathNode = addrNode.get("sub_path");
                    if (subPathNode == null || !subPathNode.isTextual()) continue;

                    String subPath = subPathNode.asText().replace('\\', '/');
                    String fullPath = (sysPathValue + "/" + subPath).replace('\\', '/');
                    boolean nodeIsDir = addrNode.has("is_dir")
                            ? addrNode.get("is_dir").asBoolean(true) : true;

                    results.get(pathType).add(new PathEntry(
                            normalizePath(fullPath), nodeIsDir, "猜测"));
                    LOG.info("[路径猜测] 匹配: sw={}, pathType={}, sysPath={}, result={}",
                            sw, pathType, sysPathKey, fullPath);
                }
            }

            if (results.get(pathType).isEmpty()) {
                LOG.debug("[路径猜测] 未匹配: sw={}, pathType={}", sw, pathType);
            }
        }

        LOG.info("[路径猜测] 完成: sw={}, results={}", sw, results);
        return results;
    }

    // ==================== 子查询 4: 进程枚举 ====================

    /**
     * 通过进程枚举获取安装路径（仅处理 inst_path）.
     * <p>
     * 对应 Python: _get_sw_install_path_from_process (L935-L943)
     *
     * @param accessor  配置访问器
     * @param sw        软件标识
     * @param pathTypes 路径类型列表（仅当包含 "inst_path" 时执行）
     * @return Map: 仅包含 inst_path 键
     */
    Map<String, List<PathEntry>> queryByProcess(
            SwConfigAccessor accessor, String sw, Collection<String> pathTypes) {
        Map<String, List<PathEntry>> results = new LinkedHashMap<>();

        if (!pathTypes.contains("inst_path")) {
            return results;
        }
        results.put("inst_path", new ArrayList<>());

        if (nativeOps == null) {
            LOG.debug("[路径进程] 未启用（需要 JNA）");
            return results;
        }

        JsonNode exeNode = accessor.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.EXECUTABLE);
        if (exeNode == null || !exeNode.isTextual()) {
            LOG.debug("[路径进程] 无 exe 配置: sw={}", sw);
            return results;
        }
        String exeName = exeNode.asText();

        List<String> wildcards = accessor.getRemoteSwAsList(
                sw, SwCoreConstants.RemoteSwKey.EXECUTABLE_WILDCARDS, Collections.emptyList());
        if (wildcards.isEmpty()) wildcards = List.of(exeName);

        Map<String, List<Integer>> namePids = nativeOps.getPidsByWildcardsAndGroup(wildcards);
        if (namePids.isEmpty()) {
            LOG.debug("[路径进程] 未找到匹配的进程: sw={}, exe={}", sw, exeName);
            return results;
        }

        for (Map.Entry<String, List<Integer>> entry : namePids.entrySet()) {
            String name = entry.getKey();
            List<Integer> pids = entry.getValue();
            if (!pids.isEmpty()) {
                try {
                    String exePath = nativeOps.getProcessImagePath(pids.get(0));
                    if (exePath != null && !exePath.isBlank()) {
                        String normalized = normalizePath(exePath);
                        if (normalized != null) {
                            results.get("inst_path").add(new PathEntry(
                                    normalized, false, "进程"));
                            LOG.info("[路径进程] 匹配: sw={}, exe={}, path={}",
                                    sw, name, exePath);
                            break;
                        }
                    }
                } catch (Exception e) {
                    LOG.debug("[路径进程] 获取进程路径失败: pid={}", pids.get(0), e);
                }
            }
        }

        LOG.info("[路径进程] 完成: sw={}, result={}", sw, results.get("inst_path"));
        return results;
    }

    // ==================== 子查询 5: 从其他 SW 推断 ====================

    /**
     * 通过其他同类软件的数据目录推断当前软件的数据目录（仅处理 data_dir）.
     * <p>
     * 对应 Python: _get_sw_data_dir_from_other_sw (L1709-L1733)
     *
     * @param accessor  配置访问器
     * @param sw        软件标识
     * @param pathTypes 路径类型列表（仅当包含 "data_dir" 时执行）
     * @return Map: 仅包含 data_dir 键
     */
    Map<String, List<PathEntry>> queryFromOtherSw(
            SwConfigAccessor accessor, String sw, Collection<String> pathTypes) {
        Map<String, List<PathEntry>> results = new LinkedHashMap<>();

        if (!pathTypes.contains("data_dir")) {
            return results;
        }
        results.put("data_dir", new ArrayList<>());

        JsonNode dataDirNameNode = accessor.getRemoteSw(sw, "data_dir_name");
        if (dataDirNameNode == null || !dataDirNameNode.isTextual()) {
            LOG.debug("[路径其他SW] 无 data_dir_name 配置: sw={}", sw);
            return results;
        }
        String dataDirName = dataDirNameNode.asText();
        if (dataDirName.isBlank()) return results;

        // 微信/企微共用同级目录
        if ("WeChat".equals(sw) || "Weixin".equals(sw)) {
            String otherKey = "WeChat".equals(sw) ? "Weixin" : "WeChat";
            String otherPath = accessor.tryGetPathOf(
                    otherKey, SwCoreConstants.LocalSettingKey.DATA_DIR);
            if (otherPath != null) {
                String path = new File(otherPath).getParent() + "/" + dataDirName;
                String normalized = normalizePath(path);
                if (normalized != null) {
                    results.get("data_dir").add(new PathEntry(normalized, true, "其他SW"));
                }
                LOG.info("[路径其他SW] 匹配: sw={}, from={}, path={}", sw, otherKey, path);
                return results;
            }
        }

        // QQ/TIM 共用同一数据目录
        if ("QQNT".equals(sw) || "TIM".equals(sw) || "QQ".equals(sw)) {
            for (String otherKey : List.of("QQNT", "TIM", "QQ")) {
                if (otherKey.equals(sw)) continue;
                String otherPath = accessor.tryGetPathOf(
                        otherKey, SwCoreConstants.LocalSettingKey.DATA_DIR);
                if (otherPath != null) {
                    String normalized = normalizePath(otherPath);
                    if (normalized != null) {
                        results.get("data_dir").add(new PathEntry(normalized, true, "其他SW"));
                    }
                    LOG.info("[路径其他SW] 匹配: sw={}, from={}, path={}", sw, otherKey, otherPath);
                    return results;
                }
            }
        }

        LOG.debug("[路径其他SW] 未匹配: sw={}", sw);
        return results;
    }

    // ==================== 子查询 6: DLL 目录文件遍历 ====================

    /**
     * 通过文件遍历方式获取 DLL 目录（仅处理 dll_dir）.
     * <p>
     * 对应 Python: _get_sw_dll_dir_by_files (L1735-L1770)
     *
     * @param accessor  配置访问器
     * @param sw        软件标识
     * @param pathTypes 路径类型列表（仅当包含 "dll_dir" 时执行）
     * @return Map: 仅包含 dll_dir 键
     */
    Map<String, List<PathEntry>> queryDllDirByFiles(
            SwConfigAccessor accessor, String sw, Collection<String> pathTypes) {
        Map<String, List<PathEntry>> results = new LinkedHashMap<>();

        if (!pathTypes.contains("dll_dir")) {
            return results;
        }
        results.put("dll_dir", new ArrayList<>());

        String installPath = accessor.tryGetPathOf(
                sw, SwCoreConstants.LocalSettingKey.INST_PATH);
        if (installPath == null || installPath.isBlank()) {
            LOG.debug("[路径DLL目录] 无安装路径: sw={}", sw);
            return results;
        }

        String installDir = new File(installPath).getParent();
        if (installDir == null) {
            LOG.debug("[路径DLL目录] 无法获取安装目录: sw={}", sw);
            return results;
        }

        JsonNode patchAddrs = accessor.getRemoteSw(sw, "patch_addresses");
        if (patchAddrs == null || !patchAddrs.isArray()) {
            LOG.debug("[路径DLL目录] 无 patch_addresses 配置: sw={}", sw);
            return results;
        }

        for (JsonNode addrNode : patchAddrs) {
            if (!addrNode.isTextual()) continue;
            String addr = addrNode.asText().replace('\\', '/');
            if (!addr.startsWith("%dll_dir%/")) continue;

            String rest = addr.substring("%dll_dir%/".length());
            if (rest.contains("/")) continue;

            String dllName = rest;

            // 使用 BFS 遍历，避免 Files.walk 在权限受限目录报错
            var queue = new ArrayDeque<Path>();
            queue.add(Path.of(installDir));
            while (!queue.isEmpty()) {
                Path dir = queue.poll();
                if (!Files.isDirectory(dir)) continue;
                if (Files.exists(dir.resolve(dllName))) {
                    String dirPath = dir.toString().replace('\\', '/');
                    results.get("dll_dir").add(new PathEntry(
                            normalizePath(dirPath), true, "DLL遍历"));
                    LOG.info("[路径DLL目录] 匹配: sw={}, dll={}, dir={}",
                            sw, dllName, dirPath);
                    return results;
                }
                try (var stream = Files.list(dir)) {
                    stream.filter(Files::isDirectory).forEach(queue::addLast);
                } catch (IOException ignored) {
                    // 跳过无权限的子目录
                }
            }
        }

        LOG.debug("[路径DLL目录] 未匹配: sw={}", sw);
        return results;
    }

    // ==================== 工具 ====================

    private String guessDocumentsPath() {
        try {
            Path docs = Path.of(System.getProperty("user.home"), "Documents");
            if (Files.exists(docs)) return docs.toString().replace('\\', '/');
        } catch (Exception ignored) {}
        return null;
    }

    // ==================== 路径探测提供者接口 ====================

    /**
     * 原生操作提供者接口.
     */
    public interface NativeOps {
        /** 读取注册表值 */
        String readRegistryValue(Long hkey, String subKey, String valueName);

        /** 通过内存映射 + 正则查询路径（单个正则，保留兼容旧调用方） */
        List<String> queryMemoryMapPaths(String sw, List<String> exeWildcards, String regex);

        /** 通过文件遍历获取 DLL 目录 */
        List<String> queryDllDirByFiles(String sw, String installDir);

        /** 通过进程枚举获取 exe 路径 */
        String getProcessImagePath(int pid);

        /** 通过通配符获取进程 PID 并按名称分组 */
        Map<String, List<Integer>> getPidsByWildcardsAndGroup(List<String> executableWildcards);

        /**
         * 懒加载迭代器：逐条返回匹配进程的内存映射文件路径.
         * <p>
         * 内部实现使用 VirtualQueryEx + GetMappedFileNameW 逐区域遍历，
         * 每次调用 {@code next()} 返回一条路径。调用方必须在使用完毕后调用
         * {@code close()} 释放进程句柄。
         * <p>
         * 迭代器语义：
         * <ul>
         *   <li>{@code hasNext()} — 是否还有更多路径</li>
         *   <li>{@code next()} — 返回下一条路径（统一使用 / 分隔符）</li>
         *   <li>{@code close()} — 释放所有 Windows 进程句柄</li>
         * </ul>
         *
         * @param sw           软件标识（用于日志）
         * @param exeWildcards 可执行文件通配符列表
         * @return 内存映射路径迭代器（可能为空迭代器，绝不返回 null）
         */
        MemoryMapIterator iterateMemoryMapPaths(String sw, List<String> exeWildcards);

        /**
         * 内存映射路径迭代器 — 扩展 {@link Iterator} 和 {@link AutoCloseable}.
         */
        interface MemoryMapIterator extends Iterator<String>, AutoCloseable {
            @Override
            boolean hasNext();

            @Override
            String next();

            @Override
            void close();
        }
    }
}
