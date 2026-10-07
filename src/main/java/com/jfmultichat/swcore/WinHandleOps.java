package com.jfmultichat.swcore;

import com.sun.jna.Library;
import com.sun.jna.Memory;
import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.ptr.IntByReference;
import com.sun.jna.ptr.PointerByReference;
import com.sun.jna.platform.win32.WinNT.HANDLE;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;

/**
 * Windows 句柄操作（互斥体查杀的核心）—— 纯 JNA 实现，**不依赖外部 handle.exe**.
 *
 * <p>对应 Python: `legacy_python/utils/handle_utils.py` 里那套 `pywinhandle_*`：
 * <ol>
 *   <li>{@code NtQuerySystemInformation(SystemExtendedHandleInformation)} 枚举**系统全部句柄**
 *       （每条含：对象指针、所属进程 PID、句柄值）</li>
 *   <li>只挑**目标 PID** 的句柄 → {@code OpenProcess(PROCESS_DUP_HANDLE)} 后
 *       {@code DuplicateHandle(DUPLICATE_SAME_ACCESS)} 复制一个到本进程，再用
 *       {@code NtQueryObject} 问出它的**名字**与**类型**，然后关掉这个本地副本</li>
 *   <li>名字按通配词匹配（`?` 单字符 / `*` 任意；Python 的规则是
 *       {@code fnmatch(name, wc) || fnmatch(name, "*"+wc+"*")}，这里照搬 —— 因为真实互斥体名带
 *       {@code \Sessions\1\BaseNamedObjects\} 前缀，必须允许"包含匹配"）</li>
 *   <li>关闭：{@code DuplicateHandle(源进程, 句柄, NULL, NULL, 0, false, DUPLICATE_CLOSE_SOURCE)} ——
 *       "复制到空目标 + 关闭源句柄"= **直接在目标进程里把该句柄关掉**（这是关别人进程句柄的标准技巧）</li>
 * </ol>
 *
 * <p>注意两点：<b>必须先全部找完再统一关闭</b>（关闭会让后续枚举的句柄失效）；枚举/复制别人的句柄需要
 * 权限（本程序是管理员时没问题，普通权限遇到更高完整性的进程会失败——跳过即可，不影响其它句柄）。
 */
public final class WinHandleOps {

    private static final Logger LOG = LoggerFactory.getLogger(WinHandleOps.class);

    private WinHandleOps() {}

    // ==================== JNA 声明 ====================

    private interface NtdllLib extends Library {
        NtdllLib INSTANCE = Native.load("ntdll", NtdllLib.class);

        int NtQuerySystemInformation(int systemInformationClass, Pointer buffer, int bufferLength,
                                     IntByReference returnLength);

        int NtQueryObject(HANDLE handle, int objectInformationClass, Pointer buffer, int bufferLength,
                          IntByReference returnLength);
    }

    /** 只声明用得上的几个 kernel32 函数（自成一体，避免和 jna-platform 的同名声明打架） */
    private interface Kernel32Lib extends Library {
        Kernel32Lib INSTANCE = Native.load("kernel32", Kernel32Lib.class);

        HANDLE OpenProcess(int desiredAccess, boolean inheritHandle, int processId);

        HANDLE GetCurrentProcess();

        boolean CloseHandle(HANDLE handle);

        boolean DuplicateHandle(HANDLE sourceProcess, HANDLE sourceHandle, HANDLE targetProcess,
                                PointerByReference targetHandle, int desiredAccess, boolean inheritHandle,
                                int options);
    }

    private static final int SYSTEM_EXTENDED_HANDLE_INFORMATION = 64;
    private static final int STATUS_INFO_LENGTH_MISMATCH = 0xC0000004;
    private static final int OBJECT_BASIC_INFORMATION = 0;
    private static final int OBJECT_NAME_INFORMATION = 1;
    private static final int OBJECT_TYPE_INFORMATION = 2;
    private static final int PROCESS_DUP_HANDLE = 0x0040;
    private static final int DUPLICATE_SAME_ACCESS = 0x00000002;
    private static final int DUPLICATE_CLOSE_SOURCE = 0x00000001;
    /** x64：SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX = 8+8+8+4+2+2+4+4 = 40 字节（x86 是 28） */
    private static final int ENTRY_SIZE = Native.POINTER_SIZE == 8 ? 40 : 28;
    private static final int HANDLE_TABLE_HEADER_SIZE = 16;

    /** 一个命中的句柄 */
    public static final class HandleRef {
        public final int pid;
        public final long handle;
        public final String name;
        public final String type;

