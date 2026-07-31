package com.jfmultichat.config;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.jfmultichat.swcore.SwConfigAccessor;

import java.util.*;

/**
 * 公开的 SwConfigAccessor.Provider 实现 — 供所有包使用
 * <p>
 * 将 ConfigManager 适配为 SwConfigAccessor.Provider 接口。
 * 独立于 JsBridge，供 appcore/acccore 等包引用。
 */
public final class SwConfigProvider implements SwConfigAccessor.Provider {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private SwConfigProvider() {}

    /** 便捷方法：创建基于 ConfigManager 的 SwConfigAccessor */
    public static SwConfigAccessor newAccessor() {
        return new SwConfigAccessor(new SwConfigProvider());
    }

    // ========== kwargs 解析 ==========

    private JsonNode resolveKwargs(JsonNode root, Map<String, Object> kwargs) {
        if (root == null || !root.isObject() || kwargs.isEmpty()) return null;
        if (kwargs.size() == 1) {
            Map.Entry<String, Object> entry = kwargs.entrySet().iterator().next();
            JsonNode node = root.get(entry.getKey());
            if (node != null) return node;
            Object def = entry.getValue();
            return def != null ? MAPPER.valueToTree(def) : null;
        }
        Iterator<Map.Entry<String, Object>> it = kwargs.entrySet().iterator();
        JsonNode cur = root;
        while (it.hasNext()) {
            Map.Entry<String, Object> entry = it.next();
            String key = entry.getKey();
            if (!it.hasNext()) {
                JsonNode node = cur.isObject() ? cur.get(key) : null;
                if (node != null) return node;
                Object def = entry.getValue();
                return def != null ? MAPPER.valueToTree(def) : null;
            }
            cur = cur.isObject() ? cur.get(key) : null;
            if (cur == null) return null;
        }
        return null;
    }

    // ========== SwConfigAccessor.Provider ==========

    @Override
    public JsonNode getRemoteSw(String sw, String... addr) {
        try {
            JsonNode remoteSw = ConfigManager.getInstance().getRemoteSw();
            if (remoteSw == null || !remoteSw.isObject()) return null;
            JsonNode node = remoteSw.get(sw);
            if (node == null || !node.isObject()) return null;
            for (String a : addr) { if (node.isObject()) node = node.get(a); else return null; }
            return node;
        } catch (Exception e) { return null; }
    }

    @Override public JsonNode getRemoteSw(String sw, Map<String, Object> kwargs) {
        JsonNode swNode = ConfigManager.getInstance().getRemoteSw().get(sw);
        return resolveKwargs(swNode, kwargs);
    }
    @Override public JsonNode getSwSetting(String sw, String... addr) {
        try {
            ObjectNode swConfig = ConfigManager.getInstance().getSwConfig(sw);
            JsonNode node = swConfig;
            for (String a : addr) { if (node.isObject()) node = node.get(a); else return null; }
            return node;
        } catch (Exception e) { return null; }
    }
    @Override public JsonNode getSwSetting(String sw, Map<String, Object> kwargs) {
        return resolveKwargs(ConfigManager.getInstance().getSwConfig(sw), kwargs);
    }
    @Override public void updateSwSettings(String sw, Map<String, String> f, Map<String, Object> k) {
        ConfigManager.getInstance().updateSwConfig(sw, k);
    }
    @Override public JsonNode getSwAccData(String sw, String... addr) {
        try {
            Map<String, ObjectNode> accMap = ConfigManager.getInstance().getAccountMap(sw);
            if (accMap.isEmpty() || addr.length == 0) return null;
            ObjectNode accNode = accMap.get(addr[0]);
            if (accNode == null) return null;
            if (addr.length == 1) return accNode;
            JsonNode node = accNode;
            for (int i = 1; i < addr.length; i++) { if (node.isObject()) node = node.get(addr[i]); else return null; }
            return node;
        } catch (Exception e) { return null; }
    }
    @Override public JsonNode getSwAccData(String sw, Map<String, Object> kwargs) {
        Map<String, ObjectNode> accMap = ConfigManager.getInstance().getAccountMap(sw);
        if (accMap.isEmpty()) return null;
        ObjectNode combined = MAPPER.createObjectNode();
        accMap.forEach(combined::set);
        return resolveKwargs(combined, kwargs);
    }
    @Override public void updateSwAccData(String sw, Map<String, String> f, Map<String, Object> k) {
        Map<String, Object> updates = new LinkedHashMap<>(k);
        String accId = f != null && !f.isEmpty() ? f.values().iterator().next() : null;
        if (accId != null) ConfigManager.getInstance().updateAccount(sw, accId, updates);
        else { Map<String, ObjectNode> accMap = ConfigManager.getInstance().getAccountMap(sw);
            if (!accMap.isEmpty()) ConfigManager.getInstance().updateAccount(sw, accMap.keySet().iterator().next(), updates); }
    }
    @Override public void clearSwAccData(String sw, String... addr) {
        if (addr.length == 0) return;
        Map<String, ObjectNode> accMap = ConfigManager.getInstance().getAccountMap(sw);
        ObjectNode accNode = accMap.get(addr[0]);
        if (accNode == null) return;
        if (addr.length == 1) accNode.removeAll();
        else { JsonNode node = accNode;
            for (int i = 1; i < addr.length - 1; i++) node = node.get(addr[i]);
            if (node.isObject()) ((ObjectNode) node).remove(addr[addr.length - 1]); }
        ConfigManager.getInstance().saveAll();
    }
    @Override public ObjectNode getSwCache() { return ConfigManager.getInstance().getSwCache(); }
    @Override public void setSwCache(ObjectNode data) { ConfigManager.getInstance().setSwCache(data); }
    @Override public boolean saveAndCheckChanged(String sw, String key, Object value) {
        try {
            ObjectNode swNode = ConfigManager.getInstance().getSwConfig(sw);
            if (swNode == null) return false;
            JsonNode existing = swNode.get(key);
            if (existing != null && existing.isValueNode()) {
                if (Objects.equals(existing.asText(""), value != null ? value.toString() : "")) return false;
            }
            if (value == null) swNode.remove(key);
            else if (value instanceof Number) swNode.put(key, ((Number) value).longValue());
            else swNode.put(key, value.toString());
            ConfigManager.getInstance().updateSwConfig(sw, Map.of(key, value));
            return true;
        } catch (Exception e) { return false; }
    }
    @Override public JsonNode fetchOrSetDefault(String sw, String key, String enumCls) { return null; }
}
