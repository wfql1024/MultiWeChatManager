package com.jfmultichat.model;

import java.util.List;
import java.util.Map;

/**
 * "关于"页数据 — 对应 remote_global JSON 的 about 节点.
 * <p>
 * 字段来源：
 * <ul>
 *   <li>home — 作者主页链接 (B站/GitHub/Gitee)</li>
 *   <li>project — 项目主页链接</li>
 *   <li>thanks — 鸣谢列表</li>
 *   <li>reference — 技术参考列表</li>
 *   <li>sponsor — 赞助列表</li>
 * </ul>
 */
public record AboutInfo(
        Map<String, LinkEntry> home,
        Map<String, LinkEntry> project,
        Map<String, LinkEntry> thanks,
        List<ReferenceEntry> reference,
        List<SponsorEntry> sponsor
) {
    public static AboutInfo empty() {
        return new AboutInfo(Map.of(), Map.of(), Map.of(), List.of(), List.of());
    }
}
