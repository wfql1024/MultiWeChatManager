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
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

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

    // ==================== 懒加载内存映射迭代器 ====================

    /**
     * 懒加载迭代器：逐条返回匹配进程的内存映射文件路径.
     * <p>
     * 实现策略：
     * <ol>
     *   <li>通过 exe 通配符获取目标进程 PID 列表</li>
     *   <li>剔除子进程</li>
     *   <li>对每个 PID 创建 {@link NativeMemoryMapIterator}，用 VirtualQueryEx
     *       逐区域遍历 + GetMappedFileNameW 获取每条映射文件路径</li>
     *   <li>多个 PID 的迭代器串联为一个组合迭代器</li>
     * </ol>
     * <p>
     * 调用方必须在使用完毕后调用 {@code close()} 释放进程句柄。
     *
     * @param sw           软件标识（用于日志）
     * @param exeWildcards 可执行文件通配符列表
     * @return 内存映射路径迭代器（可能为空迭代器，绝不返回 null）
     */
    @Override
    public SwPathDetective.NativeOps.MemoryMapIterator iterateMemoryMapPaths(
            String sw, List<String> exeWildcards) {
        Map<String, List<Integer>> namePids = getPidsByWildcardsAndGroup(exeWildcards);
        List<Integer> allPids = new ArrayList<>();
        for (List<Integer> pids : namePids.values()) allPids.addAll(pids);

        if (allPids.isEmpty()) {
            LOG.debug("[路径内存映射-ITER] sw={}, 无匹配进程", sw);
            return EmptyMemoryMapIterator.INSTANCE;
        }

        LOG.info("[路径内存映射-ITER] sw={}, allPids={}", sw, allPids);
        allPids = filterOutChildPids(allPids);
        LOG.info("[路径内存映射-ITER] sw={}, after_remove_child_pids={}", sw, allPids);

        if (allPids.isEmpty()) {
            return EmptyMemoryMapIterator.INSTANCE;
        }

        return new CompositeMemoryMapIterator(allPids);
    }

    /**
     * 空迭代器 — 无进程匹配时返回.
     */
    private static final class EmptyMemoryMapIterator
            implements SwPathDetective.NativeOps.MemoryMapIterator {
        static final EmptyMemoryMapIterator INSTANCE = new EmptyMemoryMapIterator();

        @Override
        public boolean hasNext() { return false; }

        @Override
        public String next() { throw new java.util.NoSuchElementException(); }

        @Override
        public void close() {}
    }

    /**
     * 组合迭代器 — 串联多个 PID 的 {@link NativeMemoryMapIterator}.
     */
    private static final class CompositeMemoryMapIterator
            implements SwPathDetective.NativeOps.MemoryMapIterator {
        private final List<Integer> pids;
        private int pidIndex;
        private NativeMemoryMapIterator current;

        CompositeMemoryMapIterator(List<Integer> pids) {
            this.pids = new ArrayList<>(pids);
            this.pidIndex = 0;
            advanceToNextPid();
        }

        /** 前进到下一个有数据的 PID 迭代器 */
        private void advanceToNextPid() {
            closeCurrent();
            while (pidIndex < pids.size()) {
                int pid = pids.get(pidIndex);
                pidIndex++;
                NativeMemoryMapIterator it = new NativeMemoryMapIterator(pid);
                if (it.hasNext()) {
                    current = it;
                    return;
                }
                it.close();
            }
            current = null;
        }

        @Override
        public boolean hasNext() {
            while (current != null) {
                if (current.hasNext()) return true;
                advanceToNextPid();
            }
            return false;
        }

        @Override
        public String next() {
            if (!hasNext()) throw new java.util.NoSuchElementException();
            String path = current.next();
            // 当前迭代器耗尽时自动前进到下一个 PID
            if (!current.hasNext()) {
                advanceToNextPid();
            }
            return path;
        }

        @Override
        public void close() {
            closeCurrent();
        }

        private void closeCurrent() {
            if (current != null) {
                current.close();
                current = null;
            }
        }
    }

    /**
     * 单进程内存映射迭代器 — 逐区域遍历虚拟地址空间.
     * <p>
     * 使用 VirtualQueryEx 遍历每个内存区域，通过 GetMappedFileNameW 获取映射文件路径。
     * 每次调用 {@code next()} 返回一条路径（统一使用 / 分隔符），
     * 同时推进到下一个区域。
     * <p>
     * 对应 Python: {@code psutil.Process(pid).memory_maps()} 的惰性版本.
     */
    private static final class NativeMemoryMapIterator
            implements SwPathDetective.NativeOps.MemoryMapIterator {
        private final int pid;
        private final WinNT.HANDLE hProcess;
        private long currentAddr;
        private String nextPath;
        private boolean exhausted;

        NativeMemoryMapIterator(int pid) {
            this.pid = pid;
            this.currentAddr = 0L;
            this.exhausted = false;

            WinNT.HANDLE h = null;
            try {
                h = Kernel32.INSTANCE.OpenProcess(
                        WinNT.PROCESS_QUERY_INFORMATION | WinNT.PROCESS_VM_READ,
                        false, pid);
            } catch (Exception e) {
                LOG.debug("[路径内存映射-ITER] 无法打开进程: pid={}", pid, e);
            }
            this.hProcess = h;
            if (hProcess == null) {
                this.exhausted = true;
                return;
            }
            advance();
        }

        /**
         * 推进到下一个已提交的内存区域并获取其映射文件路径.
         */
        private void advance() {
            nextPath = null;
            if (exhausted || hProcess == null) {
                exhausted = true;
                return;
            }

            WinNT.MEMORY_BASIC_INFORMATION mbi = new WinNT.MEMORY_BASIC_INFORMATION();
            char[] pathBuffer = new char[32768];

            while (true) {
                WinNT.SIZE_T queried = Kernel32.INSTANCE.VirtualQueryEx(
                        hProcess,
                        new com.sun.jna.Pointer(currentAddr),
                        mbi,
                        new WinNT.SIZE_T(mbi.size()));
                if (queried.longValue() == 0) {
                    exhausted = true;
                    return;
                }
                mbi.read();

                long regionSize = mbi.regionSize.longValue();
                long baseNative;
                try {
                    baseNative = com.sun.jna.Pointer.nativeValue(mbi.baseAddress);
                } catch (Exception e) {
                    // Pointer.nativeValue 在某些 JNA 版本不可用，回退到计算
                    baseNative = currentAddr;
                }

                // 前进到下一个区域
                currentAddr = baseNative + regionSize;
                if (currentAddr <= 0) {
                    exhausted = true;
                    return;
                }

                // 只处理已提交的内存区域
                if (mbi.state.intValue() == WinNT.MEM_COMMIT) {
                    Arrays.fill(pathBuffer, '\0');
                    try {
                        boolean mappedOk = PsapiExt.INSTANCE.GetMappedFileNameW(
                                hProcess, mbi.baseAddress, pathBuffer, pathBuffer.length);
                        if (mappedOk) {
                            String nativePath = new String(pathBuffer).trim();
                            if (!nativePath.isEmpty()) {
                                String dosPath = convertDevicePathToDosPath(nativePath);
                                if (dosPath != null) {
                                    nextPath = dosPath.replace('\\', '/');
                                    return;
                                }
                            }
                        }
                    } catch (Exception e) {
                        // 单个区域获取失败，继续下一个
                        LOG.trace("[路径内存映射-ITER] GetMappedFileNameW 失败: pid={}, addr={}",
                                pid, baseNative, e);
                    }
                }
                // 未提交或无映射文件 → 继续下一个区域
            }
        }

        @Override
        public boolean hasNext() {
            return !exhausted && nextPath != null;
        }

        @Override
        public String next() {
            if (!hasNext()) throw new java.util.NoSuchElementException();
            String result = nextPath;
            advance();
            return result;
        }

        @Override
        public void close() {
            if (hProcess != null) {
                try {
                    Kernel32.INSTANCE.CloseHandle(hProcess);
                } catch (Exception ignored) {}
            }
            exhausted = true;
        }
    }

    /**
     * 从 PID 列表中剔除所有子进程，只保留根进程
     * <p>
     * 策略：使用 Java ProcessHandle 的 parent()/children() 方法，
     * 对每个 PID 递归查找所有后代，从目标集合中移除。
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
    // 这一组是**取句柄**的基础件（用户 2026-10-07 要求抽象成核心能力）：
    // 登录窗口、主窗口的定位都走同一条链 —— 平台 pid 列表 → 该 pid 的顶层窗口 → 按规则筛选。

    /** Win32 类名上限 */
    private static final int WND_CLASS_MAX = 256;

    /** HWND → int（项目内句柄一律 int 传递，与既有 IntByReference / JS number 约定一致） */
    public static int hwndToInt(WinDef.HWND hwnd) {
        return hwnd == null ? 0 : (int) Pointer.nativeValue(hwnd.getPointer());
    }

    /** int → HWND */
    public static WinDef.HWND intToHwnd(int hwnd) {
        return new WinDef.HWND(Pointer.createConstant(Integer.toUnsignedLong(hwnd)));
    }

    /**
     * 枚举某进程的**顶层窗口**句柄.
     * 对应 Python: {@code Win32HwndGetter.win32_get_hwnds_by_pid_and_class_wildcards(pid)}
     * <p>EnumWindows 是同步调用（回调在本次调用返回前就用完了），所以匿名回调无需长期持引用。
     */
    public static List<Integer> getHwndsByPid(int pid) {
        List<Integer> result = new ArrayList<>();
        if (pid <= 0) return result;
        com.sun.jna.platform.win32.User32.INSTANCE.EnumWindows((hwnd, data) -> {
            IntByReference winPid = new IntByReference();
            com.sun.jna.platform.win32.User32.INSTANCE.GetWindowThreadProcessId(hwnd, winPid);
            if (winPid.getValue() == pid) result.add(hwndToInt(hwnd));
            return true;
        }, null);
        return result;
    }

    /**
     * 按匹配规则筛选窗口句柄.
     * 对应 Python: {@code uiautomation_filter_hwnds_by_matching_dict} + {@code _final_select_hwnds}
     *
     * <p>语义对齐旧版（这是"有的平台识别不到"的关键）：<b>初筛</b>（本方法前半段）用
     * {@code ClassNameWildcards}（`fnmatch` 语义：`*` `?` `[seq]`）、{@code Name/Title}、
     * {@code ProcessId/PID}，前缀 {@code !} 取反，{@code OR*} 表示"任一子规则"；
     * <b>尾筛</b>当命中多于一个且有 {@code FinalSelect} 时按 尺寸/宽/高 的
     * {@code Extreme|End(max/min)/Equals/Greater/Less} 逐方法挑出唯一一个
     * —— 旧版就是靠它把"登录窗 + 隐藏的同类窗"区分开的，缺了它就会一个都取不到。
     */
    public static List<Integer> filterHwndsByMatchingDict(List<Integer> hwnds, Map<String, Object> rules) {
        List<Integer> result = new ArrayList<>();
        if (hwnds == null || rules == null || rules.isEmpty()) return result;
        long t0 = System.currentTimeMillis();
        // 第一趟：**只用 Win32 类名**（便宜）—— 绝大多数平台这一趟就命中了
        for (Integer hwnd : hwnds) {
            if (hwnd != null && matchesRules(hwnd, rules, false)) result.add(hwnd);
        }
        long t1 = System.currentTimeMillis();
        // 第二趟：整条规则一个都没命中时，才改用 **UIA 类名**重扫一遍。
        // 为什么这样分（用户 2026-10-07 的观察 + 实测推理）：UIA 每次要走 COM
        //（CoCreateInstance + ElementFromHandle + 取属性），对**每个窗口**都试一遍的话，
        // 窗口一多（8~9 个实例 ≈ 100+ 个顶层窗口）就是几秒 —— 而"第一个账号很快、后面很慢"
        // 正是窗口数在涨。分两趟后：Win32 能匹配的平台**完全不碰 UIA**，
        // 只有真正需要 UIA 的平台才付这一次代价。
        if (result.isEmpty() && hasClassNameRule(rules)) {
            for (Integer hwnd : hwnds) {
                if (hwnd != null && matchesRules(hwnd, rules, true)) result.add(hwnd);
            }
            if (!result.isEmpty()) {
                LOG.info("[窗口] Win32 类名无命中，改用 UIA 类名命中 {} 个（共 {} 个候选窗口）",
                        result.size(), hwnds.size());
            }
        }
        if (hwnds.size() > 20 || System.currentTimeMillis() - t0 > 200) {
            LOG.info("[窗口] 规则匹配 {} 个候选：Win32 趟 {}ms，命中 {} 个；总计 {}ms",
                    hwnds.size(), t1 - t0, result.size(), System.currentTimeMillis() - t0);
        }
        // 尾筛：初筛不唯一时，用 FinalSelect 的方法集合逐个试，取到唯一为止
        Object finalSelect = rules.get("FinalSelect");
        if (result.size() > 1 && finalSelect instanceof List) {
            @SuppressWarnings("unchecked")
            List<Object> methods = (List<Object>) finalSelect;
            for (Object method : methods) {
                if (!(method instanceof Map)) continue;
                @SuppressWarnings("unchecked")
                Map<String, Object> conds = (Map<String, Object>) method;
                List<Integer> elected = new ArrayList<>(result);
                for (Map.Entry<String, Object> e : conds.entrySet()) {
                    elected = finalSelectFilter(elected, e.getKey(), e.getValue());
                    if (elected.size() <= 1) break;
                }
                if (elected.size() == 1) {
                    LOG.info("[窗口] 尾筛 {} 从 {} 个候选中选出 1 个: {}", conds, result.size(), elected.get(0));
                    return elected;
                }
            }
            LOG.info("[窗口] 初筛命中 {} 个但尾筛没能选出唯一：{}", result.size(), result);
        }
        return result;
    }

    /** 尾筛单条件：Size/Width/Height × Extreme|End(max|min)/Equals/Greater/Less，支持 `!` 取反 */
    private static List<Integer> finalSelectFilter(List<Integer> candidates, String key, Object value) {
        boolean negate = key.startsWith("!");
        String k = negate ? key.substring(1) : key;
        boolean extreme = k.endsWith("Extreme") || k.endsWith("End");
        boolean equals = k.endsWith("Equals");
        boolean greater = k.endsWith("Greater");
        boolean less = k.endsWith("Less");
        String metric = k.replace("Extreme", "").replace("End", "")
                .replace("Equals", "").replace("Greater", "").replace("Less", "");
        List<Integer> filtered = new ArrayList<>();
        if (extreme) {
            Map<Integer, Long> vals = new LinkedHashMap<>();
            for (Integer h : candidates) vals.put(h, metricValue(h, metric));
            if (vals.isEmpty()) return candidates;
            boolean wantMax = "max".equalsIgnoreCase(String.valueOf(value));
            long target = wantMax ? Long.MIN_VALUE : Long.MAX_VALUE;
            for (Long v : vals.values()) {
                if (wantMax ? v > target : v < target) target = v;
            }
            for (Map.Entry<Integer, Long> e : vals.entrySet()) {
                if (e.getValue() == target) filtered.add(e.getKey());
            }
        } else if (equals || greater || less) {
            long num = value instanceof Number ? ((Number) value).longValue() : -1;
            for (Integer h : candidates) {
                long v = metricValue(h, metric);
                if ((equals && v == num) || (greater && v > num) || (less && v < num)) filtered.add(h);
            }
        } else {
            LOG.warn("[窗口] 尾筛条件不认识，忽略: {}", key);
            return candidates;
        }
        if (!negate) return filtered;
        List<Integer> rest = new ArrayList<>(candidates);
        rest.removeAll(filtered);
        return rest;
    }

    /** 尾筛用的度量值：Size=面积、Width=宽、Height=高（取自 GetWindowRect） */
    private static long metricValue(int hwnd, String metric) {
        Map<String, Object> d = getHwndDetails(hwnd);
        long w = ((Number) d.getOrDefault("width", 0)).longValue();
        long h = ((Number) d.getOrDefault("height", 0)).longValue();
        if (metric.startsWith("Size")) return w * h;
        if (metric.startsWith("Width")) return w;
        if (metric.startsWith("Height")) return h;
        return w * h;
    }

    /** 规则里有没有涉及类名的条件（决定要不要为它跑第二趟 UIA） */
    private static boolean hasClassNameRule(Map<String, Object> rules) {
        for (String key : rules.keySet()) {
            if (key == null) continue;
            String k = key.startsWith("!") ? key.substring(1) : key;
            if (k.equalsIgnoreCase("ClassNameWildcards") || k.equalsIgnoreCase("ClassNames")
                    || k.startsWith("OR")) {
                return true;
            }
        }
        return false;
    }

    private static boolean matchesRules(int hwnd, Map<String, Object> rules) {
        return matchesRules(hwnd, rules, true);
    }

    /**
     * @param useUia 是否允许在 Win32 类名不中时改用 **UIA 类名**兜底。
     *               分两趟调用时：第一趟 false（快），第二趟 true（慢但能救回 Win32 报不准类名的平台）。
     */
    private static boolean matchesRules(int hwnd, Map<String, Object> rules, boolean useUia) {
        Map<String, Object> details = getHwndDetails(hwnd);
        String cls = String.valueOf(details.getOrDefault("class", ""));
        String title = String.valueOf(details.getOrDefault("title", ""));
        int pid = ((Number) details.getOrDefault("pid", 0)).intValue();
        for (Map.Entry<String, Object> entry : rules.entrySet()) {
            String key = entry.getKey() == null ? "" : entry.getKey();
            boolean negate = key.startsWith("!");
            String k = negate ? key.substring(1) : key;
            boolean matched;
            if (k.startsWith("OR")) {
                // OR 块：值是一组子规则，任一命中即可
                matched = false;
                if (entry.getValue() instanceof List) {
                    for (Object sub : (List<?>) entry.getValue()) {
                        if (sub instanceof Map && matchesRules(hwnd, castMap(sub))) {
                            matched = true;
                            break;
                        }
                    }
                }
            } else if (k.equalsIgnoreCase("ClassNameWildcards") || k.equalsIgnoreCase("ClassNames")) {
                matched = matchAnyWildcard(cls, entry.getValue());
                if (!matched && useUia) {
                    // Win32 类名对不上 → 再试 **UIA 报的类名**（旧版就是靠它匹配到部分平台的窗口；
                    // 例如 Weixin 4.0 的 mmui::LoginWindow，Win32 GetClassName 拿不到那个名字）。
                    // 只有"第二趟"才允许走到这里（用户 2026-10-07：UIA 对每个窗口都调太慢）
                    String uiaCls = UiaOps.getClassName(hwnd);
                    if (uiaCls != null && !uiaCls.equals(cls)) {
                        matched = matchAnyWildcard(uiaCls, entry.getValue());
                        if (matched) {
                            LOG.info("[窗口] hwnd=0x{} 由 UIA 类名匹配上: win32=[{}] uia=[{}] 规则={}",
                                    Integer.toHexString(hwnd), cls, uiaCls, entry.getValue());
                        }
                    }
                }
            } else if (k.equalsIgnoreCase("Name") || k.equalsIgnoreCase("Title")) {
                matched = matchAnyWildcard(title, entry.getValue());
            } else if (k.equalsIgnoreCase("FirstChild") || k.equalsIgnoreCase("LastChild")) {
                matched = matchChildRule(hwnd, k.equalsIgnoreCase("FirstChild"), entry.getValue(), useUia);
            } else if (k.equalsIgnoreCase("ProcessId") || k.equalsIgnoreCase("PID")) {
                matched = entry.getValue() instanceof Number && ((Number) entry.getValue()).intValue() == pid;
            } else if (k.equals("FinalSelect")) {
                continue;                      // 尾筛，交给 filterHwndsByMatchingDict
            } else {
                // 旧版这里查的是 UIAutomation 控件属性；Win32 侧没有对应值 → 记一条日志并按"不限制"处理
                LOG.warn("[窗口] 匹配规则里的键 {} 在 Win32 侧无法求值，已忽略（该窗口仍可能被选中）", key);
                continue;
            }
            if (negate) matched = !matched;
            if (!matched) return false;
        }
        return true;
    }

    /**
     * 规则键 {@code FirstChild} / {@code LastChild}：**子窗口子规则**（2026-10-13 补，原先 Java 完全没实现 ✗）.
     *
     * <p>旧版语义（{@code hwnd_utils.py:309-325}）：取第一个/最后一个**子控件**，把子规则**递归**跑在它的 hwnd 上，
     * 要求"**恰好 1 个命中**"才算（与顶层同一判据）。
     *
     * <p>例（QQNT 主窗，远程配置 {@code wnd_class.main.matching.9.9}）：
     * <pre>{@code {"ClassNameWildcards":["Chrome_WidgetWin_1"], "FirstChild":{"!ClassNameWildcards":[""]}}}</pre>
     * QQNT 的**登录窗与主窗类名相同**（都是 Electron 的 {@code Chrome_WidgetWin_1}）✗，
     * 只有主窗"**第一个子窗口的类名非空**" ✓ —— 没有这个键，主窗永远匹配不上（实测症状：账号查得到、窗口 0 个 ✓）。
     *
     * <p>与旧版的差别：旧版走 **UIA 控件树**（{@code Control.GetFirstChildControl}）；这里用 **Win32 子窗口**
     * （{@code GW_CHILD} / {@code GW_HWNDLAST}）—— 同语义但不必付 COM 代价 ✓。
     * 若将来有平台"子窗口类名只有 UIA 报得出来"，再升级成 UIA 版（届时用 {@code UiaProbe} 校正 vtable 下标）。
     */
    private static boolean matchChildRule(int hwnd, boolean first, Object subRule, boolean useUia) {
        if (!(subRule instanceof Map)) return false;
        int child = firstOrLastChildHwnd(hwnd, first);
        if (child == 0) return false;
        return matchesRules(child, castMap(subRule), useUia);
    }

    /** 第一个/最后一个**子窗口**句柄（Win32：GW_CHILD + GW_HWNDLAST）；没有子窗口返回 0 */
    private static int firstOrLastChildHwnd(int hwnd, boolean first) {
        try {
            com.sun.jna.platform.win32.User32 u32 = com.sun.jna.platform.win32.User32.INSTANCE;
            final int GW_CHILD = 5, GW_HWNDLAST = 1;
            com.sun.jna.platform.win32.WinDef.HWND child =
                    u32.GetWindow(intToHwnd(hwnd), new com.sun.jna.platform.win32.WinDef.DWORD(GW_CHILD));
            if (child == null) return 0;
            if (!first) {
                child = u32.GetWindow(child, new com.sun.jna.platform.win32.WinDef.DWORD(GW_HWNDLAST));
            }
            return child == null ? 0 : hwndToInt(child);
        } catch (Throwable t) {
            return 0;
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castMap(Object o) {
        return (Map<String, Object>) o;
    }

    /** 规则值可能是字符串或字符串列表 → 统一按"任一项通配匹配"处理 */
    private static boolean matchAnyWildcard(String text, Object patterns) {
        List<String> list = new ArrayList<>();
        if (patterns instanceof List) {
            for (Object o : (List<?>) patterns) if (o != null) list.add(String.valueOf(o));
        } else if (patterns != null) {
            list.add(String.valueOf(patterns));
        }
        for (String p : list) {
            if (globMatch(text, p)) return true;
        }
        return false;
    }

    /**
     * 通配匹配：`?` = 任意 1 字符，`*` = 任意串，`[seq]` = 字符集；大小写不敏感.
     * （语义对齐 Python 的 {@code fnmatch.fnmatch} —— 远程配置里的 ClassNameWildcards 就按它写。）
     */
    public static boolean globMatch(String text, String pattern) {
        if (text == null || pattern == null) return false;
        StringBuilder regex = new StringBuilder();
        StringBuilder cls = null;
        for (char c : pattern.toCharArray()) {
            if (cls != null) {                       // 正在 `[...]` 里
                cls.append(c);
                if (c == ']') {
                    regex.append(cls);
                    cls = null;
                }
                continue;
            }
            if (c == '[') {
                cls = new StringBuilder("[");
            } else if (c == '*') {
                regex.append(".*");
            } else if (c == '?') {
                regex.append('.');
            } else {
                regex.append(java.util.regex.Pattern.quote(String.valueOf(c)));
            }
        }
        if (cls != null) regex.append(java.util.regex.Pattern.quote("["));
        return text.matches("(?is)" + regex);
    }

    /**
     * **在窗口内指定位置点击**（后台点击：发消息，不移动真实鼠标）.
     * 对应 Python: {@code hwnd_utils.do_click_in_wnd(hwnd, cx, cy)}
     *
     * <p>账号级登录就靠它点"登录"按钮（见 {@code AccOperatorCore.loginOrigin}）：
     * 坐标是**客户区**坐标（相对窗口左上角），按窗口宽高乘配置的比例算出来。
     *
     * @param hwnd 目标窗口
     * @param cx   客户区横坐标
     * @param cy   客户区纵坐标
     */
    public static boolean clickInWindow(int hwnd, int cx, int cy) {
        if (hwnd == 0) return false;
        com.sun.jna.platform.win32.User32 user32 = com.sun.jna.platform.win32.User32.INSTANCE;
        WinDef.HWND h = intToHwnd(hwnd);
        if (!user32.IsWindow(h)) return false;
        // LPARAM = (y << 16) | x（客户区坐标）
        WinDef.LPARAM lParam = new WinDef.LPARAM(((long) (cy & 0xFFFF) << 16) | (cx & 0xFFFF));
        WinDef.WPARAM wParam = new WinDef.WPARAM(1);      // MK_LBUTTON
        user32.PostMessage(h, 0x0201 /* WM_LBUTTONDOWN */, wParam, lParam);
        try {
            Thread.sleep(30);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        user32.PostMessage(h, 0x0202 /* WM_LBUTTONUP */, new WinDef.WPARAM(0), lParam);
        LOG.info("[窗口] 已点击 hwnd=0x{} 位置 ({}, {})", Integer.toHexString(hwnd), cx, cy);
        return true;
    }

    /** 主屏尺寸（宽, 高）—— 摆位用（GetSystemMetrics: 0=宽, 1=高） */
    public static int[] getScreenSize() {
        try {
            int w = com.sun.jna.platform.win32.User32.INSTANCE.GetSystemMetrics(0);
            int h = com.sun.jna.platform.win32.User32.INSTANCE.GetSystemMetrics(1);
            return new int[]{w > 0 ? w : 1920, h > 0 ? h : 1080};
        } catch (Throwable t) {
            return new int[]{1920, 1080};
        }
    }

    /**
     * 把窗口移动到指定位置（**只移动、不改尺寸**）.
     * 对应 Python: {@code win32gui.SetWindowPos(hwnd, HWND_TOP, x, y, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW)}
     */
    public static boolean moveWindow(int hwnd, int x, int y) {
        if (hwnd == 0) return false;
        final int SWP_NOSIZE = 0x0001, SWP_SHOWWINDOW = 0x0040;
        return com.sun.jna.platform.win32.User32.INSTANCE.SetWindowPos(
                intToHwnd(hwnd), intToHwnd(0) /* HWND_TOP */, x, y, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW);
    }

    /**
     * 取窗口**当前标题**（用于"标题没变就不重复设置"——JNA 的 User32 只暴露了 GetWindowText ✓）
     */
    public static String getWindowTitle(int hwnd) {
        if (hwnd == 0) return "";
        try {
            char[] buf = new char[512];
            int n = com.sun.jna.platform.win32.User32.INSTANCE.GetWindowText(intToHwnd(hwnd), buf, buf.length);
            return n <= 0 ? "" : new String(buf, 0, n);
        } catch (Throwable t) {
            return "";
        }
    }

    /**
     * **设置窗口标题**（旧版 `_record_hwnd_and_set_title` 会把它改成"平台名 - 账号名"，便于任务栏辨认）.
     * 对应 Python: {@code hwnd_utils.set_window_title}
     */
    public static boolean setWindowTitle(int hwnd, String title) {
        if (hwnd == 0 || title == null) return false;
        try {
            return User32Ext.INSTANCE.SetWindowTextW(intToHwnd(hwnd), new com.sun.jna.WString(title));
        } catch (Throwable t) {
            LOG.warn("[窗口] 设置标题失败 hwnd={}: {}", hwnd, t.getMessage());
            return false;
        }
    }

    // ==================== 窗口激活 / 可见性（切换窗口用） ====================

    /** 句柄当前是否还是个有效窗口（窗口被关掉后 hwnd 立刻失效 → 前端要跟着清空） */
    public static boolean isWindow(int hwnd) {
        if (hwnd == 0) return false;
        try {
            return com.sun.jna.platform.win32.User32.INSTANCE.IsWindow(intToHwnd(hwnd));
        } catch (Throwable t) {
            return false;
        }
    }

    /** 窗口是否可见（微信被"隐藏到后台"时不可见 → 需要额外点一下把它叫醒，见 restoreWindowAndActivate） */
    public static boolean isWindowVisible(int hwnd) {
        if (hwnd == 0) return false;
        try {
            return com.sun.jna.platform.win32.User32.INSTANCE.IsWindowVisible(intToHwnd(hwnd));
        } catch (Throwable t) {
            return false;
        }
    }

    /** dwmapi：取"视觉边界"（JNA 未暴露 DwmGetWindowAttribute，自己声明一个最小的） */
    private interface DwmapiExt extends com.sun.jna.Library {
        DwmapiExt INSTANCE = Native.load("dwmapi", DwmapiExt.class);

        int DwmGetWindowAttribute(com.sun.jna.platform.win32.WinDef.HWND hwnd, int attr,
                                  com.sun.jna.platform.win32.WinDef.RECT rect, int size);
    }

    /** DWMWA_EXTENDED_FRAME_BOUNDS：窗口**视觉**边界（不含 Win10 那圈隐形边框/阴影） */
    private static final int DWMWA_EXTENDED_FRAME_BOUNDS = 9;

    /** 窗口是否最小化（JNA 的 User32 没暴露 IsIconic → 用 GetWindowPlacement 的 showCmd 判断） */
    public static boolean isMinimized(int hwnd) {
        return showCmd(hwnd) == com.sun.jna.platform.win32.WinUser.SW_SHOWMINIMIZED;
    }

    /** 窗口是否最大化（侧栏"贴边隐藏"的触发条件 ✓） */
    public static boolean isMaximized(int hwnd) {
        return showCmd(hwnd) == com.sun.jna.platform.win32.WinUser.SW_SHOWMAXIMIZED;
    }

    /** `GetWindowPlacement().showCmd`（取不到返回 -1） */
    private static int showCmd(int hwnd) {
        if (hwnd == 0) return -1;
        try {
            com.sun.jna.platform.win32.WinUser.WINDOWPLACEMENT wp =
                    new com.sun.jna.platform.win32.WinUser.WINDOWPLACEMENT();
            wp.length = wp.size();                    // 必须先填结构大小，否则 API 返回失败
            com.sun.jna.platform.win32.WinDef.BOOL ok =
                    com.sun.jna.platform.win32.User32.INSTANCE.GetWindowPlacement(intToHwnd(hwnd), wp);
            if (ok == null || !ok.booleanValue()) return -1;
            return wp.showCmd;
        } catch (Throwable t) {
            return -1;
        }
    }

    /** 当前前台窗口（0 = 无） */
    public static int getForegroundWindow() {
        try {
            return hwndToInt(com.sun.jna.platform.win32.User32.INSTANCE.GetForegroundWindow());
        } catch (Throwable t) {
            return 0;
        }
    }

    /**
     * **只还原、不置前**（`ShowWindow(SW_RESTORE)`）—— 把最大化/最小化的窗口变回普通态 ✓.
     *
     * <p>⚠️ 侧栏切窗必须用它（用户 2026-10-14："A 普通 → B 最大化"时 B 没缩回来 ✗）：
     * 直接对**最大化**窗口调 {@code SetWindowPos} 是**无效的** ✗ —— 它只改动"还原矩形"，
     * 窗口视觉上仍是最大化 ✓。必须**先真还原**、再摆位 ✓。
     */
    public static boolean restoreWindowOnly(int hwnd) {
        return showWindowCmd(hwnd, 9 /* SW_RESTORE */);
    }

    /** 让窗口**最大化**（窗口状态在账号间流转时用 ✓） */
    public static boolean maximizeWindow(int hwnd) {
        return showWindowCmd(hwnd, 3 /* SW_MAXIMIZE */);
    }

    /**
     * **只把窗口抬到最前**（不改位置、不改尺寸、不改状态）—— `SetWindowPos(HWND_TOP, SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW)`.
     *
     * <p>为什么需要（用户 2026-10-14：A 最大化 → B 普通时 B 上不来）：
     * `SetForegroundWindow` 常被 Windows 拒绝（后台进程不许抢焦点 ✗），
     * 而切到"该最大化"的目标时我们又**不摆位** ✓ → 整条链路上一次 `SetWindowPos` 都没有 ✗
     * → 目标被上面的最大化窗口压着、永远拿不到前台 ✓。
     * 这个方法就是补上"**纯粹的抬升**" ✓（对已最大化的窗口也安全 ✓ —— 不动它的几何 ✓）。
     */
    public static boolean raiseToTop(int hwnd) {
        if (hwnd == 0) return false;
        final int SWP_NOSIZE = 0x0001, SWP_NOMOVE = 0x0002, SWP_SHOWWINDOW = 0x0040;
        try {
            boolean ok = com.sun.jna.platform.win32.User32.INSTANCE.SetWindowPos(
                    intToHwnd(hwnd), intToHwnd(0) /* HWND_TOP */, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
            LOG.info("[窗口] 抬到最前 hwnd=0x{}（不动几何）= {}", Integer.toHexString(hwnd), ok);
            return ok;
        } catch (Throwable t) {
            LOG.warn("[窗口] raiseToTop 失败 hwnd={}: {}", hwnd, t.getMessage());
            return false;
        }
    }

    /**
     * **窗口"正常态"的矩形**（`GetWindowPlacement().rcNormalPosition`，物理像素 {l,t,r,b}）.
     *
     * <p>用户 2026-10-14 的关键指正 ✓：**窗口最大化时也要记住它的正常位置与尺寸** ——
     * 这样切窗时"上一个窗口的尺寸"才有意义 ✓（否则拿到的是最大化后的整屏尺寸 ✗，
     * 传给下一个窗口就变成"摆到最大化的位置和尺寸"而不是**真正最大化** ✗）。
     * <p>正好 Win32 就为这件事准备了 `rcNormalPosition` ✓：无论窗口当前是普通/最大化/最小化，
     * 它始终保存着"**还原后**的位置与尺寸" ✓。
     *
     * @return {left, top, right, bottom}；取不到返回 null
     */
    public static int[] getNormalRect(int hwnd) {
        if (hwnd == 0) return null;
        try {
            com.sun.jna.platform.win32.WinUser.WINDOWPLACEMENT wp =
                    new com.sun.jna.platform.win32.WinUser.WINDOWPLACEMENT();
            wp.length = wp.size();
            com.sun.jna.platform.win32.WinDef.BOOL ok =
                    com.sun.jna.platform.win32.User32.INSTANCE.GetWindowPlacement(intToHwnd(hwnd), wp);
            if (ok == null || !ok.booleanValue()) return null;
            com.sun.jna.platform.win32.WinDef.RECT r = wp.rcNormalPosition;
            return new int[]{r.left, r.top, r.right, r.bottom};
        } catch (Throwable t) {
            LOG.warn("[窗口] getNormalRect 失败 hwnd={}: {}", hwnd, t.getMessage());
            return null;
        }
    }

    /** `ShowWindow(hwnd, cmd)` 薄封装（SW_RESTORE=9 / SW_MAXIMIZE=3 / SW_SHOWNORMAL=1 ✓） */
    public static boolean showWindowCmd(int hwnd, int cmd) {
        if (hwnd == 0) return false;
        try {
            com.sun.jna.platform.win32.User32.INSTANCE.ShowWindow(intToHwnd(hwnd), cmd);
            LOG.info("[窗口] ShowWindow(hwnd=0x{}, cmd={})", Integer.toHexString(hwnd), cmd);
            return true;
        } catch (Throwable t) {
            LOG.warn("[窗口] ShowWindow 失败 hwnd={}, cmd={}: {}", hwnd, cmd, t.getMessage());
            return false;
        }
    }

    /**
     * **异步**版 `ShowWindow`（`ShowWindowAsync`）—— 不等待目标线程 ✓.
     * <p>用途（用户 2026-10-14 实测方向 ✓）：目标 UI 线程正忙/卡住时，
     * 同步的 `ShowWindow` 会把调用方一起拖住 ✓；托盘唤起的"温和三连"用它 ✓。
     */
    public static boolean showWindowCmdAsync(int hwnd, int cmd) {
        if (hwnd == 0) return false;
        try {
            boolean ok = User32Ext.INSTANCE.ShowWindowAsync(intToHwnd(hwnd), cmd);
            LOG.info("[窗口] ShowWindowAsync(hwnd=0x{}, cmd={}) = {}", Integer.toHexString(hwnd), cmd, ok);
            return ok;
        } catch (Throwable t) {
            LOG.warn("[窗口] ShowWindowAsync 失败 hwnd={}, cmd={}: {}", hwnd, cmd, t.getMessage());
            return false;
        }
    }

    /** 只**尝试**置前（失败是常态 ✓ 不抛、不记录为错误 ✓ —— 前台限制本来就常拒绝后台进程 ✓） */
    public static boolean tryForeground(int hwnd) {
        if (hwnd == 0) return false;
        try {
            return com.sun.jna.platform.win32.User32.INSTANCE.SetForegroundWindow(intToHwnd(hwnd));
        } catch (Throwable t) {
            return false;
        }
    }

    /**
     * **带尺寸**的窗口定位（{@code SetWindowPos}）—— 侧栏"切窗时把目标窗口摆到侧栏旁边"要用 ✓.
     *
     * @param top true = 同时抬到最前（HWND_TOP）；false = 不改 z 序
     */
    public static boolean setWindowRect(int hwnd, int x, int y, int w, int h, boolean top) {
        if (hwnd == 0) return false;
        final int SWP_NOZORDER = 0x0004, SWP_SHOWWINDOW = 0x0040;
        try {
            return com.sun.jna.platform.win32.User32.INSTANCE.SetWindowPos(
                    intToHwnd(hwnd),
                    top ? intToHwnd(0) /* HWND_TOP */ : null,
                    x, y, Math.max(1, w), Math.max(1, h),
                    top ? SWP_SHOWWINDOW : (SWP_NOZORDER | SWP_SHOWWINDOW));
        } catch (Throwable t) {
            LOG.warn("[窗口] setWindowRect 失败 hwnd={}: {}", hwnd, t.getMessage());
            return false;
        }
    }

    /** 去掉窗口的激活能力与任务栏存在感（侧栏用：点了不抢焦点、也不进 Alt-Tab） */
    public static void applyNoActivateToolWindow(int hwnd) {
        if (hwnd == 0) return;
        final int GWL_EXSTYLE = -20;
        final int WS_EX_NOACTIVATE = 0x08000000;
        final int WS_EX_TOOLWINDOW = 0x00000080;
        try {
            com.sun.jna.platform.win32.User32 u32 = com.sun.jna.platform.win32.User32.INSTANCE;
            int ex = u32.GetWindowLong(intToHwnd(hwnd), GWL_EXSTYLE);
            int want = ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW;
            if (want != ex) {
                u32.SetWindowLong(intToHwnd(hwnd), GWL_EXSTYLE, want);
                LOG.info("[侧栏] 已设置 WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW: hwnd=0x{}", Integer.toHexString(hwnd));
            }
        } catch (Throwable t) {
            LOG.warn("[侧栏] 设置窗口样式失败 hwnd={}: {}", hwnd, t.getMessage());
        }
    }

    /** 某进程的全部**顶层**可见窗口（侧栏用它认出"自己那个透明小窗"以便改样式 ✓） */
    public static java.util.List<Integer> listOwnTopLevelWindows(int pid) {
        java.util.List<Integer> out = new java.util.ArrayList<>();
        try {
            com.sun.jna.platform.win32.User32.INSTANCE.EnumWindows((hwnd, data) -> {
                com.sun.jna.ptr.IntByReference pidRef = new com.sun.jna.ptr.IntByReference();
                com.sun.jna.platform.win32.User32.INSTANCE.GetWindowThreadProcessId(hwnd, pidRef);
                if (pidRef.getValue() == pid) {
                    out.add(hwndToInt(hwnd));
                }
                return true;
            }, null);
        } catch (Throwable t) {
            LOG.warn("[侧栏] 枚举自身窗口失败: {}", t.getMessage());
        }
        return out;
    }

    /**
     * **窗口的"视觉边界"** `{left, top, right, bottom}`（物理像素）—— 侧栏贴边定位必须用它.
     *
     * <p>为什么不能直接用 {@code GetWindowRect}（用户 2026-10-13 侧栏需求的关键细节）：
     * Win10 起窗口的 `GetWindowRect` **包含那圈看不见的调整边框/阴影**（通常比视觉大 ~7px）✗ →
     * 直接贴边会**露出一条缝** ✗。DWM 的 {@code DWMWA_EXTENDED_FRAME_BOUNDS} 给的是**真实可见**边界 ✓；
     * 取不到（老系统/窗口不支持）再退回 {@code GetWindowRect} ✓。
     *
     * @return 长度 4 的数组；窗口无效返回 null
     */
    public static int[] getVisualRect(int hwnd) {
        if (hwnd == 0) return null;
        try {
            com.sun.jna.platform.win32.WinDef.HWND h = intToHwnd(hwnd);
            com.sun.jna.platform.win32.WinDef.RECT rect = new com.sun.jna.platform.win32.WinDef.RECT();
            int hr = DwmapiExt.INSTANCE.DwmGetWindowAttribute(h, DWMWA_EXTENDED_FRAME_BOUNDS, rect,
                    rect.size());
            if (hr != 0) {
                rect = new com.sun.jna.platform.win32.WinDef.RECT();
                if (!com.sun.jna.platform.win32.User32.INSTANCE.GetWindowRect(h, rect)) return null;
            }
            return new int[]{rect.left, rect.top, rect.right, rect.bottom};
        } catch (Throwable t) {
            try {
                com.sun.jna.platform.win32.WinDef.RECT rect = new com.sun.jna.platform.win32.WinDef.RECT();
                if (!com.sun.jna.platform.win32.User32.INSTANCE.GetWindowRect(intToHwnd(hwnd), rect)) return null;
                return new int[]{rect.left, rect.top, rect.right, rect.bottom};
            } catch (Throwable t2) {
                return null;
            }
        }
    }

    /**
     * **恢复并置前窗口**（点 HWND 打开窗口的核心动作）.
     * 对应 Python: {@code hwnd_utils.restore_window} = {@code ShowWindow(hwnd, SW_SHOWNORMAL)} + {@code SetForegroundWindow(hwnd)}.
     *
     * <p>补一步 {@code BringWindowToTop}：Windows 对 {@code SetForegroundWindow} 有前台权限限制，
     * 先抬到顶层能把"点了没反应"的概率压低（失败也不影响，返回 false 让上层如实报告）。
     */
    public static boolean restoreWindow(int hwnd) {
        if (hwnd == 0) return false;
        com.sun.jna.platform.win32.User32 u32 = com.sun.jna.platform.win32.User32.INSTANCE;
        try {
            final int SW_SHOWNORMAL = 1;
            u32.ShowWindow(intToHwnd(hwnd), SW_SHOWNORMAL);      // 最小化的窗口恢复出来
            u32.BringWindowToTop(intToHwnd(hwnd));
            boolean ok = u32.SetForegroundWindow(intToHwnd(hwnd));
            LOG.debug("[窗口] restoreWindow hwnd={}, SetForegroundWindow={}", hwnd, ok);
            return ok;
        } catch (Throwable t) {
            LOG.warn("[窗口] restoreWindow 失败 hwnd={}: {}", hwnd, t.getMessage());
            return false;
        }
    }

    /**
     * **恢复并激活窗口**（照旧版 {@code AccOperatorFuncCore.switch_to_sw_account_wnd}）.
     *
     * <p>微信特例：窗口**本来就不可见**（被藏到后台/托盘）时，单靠 ShowWindow 常常叫不出来 ——
     * 旧版的做法是"恢复窗口 → 等 0.2 秒 → 在窗口 (8,8) 处双击两下"把它激活；
     * 其它平台只要恢复置前即可。
     */
    public static boolean restoreWindowAndActivate(String sw, int hwnd) {
        if (hwnd == 0) return false;
        boolean visibleBefore = isWindowVisible(hwnd);
        boolean ok;
        // ⚠️ 修正（用户 2026-10-14 实测"从侧栏切回 A，A 却变回普通窗口"✗）：
        //    这里原来**无条件** `ShowWindow(SW_SHOWNORMAL)` ✗ —— 对**最大化**窗口等于"**还原**" ✓
        //    （MSDN：SW_SHOWNORMAL 会把最小化/最大化的窗口恢复为原始尺寸和位置 ✓）
        //    → 于是"切回 A"顺手把 A 的最大化抹掉了 ✗，也让"状态在账号间流转"永远失真 ✗。
        //    现在改为**保状态激活** ✓：只有**最小化**才还原 ✓；普通/最大化一律只**抬升 + 置前** ✓
        //    （切到"该最大化"的目标时，最大化由侧栏的状态趟显式做 ✓）。
        if (isMinimized(hwnd)) {
            ok = restoreWindowOnly(hwnd);                 // 最小化 → 必须还原出来 ✓
        } else {
            ok = raiseToTop(hwnd);                        // 普通/最大化 → 只抬升，**绝不改状态** ✓
        }
        boolean wechat = "WeChat".equals(sw) || "Weixin".equals(sw);
        if (wechat && !visibleBefore) {
            try {
                Thread.sleep(200);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return ok;
            }
            clickInWindow(hwnd, 8, 8);
            clickInWindow(hwnd, 8, 8);
            LOG.info("[窗口] 微信后台窗口 → 已双击标题区激活: hwnd={}", hwnd);
        }
        try {
            com.sun.jna.platform.win32.User32.INSTANCE.SetForegroundWindow(intToHwnd(hwnd));
        } catch (Throwable ignore) {
            // 置前失败不算失败：raiseToTop 已经把它抬到最前 ✓
        }
        return ok;
    }

    /**
     * **计算多个登录窗口在屏幕上的摆位**（纯函数，便于验证）.
     * 对应 Python: {@code hwnd_utils.layout_wnd_positions} —— 每行放得下几个就横排几个，
     * 行与行之间按 0.618 的错位量下移（旧版就是这个观感，用户 2026-10-07：就是为了好看）。
     *
     * @return 每个窗口的左上角 {x, y} 列表（长度 = wndCnt）
     */
    public static List<int[]> layoutWndPositions(int wndCnt, int wndW, int wndH, int screenW, int screenH) {
        List<int[]> positions = new ArrayList<>();
        if (wndCnt <= 0 || wndW <= 0 || wndH <= 0) return positions;
        int maxColumn = Math.max(1, screenW / wndW);
        int cntInRow = Math.min(wndCnt, maxColumn);
        int actualGap = Math.max(0, (screenW - cntInRow * wndW) / (cntInRow + 1));
        int allWidth = cntInRow * wndW + (cntInRow - 1) * actualGap;
        int startX = (screenW - allWidth) / 2;
        int startY = (screenH - wndH) / 2 - 25;
        for (int i = 0; i < wndCnt; i++) {
            positions.add(new int[]{
                    startX + (i % cntInRow) * (wndW + actualGap),
                    startY + (int) ((i / cntInRow - 0.618) * wndW)
            });
        }
        return positions;
    }

    /**
     * 取窗口详细信息.
     * 对应 Python: {@code hwnd_utils.get_hwnd_details_of_}（pid / class / title / left / top / width / height）
     */
    public static Map<String, Object> getHwndDetails(int hwnd) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("hwnd", hwnd);
        if (hwnd == 0) {
            details.put("width", 0);
            details.put("height", 0);
            return details;
        }
        WinDef.HWND h = intToHwnd(hwnd);
        com.sun.jna.platform.win32.User32 user32 = com.sun.jna.platform.win32.User32.INSTANCE;
        if (!user32.IsWindow(h)) {
            details.put("width", 0);
            details.put("height", 0);
            return details;
        }
        IntByReference pid = new IntByReference();
        user32.GetWindowThreadProcessId(h, pid);
        char[] cls = new char[WND_CLASS_MAX];
        user32.GetClassName(h, cls, WND_CLASS_MAX);
        char[] title = new char[512];
        user32.GetWindowText(h, title, 512);
        WinDef.RECT rect = new WinDef.RECT();
        user32.GetWindowRect(h, rect);
        details.put("pid", pid.getValue());
        details.put("class", Native.toString(cls));
        details.put("title", Native.toString(title));
        details.put("left", rect.left);
        details.put("top", rect.top);
        details.put("width", rect.right - rect.left);
        details.put("height", rect.bottom - rect.top);
        details.put("visible", user32.IsWindowVisible(h));
        return details;
    }

    /**
     * 尝试关闭一组窗口，返回**仍未关闭**的.
     * 对应 Python: {@code hwnd_utils.try_close_hwnds_in_set_and_return_remained}（PostMessage(WM_CLOSE)）
     */
    public static List<Integer> tryCloseHwndsAndReturnRemained(Set<Integer> hwnds) {
        List<Integer> remained = new ArrayList<>();
        if (hwnds == null || hwnds.isEmpty()) return remained;
        com.sun.jna.platform.win32.User32 user32 = com.sun.jna.platform.win32.User32.INSTANCE;
        for (Integer hwnd : hwnds) {
            if (hwnd != null && hwnd != 0) {
                user32.PostMessage(intToHwnd(hwnd), com.sun.jna.platform.win32.WinUser.WM_CLOSE,
                        new WinDef.WPARAM(0), new WinDef.LPARAM(0));
            }
        }
        waitHwndsClose(new ArrayList<>(hwnds), 5);
        for (Integer hwnd : hwnds) {
            if (hwnd != null && hwnd != 0 && user32.IsWindow(intToHwnd(hwnd))) remained.add(hwnd);
        }
        LOG.info("[窗口] 关闭窗口：尝试 {} 个，仍未关闭 {} 个", hwnds.size(), remained.size());
        return remained;
    }

    /**
     * 等待所有窗口关闭
     * 对应 Python: {@code hwnd_utils.wait_hwnds_close}
     */
    public static boolean waitHwndsClose(List<Integer> hwnds, int timeout) {
        if (hwnds == null || hwnds.isEmpty()) return true;
        com.sun.jna.platform.win32.User32 user32 = com.sun.jna.platform.win32.User32.INSTANCE;
        long deadline = System.currentTimeMillis() + Math.max(0, timeout) * 1000L;
        long waitStart = System.currentTimeMillis();
        while (System.currentTimeMillis() < deadline) {
            // 取消检查点（任务中心）：等窗口关闭期间也能被取消
            com.jfmultichat.core.task.TaskContext.checkpoint();
            long waited = System.currentTimeMillis() - waitStart;
            if (waited >= 1000) {
                com.jfmultichat.core.task.TaskContext.phaseSuffix("（等关闭 " + (waited / 1000) + "s）");
            }
            boolean allClosed = true;
            for (Integer hwnd : hwnds) {
                if (hwnd != null && hwnd != 0 && user32.IsWindow(intToHwnd(hwnd))) {
                    allClosed = false;
                    break;
                }
            }
            if (allClosed) return true;
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }

    // ==================== 进程操作 ====================

    /**
     * 移除子进程 PID（只保留根进程）
     * 对应 Python: process_utils.remove_child_pids
     */
    /**
     * 从 pids 中剔除**所有子进程**（含递归后代）.
     * 对应 Python: `process_utils.remove_child_pids`（那里用 `psutil.Process(pid).children(recursive=True)`）.
     *
     * <p>实现：只取**一次** Toolhelp32 进程快照，建"父 PID → 子 PID 列表"，再对给定 PID 做 BFS 展开所有后代；
     * 比"逐个 pid 查子进程"快得多，也避免快照期间进程变化导致的不一致。返回时**保持输入顺序**（与 Python 一致）。
     *
     * <p>为什么必须过滤：一个账号可能同时有主进程和辅助/子进程，它们映射同一份账号数据文件 →
     * 不过滤的话子进程的 PID 会抢先认领账号，界面上的 PID 就不是主进程了。
     */
    public static List<Integer> removeChildPids(List<Integer> pids) {
        if (pids == null || pids.isEmpty()) return new ArrayList<>();
        Map<Integer, List<Integer>> children = new HashMap<>();
        Tlhelp32.PROCESSENTRY32.ByReference pe32 = new Tlhelp32.PROCESSENTRY32.ByReference();
        HANDLE hSnapshot = Kernel32.INSTANCE.CreateToolhelp32Snapshot(
                Tlhelp32.TH32CS_SNAPPROCESS, new WinDef.DWORD(0));
        try {
            if (Kernel32.INSTANCE.Process32First(hSnapshot, pe32)) {
                do {
                    int pid = pe32.th32ProcessID.intValue();
                    int ppid = pe32.th32ParentProcessID.intValue();
                    if (pid > 0) children.computeIfAbsent(ppid, k -> new ArrayList<>()).add(pid);
                } while (Kernel32.INSTANCE.Process32Next(hSnapshot, pe32));
            }
        } finally {
            Kernel32.INSTANCE.CloseHandle(hSnapshot);
        }
        Set<Integer> removed = new HashSet<>();
        Deque<Integer> queue = new ArrayDeque<>(pids);
        while (!queue.isEmpty()) {
            List<Integer> kids = children.get(queue.poll());
            if (kids == null) continue;
            for (Integer kid : kids) {
                if (removed.add(kid)) queue.add(kid);      // 已进过队列的不再重复展开（防环）
            }
        }
        List<Integer> kept = new ArrayList<>();
        for (Integer pid : pids) if (!removed.contains(pid)) kept.add(pid);
        LOG.debug("[JNA] removeChildPids: {} → {} pids", pids.size(), kept.size());
        return kept;
    }

    /**
     * 移除不在指定路径下的进程 PID.
     * 对应 Python: `process_utils.remove_pids_not_in_path`（`path_keyword in proc.exe().lower()`）.
     *
     * <p>路径统一成"正斜杠 + 小写"比较（{@link #getProcessImagePath(int)} 返回的就是正斜杠形式）；
     * 取不到可执行路径的进程（无权限/已退出）按 Python 的语义**排除**；关键词为空则全部保留。
     */
    public static List<Integer> removePidsNotInPath(List<Integer> pids, String pathKeyword) {
        List<Integer> kept = new ArrayList<>();
        if (pids == null || pids.isEmpty()) return kept;
        if (pathKeyword == null || pathKeyword.isBlank()) return new ArrayList<>(pids);
        String needle = pathKeyword.replace('\\', '/').toLowerCase();
        for (Integer pid : pids) {
            String exe = INSTANCE.getProcessImagePath(pid);
            if (exe == null || exe.isEmpty()) continue;
            if (exe.replace('\\', '/').toLowerCase().contains(needle)) kept.add(pid);
        }
        LOG.debug("[JNA] removePidsNotInPath: {} → {} pids, keyword={}", pids.size(), kept.size(), needle);
        return kept;
    }

    // ==================== 降权启动（用 Explorer 的令牌） ====================

    /** user32：拿 shell 窗口 → 它的进程就是 explorer（普通权限） */
    private interface User32Ext extends com.sun.jna.Library {
        User32Ext INSTANCE = Native.load("user32", User32Ext.class);

        WinNT.HANDLE GetShellWindow();

        int GetWindowThreadProcessId(WinNT.HANDLE hWnd, IntByReference pid);

        /**
         * 改窗口标题（JNA 的 `User32` 只暴露了 GetWindowText ✗，没有 SetWindowText）。
         * 用 Unicode 版；跨进程 WM_SETTEXT 由系统负责编组，传我们自己的字符串是安全的。
         */
        boolean SetWindowTextW(com.sun.jna.platform.win32.WinDef.HWND hWnd, com.sun.jna.WString lpString);

        /** JNA 自带的 `User32` **没有**暴露 `ShowWindowAsync` ✗ → 这里自己声明 ✓（托盘唤起的温和三连要用 ✓） */
        boolean ShowWindowAsync(com.sun.jna.platform.win32.WinDef.HWND hWnd, int nCmdShow);
    }

    /** advapi32：拿 explorer 的令牌 → 复制一份 → 用它创建进程 */
    private interface Advapi32Ext extends com.sun.jna.Library {
        Advapi32Ext INSTANCE = Native.load("advapi32", Advapi32Ext.class);

        boolean OpenProcessToken(WinNT.HANDLE process, int desiredAccess, WinNT.HANDLEByReference token);

        boolean GetTokenInformation(WinNT.HANDLE token, int informationClass, Pointer buffer,
                                    int bufferLength, IntByReference returnLength);

        boolean DuplicateTokenEx(WinNT.HANDLE existingToken, int desiredAccess,
                                 WinBase.SECURITY_ATTRIBUTES attrs, int impersonationLevel, int tokenType,
                                 WinNT.HANDLEByReference newToken);

        boolean CreateProcessWithTokenW(WinNT.HANDLE token, int logonFlags, com.sun.jna.WString applicationName,
                                        com.sun.jna.WString commandLine, int creationFlags,
                                        com.sun.jna.Pointer environment, com.sun.jna.WString currentDirectory,
                                        WinBase.STARTUPINFO startupInfo, WinBase.PROCESS_INFORMATION processInfo);
    }

    private static final int PROCESS_QUERY_INFORMATION = 0x0400;
    private static final int TOKEN_QUERY = 0x0008;
    private static final int TOKEN_DUPLICATE = 0x0002;
    private static final int TOKEN_ALL_ACCESS = 0x000F01FF;
    private static final int TOKEN_ELEVATION_CLASS = 20;      // TOKEN_INFORMATION_CLASS.TokenElevation
    private static final int SECURITY_IMPERSONATION = 2;      // SECURITY_IMPERSONATION_LEVEL
    private static final int TOKEN_PRIMARY = 1;               // TOKEN_TYPE

    /** 本进程是否**以管理员身份**运行（结果缓存，进程内不会变） */
    private static Boolean currentProcessElevated = null;

    public static boolean isCurrentProcessElevated() {
        if (currentProcessElevated != null) return currentProcessElevated;
        boolean elevated = false;
        WinNT.HANDLEByReference tokenRef = new WinNT.HANDLEByReference();
        try {
            if (Advapi32Ext.INSTANCE.OpenProcessToken(Kernel32.INSTANCE.GetCurrentProcess(),
                    TOKEN_QUERY, tokenRef)) {
                WinNT.HANDLE token = tokenRef.getValue();
                Memory buf = new Memory(4);                 // TOKEN_ELEVATION { DWORD TokenIsElevated; }
                IntByReference ret = new IntByReference();
                if (Advapi32Ext.INSTANCE.GetTokenInformation(token, TOKEN_ELEVATION_CLASS, buf, 4, ret)) {
                    elevated = buf.getInt(0) != 0;
                }
                Kernel32.INSTANCE.CloseHandle(token);
            }
        } catch (Throwable t) {
            LOG.debug("[降权] 判断自身是否管理员失败: {}", t.getMessage());
        }
        currentProcessElevated = elevated;
        LOG.info("[降权] 本进程是否管理员: {}", elevated);
        return elevated;
    }

    /** 直接创建进程（不换令牌）—— 本进程不是管理员时用，子进程自然就是普通用户 */
    private static int startProcessPlain(String exePath, String args, int creationFlags) {
        WinBase.STARTUPINFO si = new WinBase.STARTUPINFO();
        si.cb = new WinDef.DWORD(si.size());
        WinBase.PROCESS_INFORMATION pi = new WinBase.PROCESS_INFORMATION();
        String cmdLine = (args == null || args.isBlank())
                ? "\"" + exePath + "\""
                : "\"" + exePath + "\" " + args;
        boolean ok = Kernel32.INSTANCE.CreateProcess(exePath, cmdLine, null, null, false,
                new WinDef.DWORD(creationFlags), null, null, si, pi);
        if (!ok) {
            int err = Native.getLastError();
            LOG.warn("[启动] CreateProcess 失败: exe={}, err={} ({})", exePath, err, describeWin32Error(err));
            return 0;
        }
        int pid = pi.dwProcessId.intValue();
        Kernel32.INSTANCE.CloseHandle(pi.hProcess);
        Kernel32.INSTANCE.CloseHandle(pi.hThread);
        return pid;
    }

    /** 兜底：让 **explorer.exe 代启**（explorer 是普通权限，它启动的程序自然也是普通权限） */
    private static int startViaExplorer(String exePath) {
        try {
            Process p = new ProcessBuilder("explorer.exe", exePath).start();
            LOG.info("[降权] 已改为经 explorer.exe 代启: {} (explorer pid={})", exePath, p.pid());
            return -1;                                  // -1 = 已启动但拿不到目标进程 PID（父进程是 explorer）
        } catch (Exception e) {
            LOG.warn("[降权] explorer 代启也失败: {}", e.getMessage());
            return 0;
        }
    }

    /**
     * **降权启动**：保证目标程序以**普通用户身份**运行.
     *
     * <p>分三种情况（用户 2026-10-07 实测遇到 err=1314 后定稿）：
     * <ol>
     *   <li><b>本进程本来就是普通权限</b>（非管理员）→ **直接启动即可**：子进程继承我们的中完整性令牌，天然就是普通用户。
     *       此时<b>不能</b>去用 explorer 令牌 —— `CreateProcessWithTokenW` 需要 `SeImpersonatePrivilege`，
     *       而普通权限进程没有该特权 → 直接 `ERROR_PRIVILEGE_NOT_HELD(1314)`</li>
     *   <li><b>本进程是管理员</b> → 借用 explorer 的令牌（`GetShellWindow` → explorer PID →
     *       `OpenProcessToken` → `DuplicateTokenEx` → `CreateProcessWithTokenW`）→ 子进程是中完整性</li>
     *   <li>令牌法失败（比如特权被策略禁用）→ 兜底用 **`explorer.exe 代启`**，同样得到普通权限子进程</li>
     * </ol>
     *
     * @return 子进程 PID；{@code -1} = 已启动但 PID 未知（explorer 代启）；{@code 0} = 失败
     */
    public static int createProcessWithoutAdmin(String executable, String args, int creationFlags) {
        // 路径分隔符统一成反斜杠：本项目内部路径都规范化成 `/`，而 CreateProcess* 对 `lpApplicationName`
        // 里的正斜杠并不可靠（实测直接失败）→ 这里转回 Windows 原生形式
        String exePath = executable == null ? null : executable.replace('/', '\\');
        if (exePath == null || exePath.isBlank()) return 0;

        if (!isCurrentProcessElevated()) {
            int pid = startProcessPlain(exePath, args, creationFlags);
            if (pid > 0) LOG.info("[启动] 本进程非管理员，直接启动（子进程同为普通权限）: {} → pid={}", exePath, pid);
            return pid;
        }

        WinNT.HANDLE explorer = null, token = null, primary = null;
        int lastErr = 0;
        try {
            WinNT.HANDLE shellWnd = User32Ext.INSTANCE.GetShellWindow();
            if (shellWnd == null) {
                lastErr = Native.getLastError();
                LOG.warn("[降权] GetShellWindow 失败, err={}", lastErr);
                return startViaExplorer(exePath);
            }
            IntByReference explorerPid = new IntByReference();
            User32Ext.INSTANCE.GetWindowThreadProcessId(shellWnd, explorerPid);
            if (explorerPid.getValue() <= 0) {
                LOG.warn("[降权] 取 explorer PID 失败");
                return startViaExplorer(exePath);
            }
            explorer = Kernel32.INSTANCE.OpenProcess(PROCESS_QUERY_INFORMATION, false, explorerPid.getValue());
            if (explorer == null) {
                lastErr = Native.getLastError();
                LOG.warn("[降权] 打开 explorer 进程失败, pid={}, err={}", explorerPid.getValue(), lastErr);
                return startViaExplorer(exePath);
            }
            WinNT.HANDLEByReference tokenRef = new WinNT.HANDLEByReference();
            if (!Advapi32Ext.INSTANCE.OpenProcessToken(explorer, TOKEN_DUPLICATE, tokenRef)) {
                lastErr = Native.getLastError();
                LOG.warn("[降权] OpenProcessToken 失败, err={}", lastErr);
                return startViaExplorer(exePath);
            }
            token = tokenRef.getValue();
            WinNT.HANDLEByReference primaryRef = new WinNT.HANDLEByReference();
            if (!Advapi32Ext.INSTANCE.DuplicateTokenEx(token, TOKEN_ALL_ACCESS, null,
                    SECURITY_IMPERSONATION, TOKEN_PRIMARY, primaryRef)) {
                lastErr = Native.getLastError();
                LOG.warn("[降权] DuplicateTokenEx 失败, err={}", lastErr);
                return startViaExplorer(exePath);
            }
            primary = primaryRef.getValue();

            WinBase.STARTUPINFO si = new WinBase.STARTUPINFO();
            si.cb = new WinDef.DWORD(si.size());
            WinBase.PROCESS_INFORMATION pi = new WinBase.PROCESS_INFORMATION();
            String cmdLine = (args == null || args.isBlank())
                    ? "\"" + exePath + "\""
                    : "\"" + exePath + "\" " + args;
            boolean ok = Advapi32Ext.INSTANCE.CreateProcessWithTokenW(primary, 0,
                    new com.sun.jna.WString(exePath), new com.sun.jna.WString(cmdLine),
                    creationFlags, null, null, si, pi);
            if (!ok) {
                lastErr = Native.getLastError();
                LOG.warn("[降权] CreateProcessWithTokenW 失败: exe={}, err={} ({}), 改用 explorer 代启",
                        exePath, lastErr, describeWin32Error(lastErr));
                return startViaExplorer(exePath);
            }
            int pid = pi.dwProcessId.intValue();
            Kernel32.INSTANCE.CloseHandle(pi.hProcess);
            Kernel32.INSTANCE.CloseHandle(pi.hThread);
            LOG.info("[降权] 已以普通权限启动: {} → pid={}", exePath, pid);
            return pid;
        } catch (Throwable t) {
            LOG.warn("[降权] 启动异常: {}，改用 explorer 代启", t.getMessage());
            return startViaExplorer(exePath);
        } finally {
            if (primary != null) Kernel32.INSTANCE.CloseHandle(primary);
            if (token != null) Kernel32.INSTANCE.CloseHandle(token);
            if (explorer != null) Kernel32.INSTANCE.CloseHandle(explorer);
        }
    }

    /** Win32 错误码 → 人话（诊断降权启动失败用；只列常见的几个） */
    private static String describeWin32Error(int err) {
        switch (err) {
            case 2: return "ERROR_FILE_NOT_FOUND 找不到文件（路径不对？）";
            case 3: return "ERROR_PATH_NOT_FOUND 路径不存在";
            case 5: return "ERROR_ACCESS_DENIED 拒绝访问";
            case 87: return "ERROR_INVALID_PARAMETER 参数无效（STARTUPINFO.cb / 命令行格式？）";
            case 740: return "ERROR_ELEVATION_REQUIRED 需要提升（令牌是受限令牌？）";
            case 1200: return "ERROR_BAD_ENVIRONMENT 环境块无效";
            case 1314: return "ERROR_PRIVILEGE_NOT_HELD 缺少 SeImpersonatePrivilege";
            case 1326: return "ERROR_LOGON_FAILURE 用户名或密码错误";
            default: return "见 Win32 错误码表";
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
