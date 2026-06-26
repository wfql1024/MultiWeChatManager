package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 配置访问包装器 — 提供统一的配置读取接口
 * <p>
 * 对应 Python: SwInfoFuncCore 中的 get_remote_sw, get_sw_setting,
 * get_sw_acc_data, update_sw_settings, update_sw_acc_data,
 * fetch_sw_setting_or_set_default, save_and_check_changed
 *
 * 依赖: Jackson (JSON 解析)
 */
public final class SwConfigAccessor {

    private static final Logger LOG = LoggerFactory.getLogger(SwConfigAccessor.class);
    private SwConfigAccessor() {
        throw new UnsupportedOperationException("SwConfigAccessor requires a Provider");
    }

    // ==================== 配置提供者接口 ====================

    /**
     * 配置提供者 — 由外部注入，实现实际的配置读写
     */
    public interface Provider {
        /** 获取远程 SW 配置: getRemoteSw(sw, *addr, **kwargs) */
        JsonNode getRemoteSw(String sw, String... addr);

        /** 获取远程 SW 配置: 返回指定键的值，或 kwargs 中的默认值 */
        JsonNode getRemoteSw(String sw, Map<String, Object> kwargs);

        /** 获取本地 SW 设置: getSwSetting(sw, *addr, **kwargs) */
        JsonNode getSwSetting(String sw, String... addr);

        /** 获取本地 SW 设置: 返回指定键的值，或 kwargs 中的默认值 */
        JsonNode getSwSetting(String sw, Map<String, Object> kwargs);

        /** 更新本地 SW 设置: updateSwSettings(sw, *frontAddr, **kwargs) */
        void updateSwSettings(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs);

        /** 获取账号数据: getSwAccData(sw, *addr, **kwargs) */
        JsonNode getSwAccData(String sw, String... addr);

        /** 获取账号数据: 返回指定键的值，或 kwargs 中的默认值 */
        JsonNode getSwAccData(String sw, Map<String, Object> kwargs);

        /** 更新账号数据: updateSwAccData(sw, *frontAddr, **kwargs) */
        void updateSwAccData(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs);

        /** 清除节点: clearSwAccData(sw, *addr) */
        void clearSwAccData(String sw, String... addr);

        /** 获取缓存: getSwCache() */
        ObjectNode getSwCache();

        /** 设置缓存: setSwCache(data) */
        void setSwCache(ObjectNode data);

        /** 保存并检查变化: saveAndCheckChanged(sw, key, value) */
        boolean saveAndCheckChanged(String sw, String key, Object value);

        /** 获取或设置默认值: fetchOrSetDefault(sw, key, enumCls) */
        JsonNode fetchOrSetDefault(String sw, String key, String enumCls);
    }

    private final Provider provider;

    public SwConfigAccessor(Provider provider) {
        this.provider = provider;
    }

    // ==================== 远程配置读取 ====================

    /**
     * 获取远程 SW 配置（简化版：sw + 路径键）
     * 对应 Python: get_remote_sw(sw, *addr) (L62)
     *
     * @param sw   软件标识
     * @param addr 路径键，如 "revoke", "channels"
     * @return JsonNode；不存在返回 null
     */
    public JsonNode getRemoteSw(String sw, String... addr) {
        return provider.getRemoteSw(sw, addr);
    }

    /**
     * 获取远程 SW 配置（kwargs 版：返回指定键或默认值）
     * 对应 Python: get_remote_sw(sw, **kwargs)
     *
     * @param sw     软件标识
     * @param kwargs 键名 -> 默认值，如 {RemoteSwKey.EXE: null}
     * @return JsonNode
     */
    public JsonNode getRemoteSw(String sw, Map<String, Object> kwargs) {
        return provider.getRemoteSw(sw, kwargs);
    }

    /**
     * 获取远程 SW 配置并解包为单一值
     * 对应 Python: exe, = cls.get_remote_sw(sw, **{RemoteSwKey.EXE: None})
     *
     * @param sw     软件标识
     * @param kwargs 键名 -> 默认值
     * @return 配置值（已解包为单一 JsonNode）
     */
    public JsonNode getRemoteSwSingle(String sw, Map<String, Object> kwargs) {
        JsonNode result = provider.getRemoteSw(sw, kwargs);
        if (result == null) return null;
        // 如果结果是数组（Python 的 tuple 解包），取第一个元素
        if (result.isArray() && result.size() == 1) {
            return result.get(0);
        }
        return result;
    }

    // ==================== 本地设置读取 ====================

    /**
     * 获取本地 SW 设置
     * 对应 Python: get_sw_setting(sw, *addr) (L66)
     *
     * @param sw   软件标识
     * @param addr 路径键
     * @return JsonNode
     */
    public JsonNode getSwSetting(String sw, String... addr) {
        return provider.getSwSetting(sw, addr);
    }

    /**
     * 获取本地 SW 设置（kwargs 版）
     * 对应 Python: get_sw_setting(sw, **kwargs)
     */
    public JsonNode getSwSetting(String sw, Map<String, Object> kwargs) {
        return provider.getSwSetting(sw, kwargs);
    }

