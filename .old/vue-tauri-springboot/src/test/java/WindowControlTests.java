import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.platform.win32.*;
import com.sun.jna.win32.StdCallLibrary;
import org.junit.jupiter.api.Test;

public class WindowControlTests {

    /**
     * 测试 1：通过窗口标题查找 HWND，并显示标题
     */
    @Test
    public void testFindWindow() {
//        WinDef.HWND hwnd = User32.INSTANCE.FindWindow(null, "QQNT"); // QQNT主窗口标题
        WinDef.HWND hwnd = new WinDef.HWND(new Pointer(5838926));

        char[] buffer = new char[512];
        User32.INSTANCE.GetWindowText(hwnd, buffer, 512);
        System.out.println("✅ 找到窗口: " + Native.toString(buffer) + "  HWND=" + hwnd);
    }

    /**
     * 测试 2：恢复或最小化窗口
     */
    @Test
    public void testShowHideWindow() {
        WinDef.HWND hwnd = new WinDef.HWND(new Pointer(5838926));
        WinDef.HWND hwnd1 = new WinDef.HWND(new Pointer(0x03162034));

        // 最小化
        User32.INSTANCE.ShowWindow(hwnd, WinUser.SW_MINIMIZE);
        System.out.println("✅ 已最小化");

        // 延迟2秒再恢复
        try { Thread.sleep(2000); } catch (Exception ignored) {}
        User32.INSTANCE.ShowWindow(hwnd, WinUser.SW_RESTORE);
        User32.INSTANCE.SetForegroundWindow(hwnd);
        try { Thread.sleep(2000); } catch (Exception ignored) {}
        User32.INSTANCE.ShowWindow(hwnd1, WinUser.SW_MINIMIZE);
        try { Thread.sleep(2000); } catch (Exception ignored) {}
        User32.INSTANCE.ShowWindow(hwnd1, WinUser.SW_RESTORE);
        User32.INSTANCE.SetForegroundWindow(hwnd1);
        System.out.println("✅ 已恢复并置顶");
    }

    /**
     * 测试 3：移动窗口
     */
    @Test
    public void testMoveWindow() {
        WinDef.HWND hwnd = new WinDef.HWND(new Pointer(0x004F17C4));

        char[] buffer = new char[512];
        User32.INSTANCE.GetWindowText(hwnd, buffer, 512);

        boolean ok = User32.INSTANCE.MoveWindow(hwnd, 100, 100, 900, 600, true);
        System.out.println(ok ? "✅ 窗口已移动" : "❌ 移动失败");
    }

    /**
     * 测试 4：注册并发送自定义消息（如 TaskbarCreated）
     */
    @Test
    public void testRegisterAndSendMessage() {
        WinDef.HWND hwnd = new WinDef.HWND(new Pointer(0x021A1BFE));

        char[] buffer = new char[512];
        User32.INSTANCE.GetWindowText(hwnd, buffer, 512);

        int msgId = User32.INSTANCE.RegisterWindowMessage("TaskbarCreated");
        System.out.println("✅ 注册消息 ID：" + msgId);

        User32.INSTANCE.PostMessage(hwnd, msgId,
                new WinDef.WPARAM(0), new WinDef.LPARAM(0));
    }

    /**
     * 测试 5：获取窗口矩形（坐标与尺寸）
     */
    @Test
    public void testGetWindowRect() {
        WinDef.HWND hwnd = new WinDef.HWND(new Pointer(0x021A1BFE));

        char[] buffer = new char[512];
        User32.INSTANCE.GetWindowText(hwnd, buffer, 512);

        WinDef.RECT rect = new WinDef.RECT();
        User32.INSTANCE.GetWindowRect(hwnd, rect);
        System.out.printf("✅ 窗口位置：(%d,%d) 宽高：%d×%d%n",
                rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top);
    }

    /**
     * 测试 6：模拟鼠标点击（通过 Robot）
     */
    @Test
    public void testMouseClick() throws Exception {
        java.awt.Robot robot = new java.awt.Robot();
        robot.mouseMove(300, 300);
        robot.mousePress(java.awt.event.InputEvent.BUTTON1_DOWN_MASK);
        robot.mouseRelease(java.awt.event.InputEvent.BUTTON1_DOWN_MASK);
        System.out.println("✅ 模拟点击完成");
    }

    /**
     * 测试 7：全局键盘监听（需要 JNativeHook）
     */
    // 如果你引入了 org.jnativehook:global:2.2.2
    // 可以添加如下代码：
    /*
    @Test
    public void testGlobalKeyListener() throws Exception {
        org.jnativehook.GlobalScreen.registerNativeHook();
        org.jnativehook.keyboard.NativeKeyListener listener = new org.jnativehook.keyboard.NativeKeyListener() {
            @Override
            public void nativeKeyPressed(org.jnativehook.keyboard.NativeKeyEvent e) {
                System.out.println("按下：" + org.jnativehook.keyboard.NativeKeyEvent.getKeyText(e.getKeyCode()));
            }
            @Override
            public void nativeKeyReleased(org.jnativehook.keyboard.NativeKeyEvent e) {}
            @Override
            public void nativeKeyTyped(org.jnativehook.keyboard.NativeKeyEvent e) {}
        };
        org.jnativehook.GlobalScreen.addNativeKeyListener(listener);
        System.out.println("✅ 全局键盘监听启动中...");
        Thread.sleep(10000);
        org.jnativehook.GlobalScreen.unregisterNativeHook();
    }
    */
}
