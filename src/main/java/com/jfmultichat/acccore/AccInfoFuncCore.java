package com.jfmultichat.acccore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import com.jfmultichat.appcore.AppCore;
import com.jfmultichat.config.ConfigManager;
import com.jfmultichat.config.SwConfigProvider;
import com.jfmultichat.swcore.SwConfigAccessor;
import com.jfmultichat.utils.AvatarUtils;

/**
 * 账号信息核心 — 账号数据读写、头像管理、登录状态、窗口绑定等
 * <p>
 * 对应 Python: AccInfoFuncCore (L869-L1617)
 * <p>
 * 包含：头像获取/删除/缓存、展示名、登录配置状态、账号列表、登录状态检测、窗口绑定等。
 *
 * 依赖: AccConfigAccessor, SwConfigAccessor (间接通过 AppCore)
 */
public final class AccInfoFuncCore {

    private static final Logger LOG = LoggerFactory.getLogger(AccInfoFuncCore.class);
    private static final AccConfigAccessor ACC_ACCESSOR = new AccConfigAccessor();
    private static final ExecutorService IO_EXECUTOR = Executors.newFixedThreadPool(4);

    private AccInfoFuncCore() {
        throw new UnsupportedOperationException("AccInfoFuncCore is a static utility class");
    }

    // ==================== 数据存储 ====================

    /**
     * 获取账号数据
     * 对应 Python: get_sw_acc_data (L879-L880)
     */
    public static JsonNode getSwAccData(String sw, String acc, String... addr) {
        return ACC_ACCESSOR.getSwAccData(sw, acc, addr);
    }

    /**
     * 更新账号数据
     * 对应 Python: update_sw_acc_data (L883-L884)
     */
    public static void updateSwAccData(String sw, String acc, Map<String, Object> kwargs) {
        ACC_ACCESSOR.updateSwAccData(sw, acc, kwargs);
    }

    /**
     * 清除账号数据节点
     * 对应 Python: clear_sw_acc_data (L94) → acc_func_core 未直接调用，由 SwInfoFuncCore.clear 代理
     */
    public static void clearSwAccData(String sw, String acc, String... addr) {
        ACC_ACCESSOR.clearSwAccData(sw, acc, addr);
    }

    // ==================== 主程序路径 ====================

    /**
     * 自适应获取账号对应的主程序路径
     * 对应 Python: get_acc_exe_path (L889-L895)
     */
    public static String getAccExePath(String sw, String acc) {
        if (isAccCoexist(sw, acc)) {
            return getCoexistAccExePath(sw, acc);
        }
        SwConfigAccessor swAccessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        return swAccessor.tryGetPathOf(sw, "inst_path");
    }

    // ==================== 头像操作 ====================

    /**
     * 手动选择并保存头像
     * 对应 Python: manual_choose_avatar_for_acc (L962-L1007)
     * <p>
     * Java 环境无 filedialog，仅记录日志，实际 UI 操作由前端完成。
     */
    public static void manualChooseAvatarForAcc(String sw, String acc) {
        LOG.info("[头像] manual_choose_avatar_for_acc: sw={}, acc={} (需 UI 交互，Stub)", sw, acc);
    }

    /**
     * 删除账号头像
     * 对应 Python: delete_avatar_for_acc (L1009-L1015)
     */
    public static boolean deleteAvatarForAcc(String sw, String acc) {
        try {
            String userDir = AppCore.getUserDir();
            String path = userDir + "/" + sw + "/" + acc + "/" + acc + ".jpg";
            File f = new File(path);
            if (f.exists()) {
                f.delete();
            }
            updateSwAccData(sw, acc, Map.of("avatar_url", null));
            LOG.info("[头像] 已删除: {}", path);
            return true;
        } catch (Exception e) {
            LOG.warn("[头像] 删除失败: {}", e.getMessage());
            return false;
        }
    }

    /**
     * 从本地文件或 URL 获取头像（返回 base64 data URL）
     * 对应 Python: get_acc_avatar_from_files (L1017-L1044)
     *
     * @return base64 data URL；无头像返回 null
     */
    public static String getAccAvatarFromFile(String sw, String acc) {
        try {
            return AvatarUtils.getAvatarDataUrl(sw, acc,
                    getSwAccData(sw, acc, "avatar_url") != null
                            ? getSwAccData(sw, acc, "avatar_url").asText(null) : null);
        } catch (Exception e) {
            LOG.warn("[头像] 获取失败: {}", e.getMessage());
            return null;
        }
    }

