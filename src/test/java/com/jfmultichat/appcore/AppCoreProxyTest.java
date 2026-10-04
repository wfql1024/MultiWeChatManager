package com.jfmultichat.appcore;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 代理地址归一化测试。
 *
 * <p>界面上的"代理地址"输入框允许用户直接粘贴带协议的地址，
 * 若原样塞进 {@code https.proxyHost} 会让 JDK 拼出非法代理 URI
 * （{@code URISyntaxException: Expected closing bracket for IPv6 address ... proxy.https://[http://127.0.0.1]:7890/}），
 * 这里锁定归一化规则。
 */
class AppCoreProxyTest {

    @Test
    void splitsSchemeAndPort() {
        assertArrayEquals(new String[]{"127.0.0.1", "7890"}, AppCore.splitHostPort("http://127.0.0.1:7890"));
        assertArrayEquals(new String[]{"127.0.0.1", "7890"}, AppCore.splitHostPort("127.0.0.1:7890"));
        assertArrayEquals(new String[]{"127.0.0.1", ""}, AppCore.splitHostPort("127.0.0.1"));
        assertArrayEquals(new String[]{"127.0.0.1", "7890"}, AppCore.splitHostPort(" https://127.0.0.1:7890/ "));
        assertArrayEquals(new String[]{"proxy.local", "8080"}, AppCore.splitHostPort("socks5://proxy.local:8080"));
    }

    @Test
    void handlesIpv6AndEmptyInput() {
        assertArrayEquals(new String[]{"::1", "7890"}, AppCore.splitHostPort("[::1]:7890"));
        assertArrayEquals(new String[]{"::1", ""}, AppCore.splitHostPort("[::1]"));
        // 裸 IPv6 不含端口（多个冒号）→ 整个作为主机
        assertArrayEquals(new String[]{"::1", ""}, AppCore.splitHostPort("::1"));
        assertArrayEquals(new String[]{"", ""}, AppCore.splitHostPort(null));
        assertArrayEquals(new String[]{"", ""}, AppCore.splitHostPort("   "));
    }

    @Test
    void validatesPortRange() {
        assertTrue(AppCore.isValidPort("7890"));
        assertTrue(AppCore.isValidPort("1"));
        assertTrue(AppCore.isValidPort("65535"));

        assertFalse(AppCore.isValidPort("0"));
        assertFalse(AppCore.isValidPort("65536"));
        assertFalse(AppCore.isValidPort(""));
        assertFalse(AppCore.isValidPort(null));
        assertFalse(AppCore.isValidPort("78a0"));
        assertFalse(AppCore.isValidPort("78901"));
        assertFalse(AppCore.isValidPort(" 7890 "));
    }
}
