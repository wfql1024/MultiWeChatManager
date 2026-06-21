package com.jfmultichat.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

/**
 * 加解密工具 — 对应 Python CryptoUtils.
 * <p>
 * 远程配置文件加密格式: {@code base64(IV + ciphertext) + " " + key}<br>
 * 解密流程:
 * <ol>
 *   <li>按最后一个空格拆分 → encrypted_data + key</li>
 *   <li>Base64 解码 encrypted_data</li>
 *   <li>key 左填充至 16 字节，取前 16 字节作为 AES key</li>
 *   <li>解码数据的前 16 字节 = IV，剩余 = ciphertext</li>
 *   <li>AES/CBC/PKCS5Padding 解密</li>
 *   <li>返回 UTF-8 明文 JSON</li>
 * </ol>
 */
public final class CryptoUtils {

    private static final Logger LOG = LoggerFactory.getLogger(CryptoUtils.class);

    private CryptoUtils() {}

    /**
     * 解密远程配置响应文本.
     * 与 Python CryptoUtils.decrypt_response 等效.
     *
     * @param responseText 加密的响应文本（格式: base64 + 空格 + key）
     * @return 解密后的 JSON 明文
     * @throws Exception 解密失败
     */
    public static String decryptResponse(String responseText) throws Exception {
        if (responseText == null || responseText.isBlank()) {
            throw new IllegalArgumentException("Response text is empty");
        }

        LOG.info("[解密] 收到响应文本，长度={}", responseText.length());

        // 1. 按最后一个空格拆分
        int lastSpace = responseText.lastIndexOf(' ');
        if (lastSpace < 0) {
            LOG.info("[解密] 无空格分隔符，视为未加密 JSON，直接返回前80字符: {}",
                    responseText.substring(0, Math.min(80, responseText.length())));
            return responseText;
        }

        String encryptedData = responseText.substring(0, lastSpace);
        String key = responseText.substring(lastSpace + 1);
        LOG.info("[解密] 拆分: encodedData长度={}, key='{}'", encryptedData.length(), key);

        // 2. Base64 解码
        byte[] decoded = Base64.getDecoder().decode(encryptedData);
        LOG.info("[解密] Base64解码: {} 字节, 前4字节(hex)={}", decoded.length,
                bytesToHex(decoded, 4));

        // 3. Key 处理: key.ljust(16)[:16].encode()
        String paddedKey = (key + "                ").substring(0, 16);
        byte[] aesKey = paddedKey.getBytes(StandardCharsets.UTF_8);
        LOG.info("[解密] Key处理: paddedKey='{}' (长度={})", paddedKey, aesKey.length);

        // 4. 前 16 字节 = IV，剩余 = ciphertext
        byte[] iv = new byte[16];
        byte[] ciphertext = new byte[decoded.length - 16];
        System.arraycopy(decoded, 0, iv, 0, 16);
        System.arraycopy(decoded, 16, ciphertext, 0, ciphertext.length);
        LOG.info("[解密] IV(hex)={}, 密文长度={}字节", bytesToHex(iv, 16), ciphertext.length);

        // 5. AES/CBC/PKCS5Padding 解密
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(aesKey, "AES"), new IvParameterSpec(iv));
        byte[] plaintext = cipher.doFinal(ciphertext);
        LOG.info("[解密] AES/CBC解密成功，明文长度={}字节", plaintext.length);

        // 6. 返回 UTF-8 字符串
        String result = new String(plaintext, StandardCharsets.UTF_8);
        LOG.info("[解密] UTF-8解码完成，前80字符: {}",
                result.substring(0, Math.min(80, result.length())));
        return result;
    }

    private static String bytesToHex(byte[] bytes, int maxLen) {
        StringBuilder sb = new StringBuilder();
        int len = Math.min(bytes.length, maxLen);
        for (int i = 0; i < len; i++) {
            sb.append(String.format("%02x", bytes[i] & 0xff));
        }
        if (bytes.length > maxLen) sb.append("...");
        return sb.toString();
    }
}
