package com.jfmultichat.swcore;

import com.sun.jna.Function;
import com.sun.jna.Memory;
import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.platform.win32.Guid;
import com.sun.jna.platform.win32.Ole32;
import com.sun.jna.platform.win32.OleAuto;
import com.sun.jna.platform.win32.WinDef;
import com.sun.jna.ptr.PointerByReference;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * **UIAutomation 的极小封装**（只取窗口的 UIA 属性，不做树遍历）.
 *
 * <p>为什么要它（用户 2026-10-07 实测）：有的平台用 Win32 `GetClassName` 拿到的类名**跟远程配置里的
 * 通配符对不上**，而旧版 Python 用 `uiautomation` 就能匹配上（旧版注释也写了"win32 API …
 * 但对于部分窗口并不能精确获取类名"）。这里就补这一件事：拿 UIA 报的 ClassName。
 *
 * <p>**体积**：不加任何依赖、不带任何 DLL —— `UIAutomationCore.dll` 是 Windows 系统组件，
 * 纯 JNA 走 COM vtable 调用（`CUIAutomation` coclass）。返回 null 表示取不到（调用方回退 Win32 类名）。
 *
 * <p>线程：COM 需要按线程初始化，这里每次调用先 `CoInitializeEx`（已初始化会返回 S_FALSE，忽略即可）。
 */
public final class UiaOps {

    private static final Logger LOG = LoggerFactory.getLogger(UiaOps.class);

    /** CUIAutomation coclass */
    private static final Guid.GUID CLSID_CUIAUTOMATION = new Guid.GUID("{FF48DBA4-60EF-4201-AA87-54103EEF594E}");
    /** IUIAutomation */
    private static final Guid.GUID IID_IUIAUTOMATION = new Guid.GUID("{30CBE57D-D9D0-452A-AB13-7AC5AC4825EE}");
    private static final int CLSCTX_INPROC_SERVER = 0x1;
    private static final int COINIT_APARTMENTTHREADED = 0x2;

    // IUIAutomation 的 vtable 下标（IUnknown 占 0~2）
    private static final int VT_ELEMENT_FROM_HANDLE = 6;
    // IUIAutomationElement 的属性 getter 下标（IUnknown 占 0~2，其后按字母序）
    // ⚠️ 实测校正（2026-10-07）：ClassName 在 **30**（原本按 26 猜，那一格返回 null；
    //    而 30 返回的字符串与 Win32 类名完全一致 → 就是它）。改动这里务必用 UiaProbe 复核。
    private static final int VT_GET_CURRENT_AUTOMATION_ID = 24;
    private static final int VT_GET_CURRENT_CLASS_NAME = 30;

    /** hwnd → UIA ClassName（有的平台要反复比对规则，缓存一下；失败也缓存空串免得反复 COM 调用） */
    private static final Map<Integer, String> CLASS_CACHE = new ConcurrentHashMap<>();

    /**
     * UIA 调用的**超时保护**（2026-10-12 修"取消后仍卡很久"）.
     *
     * <p>为什么必须加：UIA 的 `ElementFromHandle` 是**跨进程 COM 调用** —— 目标进程的 UI 线程若正忙/无响应，
     * 这个调用会**长时间甚至无限期阻塞** ✗（用户在"平台没有任何历史窗口、首次开窗"时遇到的卡住，怀疑就是它 ✓）。
     * 之前这个调用运行在流程线程上 ✗ → 一次阻塞就把整个任务（包括取消响应）一起拖死 ✗。
     *
     * <p>现在：放到**独立线程池**里跑 + `Future.get(800ms)` 超时 ✗→✓。
     * 连续 3 次超时就**熔断**（本会话 60 秒内不再用 UIA 兜底），避免每个窗口都白等 800ms。
     */
    private static final long UIA_TIMEOUT_MS = 800;
    private static final java.util.concurrent.ExecutorService UIA_POOL =
            java.util.concurrent.Executors.newCachedThreadPool(r -> {
                Thread t = new Thread(r, "uia-query");
                t.setDaemon(true);
                return t;
            });
    private static final java.util.concurrent.atomic.AtomicInteger UIA_TIMEOUT_STREAK =
            new java.util.concurrent.atomic.AtomicInteger();
    /** 熔断截止时刻（毫秒）；> now 时跳过 UIA */
    private static volatile long uiaDisabledUntil = 0;

    /**
     * **每个线程一个 `IUIAutomation` 实例**（不要每次查询都 `CoCreateInstance`）.
     *
     * <p>用户 2026-10-07 实测：原来每次 `getClassName` 都重新 `CoCreateInstance` + `Release` ✗，
     * 单次约 **235ms** ✗ —— 排查一堆窗口时（每个都试一次 UIA）就是几百毫秒到几秒。
     * COM 的 `IUIAutomation` 可以长期持有（按线程存 ✓），复用后单次只剩
     * `ElementFromHandle` + 取属性（毫秒级 ✓）。
     */
    private static final ThreadLocal<Pointer> UIA_INSTANCE = ThreadLocal.withInitial(() -> {
        try {
            return createUia();
        } catch (Throwable t) {
            return null;
        }
    });

    private UiaOps() {
    }