        HandleRef(int pid, long handle, String name, String type) {
            this.pid = pid;
            this.handle = handle;
            this.name = name;
            this.type = type;
        }

        @Override
        public String toString() {
            return "pid=" + pid + " handle=0x" + Long.toHexString(handle) + " type=" + type + " name=" + name;
        }
    }

    /**
     * **已经查杀过互斥体的 PID 缓存（全局共享）**：pid → 查杀时刻.
     *
     * <p>为什么需要（用户 2026-10-07 提的方案）：批量多开时，随着已打开实例增多，枚举到的同平台
     * PID 也越来越多，每个 PID 都要复制句柄 + 查名字（`NtQueryObject`）→ 时间线性膨胀。
     * 而**一个 PID 的互斥体被关掉后基本不会再出现**，所以下一次枚举时可以整段跳过这些 PID。
     *
     * <p>为什么带 TTL（10 秒）而不是永久：万一某个程序之后又**重建**了互斥体（不常见），
     * 永久跳过就会漏杀 → 表现为"点了登录却没开新窗口"。10 秒足够覆盖一次批量多开的循环，
     * 又不会把陈旧结论一直用下去。TTL 内命中缓存的 PID 直接跳过，不进句柄枚举。
     */
    private static final long KILLED_TTL_MS = 10_000;
    private static final Map<Integer, Long> KILLED_PID_AT = new java.util.concurrent.ConcurrentHashMap<>();

    /** 清空"已查杀 PID"缓存（探针/排查用；正常流程不需要） */
    public static void clearKilledPidCache() {
        KILLED_PID_AT.clear();
    }

    /** 缓存里仍然"有效"的已查杀 PID 数（日志/排查用） */
    public static int killedPidCacheSize() {
        long now = System.currentTimeMillis();
        KILLED_PID_AT.entrySet().removeIf(e -> now - e.getValue() > KILLED_TTL_MS);
        return KILLED_PID_AT.size();
    }

    // ==================== 对外入口 ====================

    /**
     * 查找指定进程里**句柄名匹配任一通配词**的句柄（只查不关）.
     *
     * @param pids          目标进程 PID（空集合 = 不限制进程）
     * @param nameWildcards 句柄名通配词；空 = 不按名字过滤（会返回该进程全部带名字的句柄）
     */
    public static List<HandleRef> findHandles(Collection<Integer> pids, List<String> nameWildcards) {
        List<HandleRef> result = new ArrayList<>();
        // ⚠️ 显式给了**空列表** = 没有目标进程 → 直接返回。
        //    （踩过：以前把它和 null 一样当成"不限制进程"，于是去扫全部 30 万个句柄 → 卡死几分钟）
        if (pids != null && pids.isEmpty()) return result;
        Pointer table = querySystemHandleTable();
        if (table == null) {
            LOG.warn("[句柄] NtQuerySystemInformation 失败，无法枚举系统句柄");
            return result;
        }
        long count = table.getLong(0);
        Set<Integer> pidFilter = (pids == null) ? null : new HashSet<>(pids);
        boolean filterByName = nameWildcards != null && !nameWildcards.isEmpty();

        // 进程句柄缓存：同一个 pid 只开一次
        Map<Integer, HANDLE> procHandles = new HashMap<>();
        int scanned = 0, candidates = 0;
        try {
            for (long i = 0; i < count; i++) {
                long off = HANDLE_TABLE_HEADER_SIZE + i * ENTRY_SIZE;
                int pid = (int) table.getLong(off + 8);
                long handleValue = table.getLong(off + 16);
                if (handleValue == 0) continue;
                if (pidFilter != null && !pidFilter.contains(pid)) continue;
                candidates++;
                scanned++;
                HANDLE proc = procHandles.get(pid);
                if (proc == null) {
                    proc = Kernel32Lib.INSTANCE.OpenProcess(PROCESS_DUP_HANDLE, false, pid);
                    procHandles.put(pid, proc);
                }
                if (proc == null) continue;
                String[] nt = queryNameAndType(proc, handleValue);
                if (nt == null || nt[0] == null) continue;
                if (filterByName && !matchAny(nt[0], nameWildcards)) continue;
                result.add(new HandleRef(pid, handleValue, nt[0], nt[1]));
            }
        } finally {
            for (HANDLE p : procHandles.values()) {
                if (p != null) Kernel32Lib.INSTANCE.CloseHandle(p);
            }
        }
        LOG.info("[句柄] 扫描 {} 条（目标进程候选 {} 条），命中 {} 条", count, candidates, result.size());
        return result;
    }

