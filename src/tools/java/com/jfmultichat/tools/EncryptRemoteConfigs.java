package com.jfmultichat.tools;

import com.jfmultichat.config.CryptoUtils;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 远程配置加密工具。
 *
 * <p>把指定工程目录下 {@code scripts/original_remote_&lt;global|sw&gt;_&lt;vN&gt;.json} 加密为
 * {@code remote_configs/remote_&lt;global|sw&gt;_&lt;vN&gt;}（客户端按 URL 直接下载的发布产物）。
 *
 * <p>加密实现直接复用应用侧的 {@link CryptoUtils#encryptAndAppendKey}，与
 * {@link CryptoUtils#decryptResponse} 同源，格式不会各自漂移。
 *
 * <p>运行方式：
 * <pre>
 *   gradle encryptRemoteConfigs              # 本工程（Java/main 分支使用的 v2/v10）
 *   gradle publishRemoteConfigs              # 一键：本工程 + Python 工程（v1/v9）
 *   java -cp ... EncryptRemoteConfigs &lt;工程根目录&gt;
 * </pre>
 *
 * <p>本类位于 {@code src/tools} 源集，不进入应用 jar / 安装包。
 */
public final class EncryptRemoteConfigs {

    /** 输入文件名规则：{@code original_remote_<global|sw>_<vN>.json}. */
    private static final Pattern INPUT_PATTERN =
            Pattern.compile("^original_remote_(global|sw)_(v\\d+)\\.json$");

    /** 输入目录（相对工程根目录）. */
    private static final String INPUT_DIR = "scripts";

    /** 输出目录（相对工程根目录）—— 客户端远端配置 URL 指向此处. */
    private static final String OUTPUT_DIR = "remote_configs";

    /** key 随机部分的字符集（对应 Python {@code string.ascii_letters + string.digits}）. */
    private static final String KEY_ALPHABET =
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

    /** key 随机部分长度（Python 版为 15，末尾再补 {@code =} 凑足 16）. */
    private static final int KEY_RANDOM_LENGTH = 15;

    private static final SecureRandom RANDOM = new SecureRandom();

    private EncryptRemoteConfigs() {}

    public static void main(String[] args) {
        Path repoRoot = Path.of(args.length > 0 ? args[0] : ".").toAbsolutePath().normalize();
        try {
            run(repoRoot, null);
        } catch (Exception e) {
            System.err.println("[错误] 加密失败: " + e.getMessage());
            System.exit(1);
        }
    }

    /**
     * 加密一个工程下的全部远程配置源文件。
     *
     * @param repoRoot 工程根目录（其下需有 {@code scripts/}，输出到其 {@code remote_configs/}）
     * @param fixedKey 指定密钥（null 表示每次随机生成）
     * @return 本次使用的密钥
     * @throws Exception 读写失败、加密失败或未找到任何输入文件
     */
    public static String run(Path repoRoot, String fixedKey) throws Exception {
        Path inputDir = repoRoot.resolve(INPUT_DIR);
        Path outputDir = repoRoot.resolve(OUTPUT_DIR);

        List<Path> inputs = listInputs(inputDir);
        if (inputs.isEmpty()) {
            throw new IOException(inputDir + " 下没有 original_remote_<global|sw>_<vN>.json");
        }
        Files.createDirectories(outputDir);

        String key = fixedKey != null ? fixedKey : randomKey(KEY_RANDOM_LENGTH) + "=";
        System.out.println("[" + repoRoot.getFileName() + "] 密钥: " + key);

        for (Path input : inputs) {
            Matcher matcher = INPUT_PATTERN.matcher(input.getFileName().toString());
            if (!matcher.matches()) continue;
            String outputName = "remote_" + matcher.group(1) + "_" + matcher.group(2);

            // 与 Python 侧一致：以通用换行方式读取（CRLF → LF）后再加密
            String json = Files.readString(input, StandardCharsets.UTF_8).replace("\r\n", "\n");
            String encrypted = CryptoUtils.encryptAndAppendKey(json, key);

            Files.writeString(outputDir.resolve(outputName), encrypted, StandardCharsets.UTF_8);
            System.out.printf("  [加密] %-32s → %-18s (%d 字符)%n",
                    input.getFileName(), outputName, encrypted.length());
        }
        return key;
    }

    /**
     * 列出输入目录中符合命名规则的文件，按文件名字典序返回（保证多次运行的输出顺序稳定）。
     *
     * @param inputDir 输入目录
     * @return 输入文件列表；目录不存在时返回空列表
     * @throws IOException 读取目录失败
     */
    public static List<Path> listInputs(Path inputDir) throws IOException {
        List<Path> result = new ArrayList<>();
        if (!Files.isDirectory(inputDir)) return result;
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(inputDir)) {
            for (Path path : stream) {
                if (Files.isRegularFile(path) && INPUT_PATTERN.matcher(path.getFileName().toString()).matches()) {
                    result.add(path);
                }
            }
        }
        result.sort(Comparator.comparing(path -> path.getFileName().toString()));
        return result;
    }

    /**
     * 生成随机 key 片段。
     *
     * @param length 字符数
     * @return 大小写字母 + 数字组成的随机串
     */
    private static String randomKey(int length) {
        StringBuilder sb = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            sb.append(KEY_ALPHABET.charAt(RANDOM.nextInt(KEY_ALPHABET.length())));
        }
        return sb.toString();
    }
}