    /**
     * 取窗口的 **UIA ClassName**（拿不到返回 null）.
     * 与 Win32 {@code GetClassName} 在多数窗口上一致，但对部分窗口（框架自绘/合成窗口）只有它能对上配置。
     */
    public static String getClassName(int hwnd) {
        if (hwnd == 0) return null;
        String cached = CLASS_CACHE.get(hwnd);
        if (cached != null) return cached.isEmpty() ? null : cached;
        // 熔断期内直接跳过（不白等 800ms）
        if (System.currentTimeMillis() < uiaDisabledUntil) return null;

        // ⚠️ 真正的 COM 调用放到独立线程里带超时执行 —— 它可能被目标进程阻塞（见字段注释）
        java.util.concurrent.Future<String> f = UIA_POOL.submit(() -> queryClassNameBlocking(hwnd));
        try {
            String cls = f.get(UIA_TIMEOUT_MS, java.util.concurrent.TimeUnit.MILLISECONDS);
            UIA_TIMEOUT_STREAK.set(0);
            return cls;
        } catch (java.util.concurrent.TimeoutException te) {
            f.cancel(true);
            CLASS_CACHE.put(hwnd, "");
            int streak = UIA_TIMEOUT_STREAK.incrementAndGet();
            LOG.warn("[UIA] 取类名超时 {}ms（hwnd=0x{}）—— COM 调用被阻塞，本窗口跳过（连续第 {} 次）",
                    UIA_TIMEOUT_MS, Integer.toHexString(hwnd), streak);
            if (streak >= 3) {
                uiaDisabledUntil = System.currentTimeMillis() + 60_000;
                UIA_TIMEOUT_STREAK.set(0);
                LOG.warn("[UIA] 连续超时 → **熔断 60 秒**：这段时间窗口匹配只用 Win32 类名（避免每个窗口白等）");
            }
            return null;
        } catch (Exception e) {
            CLASS_CACHE.put(hwnd, "");
            return null;
        }
    }

    /** 真正干活的那段（跑在 UIA 线程池里，可能被阻塞 —— 所以绝不放在流程线程上） */
    private static String queryClassNameBlocking(int hwnd) {
        Pointer element = null;
        try {
            Pointer uia = UIA_INSTANCE.get();          // 复用**本线程**的实例（不每次 CoCreateInstance）
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            String cls = readBstrProperty(element, VT_GET_CURRENT_CLASS_NAME);
            CLASS_CACHE.put(hwnd, cls == null ? "" : cls);
            return cls;
        } catch (Throwable t) {
            LOG.warn("[UIA] 取 UIA ClassName 失败: hwnd=0x{}, err={}", Integer.toHexString(hwnd), t.getMessage());
            CLASS_CACHE.put(hwnd, "");
            return null;
        } finally {
            release(element);                          // 只释放 element；IUIAutomation 留在 ThreadLocal 复用
        }
    }