    /**
     * 从其他平台偷取头像 URL
     * 对应 Python: get_avatar_from_other_sw (L1161-L1202)
     */
    public static boolean getAvatarFromOtherSw(String nowSw, List<String> nowAccList) {
        final java.util.concurrent.atomic.AtomicBoolean changed = new java.util.concurrent.atomic.AtomicBoolean(false);
        JsonNode trimsNode = AppCore.getRemoteSw(nowSw, "trims");
        if (trimsNode == null || !trimsNode.isObject()) return changed.get();
        trimsNode.fields().forEachRemaining(trimsEntry -> {
            String otherSw = trimsEntry.getKey();
            JsonNode trimValues = trimsEntry.getValue();
            if (!trimValues.isArray() || trimValues.size() != 4) return;
            int otherL = trimValues.get(0).asInt();
            int otherR = trimValues.get(1).asInt();
            int nowL = trimValues.get(2).asInt();
            int nowR = trimValues.get(3).asInt();
            int otherRAdjusted = otherR == 0 ? 0 : -otherR;
            int nowRAdjusted = nowR == 0 ? 0 : -nowR;

            // 构建裁剪映射
            Map<String, String> otherCutMap = new LinkedHashMap<>();
            List<String> otherAccs = new ArrayList<>(
                    ConfigManager.getInstance().getAccountMap(otherSw).keySet());
            for (String otherAcc : otherAccs) {
                String cutKey = otherAcc.substring(otherL,
                        otherRAdjusted == 0 ? otherAcc.length() : otherAcc.length() + otherRAdjusted);
                otherCutMap.put(cutKey, otherAcc);
            }

            // 对每个当前账号尝试匹配
            for (String nowAcc : nowAccList) {
                String nowCutAcc = nowAcc.substring(nowL,
                        nowRAdjusted == 0 ? nowAcc.length() : nowAcc.length() + nowRAdjusted);
                String otherAcc = otherCutMap.get(nowCutAcc);
                if (otherAcc == null) continue;
                // 检查头像 URL
                JsonNode nowAvatarUrl = getSwAccData(nowSw, nowAcc, "avatar_url");
                JsonNode otherAvatarUrl = getSwAccData(otherSw, otherAcc, "avatar_url");
                if (otherAvatarUrl != null && otherAvatarUrl.isTextual() && nowAvatarUrl == null) {
                    LOG.info("[头像] {} 偷取 {} 的头像: {}", nowAcc, otherAcc, otherAvatarUrl.asText());
                    updateSwAccData(nowSw, nowAcc, Map.of("avatar_url", otherAvatarUrl.asText()));
                    changed.set(true);
                }
            }
        });
        return changed.get();
    }

    /**
     * 从其他平台偷取昵称
     * 对应 Python: get_nickname_from_other_sw (L1204-L1226)
     */
    public static boolean getNicknameFromOtherSw(String nowSw, List<String> nowAccList) {
        final java.util.concurrent.atomic.AtomicBoolean changed = new java.util.concurrent.atomic.AtomicBoolean(false);
        JsonNode trimsNode = AppCore.getRemoteSw(nowSw, "trims");
        if (trimsNode == null || !trimsNode.isObject()) return changed.get();
        trimsNode.fields().forEachRemaining(trimsEntry -> {
            String otherSw = trimsEntry.getKey();
            JsonNode trimValues = trimsEntry.getValue();
            if (!trimValues.isArray() || trimValues.size() != 4) return;
            int nowL = trimValues.get(2).asInt();
            int nowR = trimValues.get(3).asInt();
            if (nowL >= trimValues.size() || nowR >= trimValues.size()) return;

            Map<String, String> otherCutMap = new LinkedHashMap<>();
            for (String otherAcc : ConfigManager.getInstance().getAccountMap(otherSw).keySet()) {
                int end = nowR == 0 ? otherAcc.length() : Math.min(otherAcc.length(), nowR);
                otherCutMap.put(otherAcc.substring(0, end), otherAcc);
            }

            for (String nowAcc : nowAccList) {
                int end = nowR == 0 ? nowAcc.length() : Math.min(nowAcc.length(), nowR);
                String nowCut = nowAcc.substring(0, nowL > 0 ? nowL : 0);
                String otherAcc = otherCutMap.get(nowCut);
                if (otherAcc == null) continue;
                JsonNode nowNick = getSwAccData(nowSw, nowAcc, "nickname");
                JsonNode otherNick = getSwAccData(otherSw, otherAcc, "nickname");
                if (otherNick != null && otherNick.isTextual() && nowNick == null) {
                    LOG.info("[昵称] {} 偷取 {} 的昵称: {}", nowAcc, otherAcc, otherNick.asText());
                    updateSwAccData(nowSw, nowAcc, Map.of("nickname", otherNick.asText()));
                    changed.set(true);
                }
            }
        });
        return changed.get();
    }

