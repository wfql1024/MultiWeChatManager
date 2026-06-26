package com.jfmultichat.swcore;

import com.sun.jna.Memory;
import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.platform.win32.Advapi32;
import com.sun.jna.platform.win32.Advapi32Util;
import com.sun.jna.platform.win32.Kernel32;
import com.sun.jna.platform.win32.Kernel32Util;
import com.sun.jna.platform.win32.Psapi;
import com.sun.jna.platform.win32.Tlhelp32;
import com.sun.jna.platform.win32.WinBase;
import com.sun.jna.platform.win32.WinDef;
import com.sun.jna.platform.win32.WinDef.DWORD;
import com.sun.jna.platform.win32.WinNT;
import com.sun.jna.platform.win32.WinNT.HANDLE;
import com.sun.jna.platform.win32.WinReg;
import com.sun.jna.ptr.IntByReference;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.ByteBuffer;
import java.nio.charset.Charset;
import java.nio.file.Files;
import java.util.*;

/**
 * JNA 原生操作实现 — Windows API 调用的封装
 * <p>
 * 内存映射枚举使用 NtQueryVirtualMemory（等价于 Python psutil 底层实现），
 * 而非 VirtualQueryEx + GetMappedFileNameW。
 */
public final class SwNativeOps implements SwPathDetective.NativeOps {

    private static final Logger LOG = LoggerFactory.getLogger(SwNativeOps.class);
    public static final SwNativeOps INSTANCE = new SwNativeOps();

    /** Package-private for SwInfoFuncCore; public for test access */
    public SwNativeOps() {}

    // ==================== NtQueryVirtualMemory 相关结构 ====================

    /**
     * MemoryInformationClass 枚举 — 仅需要 MemorySectionName
     */
    private static final int MemorySectionName = 29;

    /**
     * UNICODE_STRING 结构（与 Windows NT API 对齐）
     */
    public static class UNICODE_STRING extends com.sun.jna.Structure {
        public short Length;
        public short MaximumLength;
        public Pointer Buffer;

        public UNICODE_STRING() {}
        public UNICODE_STRING(Pointer p) {
            super(p);
            read();
        }

        @Override
        protected List<String> getFieldOrder() {
            return Arrays.asList("Length", "MaximumLength", "Buffer");
        }

        /** 从 Structure 分配足够的缓冲区 */
        public static UNICODE_STRING allocate(int maxChars) {
            UNICODE_STRING us = new UNICODE_STRING();
            // Buffer 需要足够大以容纳最大长度的 UTF-16LE 字符串
            us.Buffer = new Memory(maxChars * 2);
            us.MaximumLength = (short) (maxChars * 2);
            return us;
        }

        public String getValue() {
            if (Buffer == null || Length == 0) return "";
            try {
                byte[] bytes = Buffer.getByteArray(0, Length & 0xFFFF);
                return new String(bytes, 0, Length & 0xFFFF, Charset.forName("UTF-16LE")).trim();
            } catch (Exception e) {
                return "";
            }
        }
    }

    /**
     * ntdll 扩展接口 — NtQueryVirtualMemory
     */
    public interface NtdllExt extends com.sun.jna.Library {
        NtdllExt INSTANCE = (NtdllExt) Native.load("ntdll", NtdllExt.class);

        int NtQueryVirtualMemory(
                HANDLE hProcess,
                Pointer baseAddress,
                int memoryInformationClass,
                Pointer memoryInformation,
                int memoryInformationLength,
                IntByReference returnLength
        );
    }

    /**
     * ntdll 扩展接口 — NtQueryInformationProcess
     * ProcessBasicInformation (class 0) 返回 RTL_PROCESS_BASIC_INFORMATION
     */
    public interface NtDllExt extends com.sun.jna.Library {
        NtDllExt INSTANCE = (NtDllExt) Native.load("ntdll", NtDllExt.class);