    /**
     * 取一组常用的 UIA 属性（ClassName / AutomationId），供规则里出现 UIA 专用键时使用.
     * 任何一项取不到就留空；整体失败返回 null。
     */
    public static Map<String, Object> getProperties(int hwnd) {
        if (hwnd == 0) return null;
        Pointer element = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            Map<String, Object> props = new java.util.LinkedHashMap<>();
            props.put("ClassName", readBstrProperty(element, VT_GET_CURRENT_CLASS_NAME));
            props.put("AutomationId", readBstrProperty(element, VT_GET_CURRENT_AUTOMATION_ID));
            return props;
        } catch (Throwable t) {
            LOG.warn("[UIA] 取 UIA 属性失败: hwnd=0x{}, err={}", Integer.toHexString(hwnd), t.getMessage());
            return null;
        } finally {
            release(element);
        }
    }

    // ==================== 树遍历 + 调用控件（2026-10-14 新增：用户要求"能精准就不要瞎猜位置"） ====================
    //
    // 用途：Weixin（自绘标题栏 ✓）的最大化/最小化按钮**不要按坐标去点** ✗ ——
    //   改走 UIA：在窗口的**后代元素**里按名字找到那个按钮 → 用 **InvokePattern.Invoke()** 调它 ✓ 零坐标 ✓。
    //
    // 下标依据（与上面已有的 24/30 同一套校正方式 ✓）：
    //   IUIAutomation：6=ElementFromHandle（项目已实测 ✓）、
    //     21=CreateTrueCondition、23=CreatePropertyCondition ✓
    //   IUIAutomationElement：5=FindFirst、**6=FindAll**（本类新用 ✓）、
    //     **10=GetCurrentPropertyValue**（用来读 Name，避免再猜一个属性 getter 下标 ✓）、
    //     **16=GetCurrentPattern** ✓；属性 getter：24=AutomationId（已实测 ✓）、28=ControlType、30=ClassName（已实测 ✓）
    //   IUIAutomationElementArray：**3=get_Length、4=GetElement**（接口只有这两个方法 ✓ 无疑义 ✓）
    //   IUIAutomationInvokePattern：**3=Invoke**（接口只有这一个方法 ✓ 无疑义 ✓）
    //   ⚠️ 若行为异常，用 UiaProbe 复核这几格（与本文件既有注释的纪律一致 ✓）。

    private static final int VT_FIND_FIRST = 5;
    private static final int VT_FIND_ALL = 6;
    private static final int VT_GET_CURRENT_PROPERTY_VALUE = 10;
    private static final int VT_GET_CURRENT_PATTERN = 16;
    private static final int VT_GET_CURRENT_CONTROL_TYPE = 28;
    private static final int VT_GET_CURRENT_BOUNDING_RECT = 25;
    private static final int VT_UIA_CREATE_TRUE_CONDITION = 21;
    /** `TreeScope_Descendants`（UIA 的 TreeScope 枚举 ✓） */
    private static final int TREE_SCOPE_DESCENDANTS = 4;
    /** `UIA_NamePropertyId`（UIA 属性 id ✓） */
    private static final int PROP_NAME = 30005;
    /** `UIA_InvokePatternId` ✓ */
    private static final int PATTERN_INVOKE = 10000;
    private static final short VT_BSTR = 8;
    private static final short VT_I4 = 3;
    private static final short VT_R8 = 5;

    /**
     * **列出窗口后代控件**（名字 / 控件类型 / AutomationId / UIA 类名 / 矩形 ✓）.
     *
     * <p>这就是"**精确定位不猜**"的第一步 ✓：先把它有哪些控件、各自**叫什么名字**打出来 ✓，
     * 然后按名字去 Invoke ✓（而不是按像素 ✗）。
     *
     * @return 每行一个控件的描述（最多 {@code 60} 行 ✓）；失败返回 null
     */
    public static java.util.List<String> dumpDescendants(int hwnd) {
        if (hwnd == 0) return null;
        Pointer element = null;
        Pointer array = null;
        Pointer cond = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return null;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return null;
            array = ppArr.getValue();
            if (array == null) return null;

            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3 /*get_Length*/, len) != 0) return null;
            int n = len.getInt(0);
            java.util.List<String> out = new java.util.ArrayList<>();
            for (int i = 0; i < Math.min(n, 60); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4 /*GetElement*/, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                Pointer el = ppEl.getValue();
                try {
                    String name = readProperty(el, PROP_NAME, VT_BSTR);
                    String automationId = readBstrProperty(el, VT_GET_CURRENT_AUTOMATION_ID);
                    String cls = readBstrProperty(el, VT_GET_CURRENT_CLASS_NAME);
                    int ct = readIntProperty(el, VT_GET_CURRENT_CONTROL_TYPE);
                    String rect = readRectProperty(el, VT_GET_CURRENT_BOUNDING_RECT);
                    out.add(String.format("name=%-22s controlType=%-4d automationId=%-18s uiaClass=%-22s rect=%s",
                            name == null ? "" : name, ct, automationId == null ? "" : automationId,
                            cls == null ? "" : cls, rect));
                } finally {
                    release(el);
                }
            }
            LOG.info("[UIA] 列出后代控件 {} 个（hwnd=0x{}）", out.size(), Integer.toHexString(hwnd));
            return out;
        } catch (Throwable t) {
            LOG.warn("[UIA] 列举控件失败 hwnd=0x{}: {}", Integer.toHexString(hwnd), t.getMessage());
            return null;
        } finally {
            release(array);
            release(cond);
            release(element);
        }
    }

    /**
     * **按名字调用控件**（`InvokePattern.Invoke()` ✓ 零坐标 ✓）—— 例如微信的最大化/还原/最小化按钮 ✓.
     *
     * <p>匹配规则 ✓：先比 `Name` ✓、再比 `AutomationId` ✓；**忽略大小写** ✓；**包含**即算命中 ✓
     * （"最大化" 能命中 "最大化" 或 "Maximize" 传进来也能扩展 ✓）。
     *
     * @param names 候选名字（按顺序试 ✓ 例："最大化", "Maximize"）
     * @return 命中的名字（成功调用 ✓）；没命中返回 null ✓
     */
    public static String invokeByNames(int hwnd, String... names) {
        if (hwnd == 0 || names == null || names.length == 0) return null;
        Pointer element = null;
        Pointer array = null;
        Pointer cond = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return null;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return null;
            array = ppArr.getValue();
            if (array == null) return null;
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return null;
            int n = len.getInt(0);
            for (int i = 0; i < Math.min(n, 200); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                Pointer el = ppEl.getValue();
                try {
                    String name = readProperty(el, PROP_NAME, VT_BSTR);
                    String automationId = readBstrProperty(el, VT_GET_CURRENT_AUTOMATION_ID);
                    for (String want : names) {
                        if (want == null || want.isBlank()) continue;
                        if (containsIgnoreCase(name, want) || containsIgnoreCase(automationId, want)) {
                            if (invoke(el)) {
                                LOG.info("[UIA] 已用**控件**调用：{}（命中 {} ✓ hwnd=0x{}）",
                                        want, name == null ? automationId : name, Integer.toHexString(hwnd));
                                return want;
                            }
                            LOG.warn("[UIA] 命中 {} 但 InvokePattern 调用失败（可能该控件不支持 Invoke ✗）", want);
                        }
                    }
                } finally {
                    release(el);
                }
            }
            LOG.info("[UIA] 未命中控件（候选 {} ✓ hwnd=0x{}）", String.join("/", names), Integer.toHexString(hwnd));
            return null;
        } catch (Throwable t) {
            LOG.warn("[UIA] 调用控件失败 hwnd=0x{}: {}", Integer.toHexString(hwnd), t.getMessage());
            return null;
        } finally {
            release(array);
            release(cond);
            release(element);
        }
    }

    /** 取 `IUIAutomationInvokePattern` 并 `Invoke()`（下标 3 ✓ 该接口只有一个方法 ✓） */
    private static boolean invoke(Pointer element) {
        PointerByReference pp = new PointerByReference();
        if (vcallInt(element, VT_GET_CURRENT_PATTERN, PATTERN_INVOKE, pp) != 0 || pp.getValue() == null) return false;
        Pointer pattern = pp.getValue();
        try {
            return vcallInt(pattern, 3 /*Invoke*/) == 0;
        } finally {
            release(pattern);
        }
    }

    private static boolean containsIgnoreCase(String hay, String needle) {
        return hay != null && hay.toLowerCase(java.util.Locale.ROOT).contains(needle.toLowerCase(java.util.Locale.ROOT));
    }

    /** `GetCurrentPropertyValue(id, VARIANT*)` → 读 BSTR 字段（VARIANT 布局：vt(2B)+pad(6B)+union ✓） */
    private static String readProperty(Pointer element, int propertyId, short expectedVt) {
        Memory var = new Memory(24);                 // VARIANT 我们只需前 16 字节（vt + 指针 ✓）
        var.clear();
        if (vcallInt(element, VT_GET_CURRENT_PROPERTY_VALUE, propertyId, var) != 0) return null;
        short vt = var.getShort(0);
        if (vt != expectedVt) return null;
        Pointer p = var.getPointer(8);               // 64 位下 BSTR 指针在偏移 8 ✓
        if (p == null) return null;
        try {
            return p.getWideString(0);
        } finally {
            try {
                OleAuto.INSTANCE.SysFreeString(new com.sun.jna.platform.win32.WTypes.BSTR(p));
            } catch (Throwable ignore) {
                // 忽略
            }
        }
    }

    /** 取 int 型属性（如 ControlType ✓） */
    private static int readIntProperty(Pointer element, int vtIndex) {
        Memory m = new Memory(4);
        m.clear();
        return vcallInt(element, vtIndex, m) == 0 ? m.getInt(0) : -1;
    }

    /** 取矩形属性（`BoundingRectangle` ✓ 是个 RECT ✓） */
    private static String readRectProperty(Pointer element, int vtIndex) {
        WinDef.RECT r = new WinDef.RECT();
        if (vcallInt(element, vtIndex, r.getPointer()) != 0) return "?";
        return r.left + "," + r.top + " " + (r.right - r.left) + "x" + (r.bottom - r.top);
    }

    /**
     * **按类名关键字列举控件**（放开数量上限 ✓ 服务端不筛、客户端按 `uiaClass`/`name` 过滤 ✓）.
     *
     * <p>为什么加它 ✗（用户 2026-10-14 给出微信 4.0 的 UIA 实况 ✓）：
     * 微信是 **Qt（mmui）** 应用 ✓ —— `uiaClass` **是填好的** ✓（如 `mmui::XButton` ✓）、
     * 但 `automationId` 全空 ✗、`name` 大多空 ✗ → **按类名才是可用抓手** ✓；
     * 而且前 60 条被上限截断 ✗、看不到标题栏按钮 ✓ → 这里放开上限并按关键字过滤 ✓。
     *
     * @param keywords 类名/名字里**包含**任一关键字即保留（忽略大小写 ✓）；空则全部保留 ✓
     */
    public static java.util.List<String> listByClassKeyword(int hwnd, int limit, String... keywords) {
        java.util.List<String> all = listDescendants(hwnd, limit, keywords);
        return all;
    }

    /**
     * **按类名关键字调用控件**（`InvokePattern.Invoke()` ✓ 零坐标 ✓）.
     *
     * <p>用于微信这种"按钮没名字、但有 Qt 类名"的情况 ✓：例如按 `mmui::XWindowButton` /
     * `XButton` 之类的类名命中后 Invoke ✓。
     *
     * @return 命中的关键字（成功调用 ✓）；没命中返回 null ✓
     */
    public static String invokeByClassKeyword(int hwnd, String... keywords) {
        if (hwnd == 0 || keywords == null || keywords.length == 0) return null;
        Pointer element = null;
        Pointer array = null;
        Pointer cond = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return null;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return null;
            array = ppArr.getValue();
            if (array == null) return null;
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return null;
            int n = len.getInt(0);
            for (int i = 0; i < Math.min(n, 2000); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                Pointer el = ppEl.getValue();
                try {
                    String cls = readBstrProperty(el, VT_GET_CURRENT_CLASS_NAME);
                    String name = readProperty(el, PROP_NAME, VT_BSTR);
                    for (String key : keywords) {
                        if (key == null || key.isBlank()) continue;
                        if (containsIgnoreCase(cls, key) || containsIgnoreCase(name, key)) {
                            if (invoke(el)) {
                                LOG.info("[UIA] 已用**控件**调用（类名命中 {} ✓ class={} name={} ✓）", key, cls, name);
                                return key;
                            }
                            LOG.warn("[UIA] 类名命中 {} 但 Invoke 失败（class={}）", key, cls);
                        }
                    }
                } finally {
                    release(el);
                }
            }
            LOG.info("[UIA] 类名未命中（候选 {} ✓ hwnd=0x{}）", String.join("/", keywords), Integer.toHexString(hwnd));
            return null;
        } catch (Throwable t) {
            LOG.warn("[UIA] 按类名调用失败 hwnd=0x{}: {}", Integer.toHexString(hwnd), t.getMessage());
            return null;
        } finally {
            release(array);
            release(cond);
            release(element);
        }
    }

    /**
     * 遍历后代并按关键字过滤 ✓（**只读 `uiaClass`/`name`/`automationId`** ✓ ——
     * `controlType`/`rect` 那两个下标**按序推的、实测不准** ✗ 所以这里不用它们 ✓）。
     */
    private static java.util.List<String> listDescendants(int hwnd, int limit, String... keywords) {
        if (hwnd == 0) return null;
        Pointer element = null;
        Pointer array = null;
        Pointer cond = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return null;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return null;
            array = ppArr.getValue();
            if (array == null) return null;
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return null;
            int n = len.getInt(0);
            java.util.List<String> out = new java.util.ArrayList<>();
            int total = Math.min(n, Math.max(1, limit));
            for (int i = 0; i < total; i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                Pointer el = ppEl.getValue();
                try {
                    String cls = readBstrProperty(el, VT_GET_CURRENT_CLASS_NAME);
                    String name = readProperty(el, PROP_NAME, VT_BSTR);
                    String aid = readBstrProperty(el, VT_GET_CURRENT_AUTOMATION_ID);
                    if (keywords != null && keywords.length > 0) {
                        boolean keep = false;
                        for (String key : keywords) {
                            if (key == null || key.isBlank()) continue;
                            if (containsIgnoreCase(cls, key) || containsIgnoreCase(name, key)) { keep = true; break; }
                        }
                        if (!keep) continue;
                    }
                    out.add("name=" + (name == null ? "" : name) + "  class=" + (cls == null ? "" : cls)
                            + "  automationId=" + (aid == null ? "" : aid) + "  [#" + i + "]");
                } finally {
                    release(el);
                }
            }
            LOG.info("[UIA] 列举完成：共 {} 个后代，命中 {} 个（limit={}, hwnd=0x{}）",
                    n, out.size(), limit, Integer.toHexString(hwnd));
            return out;
        } catch (Throwable t) {
            LOG.warn("[UIA] 列举失败 hwnd=0x{}: {}", Integer.toHexString(hwnd), t.getMessage());
            return null;
        } finally {
            release(array);
            release(cond);
            release(element);
        }
    }

    /**
     * **精确**调用控件：**类名完全相等**（可选）+ **名字完全相等**（忽略大小写 ✓）→ `Invoke()` ✓.
     *
     * <p>用户 2026-10-14 用 UISpy 拿到的微信 4.0 实况 ✓：
     * <pre>
     *   ClassName=mmui::XButton   Name=最大化   ControlType=Button   （还有 最小化 / 关闭 ✓）
     * </pre>
     * → 所以**不必猜坐标** ✓ 也不必用"包含"匹配（会误点"隐藏窗口截图"之类 ✗）→ 这里用**完全相等** ✓。
     *
     * @param className  要求的类名（null/空 = 不限 ✓）；如需极稳可传 {@code "mmui::XButton"} ✓
     * @param exactNames 候选名字（按序试 ✓ 例如 "最大化" / "向下还原" / "还原" ✓）
     * @return 命中的名字 ✓；没命中返回 null ✓
     */
    public static String invokeButtonExact(int hwnd, String className, String... exactNames) {
        if (hwnd == 0 || exactNames == null || exactNames.length == 0) return null;
        Pointer element = null;
        Pointer array = null;
        Pointer cond = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return null;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return null;
            array = ppArr.getValue();
            if (array == null) return null;
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return null;
            int n = len.getInt(0);
            for (int i = 0; i < Math.min(n, 3000); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                Pointer el = ppEl.getValue();
                try {
                    String cls = readBstrProperty(el, VT_GET_CURRENT_CLASS_NAME);
                    if (className != null && !className.isBlank() && !className.equals(cls)) continue;
                    String name = readProperty(el, PROP_NAME, VT_BSTR);
                    if (name == null) continue;
                    String n1 = name.trim();
                    for (String want : exactNames) {
                        if (want == null || want.isBlank()) continue;
                        if (n1.equalsIgnoreCase(want.trim())) {
                            if (invoke(el)) {
                                LOG.info("[UIA] 精确控件调用成功：class={} name={}（候选 {} ✓ #{}）",
                                        cls, n1, want, i);
                                return want;
                            }
                            LOG.warn("[UIA] 精确命中 {} 但 Invoke 失败（class={}）", n1, cls);
                        }
                    }
                } finally {
                    release(el);
                }
            }
            LOG.info("[UIA] 精确未命中（class={} names={} ✓ hwnd=0x{}）",
                    className, String.join("/", exactNames), Integer.toHexString(hwnd));
            return null;
        } catch (Throwable t) {
            LOG.warn("[UIA] 精确调用失败 hwnd=0x{}: {}", Integer.toHexString(hwnd), t.getMessage());
            return null;
        } finally {
            release(array);
            release(cond);
            release(element);
        }
    }

    /**
     * **按"标题栏里的位置"调用窗口按钮**（**与界面语言无关** ✓）—— 用户 2026-10-14 提出的关键问题：
     * "控件的 Name 一定保持不变吗？比如我登录了英文版，它还会叫「最大化」吗？" ✓
     *
     * <p>答案 ✓：**Name 不保证稳定** ✗ —— 它基本就是**本地化的可视文本** ✓（UISpy 里
     * {@code LocalizedControlType="按钮"} 已说明它是本地化文本 ✓）→ 英文版可能是 {@code Maximize} ✓，
     * 别的语言又是另一套 ✗；而且**随状态变**（最大化↔还原 ✓）。
     * 可靠的是 **`ClassName`（不本地化 ✓）+ 在标题栏里的顺序** ✓。
     *
     * <p>做法 ✓：先找到类名 = {@code mmui::TitleBar} 的元素 ✓ → 取它的**直接子元素**（按顺序 ✓）→
     * 从**末尾往前数**第 {@code fromEnd} 个 ✓：微信实测布局 = `… 置顶 / 最小化 / 最大化 / 关闭` ✓
     * → {@code fromEnd=0 → 关闭} ✓、{@code 1 → 最大化/还原} ✓、{@code 2 → 最小化} ✓（**与语言无关** ✓✓）。
     *
     * @return 被调用控件的 `Name`（便于核对 ✓ 也顺带回答"英文版叫什么" ✓）；失败返回 null ✓
     */
    public static String invokeTitleBarButtonByIndex(int hwnd, int fromEnd) {
        if (hwnd == 0) return null;
        Pointer element = null;
        Pointer array = null;
        Pointer cond = null;
        Pointer titleBar = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return null;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return null;
            array = ppArr.getValue();
            if (array == null) return null;
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return null;
            int n = len.getInt(0);
            // ① 找类名 = mmui::TitleBar 的那个容器（不本地化 ✓ 可靠 ✓）
            for (int i = 0; i < Math.min(n, 3000); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                String cls = readBstrProperty(ppEl.getValue(), VT_GET_CURRENT_CLASS_NAME);
                if (TITLE_BAR_CLASS.equals(cls)) { titleBar = ppEl.getValue(); break; }
                release(ppEl.getValue());
            }
            if (titleBar == null) {
                LOG.info("[UIA] 没找到 {}（无法按位置取按钮 ✓）", TITLE_BAR_CLASS);
                return null;
            }
            // ② 取它的**直接子元素**（TreeScope_Children = 2 ✓ 顺序即界面顺序 ✓）
            PointerByReference ppKids = new PointerByReference();
            if (vcallInt(titleBar, VT_FIND_ALL, TREE_SCOPE_CHILDREN, cond, ppKids) != 0) return null;
            Pointer kids = ppKids.getValue();
            if (kids == null) return null;
            try {
                Memory klen = new Memory(4);
                klen.clear();
                if (vcallInt(kids, 3, klen) != 0) return null;
                int kn = klen.getInt(0);
                int idx = kn - 1 - Math.max(0, fromEnd);          // 从末尾往前数 ✓
                if (idx < 0 || idx >= kn) {
                    LOG.info("[UIA] 标题栏只有 {} 个子控件，取不到 fromEnd={} ✓", kn, fromEnd);
                    return null;
                }
                PointerByReference ppBtn = new PointerByReference();
                if (vcallInt(kids, 4, idx, ppBtn) != 0 || ppBtn.getValue() == null) return null;
                Pointer btn = ppBtn.getValue();
                try {
                    String name = readProperty(btn, PROP_NAME, VT_BSTR);
                    String cls = readBstrProperty(btn, VT_GET_CURRENT_CLASS_NAME);
                    if (invoke(btn)) {
                        LOG.info("[UIA] 按**标题栏位置**调用成功：fromEnd={} → class={} name={}（共 {} 个子控件 ✓）",
                                fromEnd, cls, name, kn);
                        return name == null ? cls : name;
                    }
                    LOG.warn("[UIA] 按位置命中（fromEnd={}, name={}）但 Invoke 失败 ✓", fromEnd, name);
                    return null;
                } finally {
                    release(btn);
                }
            } finally {
                release(kids);
            }
        } catch (Throwable t) {
            LOG.warn("[UIA] 按标题栏位置调用失败 hwnd=0x{}: {}", Integer.toHexString(hwnd), t.getMessage());
            return null;
        } finally {
            if (titleBar != null) release(titleBar);
            release(array);
            release(cond);
            release(element);
        }
    }

    /** 微信标题栏容器的 UIA 类名（实测 ✓ 不本地化 ✓） */
    private static final String TITLE_BAR_CLASS = "mmui::TitleBar";
    /** `TreeScope_Children`（UIA ✓） */
    private static final int TREE_SCOPE_CHILDREN = 2;

    /**
     * **列出标题栏（`mmui::TitleBar`）直接子控件的名字与序号** ✓ —— 诊断"到底点的是谁"用 ✓.
     *
     * <p>用途（用户 2026-10-14 实测"没反应"后 ✓）：如果 Invoke 了却毫无变化 ✓，
     * 第一件事就是**看清标题栏里到底有哪几个子控件、顺序如何** ✓ ——
     * 这能立刻区分"命中了错的控件" ✗ 与"命中了但控件不响应" ✗，不用再猜 ✓。
     *
     * @return 形如 {@code [0]=置顶 [1]=最小化 [2]=最大化 [3]=关闭} 的说明 ✓；失败返回 "?" ✓
     */
    public static String titleBarChildren(int hwnd) {
        if (hwnd == 0) return "?";
        Pointer element = null;
        Pointer array = null;
        Pointer cond = null;
        Pointer titleBar = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return "?";
            element = elementFromHandle(uia, hwnd);
            if (element == null) return "?";
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return "?";
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return "?";
            array = ppArr.getValue();
            if (array == null) return "?";
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return "?";
            int n = len.getInt(0);
            for (int i = 0; i < Math.min(n, 3000); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                String cls = readBstrProperty(ppEl.getValue(), VT_GET_CURRENT_CLASS_NAME);
                if (TITLE_BAR_CLASS.equals(cls)) { titleBar = ppEl.getValue(); break; }
                release(ppEl.getValue());
            }
            if (titleBar == null) return "（没找到 " + TITLE_BAR_CLASS + "）";
            PointerByReference ppKids = new PointerByReference();
            if (vcallInt(titleBar, VT_FIND_ALL, TREE_SCOPE_CHILDREN, cond, ppKids) != 0) return "?";
            Pointer kids = ppKids.getValue();
            if (kids == null) return "?";
            try {
                Memory klen = new Memory(4);
                klen.clear();
                if (vcallInt(kids, 3, klen) != 0) return "?";
                int kn = klen.getInt(0);
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < Math.min(kn, 20); i++) {
                    PointerByReference ppB = new PointerByReference();
                    if (vcallInt(kids, 4, i, ppB) != 0 || ppB.getValue() == null) continue;
                    Pointer b = ppB.getValue();
                    try {
                        String nm = readProperty(b, PROP_NAME, VT_BSTR);
                        String cc = readBstrProperty(b, VT_GET_CURRENT_CLASS_NAME);
                        sb.append("[").append(i).append("]=").append(nm == null ? "" : nm)
                                .append("(").append(cc == null ? "" : cc).append(") ");
                    } finally {
                        release(b);
                    }
                }
                String out = "共 " + kn + " 个: " + sb;
                LOG.info("[UIA] {}", out);
                return out;
            } finally {
                release(kids);
            }
        } catch (Throwable t) {
            LOG.warn("[UIA] 列标题栏子控件失败: {}", t.getMessage());
            return "?";
        } finally {
            if (titleBar != null) release(titleBar);
            release(array);
            release(cond);
            release(element);
        }
    }

    /**
     * **取指定名字的按钮的屏幕矩形**（`BoundingRectangle` ✓，取不到再试 `ClickablePoint` ✓）.
     *
     * <p>为什么需要（用户 2026-10-14 实测定性 ✓）：微信的 Qt 按钮**实现了 `InvokePattern` 但 `Invoke()` 是空操作** ✗
     * （日志实证：`命中=最大化`、`Invoke` 返回成功 ✓，但窗口状态 `false → false` 没变 ✗）。
     * 而用户**用鼠标真点**却有效 ✓ ⇒ 微信认**真实点击消息** ✓、不认 UIA 调用 ✗。
     * 于是正解 = **位置由 UIA 精确给出** ✓ + **在该位置发点击消息** ✓（**不猜像素** ✓）。
     *
     * @return {left, top, right, bottom}（物理屏幕像素 ✓）；取不到返回 null ✓
     */
    public static int[] buttonScreenRect(int hwnd, String className, String exactName) {
        if (hwnd == 0) return null;
        Pointer element = null, array = null, cond = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return null;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return null;
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return null;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return null;
            array = ppArr.getValue();
            if (array == null) return null;
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return null;
            int n = len.getInt(0);
            for (int i = 0; i < Math.min(n, 3000); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                Pointer el = ppEl.getValue();
                try {
                    String cls = readBstrProperty(el, VT_GET_CURRENT_CLASS_NAME);
                    if (className != null && !className.isBlank() && !className.equals(cls)) continue;
                    String nm = readProperty(el, PROP_NAME, VT_BSTR);
                    if (nm == null || !nm.trim().equalsIgnoreCase(exactName == null ? "" : exactName.trim())) continue;
                    // ① 先试 BoundingRectangle（RECT ✓）
                    WinDef.RECT r = new WinDef.RECT();
                    if (vcallInt(el, VT_GET_CURRENT_BOUNDING_RECT, r.getPointer()) == 0
                            && (r.right - r.left) > 0 && (r.bottom - r.top) > 0) {
                        LOG.info("[UIA] {} 的矩形(25)={},{},{}x{}", exactName, r.left, r.top,
                                r.right - r.left, r.bottom - r.top);
                        return new int[]{r.left, r.top, r.right, r.bottom};
                    }
                    // ② 退而求其次：ClickablePoint（POINT ✓ 用一个 1px 矩形表示 ✓）
                    Memory pt = new Memory(8);
                    pt.clear();
                    if (vcallInt(el, VT_GET_CURRENT_CLICKABLE_POINT, pt) == 0) {
                        int px = pt.getInt(0), py = pt.getInt(4);
                        if (px != 0 || py != 0) {
                            LOG.info("[UIA] {} 的可点(26)={},{}", exactName, px, py);
                            return new int[]{px, py, px + 1, py + 1};
                        }
                    }
                    LOG.warn("[UIA] 命中 {} 但取不到矩形/可点（属性下标可能需校正 ✓）", exactName);
                    return null;
                } finally {
                    release(el);
                }
            }
            return null;
        } catch (Throwable t) {
            LOG.warn("[UIA] 取按钮矩形失败: {}", t.getMessage());
            return null;
        } finally {
            release(array);
            release(cond);
            release(element);
        }
    }

    /** `ClickablePoint` 的属性 getter（下标按 24/30 校正后的序列推：25=矩形、**26=可点** ✓） */
    private static final int VT_GET_CURRENT_CLICKABLE_POINT = 26;

    /**
     * **探针：确定 `BoundingRectangle` 的真实 vtable 下标** ✓（我自己跑 ✓ 不让用户点 ✗）.
     *
     * <p>背景 ✓：项目实测 24=AutomationId、30=ClassName ✓，但按序推的 25=矩形 / 26=可点**读出来是 0** ✗
     * （用户实测：`rect=0,0 0x0` ✓）→ 需要**逐个下标试**找出真正那一格 ✓。
     * <p>安全性 ✓：**只按 RECT（16 字节）读** ✓ —— 绝不把未知指针当字符串解 ✗（那会让 JVM 崩 ✗）。
     * 判据 ✓：`right>left && bottom>top` 且宽高落在合理范围（1..4000 ✓）才算"像矩形" ✓。
     *
     * @return 每个"像矩形"的下标 + 值（形如 `idx=27 → 100,50 46x32` ✓）
     */
    public static java.util.List<String> probeRectIndices(int hwnd, String className, String exactName,
                                                        int from, int to) {
        java.util.List<String> out = new java.util.ArrayList<>();
        if (hwnd == 0) return out;
        Pointer element = null, array = null, cond = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return out;
            element = elementFromHandle(uia, hwnd);
            if (element == null) return out;
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return out;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return out;
            array = ppArr.getValue();
            if (array == null) return out;
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return out;
            int n = len.getInt(0);
            Pointer target = null;
            for (int i = 0; i < Math.min(n, 3000); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                Pointer el = ppEl.getValue();
                String cls = readBstrProperty(el, VT_GET_CURRENT_CLASS_NAME);
                if (className != null && !className.isBlank() && !className.equals(cls)) { release(el); continue; }
                String nm = readProperty(el, PROP_NAME, VT_BSTR);
                if (nm != null && nm.trim().equalsIgnoreCase(exactName == null ? "" : exactName.trim())) {
                    target = el;                                  // 找到按钮 ✓（不 release ✓ 下面还要用 ✓）
                    out.add("找到按钮：class=" + cls + " name=" + nm + " （后代第 " + i + " 个 ✓）");
                    break;
                }
                release(el);
            }
            if (target == null) {
                out.add("没找到按钮 class=" + className + " name=" + exactName);
                return out;
            }
            try {
                for (int idx = from; idx <= to; idx++) {
                    Memory mem = new Memory(16);
                    mem.clear();
                    if (vcallInt(target, idx, mem) != 0) continue;
                    int l = mem.getInt(0), t = mem.getInt(4), r = mem.getInt(8), b = mem.getInt(12);
                    int w = r - l, h = b - t;
                    if (w > 0 && h > 0 && w < 4000 && h < 4000) {
                        out.add("idx=" + idx + " → " + l + "," + t + " " + w + "x" + h);
                    }
                }
            } finally {
                release(target);
            }
            return out;
        } catch (Throwable t) {
            out.add("探针异常: " + t);
            return out;
        } finally {
            release(array);
            release(cond);
            release(element);
        }
    }

    /**
     * **按名字/类名关键字找元素，并把它的"矩形"候选下标一起打出来** ✓（找 + 校准一步到位 ✓）.
     *
     * <p>用途 ✓（用户 2026-10-15 的托盘方向 ✓）：Win11 任务栏（explorer ✓）是**原生 XAML** ✓，
     * 托盘图标就是 UIA 元素 ✓ 且**矩形是真的** ✓（不像微信自绘标题栏那样全空 ✗）
     * → 这里既能把"微信"图标找出来 ✓，又能顺便看出哪个下标是真矩形 ✓。
     *
     * @param limit 最多看多少个后代 ✓（任务栏元素多 ✓ 给大一点 ✓）
     */
    public static java.util.List<String> findByNameWithRect(int hwnd, int limit, String... keywords) {
        java.util.List<String> out = new java.util.ArrayList<>();
        if (hwnd == 0) return out;
        Pointer element = null, array = null, cond = null;
        try {
            Pointer uia = UIA_INSTANCE.get();
            if (uia == null) return out;
            element = elementFromHandle(uia, hwnd);
            if (element == null) {
                out.add("ElementFromHandle 失败（hwnd=0x" + Integer.toHexString(hwnd) + "）");
                return out;
            }
            PointerByReference ppCond = new PointerByReference();
            if (vcallInt(uia, VT_UIA_CREATE_TRUE_CONDITION, ppCond) != 0 || ppCond.getValue() == null) return out;
            cond = ppCond.getValue();
            PointerByReference ppArr = new PointerByReference();
            if (vcallInt(element, VT_FIND_ALL, TREE_SCOPE_DESCENDANTS, cond, ppArr) != 0) return out;
            array = ppArr.getValue();
            if (array == null) return out;
            Memory len = new Memory(4);
            len.clear();
            if (vcallInt(array, 3, len) != 0) return out;
            int n = len.getInt(0);
            out.add("后代共 " + n + " 个（扫描前 " + limit + " 个 ✓）");
            for (int i = 0; i < Math.min(n, Math.max(1, limit)); i++) {
                PointerByReference ppEl = new PointerByReference();
                if (vcallInt(array, 4, i, ppEl) != 0 || ppEl.getValue() == null) continue;
                Pointer el = ppEl.getValue();
                try {
                    String cls = readBstrProperty(el, VT_GET_CURRENT_CLASS_NAME);
                    String nm = readProperty(el, PROP_NAME, VT_BSTR);
                    boolean hit = false;
                    for (String k : keywords) {
                        if (k == null || k.isBlank()) continue;
                        if (containsIgnoreCase(nm, k) || containsIgnoreCase(cls, k)) { hit = true; break; }
                    }
                    if (!hit) continue;
                    StringBuilder sb = new StringBuilder("命中 #" + i + " name=" + (nm == null ? "" : nm)
                            + " class=" + (cls == null ? "" : cls) + " | 矩形候选:");
                    for (int idx = 20; idx <= 34; idx++) {
                        Memory mem = new Memory(16);
                        mem.clear();
                        if (vcallInt(el, idx, mem) != 0) continue;
                        int l = mem.getInt(0), t = mem.getInt(4), r = mem.getInt(8), b = mem.getInt(12);
                        int w = r - l, hh = b - t;
                        if (w > 4 && hh > 4 && w < 4000 && hh < 4000) {
                            sb.append(" idx").append(idx).append("=").append(l).append(",").append(t)
                              .append(" ").append(w).append("x").append(hh);
                        }
                    }
                    out.add(sb.toString());
                } finally {
                    release(el);
                }
            }
            return out;
        } catch (Throwable t) {
            out.add("异常: " + t);
            return out;
        } finally {
            release(array);
            release(cond);
            release(element);
        }
    }

    // ==================== COM 基础 ====================

    /** CoInitializeEx + CoCreateInstance(CUIAutomation) */
    private static Pointer createUia() {
        try {
            Ole32.INSTANCE.CoInitializeEx(null, COINIT_APARTMENTTHREADED);   // 已初始化/模式冲突都无所谓
        } catch (Throwable ignore) {
            // 忽略
        }
        PointerByReference ppv = new PointerByReference();
        com.sun.jna.platform.win32.WinNT.HRESULT hr = Ole32.INSTANCE.CoCreateInstance(
                CLSID_CUIAUTOMATION, null, CLSCTX_INPROC_SERVER, IID_IUIAUTOMATION, ppv);
        if (hr == null || hr.intValue() != 0) {
            LOG.warn("[UIA] CoCreateInstance(CUIAutomation) 失败: hr={}", hr == null ? "null" : hr.intValue());
            return null;
        }
        return ppv.getValue();
    }

    /** IUIAutomation::ElementFromHandle(hwnd, &element) */
    private static Pointer elementFromHandle(Pointer uia, int hwnd) {
        PointerByReference out = new PointerByReference();
        int hr = vcallInt(uia, VT_ELEMENT_FROM_HANDLE, SwNativeOps.intToHwnd(hwnd), out);
        if (hr != 0 || out.getValue() == null) return null;
        return out.getValue();
    }

    /** 取 BSTR 型属性（如 ClassName） */
    private static String readBstrProperty(Pointer element, int vtIndex) {
        Memory bstr = new Memory(Native.POINTER_SIZE);
        bstr.clear();
        int hr = vcallInt(element, vtIndex, bstr);
        if (hr != 0) return null;
        Pointer p = bstr.getPointer(0);
        if (p == null) return null;
        try {
            return p.getWideString(0);
        } finally {
            try {
                OleAuto.INSTANCE.SysFreeString(new com.sun.jna.platform.win32.WTypes.BSTR(p));
            } catch (Throwable ignore) {
                // 忽略
            }
        }
    }

    private static Pointer call(Pointer pUnk, int index, Object... args) {
        return vcall(pUnk, index, args);
    }

    /** COM vtable 调用：pUnk → vtable → 第 index 个函数（stdcall）；**第一个参数必须是 pUnk（this）** */
    private static Pointer vcall(Pointer pUnk, int index, Object... args) {
        Pointer vtbl = pUnk.getPointer(0);
        Pointer fn = vtbl.getPointer((long) index * Native.POINTER_SIZE);
        Function f = Function.getFunction(fn, Function.ALT_CONVENTION);
        return f.invokePointer(withThis(pUnk, args));
    }

    /** 同上，但按 HRESULT（int）返回 */
    private static int vcallInt(Pointer pUnk, int index, Object... args) {
        Pointer vtbl = pUnk.getPointer(0);
        Pointer fn = vtbl.getPointer((long) index * Native.POINTER_SIZE);
        Function f = Function.getFunction(fn, Function.ALT_CONVENTION);
        return f.invokeInt(withThis(pUnk, args));
    }

    /** COM 方法签名的第一个参数恒为对象自身指针 */
    private static Object[] withThis(Pointer pUnk, Object[] args) {
        Object[] all = new Object[args.length + 1];
        all[0] = pUnk;
        System.arraycopy(args, 0, all, 1, args.length);
        return all;
    }

    /** Release（vtable 下标 2） */
    private static void release(Pointer pUnk) {
        if (pUnk == null) return;
        try {
            vcallInt(pUnk, 2);
        } catch (Throwable ignore) {
            // 忽略
        }
    }
}
