package com.jfmultichat.boot;

import com.jfmultichat.config.AppEnv;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * 启动期提权（用户 2026-10-24 定：打包版**默认以管理员身份运行**）.
 *
 * <p>为什么需要：普通令牌下本机的安全软件（联想电脑管家/Huorong 文档保护）会拦 java.exe
 * 写用户目录（{@code %APPDATA%}/桌面/文档全部 AccessDenied）——**连 JNA 解压 jnidispatch.dll
 * 到 %TEMP% 都会被拒**，所以本类**刻意不依赖 JNA**，全部走系统命令（whoami / reg / powershell）。
 *
 * <p>jpackage 17 不支持自定义 manifest（{@code --resource-dir} 传 main.win.manifest 无效，
 * 产物里没有 requireAdministrator），所以两步走：
 * <ol>
 *   <li>往 {@code HKCU\...\AppCompatFlags\Layers} 写 {@code ~ RUNASADMIN}：
 *       以后从资源管理器双击就直接提权（带 U 盾图标）</li>
 *   <li>当前这次用 {@code powershell Start-Process -Verb RunAs} 重启自身，然后退出</li>
 * </ol>
 *
 * <p>开发/测试模式（{@code --dev} 或非 jar 运行）**不提权**，否则 gradle run 会被 UAC 打断。
 */
public final class AdminBoot {

    private static final String LAYERS_KEY =
            "HKCU\\Software\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Layers";
    private static final String RUN_AS_ADMIN = "~ RUNASADMIN";

    /** whoami /groups 里代表"高完整性"的 SID（语言无关） */
    private static final String[] ELEVATED_SIDS = {"S-1-16-12288", "S-1-16-16384"};

    private AdminBoot() {}

    /** 本进程是否以管理员身份运行（不依赖 JNA） */
    public static boolean isElevated() {
        String out = exec("whoami", "/groups");
        for (String sid : ELEVATED_SIDS) {
            if (out.contains(sid)) return true;
        }
        return false;
    }

    /** 当前启动器 exe 的绝对路径（jpackage 的 app launcher；开发环境可能是 java.exe） */
    public static String launcherPath() {
        String appPath = System.getProperty("jpackage.app-path");
        if (appPath != null && !appPath.isBlank()) return appPath;
        return ProcessHandle.current().info().command().orElse("");
    }

    /** 把「此 exe 需要管理员」写进当前用户的兼容性层，之后资源管理器双击即提权 */
    public static boolean markRunAsAdmin(String exePath) {
        return exec("reg", "add", LAYERS_KEY, "/v", exePath, "/t", "REG_SZ", "/d", RUN_AS_ADMIN, "/f") != null;
    }

    /** 读取兼容性层里该 exe 的值（诊断/自检用）；没有则返回 null */
    public static String readRunAsAdminFlag(String exePath) {
        String out = exec("reg", "query", LAYERS_KEY, "/v", exePath);
        if (out == null) return null;
        for (String line : out.split("\\R")) {
            String t = line.trim();
            if (t.startsWith(RUN_AS_ADMIN)) return RUN_AS_ADMIN;
        }
        return out.contains(RUN_AS_ADMIN) ? RUN_AS_ADMIN : null;
    }

    /**
     * 启动期调用：需要提权且当前未提权时，提权重启并返回 true（调用方必须立刻退出）.
     *
     * @return true = 已发起提权重启（或用户放弃，应退出）；false = 无需提权（已提权/开发模式）
     */
    public static boolean ensureElevated(String[] args) {
        if (AppEnv.isDev() || AppEnv.isTest()) return false;

        String exe = launcherPath();
        boolean launcherKnown = exe != null && !exe.isBlank();
        String lower = launcherKnown ? exe.toLowerCase() : "";
        boolean isPackagedLauncher = launcherKnown
                && !lower.endsWith("java.exe") && !lower.endsWith("javaw.exe");

        if (isElevated()) {
            // 提权已经把数据目录问题解决了；顺手登记"以后双击也提权"。
            // ⚠️ 必须放在**提权之后**：普通令牌下连写 HKCU 都会被安全软件拒绝（实测 reg add 被拒）
            if (isPackagedLauncher && readRunAsAdminFlag(exe) == null) {
                if (!markRunAsAdmin(exe)) warn("写兼容性层失败（不影响本次运行）");
            }
            return false;
        }

        if (!isPackagedLauncher) {
            warn("不是打包启动器，跳过提权: " + exe);
            return false;
        }

        // 本次立刻提权重启
        String ps = "Start-Process -FilePath '" + exe + "' -Verb RunAs" + buildArgList(args);
        String r = exec("powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps);
        if (r != null) {
            warn("已发起提权重启: " + exe);
            return true;
        }

        warn("提权失败或被取消（用户拒绝了 UAC）");
        alert("本程序需要以管理员身份运行：\n\n"
                + "普通权限下无法写入用户数据目录，补丁扫描缓存也写不进去。\n"
                + "请重新打开，并在 UAC 提示里选择「是」。");
        return true;   // 退出，避免半残运行
    }

    private static String buildArgList(String[] args) {
        if (args == null || args.length == 0) return "";
        StringBuilder sb = new StringBuilder(" -ArgumentList '");
        for (int i = 0; i < args.length; i++) {
            if (i > 0) sb.append(' ');
            sb.append(args[i]);
        }
        return sb.append("'").toString();
    }

    /** 执行命令；成功返回 stdout+stderr，失败返回 null（不抛异常） */
    private static String exec(String... cmd) {
        try {
            ProcessBuilder pb = new ProcessBuilder(cmd);
            pb.redirectErrorStream(true);
            Process p = pb.start();
            String out;
            try (InputStream in = p.getInputStream()) {
                out = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            }
            boolean ok = p.waitFor() == 0;
            return ok ? out : null;
        } catch (IOException | InterruptedException e) {
            return null;
        }
    }

    private static void warn(String msg) {
        System.err.println("[AdminBoot] " + msg);
    }

    /** 无 JNA 的可见提示（mshta 是系统自带、签名可信，不会被拦） */
    private static void alert(String text) {
        String flat = text.replace("\n", " ").replace("'", "").replace("\"", "");
        exec("mshta", "javascript:alert('" + flat + "');close()");
    }
}
