package com.jfmultichat.tools;

import java.nio.file.Path;

/**
 * 远程配置一键发布（Java/main 版 + Python/python 版）。
 *
 * <p>顺序：
 * <ol>
 *   <li>加密本工程（main 分支使用的 v2/v10）→ {@code <javaRoot>/remote_configs}</li>
 *   <li>版本适配同步（v2→v1、v10→v9）→ {@code <pythonRoot>/scripts}</li>
 *   <li>加密 Python 工程（python 分支使用的 v1/v9）→ {@code <pythonRoot>/remote_configs}</li>
 * </ol>
 *
 * <p>两侧使用同一次生成的密钥（密钥随密文一起下发，客户端自行解析，两边不必不同）。
 *
 * <p>运行方式：
 * <pre>
 *   gradle publishRemoteConfigs                          # Python 工程默认取同级 ../MultiWeChatManager
 *   gradle publishRemoteConfigs -PpythonRepo=D:/path/to/MultiWeChatManager
 * </pre>
 *
 * <p>本类位于 {@code src/tools} 源集，不进入应用 jar / 安装包。
 */
public final class PublishRemoteConfigs {

    /** Python 工程默认位置（与 Java 工程同级目录）. */
    private static final String DEFAULT_PYTHON_REPO = "../MultiWeChatManager";

    private PublishRemoteConfigs() {}

    public static void main(String[] args) {
        Path javaRoot = Path.of(args.length > 0 ? args[0] : ".").toAbsolutePath().normalize();
        Path raw = Path.of(args.length > 1 ? args[1] : DEFAULT_PYTHON_REPO);
        Path pythonRoot = (raw.isAbsolute() ? raw : javaRoot.resolve(raw)).normalize();

        try {
            System.out.println("=== 1/3 加密 main 版（" + javaRoot.getFileName() + "）→ remote_configs/ ===");
            String key = EncryptRemoteConfigs.run(javaRoot, null);

            System.out.println();
            System.out.println("=== 2/3 同步 legacy 版（v2→v1, v10→v9）→ " + pythonRoot.getFileName() + "/scripts ===");
            int changed = LegacyConfigSync.run(javaRoot, pythonRoot);

            System.out.println();
            System.out.println("=== 3/3 加密 python 版（" + pythonRoot.getFileName() + "）→ remote_configs/ ===");
            EncryptRemoteConfigs.run(pythonRoot, key);

            System.out.println();
            System.out.println("全部完成（本次密钥: " + key + "，legacy JSON 变更 " + changed + " 个）。");
            System.out.println("提交与推送：");
            System.out.println("  main   : git add -A && git commit && git push origin main && git push gitee main");
            System.out.println("  python : cd " + pythonRoot);
            System.out.println("           git add scripts/original_remote_global_v1.json scripts/original_remote_sw_v9.json"
                    + " remote_configs/remote_global_v1 remote_configs/remote_sw_v9");
            System.out.println("           git commit && git push origin python && git push gitee python");
        } catch (Exception e) {
            System.err.println("[错误] 发布失败: " + e.getMessage());
            System.exit(1);
        }
    }
}
