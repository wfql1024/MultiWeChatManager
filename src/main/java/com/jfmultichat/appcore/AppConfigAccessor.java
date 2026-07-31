package com.jfmultichat.appcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

import com.jfmultichat.config.ConfigManager;
import com.jfmultichat.config.AppPaths;

/**
 * App 配置访问器 — 读写 RootConfig、LocalGlobalConfig、RemoteGlobal、RemoteSw
 * <p>
 * 对应 Python: RootSetting, LocalSetting(GLOBAL_SECTION), RemoteSw, RemoteGlobal
 * <p>
 * 通过 ConfigManager 单例直接操作，不依赖 BridgeConfigProvider。
 */
public final class AppConfigAccessor {

    private static final Logger LOG = LoggerFactory.getLogger(AppConfigAccessor.class);
    private static final ConfigManager CM = ConfigManager.getInstance();

    public AppConfigAccessor() {}

    // ==================== 用户目录 ====================

    /**
     * 获取用户数据目录（UserFiles/DevUserFiles 完整路径）
     */
    public String getUserDir() {
        return CM.getUserDataPath().toString();
    }

    // ==================== RootConfig 读写 ====================

    /**
     * 获取 RootConfig 字段
     * 对应 Python: RootSetting().get_(*addr, **kwargs)
     */
    public JsonNode getRootConfig(String... addr) {
        com.jfmultichat.config.RootConfig rc = CM.getRootConfig();
        if (rc == null || addr.length == 0) return null;
        try {
            String methodName = "get" + capitalize(addr[0]);
            java.lang.reflect.Method m = com.jfmultichat.config.RootConfig.class.getMethod(methodName);
            Object val = m.invoke(rc);
            return convertToJsonNode(val);
        } catch (Exception e) {
            LOG.warn("[AppConfig] getRootConfig.{} failed: {}", addr[0], e.getMessage());
            return null;
        }
    }

    /**
     * 更新 RootConfig 字段
     * 对应 Python: RootSetting().update_(*front_addr, **kwargs)
     */
    public void updateRootConfig(Map<String, Object> kwargs) {
        com.jfmultichat.config.RootConfig rc = CM.getRootConfig();
        if (rc == null) return;
        for (Map.Entry<String, Object> entry : kwargs.entrySet()) {
            try {
                String setterName = "set" + capitalize(entry.getKey());
                java.lang.reflect.Method setter = com.jfmultichat.config.RootConfig.class
                        .getMethod(setterName, entry.getValue().getClass());
                setter.invoke(rc, entry.getValue());
            } catch (Exception e) {
                LOG.warn("[AppConfig] updateRootConfig.{} failed: {}", entry.getKey(), e.getMessage());
            }
        }
        try {
            CM.saveAll();
        } catch (Exception e) {
            LOG.error("[AppConfig] saveRootConfig failed: {}", e.getMessage());
        }
    }

    // ==================== RemoteSw 读写 ====================

    /**
     * 获取远程平台配置节点
     * 对应 Python: RemoteSw().get_(*addr, **kwargs)
     */
    public JsonNode getRemoteSw(String sw, String... addr) {
        ObjectNode data = CM.getRemoteSw();
        if (data == null || !data.has(sw)) return null;
        JsonNode node = data.get(sw);
        for (String key : addr) {
            if (node == null || !node.isObject()) return null;
            node = node.get(key);
        }
        return node;
    }

    /**
     * 获取远程平台配置（kwargs 版）
     */
    public JsonNode getRemoteSw(String sw, Map<String, Object> kwargs) {
        JsonNode swNode = getRemoteSw(sw);
        return resolveKwargs(swNode, kwargs);
    }

    /**
     * 设置远程平台配置
     */
    public void setRemoteSw(ObjectNode data) {
        CM.setRemoteSw(data);
    }

    // ==================== RemoteGlobal 读写 ====================

    /**
     * 获取远程全局配置节点
     * 对应 Python: RemoteGlobal().get_(*addr, **kwargs)
     */
    public JsonNode getRemoteGlobal(String... addr) {
        ObjectNode data = CM.getRemoteGlobal();
        if (data == null) return null;
        JsonNode node = data;
        for (String key : addr) {
            if (node == null || !node.isObject()) return null;
            node = node.get(key);
        }
        return node;
    }