        /**
         * NTSTATUS NtQueryInformationProcess(
         *   HANDLE  ProcessHandle,
         *   PROCESS_INFORMATION_CLASS ProcessInformationClass,
         *   PVOID ProcessInformation,
         *   ULONG ProcessInformationLength,
         *   PULONG ReturnLength
         * );
         */
        int NtQueryInformationProcess(
                HANDLE hProcess,
                int processInformationClass,
                com.sun.jna.Pointer processInformation,
                int processInformationLength,
                IntByReference returnLength
        );

        /**
         * NTSTATUS NtQuerySystemInformation(
         *   SYSTEM_INFORMATION_CLASS SystemInformationClass,
         *   PVOID SystemInformation,
         *   ULONG SystemInformationLength,
         *   PULONG ReturnLength
         * );
         */
        int NtQuerySystemInformation(
                int systemInformationClass,
                com.sun.jna.Pointer systemInformation,
                int systemInformationLength,
                IntByReference returnLength
        );
    }

    /**
     * MEMORY_SECTION_NAME 结构 — NtQueryVirtualMemory 返回的 section name 信息
     */
    public static class MEMORY_SECTION_NAME extends com.sun.jna.Structure {
        public UNICODE_STRING SectionFileName;

        @Override
        protected List<String> getFieldOrder() {
            return Arrays.asList("SectionFileName");
        }
    }

    /**
     * 将 NT 路径（如 \Device\HarddiskVolume2\Windows\...）转换为 Win32 路径（如 C:\Windows\...）
     */
    private static String convertNtPathToWin(String ntPath) {
        if (ntPath == null || ntPath.isEmpty()) return ntPath;
        // 简单方案：直接用 QueryDosDevice 枚举驱动器
        for (char drive = 'A'; drive <= 'Z'; drive++) {
            String driveLabel = String.valueOf(drive) + ":";
            int charsCopied = Kernel32.INSTANCE.QueryDosDevice(
                    driveLabel, null, 0);
            if (charsCopied > 0) {
                char[] buffer = new char[charsCopied];
                Kernel32.INSTANCE.QueryDosDevice(driveLabel, buffer, charsCopied);
                String target = new String(buffer, 0, charsCopied - 1);
                String ntPrefix = target + "\\";
                if (ntPath.startsWith(ntPrefix)) {
                    return drive + ":" + ntPath.substring(ntPrefix.length());
                }
            }
        }
        // 没找到匹配，尝试直接返回（可能是其他 NT 设备路径）
        return ntPath;
    }

