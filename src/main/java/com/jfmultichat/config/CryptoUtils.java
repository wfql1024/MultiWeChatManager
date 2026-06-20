package com.jfmultichat.config;

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

        // 1. 按最后一个空格拆分
        int lastSpace = responseText.lastIndexOf(' ');
        if (lastSpace < 0) {
            // 无空格 — 可能是未加密的 JSON，直接返回
            return responseText;
        }

        String encryptedData = responseText.substring(0, lastSpace);
        String key = responseText.substring(lastSpace + 1);

        // 2. Base64 解码
        byte[] decoded = Base64.getDecoder().decode(encryptedData);

        // 3. Key 处理: key.ljust(16)[:16].encode()
        String paddedKey = (key + "                ").substring(0, 16);
        byte[] aesKey = paddedKey.getBytes(StandardCharsets.UTF_8);

        // 4. 前 16 字节 = IV，剩余 = ciphertext
        byte[] iv = new byte[16];
        byte[] ciphertext = new byte[decoded.length - 16];
        System.arraycopy(decoded, 0, iv, 0, 16);
        System.arraycopy(decoded, 16, ciphertext, 0, ciphertext.length);

        // 5. AES/CBC/PKCS5Padding 解密
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(aesKey, "AES"), new IvParameterSpec(iv));
        byte[] plaintext = cipher.doFinal(ciphertext);

        // 6. 返回 UTF-8 字符串
        return new String(plaintext, StandardCharsets.UTF_8);
    }
}
