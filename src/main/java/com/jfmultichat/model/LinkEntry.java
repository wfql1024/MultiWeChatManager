package com.jfmultichat.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.Map;

/**
 * 链接入口 — 对应 remote_global JSON 中的 {text: "...", links: {...}} 结构.
 * <p>
 * 用于 home / project / thanks 节点.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record LinkEntry(String text, Map<String, String> links) {}
