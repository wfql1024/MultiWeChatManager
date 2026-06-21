package com.jfmultichat.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * 远程配置获取器 — 对应 Python AppFuncCore.force_fetch_remote_encrypted_cfg.
 * <p>
 * 从远程 URL 下载加密的配置文件，解密后保存到本地用户数据目录.
 * 支持多个 URL 回退（用户自定义 URL + 内置 Gitee/GitHub URL）.
 */
public final class RemoteConfigFetcher {

    private static final Logger LOG = LoggerFactory.getLogger(RemoteConfigFetcher.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .followRedirects(HttpClient.Redirect.NORMAL)
            .build();

    /** 命名空间常量 */
    public static final String NS_REMOTE_SW = "RemoteSw";
    public static final String NS_REMOTE_GLOBAL = "RemoteGlobal";

    /** 内置 URL（与旧版 Python 一致） */
    private static final String REMOTE_SW_GITEE =
            "https://gitee.com/wfql1024/MultiWeChatManager/raw/main/remote_configs/remote_sw_v9";
    private static final String REMOTE_SW_GITHUB =
            "https://raw.githubusercontent.com/wfql1024/MultiWeChatManager/main/remote_configs/remote_sw_v9";
    private static final String REMOTE_GLOBAL_GITEE =
            "https://gitee.com/wfql1024/MultiWeChatManager/raw/main/remote_configs/remote_global_v1";
    private static final String REMOTE_GLOBAL_GITHUB =
            "https://raw.githubusercontent.com/wfql1024/MultiWeChatManager/main/remote_configs/remote_global_v1";

    private RemoteConfigFetcher() {}

    /** 获取内置远程全局配置 URL 列表（供前端占位文字使用） */
    public static String[] getBuiltinRemoteGlobalUrls() {
        return new String[]{REMOTE_GLOBAL_GITEE, REMOTE_GLOBAL_GITHUB};
    }

    /** 获取内置远程平台配置 URL 列表（供前端占位文字使用） */
    public static String[] getBuiltinRemoteSwUrls() {
        return new String[]{REMOTE_SW_GITEE, REMOTE_SW_GITHUB};
    }

    /**
     * 尝试获取远程配置（先读本地缓存，失败则联网下载）.
     *
     * @param ns 命名空间: {@link #NS_REMOTE_SW} 或 {@link #NS_REMOTE_GLOBAL}
     * @return 解析后的 JSON，失败返回 null
     */
    public static JsonNode tryReadRemoteConfig(String ns) {
        // 1. 先尝试本地缓存
        Path localPath = getLocalPath(ns);
        if (Files.exists(localPath)) {
            try {
                String json = Files.readString(localPath);
                if (!json.isBlank()) {
                    LOG.info("Loaded {} from local cache: {}", ns, localPath);
                    return MAPPER.readTree(json);
                }
            } catch (Exception e) {
                LOG.warn("Failed to read local {} cache, will try download", ns);
            }
        }

        // 2. 联网下载
        ConfigManager cm = ConfigManager.getInstance();
        String userUrl;
        String[] builtinUrls;

        if (NS_REMOTE_SW.equals(ns)) {
            var urls = cm.getRootConfig().getRemoteSwUrls();
            userUrl = urls.isEmpty() ? "" : urls.get(0);
            builtinUrls = new String[]{REMOTE_SW_GITEE, REMOTE_SW_GITHUB};
        } else {
            var urls = cm.getRootConfig().getRemoteGlobalUrls();
            userUrl = urls.isEmpty() ? "" : urls.get(0);
            builtinUrls = new String[]{REMOTE_GLOBAL_GITEE, REMOTE_GLOBAL_GITHUB};
        }

        JsonNode result = forceFetchRemoteEncryptedConfig(ns, userUrl, builtinUrls);
        if (result != null) {
            // 保存到本地
            try {
                Files.writeString(localPath, MAPPER.writeValueAsString(result));
                LOG.info("Saved {} to local cache: {}", ns, localPath);
            } catch (Exception e) {
                LOG.error("Failed to save {} to local cache", ns, e);
            }
        } else {
            // 下载失败 — 如果有本地缓存就用本地
            if (Files.exists(localPath)) {
                try {
                    String json = Files.readString(localPath);
                    if (!json.isBlank()) {
                        LOG.info("Using stale local cache for {}", ns);
                        return MAPPER.readTree(json);
                    }
                } catch (Exception ex) {
                    LOG.error("Failed to read local cache fallback", ex);
                }
            }
        }
        return result;
    }

    /**
     * 强制从远程下载加密配置并解密.
     * 对应 Python force_fetch_remote_encrypted_cfg.
     *
     * @param ns           命名空间
     * @param userUrl      用户自定义 URL
     * @param builtinUrls  内置回退 URL
     * @return 解密后的 JSON，失败返回 null
     */
    private static JsonNode forceFetchRemoteEncryptedConfig(
            String ns, String userUrl, String[] builtinUrls) {

        // 组装 URL 列表（去重）
        Set<String> seen = new LinkedHashSet<>();
        List<String> urls = new ArrayList<>();
        if (userUrl != null && !userUrl.isBlank()) {
            urls.add(userUrl);
            seen.add(userUrl);
        }
        for (String url : builtinUrls) {
            if (!seen.contains(url)) {
                urls.add(url);
                seen.add(url);
            }
        }

        LOG.info("Fetching {} from {} source(s)...", ns, urls.size());

        for (String url : urls) {
            try {
                LOG.info("Trying: {}", url);
                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(url))
                        .timeout(Duration.ofSeconds(10))
                        .GET()
                        .build();

                HttpResponse<String> response = HTTP.send(request,
                        HttpResponse.BodyHandlers.ofString());

                if (response.statusCode() == 200) {
                    String body = response.body();
                    if (body == null || body.isBlank()) {
                        LOG.warn("Empty response from {}", url);
                        continue;
                    }

                    // 解密
                    String decrypted = CryptoUtils.decryptResponse(body);
                    if (decrypted == null || decrypted.isBlank()) {
                        LOG.warn("Decrypted empty content from {}", url);
                        continue;
                    }

                    JsonNode json = MAPPER.readTree(decrypted);
                    LOG.info("Successfully fetched and decrypted {} from {}", ns, url);
                    return json;
                } else {
                    LOG.warn("HTTP {} from {}", response.statusCode(), url);
                }
            } catch (java.net.http.HttpTimeoutException e) {
                LOG.warn("Timeout fetching {}: {}", url, e.getMessage());
            } catch (java.io.IOException e) {
                LOG.warn("Network error fetching {}: {}", url, e.getMessage());
            } catch (Exception e) {
                LOG.error("Failed to fetch/decode {}: {}", url, e.getMessage());
            }
        }

        LOG.warn("All sources exhausted for {}", ns);
        return null;
    }

    /**
     * 获取本地缓存路径
     */
    private static Path getLocalPath(String ns) {
        Path userDir = ConfigManager.getInstance().getUserDataPath();
        if (NS_REMOTE_SW.equals(ns)) {
            return userDir.resolve("remote_sw_config.json");
        } else {
            return userDir.resolve("remote_global_config.json");
        }
    }
}
