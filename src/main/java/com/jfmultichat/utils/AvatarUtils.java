package com.jfmultichat.utils;

import com.jfmultichat.config.ConfigManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.imageio.ImageIO;
import javax.swing.*;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Base64;
import java.util.Random;
import java.util.concurrent.Executors;

/**
 * 头像工具类 — 获取账号头像，逻辑与旧版 Python AccInfoFuncCore.get_acc_avatar_from_files 保持一致.
 * <p>
 * 获取顺序：
 * 1. 优先读取本地文件 {user_dir}/{sw}/{acc}/{acc}.jpg
 * 2. 若不存在且提供了 avatar_url（以 /0 结尾），尝试下载至该路径
 * 3. 若下载成功则返回 base64，否则生成文字头像（SVG 格式，样式同左栏平台图标）
 */
public final class AvatarUtils {

    private static final Logger LOG = LoggerFactory.getLogger(AvatarUtils.class);
    private static final int SIZE = 32; // 头像尺寸，与 Config.AVT_SIZE 一致
    private static final ThreadLocal<Base64.Encoder> BASE64_ENCODER =
            ThreadLocal.withInitial(() -> Base64.getEncoder());

    private AvatarUtils() {}

    /**
     * 获取账号头像的 data URL (base64 编码或 SVG).
     * @param sw 软件标识 (如 "WeChat")
     * @param acc 账号 id (如 "wxid_xxx")
     * @param avatarUrl 可能的头像 URL（通常来自账号数据的 avatar_url 字段）
     * @return data:image/jpeg;base64,... 或 data:image/svg+xml,...；若失败则返回空字符串
     */
    public static String getAvatarDataUrl(String sw, String acc, String avatarUrl) {
        if (sw == null || sw.isBlank() || acc == null || acc.isBlank()) {
            LOG.info("[头像] 空 sw 或 acc, 返回文字头像: sw={}, acc={}", sw, acc);
            return generateTextAvatarSvgFallback("?");
        }

        try {
            // 使用 ConfigManager 获取实际的用户数据目录（支持用户设置）
            ConfigManager cm = ConfigManager.getInstance();
            if (cm == null || cm.getUserDataPath() == null) {
                LOG.warn("[头像] ConfigManager 未初始化，使用默认路径");
                throw new IOException("ConfigManager not initialized");
            }
            String userDir = cm.getUserDataPath().toString().replace('\\', '/');
            String avatarPath = buildAvatarPath(userDir, sw, acc);
            File avatarFile = new File(avatarPath);

            LOG.info("[头像] 检查文件: path={}, exists={}", avatarPath, avatarFile.exists());

            // 1. 优先读取本地文件
            if (avatarFile.exists()) {
                try {
                    String data = encodeToDataUrl(avatarFile);
                    LOG.info("[头像] 成功读取本地头像: {}", avatarPath);
                    return data;
                } catch (IOException e) {
                    LOG.error("[头像] 本地文件读取失败: {} - {}", avatarPath, e.getMessage(), e);
                }
            }

            // 2. 尝试从 URL 下载（仅当 avatarUrl 以 /0 结尾时）
            String urlToUse = (avatarUrl != null && !avatarUrl.isBlank()) ? avatarUrl : "";
            if (urlToUse.endsWith("/0")) {
                LOG.info("[头像] 尝试从 URL 下载头像: {} -> {}", urlToUse, avatarPath);
                boolean downloaded = downloadImage(urlToUse, avatarPath);
                if (downloaded) {
                    avatarFile = new File(avatarPath); // 重新获取 File 对象
                    LOG.info("[头像] 下载后文件存在: {}", avatarFile.exists());
                    if (avatarFile.exists()) {
                        try {
                            String data = encodeToDataUrl(avatarFile);
                            LOG.info("[头像] 成功编码下载的头像");
                            return data;
                        } catch (IOException e) {
                            LOG.error("[头像] 下载后编码失败: {}", e.getMessage(), e);
                        }
                    }
                } else {
                    LOG.warn("[头像] 头像下载失败: {}", urlToUse);
                }
            }

            // 3. 回退：生成文字头像（SVG 格式，样式同左栏平台图标）
            String displayName = generateDisplayName(acc, avatarUrl);
            LOG.info("[头像] 生成文字头像替代方案: displayName=\"{}\"", displayName);
            return generateTextAvatarSvg(displayName);

        } catch (Exception e) {
            LOG.error("[头像] 获取头像时发生异常: {}", e.getMessage(), e);
            return generateTextAvatarSvgFallback("?");
        }
    }

    private static String buildAvatarPath(String userDir, String sw, String acc) {
        return userDir + "/" + sw + "/" + acc + "/" + acc + ".jpg";
    }