    /**
     * 通过 NtQueryVirtualMemory 遍历进程的所有内存映射区域
     * 等价于 Python: psutil.Process(pid).memory_maps()
     * <p>
     * 算法：
     * 1. 用 VirtualQueryEx 获取地址空间布局（区域边界）
     * 2. 对每个已提交的区域，调用 NtQueryVirtualMemory(MemorySectionName) 获取文件路径
     * 3. 将 NT 路径转换为 Win32 路径
     */
    private List<String> enumerateMemoryMapPaths(int pid, List<String> exeWildcards) {
        Kernel32 kernel32 = Kernel32.INSTANCE;
        List<String> paths = new ArrayList<>();

        HANDLE hProcess = kernel32.OpenProcess(
                WinNT.PROCESS_QUERY_INFORMATION | WinNT.PROCESS_VM_READ, false, pid);
        if (hProcess == null) return paths;

        try {
            WinNT.MEMORY_BASIC_INFORMATION mbi = new WinNT.MEMORY_BASIC_INFORMATION();
            // 从地址 0 开始遍历整个虚拟地址空间
            Pointer baseAddr = new Pointer(0L);
            long highestAddr = 0;

            // 先找出该进程的最高地址
            try {
                com.sun.jna.platform.win32.WinNT.MEMORY_BASIC_INFORMATION probe =
                        new com.sun.jna.platform.win32.WinNT.MEMORY_BASIC_INFORMATION();
                WinNT.SIZE_T probeSizeT = kernel32.VirtualQueryEx(hProcess, new Pointer(0L), probe, new WinNT.SIZE_T(probe.size()));
                if (probeSizeT.longValue() > 0) {
                    // Pointer doesn't have longValue() in JNA 5.14.0, use share(0) to get base address
                    Pointer base = probe.baseAddress.share(0);
                    // Actually, MEMORY_BASIC_INFORMATION.baseAddress is already a Pointer at the base address
                    // We need to get the actual address — use the Pointer's native value
                    // In JNA, Pointer has no longValue(), so we track it differently
                    // VirtualQueryEx returns baseAddress pointing to the start of the region
                    // We can use the fact that we start from 0 and walk sequentially
                    highestAddr = 0x7FFFFFFF0000L; // fall through to sequential walk
                }
            } catch (Exception e) {
                // 如果无法查询，使用默认上限 0x7FFFFFFF0000 (用户空间 256TB)
                highestAddr = 0x7FFFFFFF0000L;
            }

            Pointer currentAddr = new Pointer(0L);
            // 跟踪当前地址（用 long 避免 Pointer.longValue() 兼容性问题）
            long currentAddrLong = 0L;
            while (currentAddrLong < highestAddr) {
                WinNT.SIZE_T resultSizeT = kernel32.VirtualQueryEx(
                        hProcess, currentAddr, mbi,
                        new WinNT.SIZE_T(mbi.size()));
                if (resultSizeT.longValue() <= 0) break;

                mbi.read();
                Pointer regionBase = mbi.baseAddress;
                long regionSizeLong = mbi.regionSize.longValue();
                long regionBaseLong = currentAddrLong;  // 跟踪当前区域基址

                if (regionBase == null || regionSizeLong <= 0) break;

                // 只处理已提交的内存区域（MEM_COMMIT）
                if ((mbi.state.intValue() & WinNT.MEM_COMMIT) != 0) {
                    // 调用 NtQueryVirtualMemory 获取该区域映射的文件路径
                    try {
                        MEMORY_SECTION_NAME sectionName = new MEMORY_SECTION_NAME();
                        // 分配足够的缓冲区（最大 32KB）
                        UNICODE_STRING us = UNICODE_STRING.allocate(16384);
                        us.write();
                        Pointer ptr = us.getPointer();
                        ptr.write(0, new byte[us.size()], 0, us.size());

                        IntByReference returnLength = new IntByReference(0);
                        int ntStatus = NtdllExt.INSTANCE.NtQueryVirtualMemory(
                                hProcess,
                                regionBase,
                                MemorySectionName,
                                ptr,
                                us.size(),
                                returnLength
                        );

                        if (ntStatus == 0) { // STATUS_SUCCESS
                            // 重新读取结构
                            ByteBuffer bb = ptr.getByteBuffer(0, us.size());
                            byte[] raw = new byte[bb.remaining()];
                            bb.get(raw);
                            // 手动解析 UNICODE_STRING
                            short length = (short) ((raw[0] & 0xFF) | ((raw[1] & 0xFF) << 8));
                            short maxLen = (short) ((raw[2] & 0xFF) | ((raw[3] & 0xFF) << 8));
                            // Buffer 指针是 8 字节（64 位）
                            long bufLow = (raw[8] & 0xFF) | ((raw[9] & 0xFF) << 8) |
                                          ((raw[10] & 0xFF) << 16) | ((raw[11] & 0xFF) << 24);
                            long bufHigh = (raw[12] & 0xFF) | ((raw[13] & 0xFF) << 8) |
                                           ((raw[14] & 0xFF) << 16) | ((raw[15] & 0xFF) << 24);
                            long bufAddr = bufHigh << 32 | bufLow;
                            if (bufAddr != 0 && length > 0) {
                                Pointer filePathPtr = new Pointer(bufAddr);
                                // UTF-16LE 解码
                                byte[] fileBytes = filePathPtr.getByteArray(0, length);
                                String ntPath = new String(fileBytes, 0, length, "UTF-16LE");

                                // 过滤有效路径（必须以 \Device\ 开头）
                                if (ntPath.startsWith("\\Device\\")) {
                                    String winPath = convertNtPathToWin(ntPath);
                                    String normalized = winPath.replace('\\', '/');
                                    if (!normalized.isEmpty()) {
                                        paths.add(normalized);
                                    }
                                }
                            }
                        }
                    } catch (Exception e) {
                        // 单个区域解析失败不影响其他区域
                    }
                }

                // 前进到下一个区域
                currentAddrLong = regionBaseLong + regionSizeLong;
                currentAddr = new Pointer(currentAddrLong);
            }
        } finally {
            kernel32.CloseHandle(hProcess);
        }
        return paths;
    }