    /**
     * 关闭一批句柄（"复制到空目标 + DUPLICATE_CLOSE_SOURCE"= 在目标进程里关掉它）.
     *
     * @return 成功关闭的数量
     */
    public static int closeHandles(List<HandleRef> handles) {
        if (handles == null || handles.isEmpty()) return 0;
        Map<Integer, HANDLE> procHandles = new HashMap<>();
        int closed = 0;
        try {
            for (HandleRef h : handles) {
                HANDLE proc = procHandles.get(h.pid);
                if (proc == null && !procHandles.containsKey(h.pid)) {
                    proc = Kernel32Lib.INSTANCE.OpenProcess(PROCESS_DUP_HANDLE, false, h.pid);
                    procHandles.put(h.pid, proc);
                }
                if (proc == null) continue;
                boolean ok = Kernel32Lib.INSTANCE.DuplicateHandle(
                        proc, new HANDLE(Pointer.createConstant(h.handle)), null, null,
                        0, false, DUPLICATE_CLOSE_SOURCE);
                if (ok) {
                    closed++;
                } else {
                    LOG.debug("[句柄] 关闭失败: {}", h);
                }
            }
        } finally {
            for (HANDLE p : procHandles.values()) {
                if (p != null) Kernel32Lib.INSTANCE.CloseHandle(p);
            }
        }
        LOG.info("[句柄] 关闭成功 {}/{}", closed, handles.size());
        return closed;
    }

    /**
     * 一步到位：找 + 关（先全部找完再关，避免关闭后枚举失效）.
     *
     * <p>带**"已查杀 PID"缓存**（见 {@link #KILLED_PID_AT}）：批量多开时，前面几轮已经清干净的 PID
     * 直接从候选里剔除，不再进句柄枚举 —— 这是批量启动耗时随实例数增长的主要优化点。
     * 关闭成功后会把这些 PID 记进缓存（TTL 内下次跳过）。
     *
     * @return 成功关闭的数量
     */
    public static int killHandlesByName(Collection<Integer> pids, List<String> nameWildcards) {
        if (pids == null || pids.isEmpty()) return 0;
        long now = System.currentTimeMillis();
        List<Integer> candidates = new ArrayList<>();
        int skipped = 0;
        for (Integer pid : pids) {
            if (pid == null) continue;
            Long at = KILLED_PID_AT.get(pid);
            if (at != null && now - at <= KILLED_TTL_MS) {
                skipped++;
                continue;                       // 刚查杀过 → 跳过句柄枚举
            }
            candidates.add(pid);
        }
        if (skipped > 0) {
            LOG.info("[句柄] 跳过 {} 个刚查杀过的 pid（缓存命中），本次只扫 {} 个", skipped, candidates.size());
        }
        if (candidates.isEmpty()) return 0;          // 全都刚查杀过 → 无需扫描
        List<HandleRef> found = findHandles(candidates, nameWildcards);
        for (HandleRef h : found) LOG.info("[句柄] 命中互斥体: {}", h);
        int closed = closeHandles(found);
        // 记录"本进程里确实关掉过句柄"的 PID：它们此刻已不含这些互斥体
        Set<Integer> cleaned = new HashSet<>();
        for (HandleRef h : found) cleaned.add(h.pid);
        long stamp = System.currentTimeMillis();
        for (Integer pid : cleaned) KILLED_PID_AT.put(pid, stamp);
        return closed;
    }

    /** 判断某 pid 是否在"刚查杀过"的缓存里（排查用） */
    public static boolean isRecentlyCleaned(int pid) {
        Long at = KILLED_PID_AT.get(pid);
        return at != null && System.currentTimeMillis() - at <= KILLED_TTL_MS;
    }

    // ==================== 内部实现 ====================

    /** 枚举系统句柄表（缓冲不够时按返回长度扩张重试） */
    private static Pointer querySystemHandleTable() {
        int len = 1 << 20;                       // 1MB 起步（Python 直接 16MB，没必要）
        IntByReference ret = new IntByReference();
        for (int attempt = 0; attempt < 10; attempt++) {
            Memory buf = new Memory(len);
            int status = NtdllLib.INSTANCE.NtQuerySystemInformation(
                    SYSTEM_EXTENDED_HANDLE_INFORMATION, buf, len, ret);
            if (status == 0) return buf;
            if (status == STATUS_INFO_LENGTH_MISMATCH) {
                len = Math.max(len * 4, ret.getValue() + 0x10000);
                continue;
            }
            LOG.warn("[句柄] NtQuerySystemInformation 返回 0x{}", Integer.toHexString(status));
            return null;
        }
        return null;
    }

