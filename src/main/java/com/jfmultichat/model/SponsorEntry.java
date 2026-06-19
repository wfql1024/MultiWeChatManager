package com.jfmultichat.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/**
 * 赞助条目 — 对应 about.sponsor[] 数组.
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public record SponsorEntry(String date, String currency, String amount, String user) {}