    // ==================== 注册表查询 ====================

    /**
     * 读取 Windows 注册表值
     * 对应 Python: winreg.OpenKey + QueryValueEx
     */
    @Override
    public String readRegistryValue(Long hkey, String subKey, String valueName) {
        try {
            WinReg.HKEY rootKey;
            if (hkey == 0x80000001L) {
                rootKey = WinReg.HKEY_CURRENT_USER;
            } else if (hkey == 0x80000002L) {
                rootKey = WinReg.HKEY_LOCAL_MACHINE;
            } else if (hkey == 0x80000000L) {
                rootKey = WinReg.HKEY_CLASSES_ROOT;
            } else if (hkey == 0x80000003L) {
                rootKey = WinReg.HKEY_USERS;
            } else if (hkey == 0x80000005L) {
                rootKey = WinReg.HKEY_CURRENT_CONFIG;
            } else {
                LOG.debug("[JNA注册表] 不支持的 hkey: 0x{}", Long.toHexString(hkey));
                return null;
            }
            String value = Advapi32Util.registryGetStringValue(rootKey, subKey, valueName);
            if (value != null && !value.isEmpty()) {
                return value.replace('\\', '/').strip().replaceAll("^\"|\"$", "");
            }
        } catch (Exception e) {
            LOG.debug("[JNA注册表] 读取失败: hkey=0x{}, subKey={}, valueName={}",
                    Long.toHexString(hkey), subKey, valueName, e);
        }
        return null;
    }

    /**
     * 通过进程内存映射 + 正则匹配查询路径
     * 使用 VirtualQueryEx + GetMappedFileNameW 遍历进程所有内存映射区域，等价于 Python
     * `psutil.Process(pid).memory_maps()`。
     * <p>
     * 流程：获取 PID → 剔除子进程 → 枚举内存映射 → 正则匹配 → 返回结果
     *
     * @param sw           软件标识
     * @param exeWildcards 可执行文件通配符列表
     * @param regex        正则表达式
     * @return 匹配到的路径列表
     */
    @Override
    public List<String> queryMemoryMapPaths(String sw, List<String> exeWildcards, String regex) {
        Map<String, List<Integer>> namePids = getPidsByWildcardsAndGroup(exeWildcards);
        if (namePids.isEmpty()) return Collections.emptyList();

        // 合并所有 PID
        List<Integer> allPids = new ArrayList<>();
        for (List<Integer> pids : namePids.values()) allPids.addAll(pids);
        LOG.info("[路径内存映射-VQE] sw={}, allPids={}", sw, allPids);

        // 剔除子进程
        allPids = filterOutChildPids(allPids);
        LOG.info("[路径内存映射-VQE] sw={}, after_remove_child_pids={}", sw, allPids);

        java.util.regex.Pattern pattern;
        try {
            pattern = java.util.regex.Pattern.compile(regex);
        } catch (Exception e) {
            LOG.warn("[路径内存映射-VQE] 正则编译失败: sw={}, regex={}", sw, regex);
            return Collections.emptyList();
        }

        List<String> results = new ArrayList<>();
        Set<String> seenPaths = new HashSet<>();

        for (int pid : allPids) {
            List<String> memMapPaths = enumerateByVirtualQueryEx(pid);
            LOG.info("[路径内存映射-VQE-MEMMAP] sw={}, pid={}, count={}", sw, pid, memMapPaths.size());

            for (String path : memMapPaths) {
                if (seenPaths.contains(path)) continue;
                seenPaths.add(path);

                // 统一分隔符为 /，与正则表达式保持一致
                String normalizedPath = path.replace('\\', '/');

                // 打印前5条路径用于调试
                if (seenPaths.size() <= 5) {
                    LOG.info("[路径内存映射-VQE-SAMPLE] sw={}, pid={}, path={}", sw, pid, normalizedPath);
                }

                java.util.regex.Matcher matcher = pattern.matcher(normalizedPath);
                boolean matched = matcher.find();
                if (!matched) {
                    LOG.debug("[路径内存映射-VQE-NOMATCH] sw={}, pid={}, path={}", sw, pid, normalizedPath);
                    continue;
                }
                // Python: re.match(pattern, path).group(1) — 取第一个捕获组
                String captured = matcher.group(1);
                if (captured != null && !captured.isBlank()) {
                    if (results.add(captured)) {
                        LOG.info("[路径内存映射-VQE-MATCHED] sw={}, pid={}, regex={}, matched={}",
                                sw, pid, regex, captured);
                    }
                } else {
                    LOG.warn("[路径内存映射-VQE] sw={}, pid={}, path matched but group(1) is empty. path={}, regex={}",
                            sw, pid, path, regex);
                }
            }
        }
        return results;
    }

