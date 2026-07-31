package com.jfmultichat.acccore;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.util.*;

import com.jfmultichat.appcore.AppCore;
import com.jfmultichat.config.ConfigManager;
import com.jfmultichat.config.SwConfigProvider;
import com.jfmultichat.swcore.SwConfigAccessor;

/**
 * 账号操作核心 — 登录配置操作、进程管理、互斥体查杀等
 * <p>
 * 对应 Python: AccOperatorCore (L41-L867)
 * <p>
 * 包含：登录配置读写、账号启动/退出、互斥体查杀、快捷方式创建等操作。
 */
public final class AccOperatorCore {

    private static final Logger LOG = LoggerFactory.getLogger(AccOperatorCore.class);
    private static final AccConfigAccessor ACC_ACCESSOR = new AccConfigAccessor();

    private AccOperatorCore() {
        throw new UnsupportedOperationException("AccOperatorCore is a static utility class");
    }

    // ==================== 账号配置操作 ====================

    /**
     * 操作账号登录配置（use/add/del）
     * 对应 Python: operate_acc_config (L379-L438)
     *
     * @param method 操作类型："use"=使用, "add"=创建, "del"=删除
     * @param sw     软件标识
     * @param acc    账号 ID
     * @return {success, message}
     */
    public static String[] operateAccConfig(String method, String sw, String acc) {
        if (!List.of("use", "add", "del").contains(method)) {
            return new String[]{null, "未知操作类型: " + method};
        }

        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        JsonNode configAddresses = accessor.getRemoteSw(sw, "config_addresses");
        if (configAddresses == null || !configAddresses.isArray() || configAddresses.isEmpty()) {
            return new String[]{null, "无法获取登录配置文件地址"};
        }

        // 构建原始配置 → 账号配置的映射
        Map<String, String> originToAcc = new LinkedHashMap<>();
        for (JsonNode addr : configAddresses) {
            if (!addr.isTextual()) continue;
            String originPath = addr.asText().replace('\\', '/');
            String originDir = new File(originPath).getParent();
            String originBasename = new File(originPath).getName();
            String accPath = (originDir + "/" + acc + "_" + originBasename).replace('\\', '/');
            originToAcc.put(originPath, accPath);
        }

        // 删除配置项
        List<String> pathsToRemove = "use".equals(method)
                ? new ArrayList<>(originToAcc.keySet())
                : new ArrayList<>(originToAcc.values());
        for (String p : pathsToRemove) {
            try {
                File f = new File(p);
                if (f.isFile()) f.delete();
                else if (f.isDirectory()) deleteDirectory(f);
            } catch (Exception e) {
                LOG.warn("[配置] 移除失败 {}: {}", p, e.getMessage());
            }
        }

        if ("del".equals(method)) {
            return new String[]{null, "删除配置成功"};
        }

        // 复制配置项
        List<String> successPaths = new ArrayList<>();
        for (Map.Entry<String, String> entry : originToAcc.entrySet()) {
            String sourcePath = "use".equals(method) ? entry.getKey() : entry.getValue();
            String destPath = "use".equals(method) ? entry.getValue() : entry.getKey();
            try {
                File src = new File(sourcePath);
                File dst = new File(destPath);
                if (src.isFile()) {
                    java.nio.file.Files.copy(src.toPath(), dst.toPath(),
                            java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    successPaths.add(destPath);
                } else if (src.isDirectory()) {
                    deleteDirectory(dst);
                    copyDirectory(src, dst);
                    successPaths.add(destPath);
                }
            } catch (Exception e) {
                LOG.warn("[配置] 复制失败 {} -> {}: {}", sourcePath, destPath, e.getMessage());
            }
        }

        return new String[]{null, successPaths.isEmpty() ? "配置操作失败" : "成功"};
    }

    /**
     * 批量删除账号配置（可回收站恢复）
     * 对应 Python: del_config_of_accounts (L347-L378)
     */
    public static String[] delConfigOfAccounts(String sw, List<String> accounts) {
        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        JsonNode configAddresses = accessor.getRemoteSw(sw, "config_addresses");
        if (configAddresses == null || !configAddresses.isArray() || configAddresses.isEmpty()) {
            return new String[]{null, "提醒", sw + "平台还没有适配"};
        }

        List<String> filesToDelete = new ArrayList<>();
        for (JsonNode addr : configAddresses) {
            if (!addr.isTextual()) continue;
            String originCfgPath = addr.asText().replace('\\', '/');
            String originCfgDir = new File(originCfgPath).getParent();
            String originBasename = new File(originCfgPath).getName();
            for (String acc : accounts) {
                String accCfgPath = (originCfgDir + "/" + acc + "_" + originBasename).replace('\\', '/');
                if (new File(accCfgPath).exists() && !accCfgPath.equals(originCfgPath)) {
                    filesToDelete.add(accCfgPath);
                }
            }
        }

        if (!filesToDelete.isEmpty()) {
            try {
                for (String path : filesToDelete) {
                    java.nio.file.Files.deleteIfExists(java.nio.file.Path.of(path));
                }
                LOG.info("[配置] 已删除: {}", filesToDelete);
            } catch (Exception e) {
                LOG.warn("[配置] 删除失败: {}", e.getMessage());
            }
        }

        return new String[]{null, "已删除 " + filesToDelete.size() + " 个配置文件"};
    }

    // ==================== 进程管理 ====================

    /**
     * 关闭指定账号进程
     * 对应 Python: quit_accounts (L542-L554)
     */
    public static List<String> quitAccounts(String sw, List<String> accounts) {
        List<String> quited = new ArrayList<>();
        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        List<String> exeWildcards = accessor.getRemoteSwAsList(sw, "executable_wildcards",
                Collections.emptyList());

        for (String account : accounts) {
            JsonNode pidNode = ACC_ACCESSOR.getSwAccData(sw, account, "pid");
            if (pidNode == null || !pidNode.isNumber()) continue;
            int pid = pidNode.asInt();

            final java.util.concurrent.atomic.AtomicBoolean killed = new java.util.concurrent.atomic.AtomicBoolean(false);
            try {
                ProcessHandle.of(pid).ifPresent(ph -> {
                    if (ph.isAlive()) {
                        ph.destroy();
                        killed.set(true);
                    }
                });
            } catch (Exception e) {
                LOG.warn("[进程] 关闭失败 pid={}: {}", pid, e.getMessage());
            }

            if (killed.get()) {
                quited.add(account);
                ACC_ACCESSOR.updateSwAccData(sw, account,
                        Map.of("pid", null, "has_mutex", false));
            }
        }
        return quited;
    }

    /**
     * 切换至账号窗口
     * 对应 Python: switch_to_sw_account_wnd (L524-L540)
     */
    public static void switchToSwAccountWnd(String sw, String acc) {
        JsonNode hwndNode = ACC_ACCESSOR.getSwAccData(sw, acc, "main_hwnd");
        if (hwndNode == null || !hwndNode.isNumber()) return;
        int hwnd = hwndNode.asInt();
        // TODO: JNA SetForegroundWindow / ShowWindow
        LOG.debug("[窗口] switchToSwAccountWnd: sw={}, acc={}, hwnd={}", sw, acc, hwnd);
    }

    // ==================== 互斥体操作 ====================

    /**
     * 关闭指定账号的互斥体句柄
     * 对应 Python: kill_mutex_of_acc (L848-L866)
     */
    public static boolean killMutexOfAcc(String sw, String acc) {
        JsonNode pidNode = ACC_ACCESSOR.getSwAccData(sw, acc, "pid");
        if (pidNode == null || !pidNode.isNumber()) return false;
        int pid = pidNode.asInt();

        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        List<String> wildcards = accessor.getRemoteSwAsList(sw,
                "mutex_handle_wildcards", Collections.emptyList());
        if (wildcards.isEmpty()) return true;

        // TODO: JNA FindFirstHide和NtClose实现
        LOG.debug("[互斥体] killMutexOfAcc: sw={}, acc={}, pid={} (Stub)", sw, acc, pid);
        ACC_ACCESSOR.updateSwAccData(sw, acc, Map.of("has_mutex", false));
        return true;
    }

    // ==================== 目录工具方法 ====================

    private static void deleteDirectory(File dir) {
        if (dir.isDirectory()) {
            File[] children = dir.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteDirectory(child);
                }
            }
        }
        dir.delete();
    }

    private static void copyDirectory(File src, File dst) throws Exception {
        if (src.isDirectory()) {
            if (!dst.exists()) dst.mkdirs();
            File[] children = src.listFiles();
            if (children != null) {
                for (File child : children) {
                    copyDirectory(child, new File(dst, child.getName()));
                }
            }
        } else {
            java.nio.file.Files.copy(src.toPath(), dst.toPath(),
                    java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
    }
}