    /**
     * 复制目标句柄到本进程 → 问出名字与类型 → 关掉副本.
     *
     * @return {@code [name, type]}；失败返回 null
     */
    private static String[] queryNameAndType(HANDLE proc, long handleValue) {
        PointerByReference dupRef = new PointerByReference();
        // ⚠️ 目标进程必须是**当前进程**（DUPLICATE_SAME_ACCESS 要求有目标；传 null 会直接失败）
        boolean ok = Kernel32Lib.INSTANCE.DuplicateHandle(
                proc, new HANDLE(Pointer.createConstant(handleValue)), Kernel32Lib.INSTANCE.GetCurrentProcess(),
                dupRef, 0, false, DUPLICATE_SAME_ACCESS);
        if (!ok || dupRef.getValue() == null) return null;
        HANDLE dup = new HANDLE(dupRef.getValue());
        try {
            String name = queryUnicodeStringObject(dup, OBJECT_NAME_INFORMATION);
            String type = queryUnicodeStringObject(dup, OBJECT_TYPE_INFORMATION);
            return new String[]{name, type};
        } finally {
            Kernel32Lib.INSTANCE.CloseHandle(dup);
        }
    }

    /**
     * 取 OBJECT_NAME_INFORMATION / OBJECT_TYPE_INFORMATION 里的 UNICODE_STRING（x64：Length@0, Buffer@8）.
     *
     * <p>⚠️ 这里**故意不用 `ObjectBasicInformation` 预探大小**：那条路在本机恒返回
     * {@code STATUS_INFO_LENGTH_MISMATCH}，一旦据此提前 return，就会把**每个**句柄都当失败跳过
     * （实测表现：扫了 30 万条句柄、命中 0 条）。改为直接给足缓冲、只在真的长度不匹配时按返回长度扩容重试。
     */
    private static String queryUnicodeStringObject(HANDLE dup, int infoClass) {
        int size = (infoClass == OBJECT_NAME_INFORMATION) ? 0x2000 : 0x400;
        for (int attempt = 0; attempt < 4; attempt++) {
            Memory buf = new Memory(size);
            IntByReference ret = new IntByReference();
            int status = NtdllLib.INSTANCE.NtQueryObject(dup, infoClass, buf, size, ret);
            if (status == STATUS_INFO_LENGTH_MISMATCH) {
                size = Math.max(size * 4, ret.getValue() + 0x40);
                continue;
            }
            if (status != 0) return null;
            int length = buf.getShort(0) & 0xFFFF;             // 字节数
            if (length <= 0) return null;
            Pointer strPtr = buf.getPointer(8);
            if (strPtr == null) return null;
            String s = strPtr.getWideString(0);
            if (s == null) return null;
            int chars = length / 2;
            return s.length() > chars ? s.substring(0, chars) : s;
        }
        return null;
    }

    /** 通配匹配：对齐 Python `fnmatch(name, wc) || fnmatch(name, "*"+wc+"*")`（Windows 上大小写不敏感） */
    public static boolean matchAny(String name, List<String> wildcards) {
        if (name == null) return false;
        String lower = name.toLowerCase(Locale.ROOT);
        for (String wc : wildcards) {
            if (wc == null || wc.isEmpty()) continue;
            String w = wc.toLowerCase(Locale.ROOT);
            if (globMatch(lower, w) || globMatch(lower, "*" + w + "*")) return true;
        }
        return false;
    }

    /** 支持 `?`（单字符）与 `*`（任意串）的通配匹配（迭代实现，避免回溯爆炸） */
    static boolean globMatch(String text, String pattern) {
        int ti = 0, pi = 0, star = -1, match = 0;
        while (ti < text.length()) {
            if (pi < pattern.length() && (pattern.charAt(pi) == '?' || pattern.charAt(pi) == text.charAt(ti))) {
                ti++; pi++;
            } else if (pi < pattern.length() && pattern.charAt(pi) == '*') {
                star = pi++; match = ti;
            } else if (star >= 0) {
                pi = star + 1; ti = ++match;
            } else {
                return false;
            }
        }
        while (pi < pattern.length() && pattern.charAt(pi) == '*') pi++;
        return pi == pattern.length();
    }
}
