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
     * **"已知无互斥体"的 PID 集合（全局共享，软件生命周期内一直存在）**：pid → 登记时刻.
     *
     * <p>用户 2026-10-07 的方案：只要能**新开出一个窗口**，就说明启动前那些同位程序进程此刻
     * **都没有互斥体**了 → 把它们记进来；下一轮查杀先按这个集合精简 pid 列表。
     * 这样检索量从"所有实例的句柄总和"降到"只有新实例"——
     * 否则每多开一个实例就多几百上千个句柄要逐个查名字，实测正是它导致
     * "第一个账号很快、后面越来越慢"。
     *
     * <p>**不设 TTL**（用户明确要"一直存在"），前提是这些平台不会重建互斥体；
     * 万一遇到会重建的，{@link #clearKilledPidCache()} 可作总开关。
     */
    private static final Map<Integer, Long> KILLED_PID_AT = new java.util.concurrent.ConcurrentHashMap<>();

    /** 清空"已知无互斥体"缓存（排查用；遇到会重建互斥体的平台时可当总开关） */
    public static void clearKilledPidCache() {
        KILLED_PID_AT.clear();
    }

    /** 缓存规模（日志/排查用） */
    public static int killedPidCacheSize() {
        return KILLED_PID_AT.size();
    }

    /**
     * 把一批 pid 记为"已知无互斥体".
     *
     * <p>调用时机（用户 2026-10-07 的方案）：**成功开出一个新窗口之后**，把"启动前枚举到的 pid"
     * 全部记进来 —— 新窗口都能开出来，说明这些进程此刻确实都不含互斥体了。
     * 下一轮查杀先按这个集合精简，检索量就从"所有实例的句柄总和"降到"只有新实例"。
     */
    public static void markPidsClean(Collection<Integer> pids) {
        if (pids == null || pids.isEmpty()) return;
        long stamp = System.currentTimeMillis();
        for (Integer pid : pids) {
            if (pid != null) KILLED_PID_AT.put(pid, stamp);
        }
    }

    /** 从候选里剔除"已知无互斥体"的 pid，返回**还需要扫描**的那些 */
    public static List<Integer> filterCleanedPids(Collection<Integer> pids) {
        List<Integer> out = new ArrayList<>();
        if (pids == null) return out;
        for (Integer pid : pids) {
            if (pid != null && !KILLED_PID_AT.containsKey(pid)) out.add(pid);
        }
        return out;
    }

    // ==================== 对外入口 ====================

    /**
     * 查找指定进程里**句柄名匹配任一通配词**的句柄（只查不关）.
     *
     * @param pids          目标进程 PID（空集合 = 不限制进程）
     * @param nameWildcards 句柄名通配词；空 = 不按名字过滤（会返回该进程全部带名字的句柄）
     */
    public static List<HandleRef> findHandles(Collection<Integer> pids, List<String> nameWildcards) {
        return findHandles(pids, nameWildcards, 0L);
    }

    /**
     * 同 {@link #findHandles(Collection, List)}，但**带总预算**与**取消检查点**（2026-10-12 加）.
     *
     * <p>为什么需要预算：单个句柄名查询虽有 300ms 超时，但**整轮没有上限** ——
     * 1000 个候选句柄里若有几十个会阻塞，最坏就是几十秒/轮；多号登录每账号一轮、累计几分钟，
     * 表现就是用户说的"登录卡住"（2026-10-11 实测单轮卡过 13.4 秒）。
     * 现在 `deadlineMs` 一到就**停止扫描并如实报告**（已命中的照常关闭），不再让整轮无限等。
     *
     * <p>检查点：每个候选句柄前调一次 {@link com.jfmultichat.core.task.TaskContext#checkpoint()}，
     * 让"任务中心"的取消能在扫描过程中生效。
     *
     * @param deadlineMs 绝对截止时刻（{@code System.currentTimeMillis()} 口径）；≤0 表示不限时
     */
    public static List<HandleRef> findHandles(Collection<Integer> pids, List<String> nameWildcards, long deadlineMs) {
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
        boolean budgetExhausted = false;
        try {
            for (long i = 0; i < count; i++) {
                // 取消检查点（任务中心）：被取消就抛出，弹回任务边界
                com.jfmultichat.core.task.TaskContext.checkpoint();
                // 总预算：到点就停，不再无限等（已命中的照常返回并关闭）
                if (deadlineMs > 0 && System.currentTimeMillis() > deadlineMs) {
                    budgetExhausted = true;
                    break;
                }
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
        if (budgetExhausted) {
            // 记一笔"超预算"（统计里能看出"那天卡住"的前兆：这个数一涨就是有句柄在阻塞）
            com.jfmultichat.core.task.TaskContext.metric("查杀超预算", 1);
            LOG.warn("[句柄] 本轮**超预算**：已扫 {} 条（候选 {} 条）、已命中 {} 条 → 停止扫描，先拿已命中的结果继续",
                    scanned, count, result.size());
        } else {
            LOG.info("[句柄] 扫描 {} 条（目标进程候选 {} 条），命中 {} 条", count, candidates, result.size());
        }
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
        List<Integer> candidates = filterCleanedPids(pids);      // 跳过"已知无互斥体"的
        int skipped = pids.size() - candidates.size();
        if (skipped > 0) {
            LOG.info("[句柄] 跳过 {} 个已知无互斥体的 pid（长期缓存），本次只扫 {} 个", skipped, candidates.size());
        }
        if (candidates.isEmpty()) return 0;          // 全都在缓存里 → 无需扫描
        List<HandleRef> found = findHandles(candidates, nameWildcards);
        for (HandleRef h : found) LOG.info("[句柄] 命中互斥体: {}", h);
        int closed = closeHandles(found);
        // 关掉过句柄的 PID：此刻已不含这些互斥体 → 记入长期缓存
        Set<Integer> cleaned = new HashSet<>();
        for (HandleRef h : found) cleaned.add(h.pid);
        markPidsClean(cleaned);
        return closed;
    }

    /** 判断某 pid 是否在"已知无互斥体"缓存里（排查用） */
    public static boolean isRecentlyCleaned(int pid) {
        return KILLED_PID_AT.containsKey(pid);
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
            // 类型先问（OBJECT_TYPE_INFORMATION 不会阻塞）
            String type = queryUnicodeStringObject(dup, OBJECT_TYPE_INFORMATION);
            // 名字**必须带超时**：NtQueryObject(ObjectNameInformation) 在**命名管道**等句柄上会一直阻塞 ——
            // 用户 2026-10-07 实测某轮 1200 个候选句柄里有一个卡住，整轮查杀从 120ms 变成 **13425ms**
            String name = queryNameWithTimeout(dup, NAME_QUERY_TIMEOUT_MS);
            return new String[]{name, type};
        } finally {
            Kernel32Lib.INSTANCE.CloseHandle(dup);
        }
    }

    /** 句柄名查询超时（毫秒）—— 正常句柄是微秒级；会阻塞的（命名管道）直接放弃这一个 */
    private static final long NAME_QUERY_TIMEOUT_MS = 300;

    /**
     * 句柄名查询用的线程池：**cached** 池在"线程被卡住"时会自动再开新线程，
     * 所以个别句柄阻塞不会拖住整轮扫描（卡住的线程用完即弃，数量受阻塞句柄数限制）。
     */
    private static final java.util.concurrent.ExecutorService NAME_QUERY_POOL =
            java.util.concurrent.Executors.newCachedThreadPool(r -> {
                Thread t = new Thread(r, "handle-name-query");
                t.setDaemon(true);
                return t;
            });

    /**
     * 带超时地问句柄名：超时/异常都返回 null（= 跳过这一个句柄，不影响整轮；也不影响其它句柄）。
     */
    private static String queryNameWithTimeout(HANDLE dup, long timeoutMs) {
        java.util.concurrent.Future<String> f;
        try {
            f = NAME_QUERY_POOL.submit(() -> queryUnicodeStringObject(dup, OBJECT_NAME_INFORMATION));
        } catch (Exception e) {
            return null;
        }
        try {
            return f.get(timeoutMs, java.util.concurrent.TimeUnit.MILLISECONDS);
        } catch (java.util.concurrent.TimeoutException te) {
            LOG.warn("[句柄] 查句柄名超时 {}ms，跳过该句柄（NtQueryObject 在命名管道上会阻塞）", timeoutMs);
            f.cancel(true);
            return null;
        } catch (Exception e) {
            return null;
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
