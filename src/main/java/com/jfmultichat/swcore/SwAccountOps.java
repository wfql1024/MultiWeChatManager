package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;

/**
 * 账号操作 — 管理 SW 账号数据和共存程序
 * <p>
 * 对应 Python: SwInfoFuncCore.ensure_coexist_acc_formatted,
 * _get_all_coexist_acc_and_ensure_formatted, get_sw_all_accounts_existed,
 * identity_and_get_available_coexist_mode
 *
 * 依赖: SwConfigAccessor
 */
public final class SwAccountOps {

    private static final Logger LOG = LoggerFactory.getLogger(SwAccountOps.class);
    private SwAccountOps() {}

    /**
     * 账号操作提供者接口
     */
    public interface AccountOpsProvider {
        JsonNode getSwAccData(String sw, String... addr);
        JsonNode getSwAccData(String sw, Map<String, Object> kwargs);
        void updateSwAccData(String sw, Map<String, String> frontAddr, Map<String, Object> kwargs);
    }

    // ==================== 共存程序格式化 ====================

    /**
     * 确保共存程序字典格式正确
     * 对应 Python: ensure_coexist_acc_formatted (L561-L571)
     *
     * @param sw         软件标识
     * @param coexistExe 共存 exe 名
     * @param accountOps 账号操作器
     */
    public static void ensureCoexistAccFormatted(
            String sw, String coexistExe, AccountOpsProvider accountOps) {

        JsonNode coexistExeDict = accountOps.getSwAccData(sw, coexistExe);
        if (coexistExeDict == null || !coexistExeDict.isObject()) {
            // 创建空节点
            accountOps.updateSwAccData(sw, Map.of(coexistExe, ""), Map.of());
            coexistExeDict = accountOps.getSwAccData(sw, coexistExe);
        }

        ObjectNode dictNode = (ObjectNode) coexistExeDict;

        // 确保 linked_acc 字段
        if (!dictNode.has("linked_acc")) {
            accountOps.updateSwAccData(sw, Map.of(coexistExe, ""),
                    Map.of("linked_acc", null));
        }

        // 确保 channel 字段
        if (!dictNode.has("channel")) {
            accountOps.updateSwAccData(sw, Map.of(coexistExe, ""),
                    Map.of("channel", null));
        }

        // 确保 ordinals 字段
        if (!dictNode.has("ordinals")) {
            accountOps.updateSwAccData(sw, Map.of(coexistExe, ""),
                    Map.of("ordinals", null));
        }
    }

    // ==================== 获取所有共存程序 ====================

    /**
     * 获取所有共存程序并确保格式正确
     * 对应 Python: _get_all_coexist_acc_and_ensure_formatted (L573-L585)
     *
     * @param sw                  软件标识
     * @param instDir             安装目录
     * @param executableWildcards 可执行文件通配符列表
     * @param originExe           原生 exe 名
     * @param accessor            配置访问器
     * @param accountOps          账号操作器
     * @return 共存 exe 名列表（排除原生 exe）
     */
    public static List<String> getAllCoexistAccAndEnsureFormatted(
            String sw, String instDir, List<String> executableWildcards,
            String originExe, SwConfigAccessor accessor,
            AccountOpsProvider accountOps) {

        List<String> allCoexistExes = new ArrayList<>();

        // 使用通配符匹配目录中的 exe 文件
        for (String wildcard : executableWildcards) {
            List<String> matchedFiles = getFilesMatchingWildcard(instDir, wildcard);
            for (String coexistExe : matchedFiles) {
                if (coexistExe.equals(originExe)) continue;
                allCoexistExes.add(coexistExe);
                ensureCoexistAccFormatted(sw, coexistExe, accountOps);
            }
        }

        return allCoexistExes;
    }

    /**
     * 获取平台所有账号（原生 + 共存）
     * 对应 Python: get_sw_all_accounts_existed (L587-L612)
     *
     * @param sw         软件标识
     * @param dataDir    数据目录
     * @param excludedDirs 排除目录列表
     * @param instPath   安装路径
     * @param executableWildcards 可执行文件通配符
     * @param accessor   配置访问器
     * @param accountOps 账号操作器
     * @param only       "origin"=仅原生, "coexist"=仅共存, null=全部
     * @return 账号名列表
     */
    public static List<String> getSwAllAccountsExisted(
            String sw, String dataDir, List<String> excludedDirs,
            String instPath, List<String> executableWildcards,
            SwConfigAccessor accessor, AccountOpsProvider accountOps,
            String only) {

        Set<String> accounts = new HashSet<>();

        if (!"coexist".equals(only)) {
            // 原生账号 = 数据目录下的所有子目录
            if (dataDir != null && !dataDir.isBlank()) {
                java.nio.file.Path dataPath = java.nio.file.Path.of(dataDir);
                if (java.nio.file.Files.exists(dataPath)) {
                    try (var stream = java.nio.file.Files.list(dataPath)) {
                        stream.filter(java.nio.file.Files::isDirectory)
                                .map(p -> p.getFileName().toString())
                                .filter(name -> !excludedDirs.contains(name))
                                .forEach(accounts::add);
                    } catch (Exception e) {
                        LOG.warn("[账号] 扫描数据目录失败: {}", e.getMessage());
                    }
                }
            }
        }

        if (!"origin".equals(only)) {
            // 共存账号
            if (instPath != null && !instPath.isBlank() && executableWildcards != null) {
                String instDir = new java.io.File(instPath).getParent();
                String originExe = accessor.getRemoteSwAsString(sw, SwCoreConstants.RemoteSwKey.EXECUTABLE, "");
                List<String> coexistExes = getAllCoexistAccAndEnsureFormatted(
                        sw, instDir, executableWildcards, originExe, accessor, accountOps);
                accounts.addAll(coexistExes);
            }
        }

        return new ArrayList<>(accounts);
    }

