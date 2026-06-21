package com.jfmultichat.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * JSON 文件配置存储基类.
 * 封装 Jackson 读写 + 字典访问的默认实现.
 */
public class JsonConfigStore implements IConfigStore {

    private static final Logger LOG = LoggerFactory.getLogger(JsonConfigStore.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    protected final Path filePath;
    protected ObjectNode data;

    /** 创建并立即从磁盘加载 */
    public JsonConfigStore(Path filePath) {
        this.filePath = filePath;
        this.data = MAPPER.createObjectNode();
        try {
            if (Files.exists(filePath)) {
                reload();
            }
        } catch (IOException e) {
            LOG.warn("Failed to load {}, using empty", filePath, e);
        }
    }

    /** 创建空配置（不加载磁盘，用于后续 setData） */
    public JsonConfigStore(Path filePath, ObjectNode initialData) {
        this.filePath = filePath;
        this.data = (initialData != null) ? initialData : MAPPER.createObjectNode();
    }

    @Override
    public Path getFilePath() {
        return filePath;
    }

    @Override
    public ObjectNode getData() {
        return data;
    }

    @Override
    public void setData(ObjectNode data) {
        this.data = (data != null) ? data : MAPPER.createObjectNode();
    }

    @Override
    public boolean exists() {
        return Files.exists(filePath);
    }

    @Override
    public void reload() throws IOException {
        if (Files.exists(filePath)) {
            String json = Files.readString(filePath);
            if (!json.isBlank()) {
                data = (ObjectNode) MAPPER.readTree(json);
                return;
            }
        }
        data = MAPPER.createObjectNode();
    }

    @Override
    public void save() throws IOException {
        AppPaths.ensureDir(filePath.getParent());
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(filePath.toFile(), data);
    }

    /** 从 JSON 字符串加载并替换当前数据 */
    public void loadFromJson(String json) throws IOException {
        if (json != null && !json.isBlank()) {
            data = (ObjectNode) MAPPER.readTree(json);
        } else {
            data = MAPPER.createObjectNode();
        }
    }

    /** 导出为格式化的 JSON 字符串 */
    public String toJson() {
        try {
            return MAPPER.writeValueAsString(data);
        } catch (Exception e) {
            LOG.warn("Failed to serialize config: {}", filePath, e);
            return "{}";
        }
    }

    /** 浅拷贝当前数据 */
    public ObjectNode deepCopy() {
        return data.deepCopy();
    }

    // ---- 批量子节点访问 ----

    /** 获取子节点（如 local_sw 下的某个 swId 节点） */
    public ObjectNode getSubNode(String key) {
        var node = data.get(key);
        if (node != null && node.isObject()) return (ObjectNode) node;
        ObjectNode created = MAPPER.createObjectNode();
        data.set(key, created);
        return created;
    }

    /** 设置子节点 */
    public void setSubNode(String key, ObjectNode sub) {
        data.set(key, sub != null ? sub : MAPPER.createObjectNode());
    }

    /** 删除子节点 */
    public boolean removeSubNode(String key) {
        return data.remove(key) != null;
    }

    /** 枚举所有一级键 */
    public java.util.Iterator<String> fieldNames() {
        return data.fieldNames();
    }
}
