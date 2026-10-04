package com.jfmultichat.tools;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * 远程配置「版本适配中间脚本」。
 *
 * <p>Java 版（main 分支）维护的现代版 JSON 是**唯一源**；本脚本按版本映射把它同步给
 * Python 版（python 分支）使用的旧版 JSON，从而只需维护一份内容。
 *
 * <p>当前两侧 schema 完全一致（{@code v2↔v1}、{@code v10↔v9}），故 {@link #adapt} 为原样直通，
 * 保证目标文件与源文件字节级一致（含换行与字段顺序）。**一旦格式出现分化**，
 * 在 {@link #adapt} 内按映射实现字段级转换即可，其余流程不动。
 *
 * <p>运行方式：
 * <pre>
 *   gradle publishRemoteConfigs        # 推荐：加密 + 同步 + 再加密，一条命令
 *   gradle syncLegacyConfigs          # 只做同步（不加密）
 * </pre>
 *
 * <p>本类位于 {@code src/tools} 源集，不进入应用 jar / 安装包。
 */
public final class LegacyConfigSync {

    /**
     * 一条版本映射：现代版（Java/main 分支）→ 旧版（Python/python 分支）。
     *
     * @param kind          配置类别：{@code global} 或 {@code sw}
     * @param modernVersion 现代版版本号（如 v2 / v10）
     * @param legacyVersion 旧版版本号（如 v1 / v9）
     */
    private record Mapping(String kind, String modernVersion, String legacyVersion) {

        String sourceName() {
            return "original_remote_" + kind + "_" + modernVersion + ".json";
        }

        String targetName() {
            return "original_remote_" + kind + "_" + legacyVersion + ".json";
        }
    }

    /** 版本映射表 —— 新增或调整版本时**只改这里**。 */
    private static final List<Mapping> MAPPINGS = List.of(
            new Mapping("global", "v2", "v1"),
            new Mapping("sw", "v10", "v9"));

    /** 配置所在子目录（两侧工程同名）. */
    private static final String SCRIPTS_DIR = "scripts";

    private LegacyConfigSync() {}

    public static void main(String[] args) {
        Path javaRoot = Path.of(args.length > 0 ? args[0] : ".").toAbsolutePath().normalize();
        Path pythonRoot = resolve(args.length > 1 ? args[1] : "../MultiWeChatManager", javaRoot);
        try {
            int changed = run(javaRoot, pythonRoot);
            System.out.println("同步完成，变更文件数: " + changed);
        } catch (Exception e) {
            System.err.println("[错误] 同步失败: " + e.getMessage());
            System.exit(1);
        }
    }

    /**
     * 把现代版工程中的 JSON 同步到旧版工程。
     *
     * @param javaRoot   现代版工程根目录（源）
     * @param pythonRoot 旧版工程根目录（目标）
     * @return 实际发生变更的文件数（内容一致的映射不计入）
     * @throws IOException 读写失败
     */
    public static int run(Path javaRoot, Path pythonRoot) throws IOException {
        Path sourceDir = javaRoot.resolve(SCRIPTS_DIR);
        Path targetDir = pythonRoot.resolve(SCRIPTS_DIR);
        Files.createDirectories(targetDir);

        int changed = 0;
        for (Mapping mapping : MAPPINGS) {
            Path source = sourceDir.resolve(mapping.sourceName());
            Path target = targetDir.resolve(mapping.targetName());
            if (!Files.exists(source)) {
                System.out.println("  [跳过] 源文件不存在: " + source);
                continue;
            }

            String legacyJson = adapt(mapping, Files.readString(source, StandardCharsets.UTF_8));
            if (Files.exists(target) && Files.readString(target, StandardCharsets.UTF_8).equals(legacyJson)) {
                System.out.printf("  [一致] %-32s ← %s%n", mapping.targetName(), mapping.sourceName());
                continue;
            }
            Files.writeString(target, legacyJson, StandardCharsets.UTF_8);
            System.out.printf("  [同步] %-32s ← %s%n", mapping.targetName(), mapping.sourceName());
            changed++;
        }
        return changed;
    }

    /**
     * 版本适配：现代版 JSON → 旧版 JSON。
     *
     * <p>当前两版 schema 完全一致，直接原样返回（不做 JSON 解析/重排，避免字段顺序与空白变化）。
     *
     * <p>格式分化时在此按 {@code mapping.kind()} / {@code mapping.modernVersion()} 分支处理，例如：
     * <pre>
     *   if (mapping.kind().equals("global") &amp;&amp; mapping.modernVersion().equals("v3")) {
     *       ObjectNode node = (ObjectNode) MAPPER.readTree(modernJson);
     *       node.remove("new_field");        // 旧版不认识的字段
     *       return MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(node);
     *   }
     * </pre>
     *
     * @param mapping   当前映射
     * @param modernJson 现代版 JSON 原文
     * @return 旧版 JSON 原文
     */
    private static String adapt(Mapping mapping, String modernJson) {
        return modernJson;
    }

    /**
     * 解析路径：相对路径按现代版工程根目录解析。
     *
     * @param raw      原始路径
     * @param javaRoot 现代版工程根目录
     * @return 规范化后的绝对路径
     */
    private static Path resolve(String raw, Path javaRoot) {
        Path path = Path.of(raw);
        return (path.isAbsolute() ? path : javaRoot.resolve(path)).normalize();
    }
}