    public void setRemoteGlobal(ObjectNode data) {
        CM.setRemoteGlobal(data);
    }

    // ==================== LocalGlobalConfig 读写 ====================

    /**
     * 获取本地全局设置
     * 对应 Python: LocalSetting().get_(GLOBAL_SECTION, *addr, **kwargs)
     */
    public JsonNode getGlobalSetting(String... addr) {
        ObjectNode data = CM.getGlobalConfig();
        if (data == null) return null;
        JsonNode node = data;
        for (String key : addr) {
            if (node == null || !node.isObject()) return null;
            node = node.get(key);
        }
        return node;
    }

    /**
     * 更新本地全局设置
     * 对应 Python: LocalSetting().update_(GLOBAL_SECTION, *front_addr, **kwargs)
     */
    public void updateGlobalSetting(Map<String, Object> kwargs) {
        CM.updateGlobalConfig(kwargs);
    }

    /**
     * 获取或设置默认值
     * 对应 Python: fetch_or_set_default_or_none(GLOBAL_SECTION, key, enum_cls)
     */
    public JsonNode fetchOrSetDefaultGlobal(String key, Object defaultValue) {
        ObjectNode global = CM.getGlobalConfig();
        JsonNode existing = global.get(key);
        if (existing != null && !existing.isNull()) {
            return existing;
        }
        if (defaultValue != null) {
            global.put(key, defaultValue.toString());
            try {
                CM.saveAll();
            } catch (Exception e) {
                LOG.warn("[AppConfig] 保存全局设置失败: {}", e.getMessage());
            }
        }
        return global.get(key);
    }

    /**
     * 保存并检查变化
     * 对应 Python: save_and_check_changed(GLOBAL_SECTION, key, value)
     */
    public boolean saveAndCheckChangedGlobal(String key, Object value) {
        try {
            ObjectNode global = CM.getGlobalConfig();
            JsonNode existing = global.get(key);
            String oldVal = existing != null ? existing.asText("") : "";
            String newVal = value != null ? value.toString() : "";
            if (oldVal.equals(newVal)) return false;
            if (value == null) {
                global.remove(key);
            } else {
                global.put(key, newVal);
            }
            CM.saveAll();
            return true;
        } catch (Exception e) {
            LOG.error("[AppConfig] saveAndCheckChangedGlobal failed: {}", e.getMessage());
            return false;
        }
    }

    // ==================== Sw 级本地配置 ====================

    /**
     * 获取 SW 本地配置
     * 对应 Python: LocalSetting().get_(sw, *addr, **kwargs)
     */
    public JsonNode getSwSetting(String sw, String... addr) {
        ObjectNode swConfig = CM.getSwConfig(sw);
        if (swConfig == null) return null;
        JsonNode node = swConfig;
        for (String key : addr) {
            if (node == null || !node.isObject()) return null;
            node = node.get(key);
        }
        return node;
    }

    /**
     * 更新 SW 本地配置
     */
    public void updateSwSetting(String sw, Map<String, Object> kwargs) {
        CM.updateSwConfig(sw, kwargs);
    }

    /**
     * 获取或设置默认值
     */
    public JsonNode fetchOrSetDefaultSw(String sw, String key, Object defaultValue) {
        ObjectNode swConfig = CM.getSwConfig(sw);
        if (swConfig == null) return defaultValue != null ? convertToJsonNode(defaultValue) : null;
        JsonNode existing = swConfig.get(key);
        if (existing != null && !existing.isNull()) {
            return existing;
        }
        if (defaultValue != null) {
            swConfig.put(key, defaultValue.toString());
            try {
                CM.saveAll();
            } catch (Exception e) {
                LOG.warn("[AppConfig] 保存 SW 设置失败: {}", e.getMessage());
            }
        }
        return swConfig.get(key);
    }

    // ==================== 账号数据 ====================

