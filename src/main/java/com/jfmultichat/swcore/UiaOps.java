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

    /** hwnd → UIA ClassName（有的平台要反复比对规则，缓存一下；失败也缓存 null 免得反复 COM 调用） */
    private static final Map<Integer, String> CLASS_CACHE = new ConcurrentHashMap<>();

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

        Pointer uia = null;
        Pointer element = null;
        try {
            uia = createUia();
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
            release(element);
            release(uia);
        }
    }

    /**
     * 取一组常用的 UIA 属性（ClassName / AutomationId），供规则里出现 UIA 专用键时使用.
     * 任何一项取不到就留空；整体失败返回 null。
     */
    public static Map<String, Object> getProperties(int hwnd) {
        if (hwnd == 0) return null;
        Pointer uia = null;
        Pointer element = null;
        try {
            uia = createUia();
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
            release(uia);
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
