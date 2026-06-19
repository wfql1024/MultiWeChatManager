package com.jfmultichat.setting;

import com.fasterxml.jackson.databind.JsonNode;
import com.jfmultichat.model.*;

import java.io.File;
import java.util.*;
import java.util.logging.Level;

/**
 * 远程全局配置 — 对应 Python RemoteGlobal(AbsSetting).
 * <p>
 * 从本地 JSON 文件 {@code remote_global_v1} 读取远程下发的全局配置，
 * 包含：应用名、作者、支持平台列表、关于信息、更新信息。
 * <p>
 * READ-ONLY — 不可通过本类修改配置。
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
     * 设置数据文件路径（由应用初始化时调用）
     */
    public void setDataFile(File file) {
        this.dataFile = file;
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
                LOG.log(Level.WARNING, "Failed to parse reference entry: " + item, e);
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
                LOG.log(Level.WARNING, "Failed to parse sponsor entry: " + item, e);
            }
        });
        return list;
    }
}
