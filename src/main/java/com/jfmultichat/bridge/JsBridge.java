package com.jfmultichat.bridge;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.jfmultichat.config.ConfigManager;
import com.jfmultichat.config.RootConfig;
import com.jfmultichat.swcore.SwAdapterChecker;
import com.jfmultichat.swcore.SwConfigAccessor;
import com.jfmultichat.swcore.SwNativeOps;
import com.jfmultichat.swcore.SwPathDetective;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Desktop;
import java.net.URI;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

/**
 * JS ↔ Java 桥接 — 暴露给 JavaScript 的 Java 方法.
 * <p>
 * 通过 {@code JSObject.setMember("javaObject", bridge)} 注入到 WebView，
 * 前端通过 {@code JFC.bridge.call("method")} 或 {@code callWithArgs("method", args...)} 调用.
 * <p>
 * 异步操作使用后台线程池，完成后通过 {@code executeScript} 推送到 JS:
 * {@code JFC.bridge._handleAsync(type, cbId, json)}.
 */
public class JsBridge {

    private static final Logger LOG = LoggerFactory.getLogger(JsBridge.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final ExecutorService THREAD_POOL = Executors.newCachedThreadPool(r -> {
        Thread t = new Thread(r, "JsBridge-worker");
        t.setDaemon(true);
        return t;
    });

    private Consumer<String> scriptExecutor;
    private Consumer<String> themeChangeListener;
    private java.util.function.DoubleConsumer alignListener;

    // ==================== Java→JS 执行 ====================

    public void setScriptExecutor(Consumer<String> executor) {
        this.scriptExecutor = executor;
    }

    /** 注册主题变更监听器（由 MainWindow 调用） */
    public void setThemeChangeListener(Consumer<String> listener) {
        this.themeChangeListener = listener;
    }

    /** 注册 logo 对齐回调（由 MainWindow 调用） */
    public void setAlignListener(java.util.function.DoubleConsumer listener) {
        this.alignListener = listener;
    }

    /** 执行 JS 脚本 */
    public void exec(String script) {
        if (scriptExecutor != null) {
            scriptExecutor.accept(script);
        }
    }

    /** 在 JavaFX 线程上推送结果到 JS 回调 */
    private void pushToJs(String jsCall) {
        if (scriptExecutor != null) {
            javafx.application.Platform.runLater(() -> scriptExecutor.accept(jsCall));
        }
    }

    // ========== 异步操作方法（后台线程 + JS回调） ==========

    /**
     * 异步测试远程 URL.
     * 立即返回，后台线程执行 HTTP+解密+解析，完成后推送结果到 JS.
     *
     * @param url 要测试的 URL
     * @param cbId JS 回调 ID (数字字符串)
     */
    public void testRemoteUrlAsync(String url, String cbId) {
        THREAD_POOL.submit(() -> {
            LOG.info("[测试] 开始测试URL: {}", url);
            try {
                java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                        .connectTimeout(java.time.Duration.ofSeconds(5))
                        .followRedirects(java.net.http.HttpClient.Redirect.NORMAL)
                        .build();
                java.net.http.HttpRequest request = java.net.http.HttpRequest.newBuilder()
                        .uri(URI.create(url))
                        .timeout(java.time.Duration.ofSeconds(10))
                        .GET().build();
                java.net.http.HttpResponse<String> resp = client.send(request,
                        java.net.http.HttpResponse.BodyHandlers.ofString());
                LOG.info("[测试] HTTP {} ({}), body长度={}",
                        resp.statusCode(), resp.uri(),
                        resp.body() != null ? resp.body().length() : 0);
                if (resp.statusCode() != 200) {
                    LOG.warn("[测试] 失败: HTTP {}", resp.statusCode());
                    pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":false,\"error\":\"HTTP " + resp.statusCode() + "\"}')");
                    return;
                }
                String body = resp.body();
                if (body == null || body.isBlank()) {
                    LOG.warn("[测试] 失败: 响应为空");
                    pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":false,\"error\":\"响应为空\"}')");
                    return;
                }
                LOG.info("[测试] 开始解密...");
                String decrypted = com.jfmultichat.config.CryptoUtils.decryptResponse(body);
                if (decrypted == null || decrypted.isBlank()) {
                    LOG.warn("[测试] 失败: 解密后内容为空");
                    pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":false,\"error\":\"解密后内容为空\"}')");
                    return;
                }
                MAPPER.readTree(decrypted);
                LOG.info("[测试] 成功，JSON解析通过");
                pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":true}')");
            } catch (Exception e) {
                LOG.warn("[测试] 异常: {} - {}", url, e.toString());
                String err = e.getMessage() != null ? e.getMessage().replace("'", "\\'") : "未知错误";
                pushToJs("JFC.bridge._handleAsync('test'," + cbId + ",'{\"success\":false,\"error\":\"" + err + "\"}')");
            }
        });
    }

    /** 异步获取更新页数据 */
    public void fetchUpdateDataAsync(String cbId) {
        THREAD_POOL.submit(() -> {
            try {
                JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                        .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);
                ObjectNode result = MAPPER.createObjectNode();
                String curVer = com.jfmultichat.config.AppVersion.VERSION;
                result.put("currentVersion", curVer);

                if (remoteGlobal != null && remoteGlobal.has("update")) {
                    JsonNode updateNode = remoteGlobal.get("update");

                    // 收集所有版本号，用版本比较找出最新版
                    java.util.List<String> allVers = new java.util.ArrayList<>();
                    updateNode.fieldNames().forEachRemaining(allVers::add);

                    if (!allVers.isEmpty()) {
                        String[][] split = com.jfmultichat.config.AppVersion.splitVersions(curVer, allVers);
                        if (split != null) {
                            String[] newer = split[0];
                            String[] older = split[1];

                            if (newer.length > 0) {
                                // 取最新的
                                String latest = newer[0];
                                result.put("latestVersion", latest);
                                result.put("hasUpdate", true);
                                if (updateNode.has(latest) && updateNode.get(latest).has("logs"))
                                    result.set("updateLogs", updateNode.get(latest).get("logs"));
                            } else {
                                // 没有更新的版本 — 当前是最新的
                                result.put("latestVersion", older.length > 0 ? older[0] : curVer);
                                result.put("hasUpdate", false);
                            }
                        }
                    }
                } else {
                    result.put("latestVersion", "");
                    result.put("hasUpdate", false);
                }

                String json = MAPPER.writeValueAsString(result);
                pushToJs("JFC.bridge._handleAsync('update'," + cbId + ",'" + json.replace("'", "\\'") + "')");
            } catch (Exception e) {
                LOG.error("fetchUpdateDataAsync failed", e);
                pushToJs("JFC.bridge._handleAsync('update'," + cbId + ",'{}')");
            }
        });
    }

    /** 异步获取鸣谢页数据 */
    public void fetchThanksDataAsync(String cbId) {
        THREAD_POOL.submit(() -> {
            try {
                JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                        .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);
                ObjectNode result = MAPPER.createObjectNode();
                if (remoteGlobal != null && remoteGlobal.has("about")) {
                    JsonNode about = remoteGlobal.get("about");
                    result.set("thanks", about.has("thanks") ? about.get("thanks") : MAPPER.createObjectNode());
                    result.set("sponsors", about.has("sponsor") ? about.get("sponsor") : MAPPER.createArrayNode());
                    result.set("reference", about.has("reference") ? about.get("reference") : MAPPER.createArrayNode());
                } else {
                    result.putObject("thanks");
                    result.putArray("sponsors");
                    result.putArray("reference");
                }
                String json = MAPPER.writeValueAsString(result);
                pushToJs("JFC.bridge._handleAsync('thanks'," + cbId + ",'" + json.replace("'", "\\'") + "')");
            } catch (Exception e) {
                LOG.error("fetchThanksDataAsync failed", e);
                pushToJs("JFC.bridge._handleAsync('thanks'," + cbId + ",'{}')");
            }
        });
    }

    /** 异步获取关于页数据 */
    public void fetchAboutDataAsync(String cbId) {
        THREAD_POOL.submit(() -> {
            try {
                JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                        .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);
                ObjectNode result = MAPPER.createObjectNode();
                if (remoteGlobal != null) {
                    result.put("appName", remoteGlobal.has("app_name") ? remoteGlobal.get("app_name").asText() : "极峰多聊");
                    result.put("appAuthor", remoteGlobal.has("app_author") ? remoteGlobal.get("app_author").asText() : "吾峰起浪");
                    if (remoteGlobal.has("about")) {
                        JsonNode about = remoteGlobal.get("about");
                        result.set("home", about.has("home") ? about.get("home") : MAPPER.createObjectNode());
                        result.set("project", about.has("project") ? about.get("project") : MAPPER.createObjectNode());
                        result.set("reference", about.has("reference") ? about.get("reference") : MAPPER.createArrayNode());
                    }
                }
                String json = MAPPER.writeValueAsString(result);
                pushToJs("JFC.bridge._handleAsync('about'," + cbId + ",'" + json.replace("'", "\\'") + "')");
            } catch (Exception e) {
                LOG.error("fetchAboutDataAsync failed", e);
                pushToJs("JFC.bridge._handleAsync('about'," + cbId + ",'{}')");
            }
        });
    }

    // ========== 暴露给 JS 的方法 ==========

    /** JS 调用：切换主题 */
    public void setTheme(String theme) {
        LOG.info("Theme changed to: {}", theme);
        if (themeChangeListener != null) {
            themeChangeListener.accept(theme);
        }
    }

    /** JS 调用：报告侧栏图标中心 X 坐标，Java 据此对齐标题栏 logo */
    public void reportSidebarIconCenter(double x) {
        LOG.debug("Sidebar icon center reported: {}", x);
        if (alignListener != null) {
            alignListener.accept(x);
        }
    }

    /** JS 调用：用默认浏览器打开 URL */
    public void openExternal(String url) {
        try {
            Desktop.getDesktop().browse(new URI(url));
        } catch (Exception e) {
            LOG.warn("Failed to open URL: {}", url, e);
        }
    }

    /** ping — 检查桥接是否正常 */
    public String ping() {
        return "pong";
    }

    // ========== 数据访问方法（供前端展示） ==========

    /**
     * 获取所有 Sw 列表.
     * 从 LocalSwConfig.json 的顶层键（排除 "global"）中读取.
     *
     * @return Sw ID 列表的 JSON 数组字符串，如 {@code ["WeChat","Weixin","QQNT"]}
     */
    public String getSwList() {
        try {
            List<String> swList = ConfigManager.getInstance().getSwList();
            return MAPPER.writeValueAsString(swList);
        } catch (Exception e) {
            LOG.error("Failed to get Sw list", e);
            return "[]";
        }
    }

    /**
     * 获取指定 Sw 下的所有账号列表.
     * 从 SwAccData.json 中读取.
     *
     * @param swId Sw ID，如 "WeChat"、"Weixin"
     * @return 账号映射的 JSON 字符串，如 {@code {"wxid_xxx":{...},"wxid_yyy":{...}}}
     */
    public String getAccountList(String swId) {
        try {
            Map<String, ObjectNode> accounts = ConfigManager.getInstance().getAccountMap(swId);
            // 构建精简的账号列表 — 每个账号仅返回 id + nickname + avatar_url
            List<ObjectNode> list = new java.util.ArrayList<>();
            accounts.forEach((id, fields) -> {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("id", id);
                item.put("nickname", fields.has("nickname") ? fields.get("nickname").asText() : "");
                item.put("avatar_url", fields.has("avatar_url") ? fields.get("avatar_url").asText() : "");
                list.add(item);
            });
            return MAPPER.writeValueAsString(list);
        } catch (Exception e) {
            LOG.error("Failed to get account list for swId={}", swId, e);
            return "[]";
        }
    }

    /**
     * 获取当前主题设置（从 LocalGlobalConfig.json 读取 theme）.
     * 供前端初始化时读取.
     *
     * @return 主题字符串: "dark" | "light" | "auto"
     */
    public String getTheme() {
        try {
            ObjectNode globalConfig = ConfigManager.getInstance().getGlobalConfig();
            if (globalConfig.has("theme")) {
                return globalConfig.get("theme").asText();
            }
        } catch (Exception e) {
            LOG.warn("Failed to get theme from config", e);
        }
        return "auto";
    }

    /**
     * 保存当前主题设置到 LocalGlobalConfig.json.
     */
    public void saveTheme(String theme) {
        try {
            ConfigManager.getInstance().updateGlobalConfig(Map.of("theme", theme));
            LOG.info("Theme saved: {}", theme);
        } catch (Exception e) {
            LOG.warn("Failed to save theme", e);
        }
    }

    // ========== 配置页数据（供设置 → 配置 使用） ==========

    /**
     * 获取默认用户数据目录路径.
     * 供前端"配置"页的"默认"按钮使用.
     */
    public String getDefaultUserDir() {
        return com.jfmultichat.config.AppPaths.getDefaultUserDataDir().toString().replace('\\', '/');
    }

    /**
     * 获取配置页所需的所有数据 — 全部来自 RootConfig.
     *
     * @return JSON 字符串，包含 useProxy, proxyIp, proxyPort, userDataPath, remoteGlobalUrls, remoteSwUrls
     */
    public String getConfigData() {
        try {
            ConfigManager cm = ConfigManager.getInstance();
            RootConfig rc = cm.getRootConfig();
            ObjectNode result = MAPPER.createObjectNode();

            // 全部从 RootConfig.json 读取
            result.put("useProxy", rc.isUseProxy());
            result.put("proxyIp", rc.getProxyIp());
            result.put("proxyPort", rc.getProxyPort());
            result.put("userDataPath", rc.getUserDataPath());

            // 远程 URL 列表
            var globalArr = result.putArray("remoteGlobalUrls");
            rc.getRemoteGlobalUrls().forEach(globalArr::add);
            var swArr = result.putArray("remoteSwUrls");
            rc.getRemoteSwUrls().forEach(swArr::add);

            // 内置默认 URL（供前端列表展示，不持久化）
            var globalDefaults = result.putArray("remoteGlobalDefaults");
            for (String url : com.jfmultichat.config.RemoteConfigFetcher.getBuiltinRemoteGlobalUrls()) {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("url", url);
                item.put("label", url.contains("gitee") ? "Gitee" : "GitHub");
                globalDefaults.add(item);
            }
            var swDefaults = result.putArray("remoteSwDefaults");
            for (String url : com.jfmultichat.config.RemoteConfigFetcher.getBuiltinRemoteSwUrls()) {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("url", url);
                item.put("label", url.contains("gitee") ? "Gitee" : "GitHub");
                swDefaults.add(item);
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get config data", e);
            return "{}";
        }
    }

    /**
     * 获取代理预设值（从远程全局配置的 proxy 节点）.
     *
     * @return JSON 字符串，包含 ipPresets 和 portPresets 数组
     */
    public String getProxyPresets() {
        try {
            ObjectNode result = MAPPER.createObjectNode();
            com.jfmultichat.setting.RemoteGlobalSetting rgs =
                    com.jfmultichat.setting.RemoteGlobalSetting.getInstance();

            var proxyNode = rgs.get("proxy");
            if (proxyNode.isPresent()) {
                var proxy = proxyNode.get();
                if (proxy.has("ip_presets")) {
                    result.set("ipPresets", proxy.get("ip_presets"));
                } else {
                    result.putArray("ipPresets");
                }
                if (proxy.has("port_presets")) {
                    result.set("portPresets", proxy.get("port_presets"));
                } else {
                    result.putArray("portPresets");
                }
            } else {
                result.putArray("ipPresets");
                result.putArray("portPresets");
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get proxy presets", e);
            return "{\"ipPresets\":[],\"portPresets\":[]}";
        }
    }

    /**
     * 保存配置页数据.
     * 接收前端 JSON → 写入 RootConfig.json（代理、用户目录、远程URL）.
     *
     * @param json 包含 useProxy, proxyIp, proxyPort, userDataPath, remoteSwUrl, remoteGlobalUrl
     * @return JSON 字符串，包含 success(bool) 和可选的 error(string) / pathChanged(bool) / newPath(string)
     */
    public String saveConfigData(String json) {
        try {
            JsonNode data = MAPPER.readTree(json);
            ConfigManager cm = ConfigManager.getInstance();
            RootConfig rc = cm.getRootConfig();
            ObjectNode result = MAPPER.createObjectNode();

            // 代理设置 → RootConfig.json
            if (data.has("useProxy")) {
                rc.setUseProxy(data.get("useProxy").asBoolean());
            }
            if (data.has("proxyIp")) {
                rc.setProxyIp(data.get("proxyIp").asText().trim());
            }
            if (data.has("proxyPort")) {
                rc.setProxyPort(data.get("proxyPort").asText().trim());
            }

            // 远程 URL 列表 → RootConfig.json（仅保存用户添加的，不包含内置默认）
            if (data.has("remoteGlobalUrls") && data.get("remoteGlobalUrls").isArray()) {
                java.util.List<String> urls = new java.util.ArrayList<>();
                data.get("remoteGlobalUrls").forEach(u -> {
                    if (u.isTextual() && !u.asText().isBlank()) urls.add(u.asText().trim());
                });
                rc.setRemoteGlobalUrls(urls);
            }
            if (data.has("remoteSwUrls") && data.get("remoteSwUrls").isArray()) {
                java.util.List<String> urls = new java.util.ArrayList<>();
                data.get("remoteSwUrls").forEach(u -> {
                    if (u.isTextual() && !u.asText().isBlank()) urls.add(u.asText().trim());
                });
                rc.setRemoteSwUrls(urls);
            }

            // 用户目录（含冲突处理）
            boolean pathChanged = false;
            if (data.has("userDataPath")) {
                String newPath = data.get("userDataPath").asText().trim().replace('\\', '/');
                String oldPath = rc.getUserDataPath().replace('\\', '/');
                if (!newPath.isEmpty() && !newPath.equals(oldPath)) {
                    boolean useTarget = data.has("useTarget") && data.get("useTarget").asBoolean(false);
                    if (!useTarget) {
                        // 使用当前数据：迁移 + 如有冲突备份目标
                        cm.migrateAndBackup(newPath, false);
                    } else {
                        // 使用目标数据：备份来源，然后切换到目标
                        cm.migrateAndBackup(newPath, true);
                    }
                    pathChanged = true;
                    result.put("newPath", cm.getUserDataPath().toString().replace('\\', '/'));
                }
            }

            cm.saveAll();
            result.put("success", true);
            result.put("pathChanged", pathChanged);
            LOG.info("Config saved. useProxy={}, userDataPath changed={}, swUrls={}, globalUrls={}",
                    rc.isUseProxy(), pathChanged,
                    rc.getRemoteSwUrls().size(), rc.getRemoteGlobalUrls().size());

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to save config data", e);
            return "{\"success\":false,\"error\":\"" + e.getMessage() + "\"}";
        }
    }

    // ========== 更新 / 鸣谢 / 关于 页面数据 ==========

    /**
     * 获取更新页数据.
     * 从远程全局配置的 update 节点提取已发布的版本信息，
     * 结合当前应用版本做比较.
     *
     * @return JSON: {currentVersion, latestVersion, hasUpdate, updateLogs, ...}
     */
    public String getUpdateData() {
        try {
            JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                    .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);

            ObjectNode result = MAPPER.createObjectNode();
            result.put("currentVersion", com.jfmultichat.config.AppPaths.VERSION);

            if (remoteGlobal != null && remoteGlobal.has("update")) {
                JsonNode updateNode = remoteGlobal.get("update");

                // 取第一个版本作为最新版本
                var fields = updateNode.fields();
                if (fields.hasNext()) {
                    var latest = fields.next();
                    String latestVer = latest.getKey();
                    result.put("latestVersion", latestVer);
                    result.put("hasUpdate", !latestVer.contains(com.jfmultichat.config.AppPaths.VERSION));

                    // 更新日志
                    JsonNode logNode = latest.getValue();
                    if (logNode.has("logs")) {
                        result.set("updateLogs", logNode.get("logs"));
                    }
                } else {
                    result.put("latestVersion", "");
                    result.put("hasUpdate", false);
                }
            } else {
                result.put("latestVersion", "");
                result.put("hasUpdate", false);
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get update data", e);
            return "{\"currentVersion\":\"\",\"latestVersion\":\"\",\"hasUpdate\":false}";
        }
    }

    /**
     * 获取鸣谢页数据.
     * 从远程全局配置的 about 节点提取 thanks 和 sponsor.
     *
     * @return JSON: {thanks: {...}, sponsors: [...]}
     */
    public String getThanksData() {
        try {
            JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                    .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);

            ObjectNode result = MAPPER.createObjectNode();

            if (remoteGlobal != null && remoteGlobal.has("about")) {
                JsonNode about = remoteGlobal.get("about");

                // 鸣谢
                if (about.has("thanks")) {
                    result.set("thanks", about.get("thanks"));
                } else {
                    result.putObject("thanks");
                }

                // 赞助
                if (about.has("sponsor")) {
                    result.set("sponsors", about.get("sponsor"));
                } else {
                    result.putArray("sponsors");
                }
            } else {
                result.putObject("thanks");
                result.putArray("sponsors");
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get thanks data", e);
            return "{\"thanks\":{},\"sponsors\":[]}";
        }
    }

    /**
     * 获取关于页数据.
     * 从远程全局配置提取 home, project, reference, app_name, app_author.
     *
     * @return JSON: {appName, appAuthor, home, project, reference}
     */
    public String getAboutData() {
        try {
            JsonNode remoteGlobal = com.jfmultichat.config.RemoteConfigFetcher
                    .tryReadRemoteConfig(com.jfmultichat.config.RemoteConfigFetcher.NS_REMOTE_GLOBAL);

            ObjectNode result = MAPPER.createObjectNode();

            if (remoteGlobal != null) {
                result.put("appName", remoteGlobal.has("app_name")
                        ? remoteGlobal.get("app_name").asText() : "极峰多聊");
                result.put("appAuthor", remoteGlobal.has("app_author")
                        ? remoteGlobal.get("app_author").asText() : "吾峰起浪");

                if (remoteGlobal.has("about")) {
                    JsonNode about = remoteGlobal.get("about");
                    if (about.has("home")) result.set("home", about.get("home"));
                    else result.putObject("home");
                    if (about.has("project")) result.set("project", about.get("project"));
                    else result.putObject("project");
                    if (about.has("reference")) result.set("reference", about.get("reference"));
                    else result.putArray("reference");
                } else {
                    result.putObject("home");
                    result.putObject("project");
                    result.putArray("reference");
                }
            } else {
                result.put("appName", "极峰多聊");
                result.put("appAuthor", "吾峰起浪");
                result.putObject("home");
                result.putObject("project");
                result.putArray("reference");
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get about data", e);
            return "{\"appName\":\"\",\"appAuthor\":\"\",\"home\":{},\"project\":{},\"reference\":[]}";
        }
    }

    /**
     * 获取当前构建的 Git 提交信息（供更新页显示）.
     */
    public String getCommitInfo() {
        try {
            ObjectNode result = MAPPER.createObjectNode();
            try (java.io.InputStream is = getClass().getResourceAsStream("/git.properties")) {
                if (is != null) {
                    java.util.Properties props = new java.util.Properties();
                    props.load(is);
                    result.put("commitId", props.getProperty("git.commit.id.abbrev",
                            props.getProperty("git.commit.id", "")));
                    result.put("commitDate", props.getProperty("git.commit.time", ""));
                    return MAPPER.writeValueAsString(result);
                }
            } catch (Exception ignored) {}
            result.put("commitId", "");
            result.put("commitDate", "");
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.warn("Failed to get commit info", e);
            return "{\"commitId\":\"\",\"commitDate\":\"\"}";
        }
    }

    // ========== 配置页辅助方法 ==========

    /**
     * 获取默认远程配置 URL 列表.
     * 返回内置的所有地址（带标签）供前端列表展示.
     */
    public String getDefaultUrls() {
        try {
            ObjectNode result = MAPPER.createObjectNode();

            // 远程全局默认 URL
            var globalArr = result.putArray("remoteGlobalDefaults");
            for (String url : com.jfmultichat.config.RemoteConfigFetcher.getBuiltinRemoteGlobalUrls()) {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("url", url);
                item.put("label", url.contains("gitee") ? "Gitee" : "GitHub");
                globalArr.add(item);
            }

            // 远程平台默认 URL
            var swArr = result.putArray("remoteSwDefaults");
            for (String url : com.jfmultichat.config.RemoteConfigFetcher.getBuiltinRemoteSwUrls()) {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("url", url);
                item.put("label", url.contains("gitee") ? "Gitee" : "GitHub");
                swArr.add(item);
            }

            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.warn("Failed to get default URLs", e);
            return "{}";
        }
    }

    /**
     * 测试远程配置 URL 是否可用.
     * 下载 → 解密 → 尝试解析 JSON → 返回结果.
     *
     * @param url 要测试的 URL
     * @return JSON: {success: true/false, error: "..."}
     */
    public String testRemoteUrl(String url) {
        try {
            if (url == null || url.isBlank()) {
                return "{\"success\":false,\"error\":\"URL 为空\"}";
            }
            java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                    .connectTimeout(java.time.Duration.ofSeconds(5))
                    .build();
            java.net.http.HttpRequest request = java.net.http.HttpRequest.newBuilder()
                    .uri(java.net.URI.create(url))
                    .timeout(java.time.Duration.ofSeconds(10))
                    .GET().build();
            java.net.http.HttpResponse<String> resp = client.send(request,
                    java.net.http.HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() != 200) {
                return "{\"success\":false,\"error\":\"HTTP " + resp.statusCode() + "\"}";
            }
            String body = resp.body();
            if (body == null || body.isBlank()) {
                return "{\"success\":false,\"error\":\"响应为空\"}";
            }
            // 尝试解密
            String decrypted = com.jfmultichat.config.CryptoUtils.decryptResponse(body);
            if (decrypted == null || decrypted.isBlank()) {
                return "{\"success\":false,\"error\":\"解密后内容为空\"}";
            }
            // 尝试解析 JSON
            MAPPER.readTree(decrypted);
            return "{\"success\":true}";
        } catch (Exception e) {
            LOG.warn("testRemoteUrl failed: {}", url, e);
            return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}";
        }
    }

    /**
     * 打开文件夹选择对话框，返回所选目录的绝对路径.
     */
    public String browseFolder(String initialPath) {
        try {
            javafx.stage.DirectoryChooser chooser = new javafx.stage.DirectoryChooser();
            chooser.setTitle("选择用户数据目录");
            if (initialPath != null && !initialPath.isBlank()) {
                java.io.File initDir = new java.io.File(initialPath);
                if (initDir.exists() && initDir.isDirectory()) {
                    chooser.setInitialDirectory(initDir);
                }
            }
            java.io.File selected = chooser.showDialog(null);
            return selected != null ? selected.getAbsolutePath() : "";
        } catch (Exception e) {
            LOG.warn("browseFolder failed", e);
            return "";
        }
    }

    /**
     * 当前是否为开发模式.
     */
    public boolean isDevMode() {
        return com.jfmultichat.config.AppPaths.isDevMode();
    }

    // ========== 全局配置读写（供管理页窗帘偏好等使用） ==========

    /**
     * 获取 global 配置（LocalGlobalConfig.json）.
     * 供前端读取非敏感的全局偏好（如窗帘展开/收起状态）.
     *
     * @return global 节点的 JSON 字符串
     */
    public String getGlobalConfig() {
        try {
            ObjectNode global = ConfigManager.getInstance().getGlobalConfig();
            return global != null ? MAPPER.writeValueAsString(global) : "{}";
        } catch (Exception e) {
            LOG.error("Failed to get global config", e);
            return "{}";
        }
    }

    /**
     * 合并保存 global 配置.
     * 接收前端 JSON，逐字段合并到 LocalGlobalConfig.json.
     *
     * @param json 要合并的 JSON 对象字符串
     */
    public void saveGlobalConfig(String json) {
        try {
            JsonNode data = MAPPER.readTree(json);
            Map<String, Object> updates = new java.util.LinkedHashMap<>();
            data.fieldNames().forEachRemaining(key -> {
                JsonNode node = data.get(key);
                if (node.isTextual()) updates.put(key, node.asText());
                else if (node.isBoolean()) updates.put(key, node.asBoolean());
                else if (node.isInt() || node.isLong()) updates.put(key, node.asLong());
                else if (node.isDouble()) updates.put(key, node.asDouble());
                else updates.put(key, node);  // 嵌套对象/数组保持原样
            });
            if (!updates.isEmpty()) {
                ConfigManager.getInstance().updateGlobalConfig(updates);
            }
        } catch (Exception e) {
            LOG.error("Failed to save global config", e);
        }
    }

    // ========== 管理页数据访问方法 ==========

    /**
     * 检查远程配置是否已就位.
     * 返回 JSON: {ready: true} 或 {ready: false, missing: ["remote_global", "remote_sw"]}
     */
    public String checkRemoteConfigReady() {
        return checkReadyInternal();
    }

    /**
     * 异步确保远程配置就位（后台线程尝试下载）.
     * 完成后通过 _handleAsync('ensureConfig', cbId, json) 推送结果.
     * <p>
     * 前端任何需要远程配置的操作，都应先调用同步 checkRemoteConfigReady()，
     * 如果 ready=false，则调用此异步方法尝试下载。
     *
     * @param cbId JS 回调 ID
     */
    public void tryEnsureRemoteConfigsAsync(String cbId) {
        // 先快速检查 — 如果已就绪，立即回调
        String readyJson = checkReadyInternal();
        ObjectNode readyResult;
        try {
            readyResult = (ObjectNode) MAPPER.readTree(readyJson);
        } catch (Exception e) {
            readyResult = MAPPER.createObjectNode();
            readyResult.put("ready", false);
        }

        if (readyResult.get("ready").asBoolean(false)) {
            pushToJs("JFC.bridge._handleAsync('ensureConfig'," + cbId + ",'" + readyJson.replace("'", "\\'") + "')");
            return;
        }

        // 缺失配置 → 后台线程下载
        THREAD_POOL.submit(() -> {
            try {
                String dlJson = downloadRemoteConfigs();
                String finalJson = checkReadyInternal();
                pushToJs("JFC.bridge._handleAsync('ensureConfig'," + cbId + ",'" + finalJson.replace("'", "\\'") + "')");
                LOG.info("tryEnsureRemoteConfigsAsync: download completed, result={}", dlJson);
            } catch (Exception e) {
                LOG.error("tryEnsureRemoteConfigsAsync failed", e);
                pushToJs("JFC.bridge._handleAsync('ensureConfig'," + cbId + ",'{\"ready\":false,\"missing\":[\"remote_global\",\"remote_sw\"]}')");
            }
        });
    }

    /** 内部：快速检查远程配置就绪状态 */
    private String checkReadyInternal() {
        try {
            java.util.List<String> missing = new java.util.ArrayList<>();
            if (ConfigManager.getInstance().getRemoteGlobal() == null
                    || ConfigManager.getInstance().getRemoteGlobal().isEmpty()) {
                missing.add("remote_global");
            }
            if (ConfigManager.getInstance().getRemoteSw() == null
                    || ConfigManager.getInstance().getRemoteSw().isEmpty()) {
                missing.add("remote_sw");
            }
            ObjectNode result = MAPPER.createObjectNode();
            result.put("ready", missing.isEmpty());
            var arr = result.putArray("missing");
            missing.forEach(arr::add);
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to check remote config readiness", e);
            return "{\"ready\":false,\"missing\":[\"remote_global\",\"remote_sw\"]}";
        }
    }

    /**
     * 尝试自动下载缺失的远程配置文件.
     * 从 RootConfig.json 读取 remoteGlobalUrls / remoteSwUrls，
     * 逐个尝试下载 → 解密 → 验证 JSON → 保存到磁盘.
     * <p>
     * 此方法同步阻塞（在后台线程调用），逐个 URL 尝试直到成功或全部失败.
     *
     * @return JSON: {remoteSw: true/false, remoteGlobal: true/false}
     */
    public String downloadRemoteConfigs() {
        LOG.info("=== 开始下载远程配置 ===");
        ObjectNode result = MAPPER.createObjectNode();
        boolean swOk = false;
        boolean globalOk = false;

        try {
            ConfigManager cm = ConfigManager.getInstance();
            RootConfig rc = cm.getRootConfig();

            // 从 RootConfig 读取 URL 列表
            java.util.List<String> swUrls = new java.util.ArrayList<>(rc.getRemoteSwUrls());
            java.util.List<String> globalUrls = new java.util.ArrayList<>(rc.getRemoteGlobalUrls());

            LOG.info("[下载] remote_sw 候选URL: {}个, remote_global 候选URL: {}个",
                    swUrls.size(), globalUrls.size());
            for (int i = 0; i < swUrls.size(); i++) {
                LOG.info("[下载] remote_sw URL[{}]: {}", i, swUrls.get(i));
            }
            for (int i = 0; i < globalUrls.size(); i++) {
                LOG.info("[下载] remote_global URL[{}]: {}", i, globalUrls.get(i));
            }

            // 尝试下载 remote_sw
            LOG.info("[下载] --- 尝试 remote_sw ---");
            for (String url : swUrls) {
                try {
                    String decrypted = downloadAndDecrypt(url);
                    if (decrypted != null) {
                        ObjectNode data = (ObjectNode) MAPPER.readTree(decrypted);
                        cm.setRemoteSw(data);
                        swOk = true;
                        LOG.info("[下载] RemoteSwConfig.json 保存成功，节点数={}", data.size());
                        break;
                    }
                } catch (Exception e) {
                    LOG.warn("[下载] remote_sw URL失败: {} - {}", url, e.toString());
                }
            }

            // 尝试下载 remote_global
            LOG.info("[下载] --- 尝试 remote_global ---");
            for (String url : globalUrls) {
                try {
                    String decrypted = downloadAndDecrypt(url);
                    if (decrypted != null) {
                        ObjectNode data = (ObjectNode) MAPPER.readTree(decrypted);
                        cm.setRemoteGlobal(data);
                        globalOk = true;
                        LOG.info("[下载] RemoteGlobalConfig.json 保存成功，节点数={}", data.size());
                        break;
                    }
                } catch (Exception e) {
                    LOG.warn("[下载] remote_global URL失败: {} - {}", url, e.toString());
                }
            }
        } catch (Exception e) {
            LOG.error("[下载] downloadRemoteConfigs 异常", e);
        }

        LOG.info("=== 下载结束: remoteSw={}, remoteGlobal={} ===", swOk, globalOk);

        result.put("remoteSw", swOk);
        result.put("remoteGlobal", globalOk);
        try {
            return MAPPER.writeValueAsString(result);
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            LOG.error("Failed to serialize downloadRemoteConfigs result", e);
            return "{\"remoteSw\":false,\"remoteGlobal\":false}";
        }
    }

    /**
     * 下载单个远程配置 URL 并解密，返回解密后的 JSON 字符串.
     * 失败返回 null.
     */
    private String downloadAndDecrypt(String url) {
        LOG.info("[下载] 开始: {}", url);
        try {
            java.net.http.HttpClient client = java.net.http.HttpClient.newBuilder()
                    .connectTimeout(java.time.Duration.ofSeconds(10))
                    .followRedirects(java.net.http.HttpClient.Redirect.NORMAL)
                    .build();
            java.net.http.HttpRequest request = java.net.http.HttpRequest.newBuilder()
                    .uri(java.net.URI.create(url))
                    .timeout(java.time.Duration.ofSeconds(15))
                    .GET().build();
            java.net.http.HttpResponse<String> resp = client.send(request,
                    java.net.http.HttpResponse.BodyHandlers.ofString());
            LOG.info("[下载] HTTP {} ({}), body长度={}",
                    resp.statusCode(), resp.uri(), resp.body() != null ? resp.body().length() : 0);
            if (resp.statusCode() != 200) {
                LOG.warn("[下载] 失败: HTTP {}", resp.statusCode());
                return null;
            }
            String body = resp.body();
            if (body == null || body.isBlank()) {
                LOG.warn("[下载] 失败: body为空");
                return null;
            }
            LOG.info("[下载] 开始解密...");
            String decrypted = com.jfmultichat.config.CryptoUtils.decryptResponse(body);
            if (decrypted == null || decrypted.isBlank()) {
                LOG.warn("[下载] 解密后内容为空");
                return null;
            }
            // 验证是否为合法 JSON
            MAPPER.readTree(decrypted);
            LOG.info("[下载] 成功，JSON解析通过，长度={}", decrypted.length());
            return decrypted;
        } catch (Exception e) {
            LOG.warn("[下载] 异常: {} - {}", url, e.toString());
            return null;
        }
    }

    /**
     * 获取远程平台列表.
     * 完全依赖 RemoteSwConfig.json 的节点（不含 __info__）。
     * 平台名称取自节点的 alias 字段，无 alias 则用 swId。
     *
     * @return JSON: {platforms: [{swId, alias}], remoteRaw: {...}}
     */
    public String getRemoteSwList() {
        try {
            JsonNode remoteSw = ConfigManager.getInstance().getRemoteSw();
            ObjectNode result = MAPPER.createObjectNode();
            var arr = result.putArray("platforms");

            if (remoteSw != null && remoteSw.isObject()) {
                remoteSw.fieldNames().forEachRemaining(key -> {
                    if (!"__info__".equals(key)) {
                        ObjectNode item = MAPPER.createObjectNode();
                        item.put("swId", key);
                        if (remoteSw.get(key).has("alias") && remoteSw.get(key).get("alias").isTextual()) {
                            item.put("alias", remoteSw.get(key).get("alias").asText());
                        } else {
                            item.put("alias", key);
                        }
                        arr.add(item);
                    }
                });
            }

            result.set("remoteRaw", remoteSw != null ? remoteSw : MAPPER.createObjectNode());
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get remote Sw list", e);
            return "{\"platforms\":[],\"remoteRaw\":{}}";
        }
    }

    /**
     * 获取指定 Sw 的完整配置数据.
     * 从 LocalSwConfig.json 中读取该 Sw 的所有字段.
     *
     * @param swId Sw ID
     * @return JSON 字符串，包含 swId + 所有配置字段
     */
    public String getSwConfig(String swId) {
        try {
            ObjectNode swConfig = ConfigManager.getInstance().getSwConfig(swId);
            ObjectNode result = MAPPER.createObjectNode();
            result.put("swId", swId);
            // 复制所有字段
            swConfig.fieldNames().forEachRemaining(key -> {
                result.set(key, swConfig.get(key));
            });
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get Sw config for {}", swId, e);
            return "{\"swId\":\"" + swId + "\",\"state\":\"visible\"}";
        }
    }

    /**
     * 保存指定 Sw 的配置.
     * 将前端传来的完整配置合并到 LocalSwConfig.json.
     *
     * @param swId    Sw ID
     * @param configJson 前端提交的完整配置 JSON
     * @return JSON: {success: true/false, error: "..."}
     */
    public String saveSwConfig(String swId, String configJson) {
        try {
            JsonNode data = MAPPER.readTree(configJson);
            Map<String, Object> updates = new java.util.LinkedHashMap<>();
            data.fieldNames().forEachRemaining(key -> {
                if (!"swId".equals(key)) {
                    JsonNode node = data.get(key);
                    if (node.isTextual()) updates.put(key, node.asText());
                    else if (node.isBoolean()) updates.put(key, node.asBoolean());
                    else if (node.isInt() || node.isLong()) updates.put(key, node.asLong());
                    else if (node.isDouble()) updates.put(key, node.asDouble());
                    else updates.put(key, node.asText());
                }
            });
            ConfigManager.getInstance().updateSwConfig(swId, updates);
            return "{\"success\":true}";
        } catch (Exception e) {
            LOG.error("Failed to save Sw config for {}", swId, e);
            return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}";
        }
    }

    /**
     * 更新指定 Sw 的单个字段.
     *
     * @param swId   Sw ID
     * @param field  字段名
     * @param value  字段值（JSON 字符串，自动解析类型）
     * @return JSON: {success: true/false, error: "..."}
     */
    public String updateSwField(String swId, String field, String value) {
        try {
            JsonNode parsed = MAPPER.readTree(value);
            Object updateVal;
            if (parsed.isTextual()) updateVal = parsed.asText();
            else if (parsed.isBoolean()) updateVal = parsed.asBoolean();
            else if (parsed.isInt() || parsed.isLong()) updateVal = parsed.asLong();
            else if (parsed.isDouble()) updateVal = parsed.asDouble();
            else updateVal = parsed.asText();

            Map<String, Object> updates = new java.util.LinkedHashMap<>();
            updates.put(field, updateVal);
            ConfigManager.getInstance().updateSwConfig(swId, updates);
            return "{\"success\":true}";
        } catch (Exception e) {
            LOG.error("Failed to update Sw field {} for {}", field, swId, e);
            return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}";
        }
    }

    /**
     * 获取指定 Sw 的完整账号数据（含所有字段）.
     * 区别于 getAccountList（仅返回 id/nickname/avatar_url）.
     *
     * @param swId Sw ID
     * @return JSON: {swId, accounts: [{id, ...fields}]}
     */
    public String getSwDetailData(String swId) {
        try {
            Map<String, ObjectNode> accounts = ConfigManager.getInstance().getAccountMap(swId);
            ObjectNode result = MAPPER.createObjectNode();
            result.put("swId", swId);
            var arr = result.putArray("accounts");

            accounts.forEach((id, fields) -> {
                ObjectNode item = MAPPER.createObjectNode();
                item.put("id", id);
                // 复制所有字段
                fields.fieldNames().forEachRemaining(key -> {
                    JsonNode node = fields.get(key);
                    if (node.isTextual()) item.put(key, node.asText());
                    else if (node.isBoolean()) item.put(key, node.asBoolean());
                    else if (node.isInt() || node.isLong()) item.put(key, node.asLong());
                    else if (node.isDouble()) item.put(key, node.asDouble());
                    else item.put(key, node.asText());
                });
                arr.add(item);
            });
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.error("Failed to get Sw detail data for {}", swId, e);
            return "{\"swId\":\"" + swId + "\",\"accounts\":[]}";
        }
    }

    /**
     * 添加或更新一个账号（合并字段，不替换整个账号）.
     *
     * @param swId      Sw ID
     * @param accountId 账号 ID
     * @param fieldsJson 账号字段 JSON（仅更新提供的字段）
     * @return JSON: {success: true/false, error: "..."}
     */
    public String saveAccount(String swId, String accountId, String fieldsJson) {
        try {
            JsonNode data = MAPPER.readTree(fieldsJson);
            Map<String, Object> updates = new java.util.LinkedHashMap<>();
            data.fieldNames().forEachRemaining(key -> {
                JsonNode node = data.get(key);
                if (node.isTextual()) updates.put(key, node.asText());
                else if (node.isBoolean()) updates.put(key, node.asBoolean());
                else if (node.isInt() || node.isLong()) updates.put(key, node.asLong());
                else if (node.isDouble()) updates.put(key, node.asDouble());
                else updates.put(key, node.asText());
            });
            ConfigManager.getInstance().updateAccount(swId, accountId, updates);
            return "{\"success\":true}";
        } catch (Exception e) {
            LOG.error("Failed to save account for swId={}", swId, e);
            return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}";
        }
    }

    /**
     * 删除一个账号.
     *
     * @param swId      Sw ID
     * @param accountId 账号 ID
     * @return JSON: {success: true/false, error: "..."}
     */
    public String deleteAccount(String swId, String accountId) {
        try {
            boolean removed = ConfigManager.getInstance().deleteAccount(swId, accountId);
            return "{\"success\":true,\"removed\":" + removed + "}";
        } catch (Exception e) {
            LOG.error("Failed to delete account for swId={}", swId, e);
            return "{\"success\":false,\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}";
        }
    }

    /**
     * 从 EXE 文件提取图标，返回 base64 编码的 PNG 数据 URL.
     * 优先使用 FileSystemView 获取 Windows 文件关联图标（含大图标），
     * 回退到 ShellFolder 内部 API，最后使用 ImageIcon.
     *
     * @param exePath EXE 文件路径
     * @return JSON: {iconUrl: "data:image/png;base64,..."} 或 {iconUrl: ""}（无图标时）
     */
    public String extractExeIcon(String exePath) {
        try {
            if (exePath == null || exePath.isBlank()) {
                return "{\"iconUrl\":\"\"}";
            }
            java.io.File exeFile = new java.io.File(exePath);
            if (!exeFile.exists() || !exeFile.isFile()) {
                return "{\"iconUrl\":\"\"}";
            }
            // 只处理 .exe/.dll/.ico 文件
            String name = exeFile.getName().toLowerCase();
            if (!name.endsWith(".exe") && !name.endsWith(".dll") && !name.endsWith(".ico")) {
                return "{\"iconUrl\":\"\"}";
            }
            return extractIconFromFile(exeFile);
        } catch (Exception e) {
            LOG.warn("extractExeIcon failed for {}: {}", exePath, e.getMessage());
            return "{\"iconUrl\":\"\"}";
        }
    }

    /**
     * 从实际文件提取图标（多策略回退）.
     * 策略：
     * 1. FileSystemView.getSystemIcon() — 官方跨平台 API
     * 2. ShellFolder.getIcon(true) — Windows 原生大图标（反射调用）
     * 3. ImageIcon — 最后回退（对 .ico 文件有效）
     */
    private String extractIconFromFile(java.io.File file) {
        java.awt.Image img = null;

        // 方案1: FileSystemView（官方 API，跨平台）
        try {
            javax.swing.filechooser.FileSystemView fsv =
                javax.swing.filechooser.FileSystemView.getFileSystemView();
            javax.swing.Icon icon = fsv.getSystemIcon(file);
            if (icon instanceof javax.swing.ImageIcon) {
                img = ((javax.swing.ImageIcon) icon).getImage();
            } else if (icon != null) {
                // 非 ImageIcon — 渲染到 BufferedImage
                int size = Math.max(icon.getIconWidth(), 32);
                java.awt.image.BufferedImage bi =
                    new java.awt.image.BufferedImage(size, size, java.awt.image.BufferedImage.TYPE_INT_ARGB);
                java.awt.Graphics2D g = bi.createGraphics();
                icon.paintIcon(null, g, 0, 0);
                g.dispose();
                img = bi;
            }
        } catch (Exception e) {
            LOG.debug("FileSystemView.getSystemIcon failed: {}", e.getMessage());
        }

        // 方案2: ShellFolder 内部 API（Windows 原生大图标 32x32）
        if (img == null || img.getWidth(null) < 8) {
            try {
                Class<?> sfClass = Class.forName("sun.awt.shell.ShellFolder");
                java.lang.reflect.Method getShellFolder =
                    sfClass.getDeclaredMethod("getShellFolder", java.io.File.class);
                Object shellFolder = getShellFolder.invoke(null, file);
                java.lang.reflect.Method getIcon =
                    sfClass.getDeclaredMethod("getIcon", boolean.class);
                java.awt.Image largeIcon = (java.awt.Image) getIcon.invoke(shellFolder, true);
                if (largeIcon != null && largeIcon.getWidth(null) >= 8) {
                    img = largeIcon;
                }
            } catch (Exception e) {
                LOG.debug("ShellFolder.getIcon failed: {}", e.getMessage());
            }
        }

        // 方案3: ImageIcon 直接加载（对 .ico 有效）
        if (img == null || img.getWidth(null) < 8) {
            try {
                javax.swing.ImageIcon icon = new javax.swing.ImageIcon(file.getAbsolutePath());
                java.awt.Image loaded = icon.getImage();
                if (loaded != null && loaded.getWidth(null) >= 8) {
                    img = loaded;
                }
            } catch (Exception e) {
                LOG.debug("ImageIcon fallback failed: {}", e.getMessage());
            }
        }

        if (img == null) {
            return "{\"iconUrl\":\"\"}";
        }

        return imageToBase64DataUrl(img);
    }

    /**
     * 将 AWT Image 编码为 base64 PNG data URL.
     */
    private String imageToBase64DataUrl(java.awt.Image img) {
        try {
            int w = img.getWidth(null);
            int h = img.getHeight(null);
            if (w <= 0) w = 32;
            if (h <= 0) h = 32;

            // 限制最大尺寸
            if (w > 64) w = 64;
            if (h > 64) h = 64;

            java.awt.image.BufferedImage bi =
                new java.awt.image.BufferedImage(w, h, java.awt.image.BufferedImage.TYPE_INT_ARGB);
            java.awt.Graphics2D g2d = bi.createGraphics();
            g2d.setRenderingHint(java.awt.RenderingHints.KEY_INTERPOLATION,
                java.awt.RenderingHints.VALUE_INTERPOLATION_BILINEAR);
            g2d.drawImage(img, 0, 0, w, h, null);
            g2d.dispose();

            java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
            javax.imageio.ImageIO.write(bi, "png", baos);
            String base64 = java.util.Base64.getEncoder().encodeToString(baos.toByteArray());
            return "{\"iconUrl\":\"data:image/png;base64," + base64 + "\"}";
        } catch (Exception e) {
            LOG.debug("imageToBase64DataUrl failed: {}", e.getMessage());
            return "{\"iconUrl\":\"\"}";
        }
    }

    /**
     * 校验 Windows 路径合法性.
     * 检查：盘符格式（必须有冒号）、非法字符、盘符是否存在.
     *
     * @param path 待校验的绝对路径
     * @return JSON: {valid: true/false, error: "..."}
     */
    public String validatePath(String path) {
        try {
            ObjectNode result = MAPPER.createObjectNode();
            if (path == null || path.isBlank()) {
                result.put("valid", false);
                result.put("error", "路径为空");
                return MAPPER.writeValueAsString(result);
            }

            String trimmed = path.trim();
            if (!trimmed.equals(path)) {
                result.put("valid", false);
                result.put("error", "路径首尾不能有空格");
                return MAPPER.writeValueAsString(result);
            }

            // 非法字符检查
            if (trimmed.matches(".*[\\*\\?\"<>\\|].*")) {
                result.put("valid", false);
                result.put("error", "路径包含非法字符 (* ? \" < > |)");
                return MAPPER.writeValueAsString(result);
            }

            // 盘符格式检查: 必须以 [A-Z]: 开头
            if (!trimmed.matches("^[A-Za-z]:.*")) {
                if (trimmed.matches("^[A-Za-z]/.*") || trimmed.matches("^[A-Za-z]\\\\.*")) {
                    result.put("valid", false);
                    result.put("error", "盘符缺少冒号，应为 " + trimmed.charAt(0) + ":\\");
                } else {
                    result.put("valid", false);
                    result.put("error", "路径必须以盘符开头 (如 C:\\)");
                }
                return MAPPER.writeValueAsString(result);
            }

            // 盘符存在性检查
            String driveLetter = trimmed.substring(0, 1).toUpperCase() + ":\\";
            java.io.File drive = new java.io.File(driveLetter);
            if (!drive.exists()) {
                result.put("valid", false);
                result.put("error", "盘符 " + driveLetter + " 在当前系统中不存在");
                return MAPPER.writeValueAsString(result);
            }

            result.put("valid", true);
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.warn("validatePath failed", e);
            return "{\"valid\":false,\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}";
        }
    }

    // ==================== 路径自动探测 ====================

    /**
     * 异步探测指定 SW 的路径.
     * <p>
     * 三级探测策略:
     * 1. reg  (注册表) — 从 Windows 注册表读取路径
     * 2. regex (内存映射正则) — 通过进程内存映射文件匹配正则表达式
     * 3. addr (猜测) — 从已知系统目录拼接 sub_path
     * <p>
     * 结果通过 {@code _handleAsync('detectPaths', cbId, json)} 推送到 JS.
     * 每条候选路径包含 path / isDir / exists / sources 字段.
     *
     * @param swId         软件标识
     * @param cbId         JS 回调 ID
     * @param pathKeysJson 要探测的路径类型 JSON 数组（如 {@code ["inst_path","data_dir"]}）;
     *                     为空数组时默认探测全部三项
     */
    public void detectPathsAsync(String swId, String cbId, String pathKeysJson) {
        // 解析 pathKeys JSON
        java.util.List<String> pathKeysList = new java.util.ArrayList<>();
        if (pathKeysJson != null && !pathKeysJson.isBlank()) {
            try {
                JsonNode arr = MAPPER.readTree(pathKeysJson);
                if (arr.isArray()) {
                    arr.forEach(n -> { if (n.isTextual()) pathKeysList.add(n.asText()); });
                }
            } catch (Exception e) {
                LOG.warn("[路径探测] pathKeysJson 解析失败: {}", pathKeysJson, e);
            }
        }
        String[] keys = pathKeysList.isEmpty()
                ? new String[]{"inst_path", "data_dir", "dll_dir"}
                : pathKeysList.toArray(new String[0]);

        LOG.info("[路径探测] 开始: swId={}, keys={}", swId, java.util.Arrays.toString(keys));

        THREAD_POOL.submit(() -> {
            try {
                ObjectNode result = MAPPER.createObjectNode();
                result.put("swId", swId);

                // 构建配置访问器
                SwConfigAccessor accessor = new SwConfigAccessor(new BridgeConfigProvider());
                SwPathDetective detective = new SwPathDetective(new SwNativeOps());

                // 批量探测（一次调用，内部并发 + 内存映射共享扫描）
                java.util.Map<String, java.util.List<SwPathDetective.PathEntry>> detectResults =
                        detective.detectAll(accessor, swId, keys);

                for (java.util.Map.Entry<String, java.util.List<SwPathDetective.PathEntry>> entry
                        : detectResults.entrySet()) {
                    String pt = entry.getKey();
                    java.util.List<SwPathDetective.PathEntry> candidates = entry.getValue();
                    var arr = result.putArray(pt);
                    if (candidates != null) {
                        for (SwPathDetective.PathEntry pe : candidates) {
                            ObjectNode item = MAPPER.createObjectNode();
                            item.put("path", pe.path);
                            item.put("isDir", pe.isDir);
                            item.put("exists",
                                    java.nio.file.Files.exists(java.nio.file.Path.of(pe.path)));

                            // 来源列表
                            var srcArr = item.putArray("sources");
                            if (pe.sources != null) {
                                pe.sources.forEach(srcArr::add);
                            }

                            arr.add(item);
                        }
                    }
                }

                String json = MAPPER.writeValueAsString(result);
                pushToJs("JFC.bridge._handleAsync('detectPaths'," + cbId + ",'"
                        + json.replace("'", "\\'") + "')");
            } catch (Exception e) {
                LOG.error("detectPathsAsync failed for {}", swId, e);
                pushToJs("JFC.bridge._handleAsync('detectPaths'," + cbId
                        + ",'{\"error\":\"" + e.getMessage().replace("\"", "'") + "\"}')");
            }
        });
    }

    // ==================== 路径检查 ====================

    /**
     * 检查路径有效性（同步，由输入框 blur 触发）.
     * 调用 {@link SwAdapterChecker#isValidSwPath} 进行验证.
     *
     * @param swId     软件标识
     * @param pathType 路径类型 (inst_path / data_dir / dll_dir)
     * @param path     待检查的路径
     * @return JSON: {valid: bool, exists: bool, reason: string}
     */
    public String checkPath(String swId, String pathType, String path) {
        try {
            if (path == null || path.isBlank()) {
                return "{\"valid\":false,\"exists\":false,\"reason\":\"路径为空\"}";
            }
            boolean exists = java.nio.file.Files.exists(java.nio.file.Path.of(path));
            ObjectNode result = MAPPER.createObjectNode();
            result.put("exists", exists);

            // 路径不存在 → 直接返回，不进入详细检查
            if (!exists) {
                result.put("valid", false);
                result.put("reason", "路径不存在");
                return MAPPER.writeValueAsString(result);
            }

            SwConfigAccessor accessor = new SwConfigAccessor(new BridgeConfigProvider());
            java.util.Map<String, Object> detail =
                    SwAdapterChecker.checkSwPathDetail(pathType, swId, path, accessor);

            result.put("valid", Boolean.TRUE.equals(detail.get("valid")));
            String reason = (String) detail.getOrDefault("reason", "路径符合预期");
            result.put("reason", reason);
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.warn("checkPath failed for sw={}, type={}, path={}", swId, pathType, path, e);
            return "{\"valid\":false,\"exists\":false,\"reason\":\"" + e.getMessage() + "\"}";
        }
    }

    // ==================== 数据迁移 ====================

    /**
     * 检查目标数据目录是否存在文件（冲突检测）.
     *
     * @param newPath 目标数据目录路径
     * @return JSON: {conflict: bool, existingFiles: int}
     */
    public String checkDataDirConflict(String newPath) {
        try {
            ObjectNode result = MAPPER.createObjectNode();
            if (newPath == null || newPath.isBlank()) {
                result.put("conflict", false);
                result.put("existingFiles", 0);
                return MAPPER.writeValueAsString(result);
            }
            java.nio.file.Path target = java.nio.file.Path.of(newPath);
            boolean hasFiles = java.nio.file.Files.exists(target)
                    && java.nio.file.Files.isDirectory(target);
            int count = 0;
            if (hasFiles) {
                try (var stream = java.nio.file.Files.list(target)) {
                    count = (int) stream.count();
                }
            }
            result.put("conflict", count > 0);
            result.put("existingFiles", count);
            return MAPPER.writeValueAsString(result);
        } catch (Exception e) {
            LOG.warn("checkDataDirConflict failed: {}", newPath, e);
            return "{\"conflict\":false,\"existingFiles\":0}";
        }
    }

    /**
     * 将 ConfigManager 适配为 SwConfigAccessor.Provider
     */
    private class BridgeConfigProvider implements SwConfigAccessor.Provider {

        // ========== 辅助方法: kwargs → JsonNode ==========

        /**
         * 解析 kwargs {key: default} → 从指定根节点按路径取值。
         * 单 key: 直接取该 key 的值，找不到返回 default
         * 多 key: 逐层嵌套遍历，最后一层的 key 取默认值
         */
        private JsonNode resolveKwargs(JsonNode root, Map<String, Object> kwargs) {
            if (root == null || !root.isObject() || kwargs.isEmpty()) return null;
            if (kwargs.size() == 1) {
                Map.Entry<String, Object> entry = kwargs.entrySet().iterator().next();
                JsonNode node = root.get(entry.getKey());
                if (node != null) return node;
                // 有默认值则返回默认值
                Object def = entry.getValue();
                if (def != null) {
                    ObjectMapper mapper = new ObjectMapper();
                    return mapper.valueToTree(def);
                }
                return null;
            }
            // 多 key: 逐层深入，最后一个 key 用 kwargs 取值
            Iterator<Map.Entry<String, Object>> it = kwargs.entrySet().iterator();
            JsonNode cur = root;
            while (it.hasNext()) {
                Map.Entry<String, Object> entry = it.next();
                String key = entry.getKey();
                if (!it.hasNext()) {
                    // 最后一个 key，使用 kwargs 语义
                    JsonNode node = cur.isObject() ? cur.get(key) : null;
                    if (node != null) return node;
                    Object def = entry.getValue();
                    if (def != null) {
                        ObjectMapper mapper = new ObjectMapper();
                        return mapper.valueToTree(def);
                    }
                    return null;
                }
                // 中间层 key，简单路径遍历
                if (cur.isObject()) {
                    cur = cur.get(key);
                } else {
                    return null;
                }
            }
            return null;
        }

        @Override
        public JsonNode getRemoteSw(String sw, String... addr) {
            try {
                JsonNode remoteSw = ConfigManager.getInstance().getRemoteSw();
                if (remoteSw == null || !remoteSw.isObject()) return null;
                JsonNode node = remoteSw.get(sw);
                if (node == null || !node.isObject()) return null;
                for (String a : addr) {
                    if (node.isObject()) node = node.get(a);
                    else return null;
                }
                return node;
            } catch (Exception e) {
                LOG.warn("[路径探测] getRemoteSw failed for {}: {}", sw, e.getMessage());
                return null;
            }
        }

        @Override
        public JsonNode getRemoteSw(String sw, Map<String, Object> kwargs) {
            JsonNode remoteSw = ConfigManager.getInstance().getRemoteSw();
            JsonNode swNode = (remoteSw != null && remoteSw.isObject()) ? remoteSw.get(sw) : null;
            return resolveKwargs(swNode, kwargs);
        }

        @Override
        public JsonNode getSwSetting(String sw, String... addr) {
            try {
                ObjectNode swConfig = ConfigManager.getInstance().getSwConfig(sw);
                if (swConfig == null) return null;
                JsonNode node = swConfig;
                for (String a : addr) {
                    if (node.isObject()) node = node.get(a);
                    else return null;
                }
                return node;
            } catch (Exception e) {
                return null;
            }
        }

        @Override
        public JsonNode getSwSetting(String sw, Map<String, Object> kwargs) {
            ObjectNode swConfig = ConfigManager.getInstance().getSwConfig(sw);
            return resolveKwargs(swConfig, kwargs);
        }

        @Override
        public void updateSwSettings(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs) {
            try {
                Map<String, Object> updates = new LinkedHashMap<>();
                // frontAddr 是路径前缀，kwargs 是 key -> value
                // 逐层嵌套设置
                ObjectNode target = ConfigManager.getInstance().getSwConfig(sw);
                if (frontAddr != null) {
                    for (Map.Entry<String, String> fa : frontAddr.entrySet()) {
                        String prefix = fa.getKey();
                        target = (ObjectNode) target.putArray(prefix).get(0);
                        // 实际上 frontAddr 是 Map，值可能是子节点名
                        // 简化: 直接将 kwargs 写入目标节点
                    }
                }
                for (Map.Entry<String, Object> entry : kwargs.entrySet()) {
                    if (entry.getValue() == null) {
                        target.remove(entry.getKey());
                    } else {
                        ObjectMapper mapper = new ObjectMapper();
                        target.set(entry.getKey(), mapper.valueToTree(entry.getValue()));
                    }
                }
                ConfigManager.getInstance().updateSwConfig(sw,
                        kwargs.entrySet().stream()
                                .collect(java.util.stream.Collectors.toMap(
                                        Map.Entry::getKey, e -> e.getValue())));
            } catch (Exception e) {
                LOG.warn("[路径探测] updateSwSettings failed for {}: {}", sw, e.getMessage());
            }
        }

        @Override
        public JsonNode getSwAccData(String sw, String... addr) {
            try {
                Map<String, ObjectNode> accMap = ConfigManager.getInstance().getAccountMap(sw);
                if (accMap.isEmpty()) return null;
                JsonNode node = null;
                // 第一个 addr 是账号 ID
                if (addr.length == 0) {
                    return MAPPER.valueToTree(accMap);
                }
                String accId = addr[0];
                ObjectNode accNode = accMap.get(accId);
                if (accNode == null) return null;
                if (addr.length == 1) return accNode;
                // 多层路径
                node = accNode;
                for (int i = 1; i < addr.length; i++) {
                    if (node.isObject()) node = node.get(addr[i]);
                    else return null;
                }
                return node;
            } catch (Exception e) {
                LOG.warn("[路径探测] getSwAccData failed for {}: {}", sw, e.getMessage());
                return null;
            }
        }

        @Override
        public JsonNode getSwAccData(String sw, Map<String, Object> kwargs) {
            Map<String, ObjectNode> accMap = ConfigManager.getInstance().getAccountMap(sw);
            if (accMap.isEmpty()) return null;
            // 合并所有账号节点为一个 ObjectNode 再解析
            ObjectNode combined = MAPPER.createObjectNode();
            accMap.forEach(combined::set);
            return resolveKwargs(combined, kwargs);
        }

        @Override
        public void updateSwAccData(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs) {
            try {
                // frontAddr: [accountId, ...path] → 定位到具体账号节点
                // kwargs: key -> value → 写入
                Map<String, Object> updates = new LinkedHashMap<>();
                kwargs.forEach((k, v) -> updates.put(k, v));
                // 取第一个 addr 作为 accountId
                String accId = null;
                if (frontAddr != null && !frontAddr.isEmpty()) {
                    accId = frontAddr.values().iterator().next();
                }
                if (accId != null) {
                    ConfigManager.getInstance().updateAccount(sw, accId, updates);
                } else {
                    // 无 accountId，直接更新整个账号字典
                    // 简化处理：写入第一个账号或创建
                    Map<String, ObjectNode> accMap = ConfigManager.getInstance().getAccountMap(sw);
                    if (!accMap.isEmpty()) {
                        String firstAcc = accMap.keySet().iterator().next();
                        ConfigManager.getInstance().updateAccount(sw, firstAcc, updates);
                    }
                }
            } catch (Exception e) {
                LOG.warn("[路径探测] updateSwAccData failed for {}: {}", sw, e.getMessage());
            }
        }

        @Override
        public void clearSwAccData(String sw, String... addr) {
            try {
                if (addr.length == 0) return;
                String accId = addr[0];
                Map<String, ObjectNode> accMap = ConfigManager.getInstance().getAccountMap(sw);
                ObjectNode accNode = accMap.get(accId);
                if (accNode == null) return;
                if (addr.length == 1) {
                    // 清空整个账号节点
                    accNode.fieldNames().forEachRemaining(accNode::remove);
                } else {
                    // 删除深层路径
                    JsonNode node = accNode;
                    for (int i = 1; i < addr.length - 1; i++) {
                        if (node.isObject()) node = node.get(addr[i]);
                        else return;
                    }
                    if (node.isObject()) ((ObjectNode) node).remove(addr[addr.length - 1]);
                }
                ConfigManager.getInstance().saveAll();
            } catch (Exception e) {
                LOG.warn("[路径探测] clearSwAccData failed for {}: {}", sw, e.getMessage());
            }
        }

        @Override
        public ObjectNode getSwCache() {
            return ConfigManager.getInstance().getSwCache();
        }

        @Override
        public void setSwCache(ObjectNode data) {
            ConfigManager.getInstance().setSwCache(data);
        }

        @Override
        public boolean saveAndCheckChanged(String sw, String key, Object value) {
            try {
                ObjectNode swNode = ConfigManager.getInstance().getSwConfig(sw);
                if (swNode == null) return false;
                // 检查是否变化
                JsonNode existing = swNode.get(key);
                if (existing != null && existing.isValueNode()) {
                    String oldVal = existing.asText("");
                    String newVal = (value != null) ? value.toString() : "";
                    if (oldVal.equals(newVal)) return false;
                }
                // 更新
                if (value == null) {
                    swNode.remove(key);
                } else if (value instanceof Boolean) {
                    swNode.put(key, (Boolean) value);
                } else if (value instanceof Number) {
                    if (value instanceof Integer || value instanceof Long) {
                        swNode.put(key, ((Number) value).longValue());
                    } else {
                        swNode.put(key, ((Number) value).doubleValue());
                    }
                } else {
                    swNode.put(key, value.toString());
                }
                ConfigManager.getInstance().updateSwConfig(sw,
                        java.util.Map.of(key, value));
                return true;
            } catch (Exception e) {
                LOG.warn("[路径探测] saveAndCheckChanged failed for {}: {}", sw, e.getMessage());
                return false;
            }
        }

        @Override
        public JsonNode fetchOrSetDefault(String sw, String key, String enumCls) {
            try {
                ObjectNode swNode = ConfigManager.getInstance().getSwConfig(sw);
                if (swNode == null) return null;
                JsonNode existing = swNode.get(key);
                if (existing != null && !existing.isNull()) {
                    return existing;
                }
                // 设置默认值
                JsonNode defaultValue;
                if (enumCls != null && !enumCls.isEmpty()) {
                    // 尝试从枚举获取默认值（简化：返回 null）
                    defaultValue = MAPPER.nullNode();
                } else {
                    defaultValue = MAPPER.nullNode();
                }
                if (defaultValue != null && !defaultValue.isNull()) {
                    swNode.set(key, defaultValue);
                    ConfigManager.getInstance().saveAll();
                }
                return defaultValue;
            } catch (Exception e) {
                LOG.warn("[路径探测] fetchOrSetDefault failed for {}: {}", sw, e.getMessage());
                return null;
            }
        }
    }
}
