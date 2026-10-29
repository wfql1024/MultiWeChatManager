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

    private static final com.fasterxml.jackson.databind.ObjectMapper MAPPER =
            new com.fasterxml.jackson.databind.ObjectMapper();

    /** 与仓库里既有 JSON 的排版保持一致：4 空格缩进、冒号后的单空格分隔 */
    private static final com.fasterxml.jackson.databind.ObjectWriter PRETTY = buildPrettyWriter();

    private static com.fasterxml.jackson.databind.ObjectWriter buildPrettyWriter() {
        com.fasterxml.jackson.core.util.DefaultIndenter indenter =
                new com.fasterxml.jackson.core.util.DefaultIndenter("    ", "\n");
        com.fasterxml.jackson.core.util.DefaultPrettyPrinter printer =
                new com.fasterxml.jackson.core.util.DefaultPrettyPrinter()
                        .withSeparators(new com.fasterxml.jackson.core.util.Separators()
                                .withObjectFieldValueSpacing(
                                        com.fasterxml.jackson.core.util.Separators.Spacing.AFTER));
        printer.indentObjectsWith(indenter);
        printer.indentArraysWith(indenter);
        return MAPPER.writer(printer);
    }

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

    /**
     * 版本映射表 —— 新增或调整版本时**只改这里**。
     *
     * <p>原则（用户 2026-10-23 明确）：
     * <ol>
     *   <li>每个已发布的旧版 JSON **结构不可改动** —— 旧客户端写死了版本号和解析方式；</li>
     *   <li>同步 = **按旧版已有结构去填充内容**；旧版结构表达不了的内容**直接丢弃**；</li>
     *   <li>多条映射按版本**级联**：v10→v9→v8…，每一步都以前一步的产物为输入。</li>
     * </ol>
     *
     * <p>已确认的结构差异（2026-10-23 实测对比 key 路径）：
     * <ul>
     *   <li><b>sw v10 → v9</b>：仅 {@code channels.<ch>.relation}（渠道级关系）是 v10 新增；
     *       v9 只有 {@code features[].patch_rules[]} 里 {@code type=relation} 的写法 → 搬进去即可</li>
     *   <li><b>global v2 → v1</b>：结构完全一致 → 原样直通</li>
     *   <li><b>setting v8 → v7</b>（尚未实现，无 main 侧源）：v8 用 {@code channels.<ch>.features[]}，
     *       v7 用 {@code channels.<ch>.feature_ver_adaptations.<ver>[]}（按版本分组）</li>
     *   <li><b>setting v7 → v4</b>（尚未实现）：v4 更老 —— {@code mode.channel.<ch>} + {@code mode.feature.<ver>.<ch>}
     *       + {@code mode.precise.<ver>} 的平面结构，信息量明显更少，只能填它支持的部分</li>
     * </ul>
     */
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
        if (!"sw".equals(mapping.kind())) return modernJson;
        try {
            com.fasterxml.jackson.databind.JsonNode root = MAPPER.readTree(modernJson);
            boolean changed = false;
            // 结构：{平台: {模式: {channels: {渠道: {...}}}}}
            for (com.fasterxml.jackson.databind.JsonNode swNode : root) {
                if (!swNode.isObject()) continue;
                for (com.fasterxml.jackson.databind.JsonNode modeNode : swNode) {
                    com.fasterxml.jackson.databind.JsonNode channels = modeNode.get("channels");
                    if (channels == null || !channels.isObject()) continue;
                    java.util.Iterator<java.util.Map.Entry<String, com.fasterxml.jackson.databind.JsonNode>> it =
                            channels.fields();
                    while (it.hasNext()) {
                        com.fasterxml.jackson.databind.JsonNode chNode = it.next().getValue();
                        if (!(chNode instanceof com.fasterxml.jackson.databind.node.ObjectNode ch)) continue;
                        // 新版把 relation 提到渠道级；旧版( python )只认 patch_rules 里的 relation 规则
                        com.fasterxml.jackson.databind.JsonNode rel = ch.remove("relation");
                        if (rel == null || !rel.isObject()) continue;
                        com.fasterxml.jackson.databind.JsonNode features = ch.get("features");
                        if (features == null || !features.isArray() || features.isEmpty()) continue;
                        com.fasterxml.jackson.databind.node.ObjectNode feature =
                                (com.fasterxml.jackson.databind.node.ObjectNode) features.get(0);
                        com.fasterxml.jackson.databind.node.ArrayNode rules =
                                feature.withArray("patch_rules");
                        com.fasterxml.jackson.databind.node.ObjectNode rule = MAPPER.createObjectNode();
                        rule.put("type", "relation");
                        if (rel.has("ver_adaptations")) rule.set("ver_adaptations", rel.get("ver_adaptations"));
                        rules.add(rule);
                        changed = true;
                    }
                }
            }
            if (!changed) return modernJson;
            // Jackson 把空对象/空数组写成 " { } " / " [ ] "，仓库里的排版是 "{}" / "[]" → 归一化，避免无意义 diff
            return PRETTY.writeValueAsString(root)
                    .replace("{ }", "{}")
                    .replace("[ ]", "[]");
        } catch (Exception e) {
            throw new IllegalStateException("同步失败：无法解析 " + mapping.sourceName() + " -> " + e.getMessage(), e);
        }
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