    /**
     * 从 PID 列表中剔除所有子进程，只保留根进程
     * <p>
     * 策略：先建立 PID→ParentPID 映射，然后递归剔除所有后代。
     * 即：如果一个 PID 的父进程（直接或间接）在列表中，则剔除。
     */
    /**
     * 从 PID 列表中剔除所有子进程，只保留根进程
     * <p>
     * 策略：使用 Java ProcessHandle 的 parent()/children() 方法，
     * 对每个 PID 递归查找所有后代，从目标集合中移除。
     */
    public static List<Integer> filterOutChildPids(List<Integer> pids) {
        if (pids.size() <= 1) return pids;
        Set<Integer> targetSet = new LinkedHashSet<>(pids);

        for (int pid : pids) {
            ProcessHandle.of(pid).ifPresent(ph -> {
                // 递归收集所有后代 PID
                Set<Integer> allDescendants = new HashSet<>();
                ph.descendants().forEach(child -> allDescendants.add((int) child.pid()));
                // 从目标集合中移除后代
                targetSet.removeAll(allDescendants);
            });
        }

        return new ArrayList<>(targetSet);
    }


    // ==================== DLL 目录文件遍历 ====================

    /**
     * 通过文件遍历方式获取 DLL 目录
     * 对应 Python: _get_sw_dll_dir_by_files (L1735-L1770)
     */
    @Override
    public List<String> queryDllDirByFiles(String sw, String installDir) {
        // 纯 Java 实现：遍历安装目录查找 DLL 文件
        List<String> results = new ArrayList<>();
        try {
            java.nio.file.Files.walk(java.nio.file.Path.of(installDir))
                    .filter(java.nio.file.Files::isDirectory)
                    .forEach(dir -> {
                        // 检查是否有 .dll 文件
                        try {
                            if (Files.exists(dir) && Files.list(dir).anyMatch(p -> p.toString().toLowerCase().endsWith(".dll"))) {
                                results.add(dir.toString().replace('\\', '/'));
                            }
                        } catch (Exception ignored) {}
                    });
        } catch (Exception e) {
            LOG.warn("[DLL目录] 遍历失败: {}", e.getMessage());
        }
        return results;
    }

    @Override
    public String getProcessImagePath(int pid) {
        Kernel32 kernel32 = Kernel32.INSTANCE;
        HANDLE hProcess = kernel32.OpenProcess(
                WinNT.PROCESS_QUERY_LIMITED_INFORMATION, false, pid);
        if (hProcess == null) return null;
        try {
            char[] pathBuffer = new char[1024];
            IntByReference size = new IntByReference(1024);
            boolean success = kernel32.QueryFullProcessImageName(hProcess, 0, pathBuffer, size);
            if (success && size.getValue() > 0) {
                return new String(pathBuffer, 0, size.getValue()).replace('\\', '/');
            }
        } finally {
            kernel32.CloseHandle(hProcess);
        }
        return null;
    }

