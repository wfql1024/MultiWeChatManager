package com.jfmultichat.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.IOException;
import java.nio.file.Path;

/**
 * 统一配置存储接口 — 所有本地/远程配置文件通过此接口读写.
 * 内部以 JSON ObjectNode 存储，对外暴露字典式读写方法.
 */
public interface IConfigStore {

    /** 配置文件路径 */
    Path getFilePath();

    /** 获取整个配置为 ObjectNode（可修改） */
    ObjectNode getData();

    /** 用 ObjectNode 替换整个配置 */
    void setData(ObjectNode data);

    /** 从磁盘重新加载 */
    void reload() throws IOException;

    /** 保存到磁盘 */
    void save() throws IOException;

    /** 文件是否存在 */
    boolean exists();

    // ---- 字典式访问 ----

    default String getString(String key, String defaultVal) {
        JsonNode n = getData().get(key);
        return (n != null && !n.isNull()) ? n.asText() : defaultVal;
    }

    default boolean getBoolean(String key, boolean defaultVal) {
        JsonNode n = getData().get(key);
        return (n != null && !n.isNull()) ? n.asBoolean(defaultVal) : defaultVal;
    }

    default int getInt(String key, int defaultVal) {
        JsonNode n = getData().get(key);
        return (n != null && !n.isNull()) ? n.asInt(defaultVal) : defaultVal;
    }

    default void put(String key, Object value) {
        if (value == null) {
            getData().remove(key);
        } else {
            getData().putPOJO(key, value);
        }
    }

    default void remove(String key) {
        getData().remove(key);
    }

    default boolean has(String key) {
        return getData().has(key);
    }

    default boolean isEmpty() {
        return getData().isEmpty();
    }

    default void ensureFile() throws IOException {
        if (!exists()) {
            save();
        }
    }
}
