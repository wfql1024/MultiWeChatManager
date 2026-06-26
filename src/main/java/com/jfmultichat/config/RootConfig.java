package com.jfmultichat.config;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.ArrayList;
import java.util.List;

/**
 * 根配置模型 — RootConfig.json 的数据结构.
 * <p>
 * 存放软件全局设置（代理、数据目录、远程配置源），
 * 此文件永远留在版本根目录，不随 user_data_path 移动.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class RootConfig {

    @JsonProperty("user_data_path")
    private String userDataPath;

    @JsonProperty("remote_global_urls")
    private List<String> remoteGlobalUrls = new ArrayList<>();

    @JsonProperty("remote_sw_urls")
    private List<String> remoteSwUrls = new ArrayList<>();

    @JsonProperty("use_proxy")
    private boolean useProxy;

    @JsonProperty("proxy_ip")
    private String proxyIp;

    @JsonProperty("proxy_port")
    private String proxyPort;

    // ---- 兼容旧字段（反序列化时读入，不写出） ----
    @JsonProperty("remote_global_url")
    private void setRemoteGlobalUrlCompat(String url) {
        if (url != null && !url.isBlank() && !remoteGlobalUrls.contains(url)) {
            remoteGlobalUrls.add(url);
        }
    }

    @JsonProperty("remote_sw_url")
    private void setRemoteSwUrlCompat(String url) {
        if (url != null && !url.isBlank() && !remoteSwUrls.contains(url)) {
            remoteSwUrls.add(url);
        }
    }

    // ==================== Getter/Setter ====================

    public String getUserDataPath() {
        return userDataPath;
    }

    public void setUserDataPath(String userDataPath) {
        this.userDataPath = userDataPath;
    }

    public List<String> getRemoteGlobalUrls() {
        return remoteGlobalUrls;
    }

    public void setRemoteGlobalUrls(List<String> urls) {
        this.remoteGlobalUrls = urls != null ? urls : new ArrayList<>();
    }

    public List<String> getRemoteSwUrls() {
        return remoteSwUrls;
    }

    public void setRemoteSwUrls(List<String> urls) {
        this.remoteSwUrls = urls != null ? urls : new ArrayList<>();
    }

    public boolean isUseProxy() {
        return useProxy;
    }

    public void setUseProxy(boolean useProxy) {
        this.useProxy = useProxy;
    }

    public String getProxyIp() {
        return proxyIp != null ? proxyIp : "";
    }

    public void setProxyIp(String proxyIp) {
        this.proxyIp = proxyIp;
    }

    public String getProxyPort() {
        return proxyPort != null ? proxyPort : "";
    }

    public void setProxyPort(String proxyPort) {
        this.proxyPort = proxyPort;
    }

    // ---- 兼容旧版单 URL 访问（取列表第一个） ----

    /** @deprecated 使用 {@link #getRemoteGlobalUrls()} */
    @Deprecated
    public String getRemoteGlobalUrl() {
        return remoteGlobalUrls.isEmpty() ? "" : remoteGlobalUrls.get(0);
    }

    /** @deprecated 使用 {@link #getRemoteSwUrls()} */
    @Deprecated
    public String getRemoteSwUrl() {
        return remoteSwUrls.isEmpty() ? "" : remoteSwUrls.get(0);
    }

    @Override
    public String toString() {
        return "RootConfig{" +
                "userDataPath='" + userDataPath + '\'' +
                ", remoteGlobalUrls=" + remoteGlobalUrls +
                ", remoteSwUrls=" + remoteSwUrls +
                ", useProxy=" + useProxy +
                ", proxyIp='" + proxyIp + '\'' +
                ", proxyPort='" + proxyPort + '\'' +
                '}';
    }
}
