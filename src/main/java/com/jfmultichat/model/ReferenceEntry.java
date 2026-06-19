package com.jfmultichat.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/**
 * 技术参考条目 — 对应 about.reference[] 数组.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ReferenceEntry(String title, String link) {}
