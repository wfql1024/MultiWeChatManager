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

    private static Entry entryOf(String sw, String acc) {
        return STORE.computeIfAbsent(sw, k -> new ConcurrentHashMap<>())
                    .computeIfAbsent(acc, k -> new Entry());
    }

    /** 写入 PID（null = 该账号未运行，清除） */
    public static void setPid(String sw, String acc, Integer pid) {
        if (sw == null || acc == null) return;
        if (pid == null) { clearPid(sw, acc); return; }
        entryOf(sw, acc).pid = pid;
    }

    /** 读取 PID（无记录返回 null） */
    public static Integer getPid(String sw, String acc) {
        Entry e = raw(sw, acc);
        return e == null ? null : e.pid;
    }

    /** 清除 PID（账号退出时） */
    public static void clearPid(String sw, String acc) {
        Entry e = raw(sw, acc);
        if (e != null) e.pid = null;
    }

    /** 写入主窗口句柄（null = 清除绑定） */
    public static void setHwnd(String sw, String acc, Long hwnd) {
        if (sw == null || acc == null) return;
        entryOf(sw, acc).hwnd = hwnd;
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