    @Override
    public Map<String, List<Integer>> getPidsByWildcardsAndGroup(List<String> executableWildcards) {
        com.sun.jna.platform.win32.Tlhelp32.PROCESSENTRY32.ByReference pe32 =
                new com.sun.jna.platform.win32.Tlhelp32.PROCESSENTRY32.ByReference();
        HANDLE hSnapshot = Kernel32.INSTANCE.CreateToolhelp32Snapshot(
                Tlhelp32.TH32CS_SNAPPROCESS, new com.sun.jna.platform.win32.WinDef.DWORD(0));
        try {
            if (!Kernel32.INSTANCE.Process32First(hSnapshot, pe32)) {
                return Collections.emptyMap();
            }
            Map<String, List<Integer>> result = new LinkedHashMap<>();
            do {
                String exeName = Native.toString(pe32.szExeFile);
                if (exeName == null || exeName.isEmpty()) continue;
                int pid = pe32.th32ProcessID.intValue();
                for (String wc : executableWildcards) {
                    if (wildcardMatch(exeName, wc)) {
                        result.computeIfAbsent(exeName, k -> new ArrayList<>()).add(pid);
                        break;
                    }
                }
            } while (Kernel32.INSTANCE.Process32Next(hSnapshot, pe32));
            return result;
        } finally {
            Kernel32.INSTANCE.CloseHandle(hSnapshot);
        }
    }

    /** 简易通配符匹配: ? 匹配单字符, * 匹配零或多字符 */
    private boolean wildcardMatch(String name, String wildcard) {
        // 转为正则
        String regex = wildcard.replace(".", "\\.").replace("*", ".*").replace("?", ".");
        return name.matches(regex);
    }

    // ==================== 互斥体操作 ====================

    /**
     * 通过 PID 和句柄名通配符查找互斥体句柄
     * 对应 Python: handle_utils.pywinhandle_find_handles_by_pids_and_handle_name_wildcards
     */
    public static List<Map<String, Object>> findHandlesByPidsAndWildcards(
            List<Integer> pids, List<String> handleNameWildcards) {
        // TODO: JNA 实现
        LOG.debug("[JNA] findHandlesByPidsAndWildcards: {} pids, {} wildcards (Stub)",
                pids.size(), handleNameWildcards.size());
        return Collections.emptyList();
    }

    /**
     * 关闭互斥体句柄
     * 对应 Python: handle_utils.pywinhandle_close_handles
     */
    public static boolean closeHandles(List<Map<String, Object>> handleInfos) {
        // TODO: JNA 实现
        LOG.debug("[JNA] closeHandles: {} handles (Stub)", handleInfos.size());
        return false;
    }

    // ==================== 窗口操作 ====================

    /**
     * 等待所有窗口关闭
     * 对应 Python: hwnd_utils.wait_hwnds_close
     */
    public static boolean waitHwndsClose(List<Integer> hwnds, int timeout) {
        // TODO: JNA 实现
        LOG.debug("[JNA] waitHwndsClose: {} windows, {}s timeout (Stub)", hwnds.size(), timeout);
        return false;
    }

    /**
     * 尝试关闭一组窗口，返回剩余的未关闭窗口
     * 对应 Python: hwnd_utils.try_close_hwnds_in_set_and_return_remained
     */
    public static List<Integer> tryCloseHwndsAndReturnRemained(Set<Integer> hwnds) {
        // TODO: JNA 实现
        LOG.debug("[JNA] tryCloseHwnds: {} windows (Stub)", hwnds.size());
        return Collections.emptyList();
    }

    /**
     * 获取窗口详细信息
     * 对应 Python: hwnd_utils.get_hwnd_details_of_
     */
    public static Map<String, Object> getHwndDetails(int hwnd) {
        // TODO: JNA 实现
        LOG.debug("[JNA] getHwndDetails: hwnd={} (Stub)", hwnd);
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("hwnd", hwnd);
        details.put("width", 0);
        details.put("height", 0);
        return details;
    }

    // ==================== 进程操作 ====================

    /**
     * 移除子进程 PID（只保留根进程）
     * 对应 Python: process_utils.remove_child_pids
     */
    public static List<Integer> removeChildPids(List<Integer> pids) {
        // TODO: JNA 实现
        LOG.debug("[JNA] removeChildPids: {} pids (Stub)", pids.size());
        return new ArrayList<>(pids);
    }

