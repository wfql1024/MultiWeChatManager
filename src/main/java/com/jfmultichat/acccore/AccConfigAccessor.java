package com.jfmultichat.acccore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;

/**
 * 账号信息访问器 — 读写 SwAccData.json 中的账号级别数据
 * <p>
 * 对应 Python: SwAccData().get_(sw, acc, *addr, **kwargs) 等
 */
public final class AccConfigAccessor {

    private static final Logger LOG = LoggerFactory.getLogger(AccConfigAccessor.class);
    private static final com.jfmultichat.config.ConfigManager CM =
            com.jfmultichat.config.ConfigManager.getInstance();

    public AccConfigAccessor() {}

    /**
     * 获取账号数据
     * 对应 Python: SwAccData().get_(sw, acc, *addr, **kwargs)
     *
     * @param sw   软件标识
     * @param acc  账号 ID
     * @param addr 路径键（可为空）
     * @return JsonNode；不存在返回 null
     */
    public JsonNode getSwAccData(String sw, String acc, String... addr) {
        Map<String, ObjectNode> accMap = CM.getAccountMap(sw);
        if (accMap.isEmpty()) return null;
        ObjectNode accNode = accMap.get(acc);
        if (accNode == null) return null;
        if (addr.length == 0) return accNode;
        JsonNode node = accNode;
        for (String key : addr) {
            if (node == null || !node.isObject()) return null;
            node = node.get(key);
        }
        return node;
    }

    /**
     * 更新账号数据
     * 对应 Python: SwAccData().update_(sw, acc, *addr, **kwargs)
     *
     * @param sw      软件标识
     * @param acc     账号 ID
     * @param kwargs  key → value 更新对
     */
    public void updateSwAccData(String sw, String acc, Map<String, Object> kwargs) {
        CM.updateAccount(sw, acc, kwargs);
    }

    /**
     * 清除账号数据节点
     * 对应 Python: SwAccData().clear_node(sw, *addr)
     */
    public void clearSwAccData(String sw, String acc, String... addr) {
        if (addr.length == 0) {
            // 清空整个账号节点
            CM.getAccountMap(sw);
            // SwAccData 使用 ObjectNode，此处简化：移除该账号
            LOG.info("[Acc] clearSwAccData stub for sw={}, acc={}", sw, acc);
            return;
        }
        Map<String, ObjectNode> accMap = CM.getAccountMap(sw);
        ObjectNode accNode = accMap.get(acc);
        if (accNode == null) return;
        JsonNode node = accNode;
        for (int i = 0; i < addr.length - 1; i++) {
            if (node.isObject()) node = node.get(addr[i]);
            else return;
        }
        if (node.isObject()) ((ObjectNode) node).remove(addr[addr.length - 1]);
        try {
            CM.saveAll();
        } catch (Exception e) {
            LOG.warn("[Acc] 保存失败: {}", e.getMessage());
        }
    }

    /**
     * 删除账号节点
     */
    public boolean deleteAccount(String sw, String acc) {
        return CM.deleteAccount(sw, acc);
    }

    /**
     * 获取所有账号列表
     */
    public List<String> getAllAccounts(String sw) {
        List<String> result = new ArrayList<>();
        Map<String, ObjectNode> accMap = CM.getAccountMap(sw);
        result.addAll(accMap.keySet());
        return result;
    }
}