    /**
     * 获取已保存的路径
     * 对应 Python: get_saved_path_of_ (L668-L673)
     *
     * @param sw       软件标识
     * @param pathType 路径类型
     * @return 路径字符串；无效则 null
     */
    public String getSavedPathOf(String sw, String pathType) {
        Map<String, Object> kwargs = new LinkedHashMap<>();
        kwargs.put(pathType, null);
        JsonNode path = provider.getSwSetting(sw, kwargs);
        if (path != null && path.isTextual()) {
            String pathStr = path.asText();
            if (isValidPath(pathStr)) {
                return pathStr;
            }
        }
        return null;
    }

    /**
     * 优先获取已保存路径，没有则检测
     * 对应 Python: try_get_path_of_ (L659-L666)
     *
     * @param sw       软件标识
     * @param pathType 路径类型
     * @return 路径字符串；检测失败返回 null
     */
    public String tryGetPathOf(String sw, String pathType) {
        String saved = getSavedPathOf(sw, pathType);
        if (saved != null) return saved;
        // 检测逻辑由 SwPathDetective 实现，此处返回 null 让调用方处理
        return null;
    }

    /**
     * 获取本地设置的字符串值（便捷方法）
     */
    public String getSwSettingAsString(String sw, String key, String defaultValue) {
        JsonNode node = provider.getSwSetting(sw, Map.of(key, null));
        if (node != null && node.isTextual()) return node.asText();
        return defaultValue;
    }

    // ==================== 配置更新 ====================

    /**
     * 更新本地 SW 设置
     * 对应 Python: update_sw_settings (L70)
     */
    public void updateSwSettings(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs) {
        provider.updateSwSettings(sw, frontAddr, kwargs);
    }

    /**
     * 更新账号数据
     * 对应 Python: update_sw_acc_data (L89)
     */
    public void updateSwAccData(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs) {
        provider.updateSwAccData(sw, frontAddr, kwargs);
    }

    /**
     * 保存并检查变化
     * 对应 Python: save_and_check_changed (L78)
     *
     * @param sw    软件标识
     * @param key   配置键
     * @param value 配置值
     * @return true 如果值发生了变化
     */
    public boolean saveAndCheckChanged(String sw, String key, Object value) {
        return provider.saveAndCheckChanged(sw, key, value);
    }

    /**
     * 清除账号数据节点
     * 对应 Python: clear_sw_acc_data (L94)
     */
    public void clearSwAccData(String sw, String... addr) {
        provider.clearSwAccData(sw, addr);
    }

    // ==================== 账号数据读取 ====================

    /**
     * 获取账号数据
     * 对应 Python: get_sw_acc_data (L86)
     */
    public JsonNode getSwAccData(String sw, String... addr) {
        return provider.getSwAccData(sw, addr);
    }

    /**
     * 获取账号数据（kwargs 版）
     */
    public JsonNode getSwAccData(String sw, Map<String, Object> kwargs) {
        return provider.getSwAccData(sw, kwargs);
    }

    // ==================== 缓存操作 ====================

    /**
     * 获取 SwCache 数据
     */
    public ObjectNode getSwCache() {
        return provider.getSwCache();
    }

    /**
     * 设置 SwCache 数据
     */
    public void setSwCache(ObjectNode data) {
        provider.setSwCache(data);
    }

    /**
     * 获取或设置默认值
     * 对应 Python: fetch_sw_setting_or_set_default (L74)
     */
    public JsonNode fetchOrSetDefault(String sw, String key, String enumCls) {
        return provider.fetchOrSetDefault(sw, key, enumCls);
    }

    // ==================== 路径验证 ====================

    /**
     * 验证路径合法性
     * 对应 Python: PathUtils.is_valid_path
     */
    public static boolean isValidPath(String path) {
        if (path == null || path.isBlank()) return false;
        // 至少包含一个盘符冒号（Windows 路径）或斜杠
        return path.matches("^[A-Za-z]:.*") || path.contains("/");
    }

    // ==================== 便捷方法 ====================

    /**
     * 从远程配置获取列表字段，确保返回列表
     * 对应 Python 中常见的: list, = cls.get_remote_sw(sw, **{Key: []})
     */
    public List<String> getRemoteSwAsList(String sw, String key, List<String> defaultValue) {
        Map<String, Object> kwargs = new LinkedHashMap<>();
        kwargs.put(key, null);
        JsonNode node = provider.getRemoteSw(sw, kwargs);
        LOG.info("[远程配置] sw={}, key={}, node={}", sw, key, node);
        if (node == null) return defaultValue;
        if (node.isArray()) {
            List<String> result = new ArrayList<>();
            node.forEach(n -> { if (n.isTextual()) result.add(n.asText()); });
            return result;
        }
        return defaultValue;
    }

    /**
     * 从远程配置获取字符串字段
     */
    public String getRemoteSwAsString(String sw, String key, String defaultValue) {
        Map<String, Object> kwargs = new LinkedHashMap<>();
        kwargs.put(key, null);
        JsonNode node = provider.getRemoteSw(sw, kwargs);
        if (node != null && node.isTextual()) return node.asText();
        return defaultValue;
    }

    /**
     * 从远程配置获取布尔字段
     */
    public Boolean getRemoteSwAsBoolean(String sw, String key, Boolean defaultValue) {
        Map<String, Object> kwargs = new LinkedHashMap<>();
        kwargs.put(key, null);
        JsonNode node = provider.getRemoteSw(sw, kwargs);
        if (node != null && node.isBoolean()) return node.asBoolean();
        return defaultValue;
    }
}
