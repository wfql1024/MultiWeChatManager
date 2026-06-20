package com.jfmultichat.config;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 根配置模型 — root_config.json 的数据结构.
 * <p>
 * 包含三个字段：user_data_path、remote_global_url、remote_sw_url.
 * 此文件永远留在版本根目录，不随 user_data_path 移动.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class RootConfig {

    @JsonProperty("user_data_path")
    private String userDataPath;

    @JsonProperty("remote_global_url")
    private String remoteGlobalUrl;

    @JsonProperty("remote_sw_url")
    private String remoteSwUrl;

    public RootConfig() {}

    public RootConfig(String userDataPath, String remoteGlobalUrl, String remoteSwUrl) {
        this.userDataPath = userDataPath;
        this.remoteGlobalUrl = remoteGlobalUrl;
        this.remoteSwUrl = remoteSwUrl;
    }

    // ==================== Getter/Setter ====================

    public String getUserDataPath() {
        return userDataPath;
    }

    public void setUserDataPath(String userDataPath) {
        this.userDataPath = userDataPath;
    }

    public String getRemoteGlobalUrl() {
        return remoteGlobalUrl != null ? remoteGlobalUrl : "";
    }

    public void setRemoteGlobalUrl(String remoteGlobalUrl) {
        this.remoteGlobalUrl = remoteGlobalUrl;
    }

    public String getRemoteSwUrl() {
        return remoteSwUrl != null ? remoteSwUrl : "";
    }

    public void setRemoteSwUrl(String remoteSwUrl) {
        this.remoteSwUrl = remoteSwUrl;
    }

    @Override
    public String toString() {
        return "RootConfig{" +
                "userDataPath='" + userDataPath + '\'' +
                ", remoteGlobalUrl='" + remoteGlobalUrl + '\'' +
                ", remoteSwUrl='" + remoteSwUrl + '\'' +
                '}';
    }
}