    /**
     * 从缓存目录恢复头像
     * 对应 Python: get_avatar_from_cache (L1108-L1137)
     */
    public static boolean getAvatarFromCache(String sw, List<String> accList) {
        boolean changed = false;
        String userDir = AppCore.getUserDir();
        String tempDir = System.getProperty("java.io.tmpdir");
        String cacheSuffix = "avatar_cache";
        java.text.SimpleDateFormat sdf = new java.text.SimpleDateFormat("yyyyMMdd");
        String today = sdf.format(new java.util.Date());

        for (String acc : accList) {
            JsonNode pidNode = getSwAccData(sw, acc, "pid");
            String avatarPath = userDir + "/" + sw + "/" + acc + "/" + acc + ".jpg";
            if (new File(avatarPath).exists()) continue;
            if (pidNode == null || !pidNode.isNumber()) continue;
            int pid = pidNode.asInt();
            String captDir = tempDir + "/" + cacheSuffix + "/" + pid + "_" + today;
            File dir = new File(captDir);
            if (!dir.exists() || !dir.isDirectory()) continue;
            File[] files = dir.listFiles((d, n) -> n.endsWith(".png") || n.endsWith(".jpg"));
            if (files == null || files.length == 0) continue;
            Arrays.sort(files, (a, b) -> Long.compare(b.lastModified(), a.lastModified()));
            File cacheFile = files.length > 1 ? files[1] : files[0];
            try {
                new File(new File(avatarPath).getParent()).mkdirs();
                java.nio.file.Files.copy(cacheFile.toPath(),
                        java.nio.file.Path.of(avatarPath),
                        java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                changed = true;
                LOG.info("[头像缓存] 恢复: {} -> {}", cacheFile, avatarPath);
            } catch (Exception e) {
                LOG.warn("[头像缓存] 恢复失败: {}", e.getMessage());
            }
        }
        return changed;
    }

    // ==================== 展示名 ====================

    /**
     * 获取账号展示名
     * 对应 Python: get_acc_origin_display_name (L1057-L1066)
     */
    public static String getAccOriginDisplayName(String sw, String acc) {
        String display = acc;
        for (String key : List.of("remark", "nickname", "alias")) {
            JsonNode val = getSwAccData(sw, acc, key);
            if (val != null && val.isTextual() && !val.asText().isEmpty()) {
                display = val.asText();
                break;
            }
        }
        return display;
    }

    // ==================== 登录配置状态 ====================

    /**
     * 获取账号登录配置状态
     * 对应 Python: get_sw_acc_login_cfg_status (L1068-L1104)
     */
    public static String getSwAccLoginCfgStatus(String sw, String account) {
        try {
            SwConfigAccessor swConfigAccessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
            JsonNode configAddresses = swConfigAccessor.getRemoteSw(sw, "config_addresses");
            if (configAddresses == null || !configAddresses.isArray() || configAddresses.isEmpty()) {
                return "无法获取登录配置文件地址";
            }
            String originCfgPath = com.jfmultichat.appcore.AppCore.readRemoteCfgInRules("RemoteSw") != null
                    ? sw : ""; // 简化处理，实际需要 SwPathResolver.resolveSwPath
            // 直接使用 resolved path
            String originCfgBasename = new File(originCfgPath).getName();
            String oldFileSuffix = originCfgBasename.contains(".")
                    ? originCfgBasename.substring(originCfgBasename.lastIndexOf('.') + 1) : "dat";
            String oldAccCfgBasename = account + "." + oldFileSuffix;
            String newAccCfgBasename = account + "_" + originCfgBasename;
            String oneAccCfgPath = new File(originCfgPath).getParent() + "/" + newAccCfgBasename;
            File accCfgFile = new File(oneAccCfgPath.replace('\\', '/'));
            if (accCfgFile.exists()) {
                long modTime = accCfgFile.lastModified();
                java.util.Date date = new java.util.Date(modTime);
                java.text.SimpleDateFormat sdf = new java.text.SimpleDateFormat("yy/MM/dd HH:mm");
                return sdf.format(date);
            }
            return AccCoreConstants.CfgStatus.NO_CFG;
        } catch (Exception e) {
            LOG.warn("[登录配置] 获取状态失败: {}", e.getMessage());
            return "error";
        }
    }

    // ==================== 共存判断 ====================

    /**
     * 判断是否为共存账号
     * 对应 Python: is_acc_coexist (L1230-L1235)
     */
    public static boolean isAccCoexist(String sw, String acc) {
        JsonNode accDict = getSwAccData(sw, acc);
        if (accDict == null || !accDict.isObject()) return false;
        return accDict.has("linked_acc");
    }

    /**
     * 获取真实关联账号
     * 对应 Python: get_real_acc (L1237-L1245)
     */
    public static String getRealAcc(String sw, String acc) {
        JsonNode accDict = getSwAccData(sw, acc);
        if (accDict == null || !accDict.isObject()) return acc;
        JsonNode linked = accDict.get("linked_acc");
        return linked != null && linked.isTextual() ? linked.asText(acc) : acc;
    }

    /**
     * 获取共存 exe 名
     */
    public static String getCoexistAccExe(String sw, String acc) {
        return isAccCoexist(sw, acc) ? acc : null;
    }

    /**
     * 获取共存 exe 路径
     */
    public static String getCoexistAccExePath(String sw, String acc) {
        String exeName = getCoexistAccExe(sw, acc);
        if (exeName == null) return null;
        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        String swPath = accessor.tryGetPathOf(sw, "inst_path");
        if (swPath == null) return null;
        return new File(swPath).getParent() + "/" + exeName;
    }

    /**
     * 获取共存账号的方案和序号
     */
    public static String[] getCoexistAccChannelAndOrdinal(String sw, String acc) {
        String channel = getCoexistAccChannel(sw, acc);
        if (channel == null) return new String[]{null, null};
        // ordinal 从 exe_wildcard 中提取
        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        JsonNode exeWildcard = accessor.getRemoteSw(sw, "coexist", "channels", channel, "exe_wildcard");
        if (exeWildcard == null || !exeWildcard.isTextual()) return new String[]{channel, null};
        String exeName = getCoexistAccExe(sw, acc);
        String ordinal = extractWildcardChar(exeName, exeWildcard.asText());
        return new String[]{channel, ordinal};
    }

    /**
     * 获取共存账号使用的方案
     */
    public static String getCoexistAccChannel(String sw, String acc) {
        String exeName = getCoexistAccExe(sw, acc);
        JsonNode cachedChannel = getSwAccData(sw, acc, "channel");
        if (cachedChannel != null && cachedChannel.isTextual()) {
            return cachedChannel.asText();
        }
        // 遍历远程配置寻找匹配
        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        JsonNode channelsDict = accessor.getRemoteSw(sw, "coexist", "channels");
        if (channelsDict == null || !channelsDict.isObject()) return null;
        channelsDict.fields().forEachRemaining(chEntry -> {
            String channel = chEntry.getKey();
            JsonNode wc = chEntry.getValue().get("exe_wildcard");
            if (wc != null && wc.isTextual() && wildcardMatch(exeName, wc.asText())) {
                updateSwAccData(sw, acc, Map.of("channel", channel));
            }
        });
        return cachedChannel != null && cachedChannel.isTextual() ? cachedChannel.asText() : null;
    }

    /**
     * 获取共存账号的互斥锁列表
     */
    public static List<String> getCoexistAccMutexList(String sw, String acc) {
        List<String> mutexList = new ArrayList<>();
        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        JsonNode mutantHandles = accessor.getRemoteSw(sw, "mutex_handles");
        if (mutantHandles == null || !mutantHandles.isArray()) return mutexList;
        mutantHandles.forEach(handleRegex -> {
            String mutexName = handleRegex.has("handle_name")
                    ? handleRegex.get("handle_name").asText() : null;
            if (mutexName == null) return;
            if (isAccCoexist(sw, acc)) {
                String[] coexistInfo = getCoexistAccChannelAndOrdinal(sw, acc);
                String channel = coexistInfo[0];
                if (channel != null) {
                    JsonNode mutexWcNode = accessor.getRemoteSw(
                            sw, "coexist", "channels", channel, "mutex_wc", mutexName);
                    if (mutexWcNode != null && mutexWcNode.isTextual()) {
                        mutexName = mutexWcNode.asText().replace("?", coexistInfo[1] != null ? coexistInfo[1] : "");
                    }
                }
            }
            mutexList.add(mutexName);
        });
        return mutexList;
    }

    // ==================== 账号列表 & 登录状态 ====================

    /**
     * 获取平台所有账号
     * 对应 Python: Sw.get_existed_accounts (L200-L201) → SwInfoFuncCore.get_sw_all_accounts_existed
     */
    public static List<String> getSwAllAccountsExisted(String sw, String only) {
        SwConfigAccessor swAccessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        return com.jfmultichat.swcore.SwAccountOps.getSwAllAccountsExisted(
                sw,
                swAccessor.tryGetPathOf(sw, "data_dir"),
                swAccessor.getRemoteSwAsList(sw, "excluded_dirs", Collections.emptyList()),
                swAccessor.tryGetPathOf(sw, "inst_path"),
                swAccessor.getRemoteSwAsList(sw, "executable_wildcards", Collections.emptyList()),
                swAccessor, null, only);
    }

    /**
     * 获取账号登录状态
     * 对应 Python: get_sw_accounts_login_status (L1393-L1461)
     * <p>
     * 门面方法：依次调用拆分后的步骤（解析PID → 共存关联 → 数据回写），并计算登录/未登录列表。
     */
    public static String[] getSwAccountsLoginStatus(String sw) {
        Map<Integer, String> pidAccMap = resolvePidAccountMap(sw);
        if (pidAccMap == null) {
            return new String[]{"false", "数据路径不存在"};
        }
        pidAccMap = associateCoexistAccounts(sw, pidAccMap);
        List<String> allAccs = getSwAllAccountsExisted(sw, null);
        updateAccLoginData(sw, pidAccMap, allAccs);

        // 计算登录/未登录列表
        Set<String> loginSet = new HashSet<>(pidAccMap.values());
        List<String> logins = new ArrayList<>(loginSet);
        logins.retainAll(allAccs);
        List<String> logouts = new ArrayList<>(allAccs);
        logouts.removeAll(loginSet);
        return new String[]{"true", "{login=" + logins + ",logout=" + logouts + "}"};
    }

    /**
     * 解析进程到账号的 PID 映射（配置读取 + 进程枚举/过滤 + 内存映射匹配）.
     * <p>
     * 对应 Python: get_sw_accounts_login_status 的 PID 解析段 (L1398-L1425).
     *
     * @param sw 软件标识
     * @return PID → 账号 ID 映射；data_dir 缺失时返回 null（调用方据此提示"数据路径不存在"）
     */
    public static Map<Integer, String> resolvePidAccountMap(String sw) {
        SwConfigAccessor swAccessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        String dataDir = swAccessor.tryGetPathOf(sw, "data_dir");
        if (dataDir == null) {
            return null;
        }
        List<String> excludedDirs = swAccessor.getRemoteSwAsList(sw, "excluded_dirs", Collections.emptyList());
        List<String> exeWildcards = swAccessor.getRemoteSwAsList(sw, "executable_wildcards", Collections.emptyList());

        // 获取所有 PID
        List<Integer> allPids = com.jfmultichat.swcore.SwNativeOps.INSTANCE
                .getPidsByWildcardsAndGroup(exeWildcards).values().stream()
                .flatMap(List::stream).toList();
        allPids = com.jfmultichat.swcore.SwNativeOps.removeChildPids(allPids);
        allPids = com.jfmultichat.swcore.SwNativeOps.removePidsNotInPath(
                allPids, new File(swAccessor.tryGetPathOf(sw, "inst_path")).getParent());

        // 匹配进程到账号（内存映射）
        Map<Integer, String> pidAccMap = new HashMap<>();
        for (int pid : allPids) {
            List<String> memPaths = com.jfmultichat.swcore.SwNativeOps.INSTANCE
                    .enumerateByVirtualQueryEx(pid);
            for (String path : memPaths) {
                if (path.startsWith(dataDir.replace('\\', '/'))) {
                    String[] parts = path.replace('\\', '/').split("/");
                    int dataDirIdx = -1;
                    for (int i = 0; i < parts.length; i++) {
                        if (parts[i].equals(new File(dataDir).getName())) {
                            dataDirIdx = i;
                            break;
                        }
                    }
                    if (dataDirIdx >= 0 && dataDirIdx + 1 < parts.length) {
                        String acc = parts[dataDirIdx + 1];
                        if (!excludedDirs.contains(acc)) {
                            pidAccMap.put(pid, acc);
                            break;
                        }
                    }
                }
            }
        }
        return pidAccMap;
    }

    /**
     * 关联共存进程（写入 linked_acc 并补全 PID 映射）.
     * <p>
     * 对应 Python: get_sw_accounts_login_status 的共存段 (L1436-L1447).
     *
     * @param sw        软件标识
     * @param pidAccMap PID → 账号映射（会被修改：新增共存项）
     * @return 补全后的 PID → 账号映射
     */
    public static Map<Integer, String> associateCoexistAccounts(String sw, Map<Integer, String> pidAccMap) {
        SwConfigAccessor swAccessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        List<String> exeWildcards = swAccessor.getRemoteSwAsList(sw, "executable_wildcards", Collections.emptyList());
        String originExe = swAccessor.getRemoteSwAsString(sw, "executable", "");
        for (Map.Entry<Integer, String> entry : pidAccMap.entrySet()) {
            int pid = entry.getKey();
            String acc = entry.getValue();
            String pidExe = com.jfmultichat.swcore.SwNativeOps.INSTANCE
                    .getProcessImagePath(pid);
            if (pidExe != null && !originExe.isEmpty()) {
                for (String wc : exeWildcards) {
                    if (wildcardMatch(new File(pidExe).getName(), wc)
                            && !new File(pidExe).getName().equals(originExe)) {
                        updateSwAccData(sw, pidExe.split("/").length > 0
                                ? pidExe.substring(pidExe.lastIndexOf('/') + 1) : pidExe,
                                Map.of("linked_acc", acc));
                        pidAccMap.put(pid, pidExe.split("/").length > 0
                                ? pidExe.substring(pidExe.lastIndexOf('/') + 1) : pidExe);
                        break;
                    }
                }
            }
        }
        return pidAccMap;
    }

    /**
     * 回写账号登录相关本地数据：PID 与互斥体状态（含 relay 读回）.
     * <p>
     * 对应 Python: get_sw_accounts_login_status 的数据回写段 (L1450-L1461).
     *
     * @param sw        软件标识
     * @param pidAccMap PID → 账号映射
     * @param allAccs   磁盘扫描得到的全部账号 ID 列表
     */
    public static void updateAccLoginData(String sw, Map<Integer, String> pidAccMap, List<String> allAccs) {
        // 记录 pid
        for (String acc : allAccs) {
            Integer pid = null;
            for (Map.Entry<Integer, String> e : pidAccMap.entrySet()) {
                if (e.getValue().equals(acc)) {
                    pid = e.getKey();
                    break;
                }
            }
            // 用 HashMap：pid 可能为 null（未运行的账号），Map.of 不允许 null 值会抛 NPE
            // updateAccount 对 null 值会移除该键，未运行账号不存 pid
            Map<String, Object> accData = new HashMap<>();
            accData.put(AccCoreConstants.AccKey.PID, pid);
            accData.put(AccCoreConstants.AccKey.HAS_MUTEX, false);
            updateSwAccData(sw, acc, accData);
        }

        // 从记录加载互斥体
        JsonNode relayNode = getSwAccData(sw, AccCoreConstants.AccKey.RELAY);
        if (relayNode != null && relayNode.isObject() && relayNode.has("pid_mutex")) {
            JsonNode pidMutexNode = relayNode.get("pid_mutex");
            if (pidMutexNode != null && pidMutexNode.isObject()) {
                for (String acc : allAccs) {
                    JsonNode accNode = getSwAccData(sw, acc);
                    if (accNode != null && accNode.isObject() && accNode.has("pid")) {
                        int accPid = accNode.get("pid").asInt();
                        // pid 可能不在 pid_mutex 映射中，需判空再取（缺省视为 false）
                        JsonNode pmNode = pidMutexNode.get(String.valueOf(accPid));
                        boolean pm = pmNode != null && pmNode.asBoolean(false);
                        updateSwAccData(sw, acc, Map.of(AccCoreConstants.AccKey.HAS_MUTEX, pm));
                    }
                }
            }
        }
    }

    // ==================== 账号同步 ====================

    /**
     * 确保 SwAccData 中存在已加载账号的节点；缺失的自动补充为空节点.
     * <p>
     * 对应 Python: get_sw_accounts_login_status 中 allAccs = getSwAllAccountsExisted(sw, null)
     * 之后的账号补齐思路（目前无 pid 获取，仅保证本地数据包含已加载账号）.
     *
     * @param sw         软件标识
     * @param accountIds 已加载的账号 ID 列表（磁盘扫描结果）
     * @return 本次新增的账号 ID 列表
     */
    public static List<String> syncSwAccAccounts(String sw, List<String> accountIds) {
        List<String> added = new ArrayList<>();
        if (accountIds == null || accountIds.isEmpty()) return added;
        for (String acc : accountIds) {
            JsonNode node = getSwAccData(sw, acc);
            if (node == null || !node.isObject()) {
                updateSwAccData(sw, acc, Collections.emptyMap());
                added.add(acc);
            }
        }
        if (!added.isEmpty()) {
            LOG.info("[Acc] 自动补充 SwAccData 账号节点: {} -> {}", sw, added);
        }
        return added;
    }

    // ==================== 详情 ====================

    /**
     * 获取账号详情
     * 对应 Python: get_acc_details (L1465-L1520)
     */
    public static Map<String, Object> getAccDetails(String sw, String account) {
        Map<String, Object> details = new LinkedHashMap<>();
        String linkedAcc = getRealAcc(sw, account);
        boolean coexist = isAccCoexist(sw, account);

        // 头像
        String avatarUrl = null;
        JsonNode avatarNode = getSwAccData(sw, account, "avatar_url");
        if (avatarNode != null && avatarNode.isTextual()) avatarUrl = avatarNode.asText();
        String avatarDataUrl = AvatarUtils.getAvatarDataUrl(sw, account, avatarUrl);
        details.put(AccCoreConstants.AccKey.AVATAR, avatarDataUrl);

        // 展示名
        String accDisplayName = getAccOriginDisplayName(sw, account);
        String linkedDisplayName = getAccOriginDisplayName(sw, linkedAcc);
        String displayName = accDisplayName.equals(account) ? linkedDisplayName : accDisplayName;

        // 配置状态
        String configStatus = coexist ? account : getSwAccLoginCfgStatus(sw, account);

        // pid, has_mutex 等
        JsonNode pidNode = getSwAccData(sw, account, "pid");
        JsonNode hasMutexNode = getSwAccData(sw, account, "has_mutex");
        JsonNode hotkeyNode = getSwAccData(sw, account, "hotkey");
        JsonNode hiddenNode = getSwAccData(sw, account, "hidden");
        JsonNode autoStartNode = getSwAccData(sw, account, "auto_start");

        details.put(AccCoreConstants.AccKey.IID, sw + "/" + account);
        details.put(AccCoreConstants.AccKey.DISPLAY, displayName);
        details.put(AccCoreConstants.AccKey.CONFIG_STATUS, configStatus);
        details.put(AccCoreConstants.AccKey.PID, pidNode != null ? pidNode.asInt() : null);
        details.put(AccCoreConstants.AccKey.HAS_MUTEX,
                hasMutexNode != null ? hasMutexNode.asBoolean() : false);
        details.put(AccCoreConstants.AccKey.HOTKEY,
                hotkeyNode != null ? hotkeyNode.asText() : null);
        details.put(AccCoreConstants.AccKey.HIDDEN,
                hiddenNode != null ? hiddenNode.asBoolean() : null);
        details.put(AccCoreConstants.AccKey.AUTO_START,
                autoStartNode != null ? autoStartNode.asBoolean() : null);
        details.put(AccCoreConstants.AccKey.LINKED_ACC, linkedAcc);

        JsonNode aliasNode = getSwAccData(sw, linkedAcc, "alias");
        JsonNode nicknameNode = getSwAccData(sw, linkedAcc, "nickname");
        details.put(AccCoreConstants.AccKey.ALIAS,
                aliasNode != null ? aliasNode.asText("请获取数据") : "请获取数据");
        details.put(AccCoreConstants.AccKey.NICKNAME,
                nicknameNode != null ? nicknameNode.asText("请获取数据") : "请获取数据");

        return details;
    }

    // ==================== 窗口绑定 ====================

    /**
     * 获取账号主窗口句柄
     * 对应 Python: get_main_hwnd_of_accounts (L1524-L1547)
     */
    public static Map<String, Integer> getMainHwndOfAccounts(String sw, List<String> accList) {
        Map<String, Integer> result = new LinkedHashMap<>();
        SwConfigAccessor swAccessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        List<Map<String, Object>> wndMatchingDicts = swAccessor.getRemoteSw(sw,
                "wnd_class", "main", "matching") != null
                ? swAccessor.getRemoteSw(sw, "wnd_class", "main", "matching")
                        .has("class_name")
                        ? Collections.singletonList(
                                Map.of("class_name", swAccessor.getRemoteSw(sw, "wnd_class", "main", "original")
                                        .path("class_name").asText()))
                        : Collections.emptyList()
                : Collections.emptyList();

        for (String acc : accList) {
            JsonNode pidNode = getSwAccData(sw, acc, "pid");
            if (pidNode == null || !pidNode.isNumber()) continue;
            int pid = pidNode.asInt();
            for (Map<String, Object> rule : wndMatchingDicts) {
                // TODO: 需要 JNA 枚举窗口并按规则筛选
                LOG.debug("[窗口] getMainHwnd: sw={}, acc={}, pid={}, rule={}", sw, acc, pid, rule);
            }
        }
        return result;
    }

    /**
     * 自动绑定主窗口到账号
     * 对应 Python: auto_bind_main_wnd_to_accounts_in_sw (L1549-L1558)
     */
    public static void autoBindMainWndToAccounts(String sw, List<String> accList) {
        Map<String, Integer> hwndMap = getMainHwndOfAccounts(sw, accList);
        for (Map.Entry<String, Integer> entry : hwndMap.entrySet()) {
            recordHwndAndSetTitle(sw, entry.getKey(), entry.getValue());
        }
    }

    /**
     * 记录窗口句柄并设置标题
     */
    private static void recordHwndAndSetTitle(String sw, String acc, int hwnd) {
        updateSwAccData(sw, acc, Map.of("main_hwnd", hwnd));
        String swDisplay = com.jfmultichat.swcore.SwAccountOps.getSwOriginDisplayName(sw,
                com.jfmultichat.config.SwConfigProvider.newAccessor());
        String accDisplay = getAccOriginDisplayName(sw, acc);
        LOG.info("[窗口] 设置标题: {} - {}", swDisplay, accDisplay);
    }

    /**
     * 解除账号与窗口的绑定
     */
    public static void unlinkHwndOfAccount(String sw, String account) {
        updateSwAccData(sw, account, Map.of("main_hwnd", null));
        LOG.info("[窗口] 已解绑账号: {}", account);
    }

    // ==================== 工具方法 ====================

    /**
     * 从 exe 名称中通配符提取序号字符
     */
    public static String extractWildcardChar(String name, String wildcard) {
        if (name == null || wildcard == null) return null;
        StringBuilder sb = new StringBuilder();
        int wi = 0, ni = 0;
        while (wi < wildcard.length() && ni < name.length()) {
            char wc = wildcard.charAt(wi);
            if (wc == '?') {
                sb.append(name.charAt(ni));
            } else if (wc == '*') {
                // * 匹配任意长度
            } else if (wc == name.charAt(ni)) {
                // 字符匹配
            } else {
                break;
            }
            wi++;
            ni++;
        }
        return sb.length() > 0 ? sb.toString() : null;
    }

    private static boolean wildcardMatch(String name, String wildcard) {
        String regex = wildcard.replace(".", "\\.").replace("*", ".*").replace("?", ".");
        return name.matches("^" + regex + "$");
    }
}
