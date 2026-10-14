package com.jfmultichat.acccore;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 账号**运行时**数据（PID / HWND）的内存存储 —— <b>不落任何配置文件</b>（用户 2026-10-06 定）.
 *
 * <p>为什么：pid / hwnd 讲究"实际性"，写进文件下次读出来就是过时的、没有意义；为保证实时性，
 * 每次重新获取即可。旧版 Python 把这两个值写进账号配置节点的做法在这里改为**只存内存**。
 *
 * <p>结构：{@code swId -> accId -> Entry{pid, hwnd}}。生命周期随进程（静态、线程安全）；
 * 平台/账号被删除时由调用方清理（也可整体忽略 —— 数据本身无持久价值）。
 */
public final class AccRuntimeStore {

    private AccRuntimeStore() {}

    /** 单个账号的运行时数据（可空字段表示"当前没有"） */
    public static final class Entry {
        public volatile Integer pid;     // 账号登录进程 PID
        public volatile Long hwnd;       // 主窗口句柄（Windows HANDLE 是 64 位，故用 Long）
    }

    private static final Map<String, Map<String, Entry>> STORE = new ConcurrentHashMap<>();

    /**
     * **变更版本号**：任何 pid/hwnd 变化都 +1.
     * <p>侧栏靠它判断"要不要重建按钮列表" ✓ —— 每帧只读一个 long ✓（用户要求资源占用尽量小 ✓），
     * 不需要轮询内存表、也不需要额外的推送通道 ✓。
     */
    private static final java.util.concurrent.atomic.AtomicLong VERSION =
            new java.util.concurrent.atomic.AtomicLong();

    /** 版本号（只增不减；每帧读一次即可知道有没有变化 ✓） */
    public static long version() {
        return VERSION.get();
    }

    private static void bump() {
        VERSION.incrementAndGet();
    }

    private static Entry entryOf(String sw, String acc) {
        return STORE.computeIfAbsent(sw, k -> new ConcurrentHashMap<>())
                    .computeIfAbsent(acc, k -> new Entry());
    }

    /** 写入 PID（null = 该账号未运行，清除） */
    public static void setPid(String sw, String acc, Integer pid) {
        if (sw == null || acc == null) return;
        if (pid == null) { clearPid(sw, acc); return; }
        Entry e = entryOf(sw, acc);
        if (!java.util.Objects.equals(e.pid, pid)) {
            e.pid = pid;
            bump();
        }
    }

    /** 读取 PID（无记录返回 null） */
    public static Integer getPid(String sw, String acc) {
        Entry e = raw(sw, acc);
        return e == null ? null : e.pid;
    }

    /** 清除 PID（账号退出时） */
    public static void clearPid(String sw, String acc) {
        Entry e = raw(sw, acc);
        if (e != null && e.pid != null) {
            e.pid = null;
            bump();
        }
    }

    /** 写入主窗口句柄（null = 清除绑定） */
    public static void setHwnd(String sw, String acc, Long hwnd) {
        if (sw == null || acc == null) return;
        Entry e = entryOf(sw, acc);
        if (!java.util.Objects.equals(e.hwnd, hwnd)) {
            e.hwnd = hwnd;
            bump();
        }
    }

    /** 读取主窗口句柄（无记录返回 null） */
    public static Long getHwnd(String sw, String acc) {
        Entry e = raw(sw, acc);
        return e == null ? null : e.hwnd;
    }

    /** 清除该账号的全部运行时数据（删除账号时） */
    public static void clear(String sw, String acc) {
        Map<String, Entry> bySw = STORE.get(sw);
        if (bySw != null) bySw.remove(acc);
    }

    /** 清除整个平台（平台切换/删除时可选调用） */
    public static void clearPlatform(String sw) {
        STORE.remove(sw);
    }

    /**
     * **全部平台**当前已绑定的主窗口句柄（侧栏"可跟随窗口"的判据）.
     *
     * <p>用户 2026-10-13 定：侧栏只跟随**内部已绑定**的窗口（外部窗口一概不作为 ✓），
     * 所以判据就是"这个 hwnd 在不在本表里"✓ —— 不区分平台、也不区分原生/共存 ✓。
     *
     * @return hwnd 集合（只含非空值）
     */
    public static java.util.Set<Integer> allHwnds() {
        java.util.Set<Integer> out = new java.util.HashSet<>();
        for (Map<String, Entry> bySw : STORE.values()) {
            for (Entry e : bySw.values()) {
                Long h = e.hwnd;
                if (h != null && h != 0) out.add(h.intValue());
            }
        }
        return out;
    }

    /** 一条"已绑定"记录（侧栏要按它画按钮 + 反查是哪个平台哪个账号 ✓） */
    public static final class Bound {
        public final String sw;
        public final String acc;
        public final int hwnd;
        public final Integer pid;

        Bound(String sw, String acc, int hwnd, Integer pid) {
            this.sw = sw;
            this.acc = acc;
            this.hwnd = hwnd;
            this.pid = pid;
        }
    }

    /**
     * 全部已绑定记录（**侧栏按钮列表的数据源** ✓）.
     * <p>顺序：先按平台名，再按账号名 —— 稳定顺序才能让按钮位置不来回跳 ✓。
     */
    public static java.util.List<Bound> allBounds() {
        java.util.List<Bound> out = new java.util.ArrayList<>();
        java.util.List<String> swKeys = new java.util.ArrayList<>(STORE.keySet());
        java.util.Collections.sort(swKeys);
        for (String sw : swKeys) {
            Map<String, Entry> bySw = STORE.get(sw);
            if (bySw == null) continue;
            java.util.List<String> accKeys = new java.util.ArrayList<>(bySw.keySet());
            java.util.Collections.sort(accKeys);
            for (String acc : accKeys) {
                Entry e = bySw.get(acc);
                Long h = e.hwnd;
                if (h != null && h != 0) out.add(new Bound(sw, acc, h.intValue(), e.pid));
            }
        }
        return out;
    }

    private static Entry raw(String sw, String acc) {
        Map<String, Entry> bySw = STORE.get(sw);
        return bySw == null ? null : bySw.get(acc);
    }

    /**
     * 某平台的快照（供前端渲染）：{@code {accId: {pid, hwnd}}}.
     * pid/hwnd 没有值时该字段为 {@code null}（前端显示空）。
     */
    public static Map<String, Map<String, Object>> snapshot(String sw) {
        Map<String, Map<String, Object>> out = new LinkedHashMap<>();
        Map<String, Entry> bySw = STORE.get(sw);
        if (bySw == null) return out;
        for (Map.Entry<String, Entry> e : bySw.entrySet()) {
            Entry v = e.getValue();
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("pid", v.pid);
            item.put("hwnd", v.hwnd);
            out.put(e.getKey(), item);
        }
        return out;
    }
}
