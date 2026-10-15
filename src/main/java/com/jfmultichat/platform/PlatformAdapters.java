package com.jfmultichat.platform;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * **平台适配器的加载器**（约定优于配置 ✓）—— 业务代码只问它"这个平台用哪个适配器" ✓.
 *
 * <p>约定（用户 2026-10-14 的要求：外部类扩展、没写就走默认 ✓）：
 * <pre>
 *   com.jfmultichat.platform.adapt.{平台id}Adaptation
 *   例：WeChat  → com.jfmultichat.platform.adapt.WeChatAdaptation
 *       Weixin  → com.jfmultichat.platform.adapt.WeixinAdaptation
 *       QQNT    → com.jfmultichat.platform.adapt.QQNTAdaptation
 * </pre>
 * <ul>
 *   <li>类**存在** → 用它（没覆盖的方法自动走接口默认 ✓✓ 这就是他要的"没写同名方法就走默认" ✓）</li>
 *   <li>类**不存在** → 用默认适配器 ✓（接口全默认 ✓，不会报错、不会中断 ✓）</li>
 *   <li>**新增平台 = 丢一个类进去** ✓ —— 注册表、业务代码、配置文件**都不用改** ✓</li>
 * </ul>
 *
 * <p>加载结果**缓存** ✓（切窗链路上会频繁问 ✓ 不能每次都反射 ✓）；
 * 失败的加载也缓存 ✓（避免反复抛异常 ✓）。
 */
public final class PlatformAdapters {

    private static final Logger LOG = LoggerFactory.getLogger(PlatformAdapters.class);

    /** 适配类所在包（约定 ✓） */
    private static final String PKG = "com.jfmultichat.platform.adapt.";

    /**
     * 平台 id → 适配类名 的**别名表**（只在"该平台要借用另一个平台的适配"时才需要 ✓）.
     * <p>⚠️ 用户 2026-10-14 澄清 ✓：**有"蒙一圈颜色"副作用的是新版微信 `Weixin`** ✓、
     * `WeChat` 是**旧版**微信 ✓ —— 所以这里**没有** {@code Weixin→WeChat} 的别名 ✗，
     * 两个平台各走各的（旧版 WeChat 没建专属类 → 自动走**默认适配器** ✓）。
     */
    private static final Map<String, String> ALIAS = Map.of(
            "QQ", "QQNT");     // 老 QQ 暂时按 QQNT 处理（将来单独建 QQAdaptation 即可自动生效 ✓）

    /** 默认适配器（接口全默认 ✓ 单例 ✓） */
    private static final PlatformAdapter DEFAULT = new PlatformAdapter() { };

    private static final Map<String, PlatformAdapter> CACHE = new ConcurrentHashMap<>();
    private static final java.util.Set<String> FAILED = ConcurrentHashMap.newKeySet();

    private PlatformAdapters() {}

    /** 取某平台的适配器（永远不返回 null ✓） */
    public static PlatformAdapter of(String sw) {
        if (sw == null || sw.isBlank()) return DEFAULT;
        PlatformAdapter cached = CACHE.get(sw);
        if (cached != null) return cached;
        if (FAILED.contains(sw)) return DEFAULT;

        String simple = ALIAS.getOrDefault(sw, sw);
        // 本名优先 ✓（平台自己建了 WeixinAdaptation 就该用它 ✓），别名只作兜底 ✓
        String[] candidates = simple.equals(sw) ? new String[]{sw} : new String[]{sw, simple};
        for (String name : candidates) {
            if (name == null || name.isBlank()) continue;
            try {
                Class<?> c = Class.forName(PKG + name + "Adaptation");
                Object o = c.getDeclaredConstructor().newInstance();
                if (o instanceof PlatformAdapter ad) {
                    CACHE.put(sw, ad);
                    LOG.info("[适配] 平台 {} → {} ✓", sw, c.getSimpleName());
                    return ad;
                }
                LOG.warn("[适配] {} 没实现 PlatformAdapter → 用默认 ✓", c.getName());
                break;
            } catch (ClassNotFoundException e) {
                // 继续试下一个候选 ✓
            } catch (Throwable t) {
                LOG.warn("[适配] 加载 {} 失败（用默认 ✓）: {}", name, t.toString());
                break;
            }
        }
        FAILED.add(sw);
        LOG.info("[适配] 平台 {} 没有专属适配类 → 用默认适配器 ✓", sw);
        return DEFAULT;
    }

    /** 给测试/诊断用：列出已成功加载的平台 ✓ */
    public static java.util.Set<String> loaded() {
        return java.util.Set.copyOf(CACHE.keySet());
    }
}