    /**
     * 获取账号数据
     * 对应 Python: SwAccData().get_(sw, *addr, **kwargs)
     */
    public JsonNode getSwAccData(String sw, String... addr) {
        Map<String, ObjectNode> accMap = CM.getAccountMap(sw);
        if (accMap.isEmpty() && addr.length == 0) return null;
        if (addr.length == 0) {
            // 返回整个 sw 的账号字典
            ObjectNode combined = convertToNode(accMap);
            return combined;
        }
        String accId = addr[0];
        ObjectNode accNode = accMap.get(accId);
        if (accNode == null) return null;
        if (addr.length == 1) return accNode;
        JsonNode node = accNode;
        for (int i = 1; i < addr.length; i++) {
            if (node.isObject()) node = node.get(addr[i]);
            else return null;
        }
        return node;
    }

    /**
     * 更新账号数据
     */
    public void updateSwAccData(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs) {
        String accId = frontAddr != null && !frontAddr.isEmpty()
                ? new ArrayList<>(frontAddr.values()).get(0) : null;
        if (accId != null) {
            CM.updateAccount(sw, accId, kwargs);
        }
    }

    /**
     * 清除账号数据节点
     */
    public void clearSwAccData(String sw, String... addr) {
        if (addr.length == 0) return;
        String accId = addr[0];
        CM.getAccountMap(sw);
        // 简化处理：直接删除整个账号节点
        // TODO: 支持多层路径清除
        LOG.info("[AppConfig] clearSwAccData stub for sw={}, acc={}", sw, accId);
    }

    // ==================== 缓存操作 ====================

    /**
     * 获取适配缓存
     */
    public ObjectNode getSwCache() {
        return CM.getSwCache();
    }

    /**
     * 设置适配缓存
     */
    public void setSwCache(ObjectNode cache) {
        CM.setSwCache(cache);
    }

    // ==================== 工具方法 ====================

    /**
     * 解析 kwargs → JsonNode（单 key 取默认值，多 key 逐层遍历）
     */
    private JsonNode resolveKwargs(JsonNode root, Map<String, Object> kwargs) {
        if (root == null || !root.isObject() || kwargs.isEmpty()) return null;
        if (kwargs.size() == 1) {
            Map.Entry<String, Object> entry = kwargs.entrySet().iterator().next();
            JsonNode node = root.get(entry.getKey());
            if (node != null) return node;
            Object def = entry.getValue();
            return def != null ? convertToJsonNode(def) : null;
        }
        JsonNode cur = root;
        Iterator<Map.Entry<String, Object>> it = kwargs.entrySet().iterator();
        while (it.hasNext()) {
            Map.Entry<String, Object> entry = it.next();
            if (!it.hasNext()) {
                JsonNode node = cur.isObject() ? cur.get(entry.getKey()) : null;
                if (node != null) return node;
                return entry.getValue() != null ? convertToJsonNode(entry.getValue()) : null;
            }
            cur = cur.isObject() ? cur.get(entry.getKey()) : null;
            if (cur == null) return null;
        }
        return null;
    }

    /**
     * 将 Java 对象转为 JsonNode
     */
    @SuppressWarnings("unchecked")
    private JsonNode convertToJsonNode(Object val) {
        if (val == null) return com.fasterxml.jackson.databind.node.NullNode.instance;
        if (val instanceof String) return com.fasterxml.jackson.databind.node.TextNode.valueOf((String) val);
        if (val instanceof Boolean) return com.fasterxml.jackson.databind.node.BooleanNode.valueOf((Boolean) val);
        if (val instanceof Number) {
            Number n = (Number) val;
            return com.fasterxml.jackson.databind.node.LongNode.valueOf(n.longValue());
        }
        if (val instanceof List) {
            com.fasterxml.jackson.databind.node.ArrayNode arr =
                    com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.arrayNode();
            ((List<?>) val).forEach(v -> arr.add(String.valueOf(v)));
            return arr;
        }
        return com.fasterxml.jackson.databind.node.TextNode.valueOf(val.toString());
    }

    /**
     * 将 Map<String, ObjectNode> 转为 ObjectNode
     */
    private ObjectNode convertToNode(Map<String, ObjectNode> map) {
        ObjectNode node = com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode();
        map.forEach(node::set);
        return node;
    }

    private static String capitalize(String s) {
        if (s == null || s.isEmpty()) return s;
        return s.substring(0, 1).toUpperCase() + s.substring(1);
    }
}