    // ==================== 可用共存模式识别 ====================

    /**
     * 选择一个可用的共存构造模式
     * 对应 Python: identity_and_get_available_coexist_mode (L614-L624)
     *
     * @param sw         软件标识
     * @param accessor   配置访问器
     * @param accountOps 账号操作器
     * @return {channel, channelResDict, message}
     */
    public static String[] identityAndGetAvailableCoexistMode(
            String sw, SwConfigAccessor accessor, AccountOpsProvider accountOps) {

        // 获取用户选择的共存模式
        JsonNode userCoexistChannel = accessor.fetchOrSetDefault(
                sw, SwCoreConstants.LocalSettingKey.COEXIST_MODE, null);

        // TODO: 调用 identifyDllCore 检测共存模式状态
        // channelResDict, msg = cls.identify_dll_core(sw, RemoteSwKey.COEXIST)

        if (userCoexistChannel != null && userCoexistChannel.isTextual()) {
            String channel = userCoexistChannel.asText();
            return new String[]{channel, "{}", "共存模式可用"};
        }

        return new String[]{null, "{}", "没有可用的共存构造模式"};
    }

    // ==================== 文件通配符匹配 ====================

    /**
     * 获取目录下匹配通配符的文件名列表
     */
    private static List<String> getFilesMatchingWildcard(String dir, String wildcard) {
        List<String> result = new ArrayList<>();
        java.nio.file.Path dirPath = java.nio.file.Path.of(dir);
        if (!java.nio.file.Files.exists(dirPath)) return result;

        try (var stream = java.nio.file.Files.list(dirPath)) {
            stream.map(p -> p.getFileName().toString())
                    .filter(name -> matchesWildcard(name, wildcard))
                    .forEach(result::add);
        } catch (Exception e) {
            LOG.warn("[账号] 扫描目录失败: {}", e.getMessage());
        }

        return result;
    }

    /**
     * 检查文件名是否匹配通配符（支持 ? 和 *）
     */
    private static boolean matchesWildcard(String name, String wildcard) {
        // 简单实现：将 ? 转为 .，* 转为 .*，然后用正则匹配
        String regex = wildcard
                .replace(".", "\\.")
                .replace("?", ".")
                .replace("*", ".*");
        regex = "^" + regex + "$";
        return name.matches(regex);
    }

    // ==================== 平台图标获取 ====================

    /**
     * 获取平台图标
     * 对应 Python: get_sw_logo (L693-L744)
     *
     * @param sw         软件标识
     * @param userDir    用户目录
     * @param instPath   安装路径（用于提取图标）
     * @param accessor   配置访问器
     * @return 图标文件路径；失败返回 null
     */
    public static String getSwLogo(String sw, String userDir, String instPath,
                                    SwConfigAccessor accessor) {
        // 构建头像文件路径
        String userSwDir = userDir + "/" + sw;
        String avatarPath = userSwDir + "/" + sw + ".png";

        java.nio.file.Path avatarFile = java.nio.file.Path.of(avatarPath);
        if (java.nio.file.Files.exists(avatarFile)) {
            return avatarPath;
        }

        // 从 exe 文件提取图标
        if (instPath != null && !instPath.isBlank()) {
            try {
                // TODO: 调用 extractIconToPNG(instPath, avatarPath)
                // image_utils.extract_icon_to_png(executable, avatar_path)
                LOG.debug("[图标] 从 exe 提取图标: {} -> {}", instPath, avatarPath);
            } catch (Exception e) {
                LOG.warn("[图标] 提取图标失败: {}", e.getMessage());
            }
        }

        // 再次检查
        if (java.nio.file.Files.exists(avatarFile)) {
            return avatarPath;
        }

        // 检查 default.jpg
        String defaultPath = userDir + "/" + SwCoreConstants.DEFAULT_AVATAR_FILENAME;
        java.nio.file.Path defaultFile = java.nio.file.Path.of(defaultPath);
        if (java.nio.file.Files.exists(defaultFile)) {
            return defaultPath;
        }

        LOG.warn("[图标] 所有方法都失败");
        return null;
    }

    // ==================== 账号展示名获取 ====================

    /**
     * 获取账号展示名
     * 对应 Python: get_sw_origin_display_name (L746-L758)
     *
     * @param sw       软件标识
     * @param accessor 配置访问器
     * @return 展示名（remark > alias > swId）
     */
    public static String getSwOriginDisplayName(String sw, SwConfigAccessor accessor) {
        // 1. 先查本地 remark
        JsonNode remark = accessor.getSwSetting(sw, SwCoreConstants.LocalSettingKey.REMARK);
        if (remark != null && remark.isTextual()) {
            return remark.asText();
        }

        // 2. 再查远程 alias
        JsonNode alias = accessor.getRemoteSw(sw, SwCoreConstants.RemoteSwKey.ALIAS);
        if (alias != null && alias.isTextual()) {
            return alias.asText();
        }

        return sw;
    }
}
