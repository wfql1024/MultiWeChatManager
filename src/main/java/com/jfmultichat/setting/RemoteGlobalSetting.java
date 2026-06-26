package com.jfmultichat.setting;

import com.fasterxml.jackson.databind.JsonNode;
import com.jfmultichat.config.ConfigManager;
import com.jfmultichat.model.*;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * 远程全局配置 — 对应 Python RemoteGlobal(AbsSetting).
 * <p>
 * 从远程下载的配置缓存中读取全局配置（只读），
 * 包含：应用名、作者、支持 Sw 列表、关于信息.
 * <p>
 * 首次使用时会检查 {@code {user_data_path}/RemoteGlobalConfig.json}，
 * 若不存在则从 classpath 种子数据 {@code data/remote_global_v1.json} 加载.
 */
public class RemoteGlobalSetting extends AbsSetting {

    private static RemoteGlobalSetting instance;

    private RemoteGlobalSetting() {}

    public static synchronized RemoteGlobalSetting getInstance() {
        if (instance == null) {
            instance = new RemoteGlobalSetting();
        }
        return instance;
    }

    /**
     * 从 ConfigManager 的 user_data_path 加载数据，不存在时回退到种子文件.
     */
    @Override
    public synchronized JsonNode load() {
        // 优先读取 user_data_path/RemoteGlobalConfig.json
        Path remotePath = ConfigManager.getInstance().getUserDataPath()
                .resolve("RemoteGlobalConfig.json");
        dataFile = remotePath.toFile();

        if (dataFile.exists()) {
            try {
                data = mapper.readTree(dataFile);
                return data;
            } catch (IOException e) {
                LOG.warn("Failed to read RemoteGlobalConfig.json from user_data_path, falling back to seed", e);
            }
        }

        // 回退到 classpath 种子数据
        try (InputStream is = getClass().getResourceAsStream("/data/remote_global_v1.json")) {
            if (is != null) {
                data = mapper.readTree(is);
                LOG.info("Loaded remote global config from classpath seed");
                return data;
            }
        } catch (IOException e) {
            LOG.warn("Failed to load remote global seed data", e);
        }

        data = mapper.createObjectNode();
        return data;
    }

    // ========== 类型化访问方法 ==========

    public String getAppName() {
        return getString("app_name");
    }

    public String getAppAuthor() {
        return getString("app_author");
    }

    public List<String> getSupportPlatforms() {
        return get("support_sw")
                .map(node -> {
                    List<String> list = new ArrayList<>();
                    node.forEach(n -> list.add(n.asText()));
                    return list;
                })
                .orElse(List.of());
    }

    /**
     * 获取 "关于" 页数据
     */
    public AboutInfo getAboutInfo() {
        Optional<JsonNode> node = get("about");
        if (node.isEmpty()) return AboutInfo.empty();

        JsonNode about = node.get();
        return new AboutInfo(
                parseLinkMap(about.get("home")),
                parseLinkMap(about.get("project")),
                parseLinkMap(about.get("thanks")),
                parseReferenceList(about.get("reference")),
                parseSponsorList(about.get("sponsor"))
        );
    }

    // ========== 解析辅助方法 ==========

    private Map<String, LinkEntry> parseLinkMap(JsonNode node) {
        if (node == null) return Map.of();
        Map<String, LinkEntry> map = new LinkedHashMap<>();
        node.fields().forEachRemaining(entry ->
            map.put(entry.getKey(), mapper.convertValue(entry.getValue(), LinkEntry.class))
        );
        return map;
    }

    private List<ReferenceEntry> parseReferenceList(JsonNode node) {
        if (node == null || !node.isArray()) return List.of();
        List<ReferenceEntry> list = new ArrayList<>();
        node.forEach(item -> {
            try {
                list.add(mapper.treeToValue(item, ReferenceEntry.class));
            } catch (Exception e) {
                LOG.warn("Failed to parse reference entry: {}", item, e);
            }
        });
        return list;
    }

    private List<SponsorEntry> parseSponsorList(JsonNode node) {
        if (node == null || !node.isArray()) return List.of();
        List<SponsorEntry> list = new ArrayList<>();
        node.forEach(item -> {
            try {
                list.add(mapper.treeToValue(item, SponsorEntry.class));
            } catch (Exception e) {
                LOG.warn("Failed to parse sponsor entry: {}", item, e);
            }
        });
        return list;
    }
}
