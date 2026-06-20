package com.jfmultichat.setting;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.util.Optional;

/**
 * 抽象设置基类 — 对应 Python 的 AbsSetting.
 * <p>
 * 封装 JSON 文件读写，提供类似 Python dict 的嵌套路径访问方式：
 * {@code get("about", "home", "bilibili") → 对应 JSON 的 about.home.bilibili 节点}
 * <p>
 * 子类通常为单例，各自对应一个 JSON 文件。
 */
public abstract class AbsSetting {

    protected final Logger LOG = LoggerFactory.getLogger(getClass());
    protected final ObjectMapper mapper = new ObjectMapper();

    protected JsonNode data;
    protected File dataFile;

    /**
     * 从文件加载 JSON → JsonNode 树（类似 Python dict）
     */
    public synchronized JsonNode load() {
        if (dataFile == null || !dataFile.exists()) {
            LOG.warn("Data file not found: {}", dataFile);
            data = mapper.createObjectNode();
            return data;
        }
        try {
            data = mapper.readTree(dataFile);
            return data;
        } catch (IOException e) {
            LOG.error("Failed to load JSON: {}", dataFile, e);
            data = mapper.createObjectNode();
            return data;
        }
    }

    /**
     * 按路径获取嵌套 JsonNode，路径为空则返回整个 data.
     * <p>
     * 对应 Python 的 {@code get(*addr)}。
     */
    public Optional<JsonNode> get(String... path) {
        load();
        JsonNode current = data;
        for (String key : path) {
            if (current == null || !current.has(key)) return Optional.empty();
            current = current.get(key);
        }
        return Optional.ofNullable(current);
    }

    /**
     * 获取字符串值
     */
    public String getString(String... path) {
        return get(path).map(JsonNode::asText).orElse("");
    }

    /**
     * 获取字符串值（带默认值，在路径前以提高区分度）
     */
    public String getStringOr(String defaultVal, String... path) {
        return get(path).map(JsonNode::asText).orElse(defaultVal);
    }

    /**
     * 重新加载并返回 data
     */
    public JsonNode reload() {
        return load();
    }
}