    /**
     * 移除不在指定路径下的进程 PID
     * 对应 Python: process_utils.remove_pids_not_in_path
     */
    public static List<Integer> removePidsNotInPath(List<Integer> pids, String instDir) {
        // TODO: JNA 实现
        LOG.debug("[JNA] removePidsNotInPath: {} pids, dir={} (Stub)", pids.size(), instDir);
        return new ArrayList<>(pids);
    }

    /**
     * 以非管理员身份创建进程
     */
    public static Process createProcessWithoutAdmin(String executable, String args, int creationFlags) {
        try {
            ProcessBuilder pb = new ProcessBuilder(executable);
            if (args != null && !args.isBlank()) {
                pb.command().addAll(List.of(args.split("\\s+")));
            }
            return pb.start();
        } catch (Exception e) {
            LOG.warn("[JNA] createProcessWithoutAdmin failed: {}", e.getMessage());
            return null;
        }
    }

    // ==================== 文件操作 ====================

    /**
     * 备份文件
     */
    public static void backupFiles(List<String> filePaths) {
        for (String path : filePaths) {
            java.nio.file.Path src = java.nio.file.Path.of(path);
            java.nio.file.Path bak = java.nio.file.Path.of(path + ".bak");
            try {
                if (java.nio.file.Files.exists(src) && !java.nio.file.Files.exists(bak)) {
                    java.nio.file.Files.copy(src, bak,
                            java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    LOG.debug("[文件] 备份: {} -> {}", path, bak);
                }
            } catch (Exception e) {
                LOG.warn("[文件] 备份失败: {}", e.getMessage());
            }
        }
    }

    /**
     * 移动文件到回收站
     */
    public static void moveFilesToRecycleBin(List<String> filePaths) {
        // TODO: JNA 实现
        // 使用 SHFileOperationW with FO_DELETE + FOF_ALLOWUNDO
        LOG.debug("[文件] 移动到回收站: {} files (Stub)", filePaths.size());
    }

    // ==================== 进程内存映射枚举（三种方案，用于对比测试） ====================

    /**
     * Psapi 扩展接口 — JNA 5.14.0 缺少的函数在此声明
     */
    private interface PsapiExt extends com.sun.jna.platform.win32.Psapi {
        PsapiExt INSTANCE = (PsapiExt) Native.load("psapi", PsapiExt.class);

        /** EnumProcessModulesEx 的 LIST_MODULES_ALL 常量 */
        int LIST_MODULES_ALL = 0x0F;

        /** EnumProcessModulesEx: 列出进程所有模块 (HMODULE[]) */
        boolean EnumProcessModulesEx(HANDLE hProcess, WinDef.HMODULE[] lphModule, int cb,
                                     IntByReference lpcbNeeded, DWORD ListModules);

        /** GetModuleFileNameExW: 返回 int (长度)，接受 char[] 缓冲区 */
        int GetModuleFileNameExW(HANDLE hProcess, WinDef.HMODULE hModule, char[] lpFilename, int nSize);

        /** GetMappedFileNameW: 返回 boolean，接受 char[] 缓冲区 */
        boolean GetMappedFileNameW(HANDLE hProcess, Pointer lpv, char[] lpFilename, int nSize);
    }

    /**
     * 方案1: EnumProcessModulesEx + GetModuleFileNameEx (Psapi)
     * 返回: exe, dll
     */
    public static List<String> enumerateByPsapi(int pid) {
        List<String> result = new ArrayList<>();
        WinNT.HANDLE process = Kernel32.INSTANCE.OpenProcess(
                WinNT.PROCESS_QUERY_INFORMATION | WinNT.PROCESS_VM_READ, false, pid);
        if (process == null) return result;
        try {
            WinDef.HMODULE[] modules = new WinDef.HMODULE[4096];
            IntByReference needed = new IntByReference();
            if (!PsapiExt.INSTANCE.EnumProcessModulesEx(
                    process, modules, modules.length * Native.POINTER_SIZE,
                    needed, new DWORD(PsapiExt.LIST_MODULES_ALL))) {
                return result;
            }
            int count = needed.getValue() / Native.POINTER_SIZE;
            char[] buffer = new char[32768];
            for (int i = 0; i < count; i++) {
                Arrays.fill(buffer, '\0');
                int len = PsapiExt.INSTANCE.GetModuleFileNameExW(
                        process, modules[i], buffer, buffer.length);
                if (len > 0) {
                    result.add(new String(buffer, 0, len));
                }
            }
        } finally {
            Kernel32.INSTANCE.CloseHandle(process);
        }
        return result;
    }

    /**
     * 方案2: ToolHelp32Snapshot (CreateToolhelp32Snapshot + Module32FirstW/NextW)
     * 返回: exe, dll
     */
    public static List<String> enumerateByToolHelp(int pid) {
        List<String> result = new ArrayList<>();
        // TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32 = 0x00000006 | 0x00000010 = 0x00000016
        WinNT.HANDLE snapshot = Kernel32.INSTANCE.CreateToolhelp32Snapshot(
                Tlhelp32.TH32CS_SNAPMODULE,
                new WinDef.DWORD(pid));
        if (WinBase.INVALID_HANDLE_VALUE.equals(snapshot)) return result;
        try {
            Tlhelp32.MODULEENTRY32W module = new Tlhelp32.MODULEENTRY32W();
            if (!Kernel32.INSTANCE.Module32FirstW(snapshot, module)) return result;
            do {
                result.add(Native.toString(module.szExePath));
            } while (Kernel32.INSTANCE.Module32NextW(snapshot, module));
        } finally {
            Kernel32.INSTANCE.CloseHandle(snapshot);
        }
        return result;
    }

    /**
     * 方案3: VirtualQueryEx + GetMappedFileNameW (最接近 psutil.Process(pid).memory_maps())
     * 返回: exe, dll, db, sqlite, pak, dat, mmap 文件
     */
    public static List<String> enumerateByVirtualQueryEx(int pid) {
        Set<String> result = new LinkedHashSet<>();
        WinNT.HANDLE process = Kernel32.INSTANCE.OpenProcess(
                WinNT.PROCESS_QUERY_INFORMATION | WinNT.PROCESS_VM_READ, false, pid);
        if (process == null) return new ArrayList<>();
        try {
            long address = 0;
            WinNT.MEMORY_BASIC_INFORMATION mbi = new WinNT.MEMORY_BASIC_INFORMATION();
            char[] pathBuffer = new char[32768];
            while (true) {
                WinNT.SIZE_T queried = Kernel32.INSTANCE.VirtualQueryEx(
                        process, new Pointer(address), mbi, new WinNT.SIZE_T(mbi.size()));
                if (queried.longValue() == 0) break;
                mbi.read();
                if (mbi.state.intValue() == WinNT.MEM_COMMIT) {
                    Arrays.fill(pathBuffer, '\0');
                    boolean mappedOk = PsapiExt.INSTANCE.GetMappedFileNameW(
                            process, mbi.baseAddress, pathBuffer, pathBuffer.length);
                    if (mappedOk) {
                        String nativePath = new String(pathBuffer, 0, pathBuffer.length).trim();
                        String dosPath = convertDevicePathToDosPath(nativePath);
                        if (dosPath != null) result.add(dosPath);
                    }
                }
                long baseNative = Pointer.nativeValue(mbi.baseAddress);
                long regionSize = mbi.regionSize.longValue();
                address = baseNative + regionSize;
                if (address <= 0) break;
            }
        } finally {
            Kernel32.INSTANCE.CloseHandle(process);
        }
        return new ArrayList<>(result);
    }

    /**
     * 将 \Device\HarddiskVolume3\Windows\... 转换为 C:\Windows\...
     */
    private static String convertDevicePathToDosPath(String devicePath) {
        List<String> driveList = Kernel32Util.getLogicalDriveStrings();
        for (String drive : driveList) {
            if (drive.isEmpty()) continue;
            String letter = drive.substring(0, 2);
            char[] target = new char[32768];
            int len = Kernel32.INSTANCE.QueryDosDevice(letter, target, target.length);
            if (len == 0) continue;
            String device = Native.toString(target);
            if (devicePath.startsWith(device)) {
                return letter + devicePath.substring(device.length());
            }
        }
        return devicePath;
    }
}
