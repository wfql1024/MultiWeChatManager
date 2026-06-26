package com.jfmultichat.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.locks.ReadWriteLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * JSON 文件配置存储基类.
 * 封装 Jackson 读写 + 字典访问的默认实现.
 * <p>
 * 每次 getData() 调用都会先从磁盘重新加载，保证读取到最新文件内容。
 * 使用读写锁保证多线程安全：写操作独占，读操作共享。
 */
public class JsonConfigStore implements IConfigStore {

    private static final Logger LOG = LoggerFactory.getLogger(JsonConfigStore.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();

    protected final Path filePath;
    protected ObjectNode data;
    private final ReadWriteLock rwLock = new ReentrantReadWriteLock();

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
        // 每次读取都从磁盘重新加载，保证拿到最新内容
        rwLock.readLock().lock();
        try {
            try {
                reloadInternal();
            } catch (IOException e) {
                LOG.warn("Failed to reload {} on read, using stale data", filePath, e);
            }
            return data;
        } finally {
            rwLock.readLock().unlock();
        }
    }

    @Override
    public void setData(ObjectNode data) {
        rwLock.writeLock().lock();
        try {
            this.data = (data != null) ? data : MAPPER.createObjectNode();
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    @Override
    public boolean exists() {
        return Files.exists(filePath);
    }

    /** 内部重载，不获取锁（由外部方法在持有锁后调用） */
    private void reloadInternal() throws IOException {
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
    public void reload() throws IOException {
        rwLock.writeLock().lock();
        try {
            reloadInternal();
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    @Override
    public void save() throws IOException {
        rwLock.writeLock().lock();
        try {
            // 先持久化 caller 在 getData() 返回后做的修改
            AppPaths.ensureDir(filePath.getParent());
            MAPPER.writerWithDefaultPrettyPrinter().writeValue(filePath.toFile(), data);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    /** 从 JSON 字符串加载并替换当前数据 */
    public void loadFromJson(String json) throws IOException {
        rwLock.writeLock().lock();
        try {
            if (json != null && !json.isBlank()) {
                data = (ObjectNode) MAPPER.readTree(json);
            } else {
                data = MAPPER.createObjectNode();
            }
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    /** 导出为格式化的 JSON 字符串 */
    public String toJson() {
        rwLock.readLock().lock();
        try {
            return MAPPER.writeValueAsString(data);
        } catch (Exception e) {
            LOG.warn("Failed to serialize config: {}", filePath, e);
            return "{}";
        } finally {
            rwLock.readLock().unlock();
        }
    }

    /** 浅拷贝当前数据 */
    public ObjectNode deepCopy() {
        rwLock.readLock().lock();
        try {
            return data.deepCopy();
        } finally {
            rwLock.readLock().unlock();
        }
    }

    // ---- 批量子节点访问 ----

    /** 获取子节点（如 local_sw 下的某个 swId 节点） */
    public ObjectNode getSubNode(String key) {
        rwLock.writeLock().lock();
        try {
            var node = data.get(key);
            if (node != null && node.isObject()) return (ObjectNode) node;
            ObjectNode created = MAPPER.createObjectNode();
            data.set(key, created);
            return created;
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    /** 设置子节点 */
    public void setSubNode(String key, ObjectNode sub) {
        rwLock.writeLock().lock();
        try {
            data.set(key, sub != null ? sub : MAPPER.createObjectNode());
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    /** 删除子节点 */
    public boolean removeSubNode(String key) {
        rwLock.writeLock().lock();
        try {
            return data.remove(key) != null;
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    /** 枚举所有一级键 */
    public java.util.Iterator<String> fieldNames() {
        rwLock.readLock().lock();
        try {
            return data.fieldNames();
        } finally {
            rwLock.readLock().unlock();
        }
    }
}