    private static boolean downloadImage(String urlStr, String filePath) {
        try {
            URL url = new URL(urlStr);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(5000);
            conn.setRequestMethod("GET");

            if (conn.getResponseCode() != 200) {
                LOG.warn("[头像] HTTP 下载失败: " + url + ", code=" + conn.getResponseCode());
                return false;
            }

            File file = new File(filePath);
            File parentDir = file.getParentFile();
            if (parentDir != null && !parentDir.exists()) {
                parentDir.mkdirs();
            }

            // 使用字节流写入
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(file)) {
                byte[] buffer = new byte[8192];
                int bytesRead;
                while ((bytesRead = conn.getInputStream().read(buffer)) != -1) {
                    out.write(buffer, 0, bytesRead);
                }
            }
            conn.disconnect();
            LOG.info("[头像] 下载成功: {} -> {}", urlStr, filePath);
            return true;
        } catch (Exception e) {
            LOG.warn("[头像] 下载异常: " + e.getMessage(), e);
            return false;
        }
    }

    private static String encodeToDataUrl(File file) throws IOException {
        try {
            byte[] bytes = java.nio.file.Files.readAllBytes(java.nio.file.Path.of(file.getPath()));
            String encoded = BASE64_ENCODER.get().encodeToString(bytes);
            return "data:image/jpeg;base64," + encoded;
        } catch (IOException e) {
            throw new IOException("无法读取头像文件: " + file.getPath(), e);
        }
    }

    /**
     * 生成文字头像的 SVG 格式（直接作为 img src），包含圆角矩形背景和首字母.
     * 样式完全匹配左栏平台图标，但使用硬编码颜色以便在 img 中可见.
     */
    private static String generateTextAvatarSvg(String text) {
        try {
            // 取首字符作为头像文字（参考左栏平台图标逻辑）
            String displayChar = text != null && text.length() > 0
                ? text.substring(0, 1).toUpperCase() : "?";

            // 生成 SVG，使用硬编码颜色确保在 img 中可见
            // 深灰色背景 + 白色文字，与留白风格一致
            StringBuilder sb = new StringBuilder();
            sb.append("data:image/svg+xml,");
            sb.append("<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24' ")
              .append("fill='#555' stroke='#aaa' stroke-width='2'>");
            sb.append("<rect x='3' y='3' width='18' height='18' rx='4' ry='4'/>");
            sb.append("<text x='12' y='16' text-anchor='middle' font-size='10' fill='white' stroke='none'>")
              .append(escapeSvg(displayChar)).append("</text></svg>");
            return sb.toString();
        } catch (Exception e) {
            LOG.warn("[头像] 生成标准 SVG 头像失败: " + e.getMessage());
            return generateTextAvatarSvgFallback(text);
        }
    }

    private static String generateTextAvatarSvgFallback(String text) {
        try {
            String displayChar = text != null && text.length() > 0
                ? text.substring(0, 1).toUpperCase() : "?";
            return "data:image/svg+xml," +
                "<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24'>" +
                "<rect x='3' y='3' width='18' height='18' rx='4' ry='4' fill='#555' stroke='#aaa'/>" +
                "<text x='12' y='16' text-anchor='middle' font-size='10' fill='white' stroke='none'>" +
                escapeSvg(displayChar) + "</text></svg>";
        } catch (Exception e) {
            LOG.warn("[头像] 回退生成也失败", e);
            return "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32'><rect width='100%25' height='100%25' fill='%23888' rx='4'/><text x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='white' font-size='16'>?</text></svg>";
        }
    }

    private static String escapeSvg(String s) {
        if (s == null) return "";
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;");
        s = s.replace("'", "&#39;");
        return s;
    }

    private static String generateDisplayName(String acc, String avatarUrl) {
        // 旧版逻辑：取 acc 的第一个字符作为头像占位文本
        if (acc != null && acc.length() > 0) {
            return acc.substring(0, 1).toUpperCase();
        }
        return "?";
    }

    /**
     * 异步下载头像（用于账号列表刷新时不阻塞 UI）.
     * @param sw 软件标识
     * @param acc 账号 id
     * @param avatarUrl 头像 URL
     * @param callback 完成回调，包含 dataUrl 或错误信息
     */
    public static void downloadAvatarAsync(String sw, String acc, String avatarUrl,
                                           java.util.function.Consumer<String> callback) {
        Executors.newSingleThreadExecutor().submit(() -> {
            try {
                ConfigManager cm = ConfigManager.getInstance();
                if (cm == null || cm.getUserDataPath() == null) {
                    callback.accept(generateTextAvatarSvgFallback("?"));
                    return;
                }
                String userDir = cm.getUserDataPath().toString().replace('\\', '/');
                String avatarPath = buildAvatarPath(userDir, sw, acc);
                File avatarFile = new File(avatarPath);

                LOG.info("[头像异步] 检查文件: path={}, exists={}", avatarPath, avatarFile.exists());

                // 先检查是否已有
                if (avatarFile.exists()) {
                    LOG.info("[头像异步] 文件已存在，直接编码");
                    callback.accept(encodeToDataUrl(avatarFile));
                    return;
                }

                // 尝试下载
                String urlToUse = (avatarUrl != null && !avatarUrl.isBlank()) ? avatarUrl : "";
                if (urlToUse.endsWith("/0")) {
                    LOG.info("[头像异步] 尝试下载头像: {} -> {}", urlToUse, avatarPath);
                    boolean downloaded = downloadImage(urlToUse, avatarPath);
                    if (downloaded) {
                        avatarFile = new File(avatarPath);
                        LOG.info("[头像异步] 下载后文件存在: {}", avatarFile.exists());
                        if (avatarFile.exists()) {
                            callback.accept(encodeToDataUrl(avatarFile));
                            return;
                        }
                    }
                }

                // 失败则生成文字头像
                String displayName = generateDisplayName(acc, avatarUrl);
                LOG.info("[头像异步] 生成文字头像替代方案");
                callback.accept(generateTextAvatarSvg(displayName));
            } catch (Exception e) {
                LOG.error("[头像异步] 处理失败", e);
                callback.accept(generateTextAvatarSvgFallback("?"));
            }
        });
    }
}
