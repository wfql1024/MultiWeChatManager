package com.jfmultichat.acccore;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * 账号操作提供器 — 账号数据的读取和写入操作
 * <p>
 * 通过构造函数注入供 SwAccountOps 使用，避免 acccore → swcore 的循环依赖。
 */
public final class AccOpsProvider {

    private static final AccConfigAccessor ACC_ACCESSOR = new AccConfigAccessor();

    public AccOpsProvider() {}

    /**
     * 获取账号数据
     */
    public JsonNode getSwAccData(String sw, String acc, String... addr) {
        return ACC_ACCESSOR.getSwAccData(sw, acc, addr);
    }

    /**
     * 更新账号数据
     */
    public void updateSwAccData(String sw, String acc, Map<String, Object> kwargs) {
        ACC_ACCESSOR.updateSwAccData(sw, acc, kwargs);
    }

    /**
     * 确保共存账号格式正确
     * 对应 Python: ensure_coexist_acc_formatted
     */
    public void ensureCoexistAccFormatted(String sw, String coexistExe) {
        JsonNode node = ACC_ACCESSOR.getSwAccData(sw, coexistExe);
        if (node == null || !node.isObject()) {
            ACC_ACCESSOR.updateSwAccData(sw, coexistExe, Collections.emptyMap());
            node = ACC_ACCESSOR.getSwAccData(sw, coexistExe);
        }
        var obj = (com.fasterxml.jackson.databind.node.ObjectNode) node;
        if (!obj.has("linked_acc")) ACC_ACCESSOR.updateSwAccData(sw, coexistExe, Map.of("linked_acc", null));
        if (!obj.has("channel")) ACC_ACCESSOR.updateSwAccData(sw, coexistExe, Map.of("channel", null));
        if (!obj.has("ordinals")) ACC_ACCESSOR.updateSwAccData(sw, coexistExe, Map.of("ordinals", null));
    }

    /**
     * 转换为 SwAccountOps 所需的 Provider 接口实现
     * 供外部（如 SwInfoFuncCore）通过构造函数注入
     */
    public com.jfmultichat.swcore.SwAccountOps.AccountOpsProvider toSwProvider() {
        return new com.jfmultichat.swcore.SwAccountOps.AccountOpsProvider() {
            @Override
            public JsonNode getSwAccData(String s, String... a) {
                if (a.length == 0) return null;
                return ACC_ACCESSOR.getSwAccData(s, a[0], Arrays.copyOfRange(a, 1, a.length));
            }
            @Override
            public JsonNode getSwAccData(String s, Map<String, Object> k) { return null; }
            @Override
            public void updateSwAccData(String s, Map<String, String> f, Map<String, Object> k) {
                // f 形如 {账号名: ""}——取 key（账号名），不能取 value（可能是空串）
                String acc = f != null && !f.isEmpty() ? f.keySet().iterator().next() : "";
                ACC_ACCESSOR.updateSwAccData(s, acc, k);
            }
        };
    }
}
