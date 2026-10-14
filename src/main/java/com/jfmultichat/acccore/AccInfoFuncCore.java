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
     * 清除账号在数据目录里的头像文件：`{userData}/{sw}/{acc}/` 下的图片，随后删掉空目录.
     *
     * <p>读取端只认 {@code {acc}.jpg}，但目录里可能残留历史的 png/gif → 按扩展名扫掉**所有图片**，
     * 再在目录为空时删掉目录本身（**只删空目录，绝不递归删其它文件**）。
     *
     * <p>只清文件、**不动配置** —— 供"重置/删除账号"复用（重置的配置清空由 ConfigManager 负责）。
     *
     * @return 有文件或目录被删除时 true；目录本来就不存在时 false
     */
    public static boolean deleteAccountAvatarFiles(String sw, String acc) {
        try {
            String userDir = AppCore.getUserDir();
            File dir = new File(userDir + "/" + sw + "/" + acc);
            if (!dir.isDirectory()) return false;
            boolean deleted = false;
            File[] files = dir.listFiles();
            if (files != null) {
                for (File f : files) {
                    String n = f.getName().toLowerCase();
                    if (f.isFile() && (n.endsWith(".jpg") || n.endsWith(".jpeg") || n.endsWith(".png")
                            || n.endsWith(".bmp") || n.endsWith(".gif"))) {
                        if (f.delete()) deleted = true;
                        else LOG.warn("[头像] 删除失败: {}", f);
                    }
                }
            }
            File[] left = dir.listFiles();
            if (left != null && left.length == 0 && dir.delete()) deleted = true;
            if (deleted) LOG.info("[头像] 已清除账号头像文件: {}/{}", sw, acc);
            return deleted;
        } catch (Exception e) {
            LOG.warn("[头像] 清除头像文件失败: {}", e.getMessage());
            return false;
        }
    }

    /**
     * 删除账号头像
     * 对应 Python: delete_avatar_for_acc (L1009-L1015)
     */
    public static boolean deleteAvatarForAcc(String sw, String acc) {
        try {
            String userDir = AppCore.getUserDir();
            String path = userDir + "/" + sw + "/" + acc + "/" + acc + ".jpg";
            deleteAccountAvatarFiles(sw, acc);
            // 注意：这里**不能**用 Map.of —— Map.of 不接受 null 值，会抛 NPE 被下面的 catch 吞掉，
            // 结果是"文件删了但方法返回 false、avatar_url 也没清掉"（真实踩过）
            updateSwAccData(sw, acc, java.util.Collections.singletonMap("avatar_url", null));
            LOG.info("[头像] 已删除: {}", path);
            return true;
        } catch (Exception e) {
            LOG.warn("[头像] 删除失败: {}", e.getMessage());
            return false;
        }
    }

    /**
     * 手动导入头像：把用户选中的图片写成该账号的本地头像文件.
     *
     * <p>目标路径与 {@link AvatarUtils} 的读取路径一致（{@code {userData}/{sw}/{acc}/{acc}.jpg}），
     * 源图可能是 png/bmp/gif，统一转成 JPEG 再写（读取端固定按 jpg 编 data URL）。
     * 同时清掉 {@code avatar_url}：手动选的头像不应被网络头像覆盖（与旧版 Python 语义一致）。
     *
     * @param src 用户选中的图片文件
     * @return 新头像的 data URL；失败返回 null
     */
    public static String importAvatarForAcc(String sw, String acc, File src) {
        try {
            if (src == null || !src.isFile()) return null;
            java.awt.image.BufferedImage img = javax.imageio.ImageIO.read(src);
            if (img == null) return null;   // 不是可识别的图片格式

            String userDir = AppCore.getUserDir();
            File dest = new File(userDir + "/" + sw + "/" + acc + "/" + acc + ".jpg");
            File parent = dest.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs()) {
                LOG.warn("[头像] 无法创建目录: {}", parent);
                return null;
            }
            // JPEG 不支持透明通道：先铺白底再转 TYPE_INT_RGB
            java.awt.image.BufferedImage rgb = img;
            if (img.getType() != java.awt.image.BufferedImage.TYPE_INT_RGB) {
                rgb = new java.awt.image.BufferedImage(img.getWidth(), img.getHeight(),
                        java.awt.image.BufferedImage.TYPE_INT_RGB);
                java.awt.Graphics2D g = rgb.createGraphics();
                g.drawImage(img, 0, 0, java.awt.Color.WHITE, null);
                g.dispose();
            }
            if (!javax.imageio.ImageIO.write(rgb, "jpg", dest)) {
                LOG.warn("[头像] 写文件失败: {}", dest);
                return null;
            }
            updateSwAccData(sw, acc, java.util.Collections.singletonMap("avatar_url", null));
            LOG.info("[头像] 手动导入: {} -> {}", src, dest);
            return AvatarUtils.getLocalAvatarDataUrl(sw, acc);
        } catch (Exception e) {
            LOG.warn("[头像] 手动导入失败: {}", e.getMessage());
            return null;
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
            // 文字兜底用的名称 = 账号展示名（备注 > 昵称 > 平台内ID > ID）；取名称末尾 4 个字符宽
            return AvatarUtils.getAvatarDataUrl(sw, acc,
                    getSwAccData(sw, acc, "avatar_url") != null
                            ? getSwAccData(sw, acc, "avatar_url").asText(null) : null,
                    getAccOriginDisplayName(sw, acc));
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
            // pid 改从**内存**运行时存储取（旧版从配置读，值是过时的）
            Integer pidVal = AccRuntimeStore.getPid(sw, acc);
            String avatarPath = userDir + "/" + sw + "/" + acc + "/" + acc + ".jpg";
            if (new File(avatarPath).exists()) continue;
            if (pidVal == null) continue;
            int pid = pidVal;
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

    /**
     * **表格里真正显示的那个名字**（用户 2026-10-13：窗口标题要用名称，不要用 id）.
     *
     * <p>规则与前端名称列一致：自身有备注/昵称/别名就用它；**退化成 id 时改用"链接账号"的名字**
     * —— 共存账号（id 是副本 exe 名 ✗）正是这种情况，它的名字来自所链接的原生账号 ✓。
     */
    public static String getAccDisplayName(String sw, String acc) {
        if (acc == null) return "";
        String own = getAccOriginDisplayName(sw, acc);
        if (!own.equals(acc)) return own;
        String linked = getRealAcc(sw, acc);
        if (linked != null && !linked.equals(acc)) {
            String linkedName = getAccOriginDisplayName(sw, linked);
            if (!linkedName.equals(linked)) return linkedName;
        }
        return own;
    }

    // ==================== 登录配置状态 ====================

    /**
     * 获取账号登录配置状态
     * 对应 Python: get_sw_acc_login_cfg_status (L1068-L1104)
     *
     * <p>修（2026-10-07）：原来路径解析是假的 —— `originCfgPath` 被直接赋成平台 id（注释还写着
     * "简化处理，实际需要 SwPathResolver.resolveSwPath"），拼出来的 `{account}_{配置文件名}`
     * 永远不存在 → **所有账号一律 no_cfg**。现在按旧版用 SwPathResolver 解析每个 config_address，
     * 并**同时认旧命名**（`{account}.{ext}`，旧版会把它复制成新命名；这里只读不写，不污染平台目录）。
     *
     * @return 配置文件的修改时间 "yy/MM/dd HH:mm"；没有则 {@link AccCoreConstants.CfgStatus#NO_CFG}
     */
    public static String getSwAccLoginCfgStatus(String sw, String account) {
        try {
            com.jfmultichat.swcore.SwConfigAccessor accessor =
                    com.jfmultichat.config.SwConfigProvider.newAccessor();
            JsonNode configAddresses = accessor.getRemoteSw(sw, "config_addresses");
            if (configAddresses == null || !configAddresses.isArray() || configAddresses.isEmpty()) {
                return "无法获取登录配置文件地址";
            }
            long bestTime = -1;
            for (JsonNode addrNode : configAddresses) {
                if (addrNode == null || !addrNode.isTextual()) continue;
                String originCfgPath = com.jfmultichat.swcore.SwPathResolver
                        .resolveSwPath(sw, addrNode.asText(), accessor);
                if (originCfgPath == null || originCfgPath.isBlank()) continue;
                File originCfgFile = new File(originCfgPath);
                String dir = originCfgFile.getParent();
                String base = originCfgFile.getName();
                if (dir == null || base.isEmpty()) continue;
                String suffix = base.contains(".")
                        ? base.substring(base.lastIndexOf('.') + 1) : "dat";
                // 新命名：{account}_{配置文件名}（旧版主用）；旧命名：{account}.{ext}（兼容）
                File newCfg = new File(dir, account + "_" + base);
                File oldCfg = new File(dir, account + "." + suffix);
                if (newCfg.exists()) bestTime = Math.max(bestTime, newCfg.lastModified());
                else if (oldCfg.exists()) bestTime = Math.max(bestTime, oldCfg.lastModified());
            }
            if (bestTime > 0) {
                return new java.text.SimpleDateFormat("yy/MM/dd HH:mm")
                        .format(new java.util.Date(bestTime));
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
     *
     * <p>修（2026-10-07）：原来遍历远程配置时**只把命中的 channel 写进了配置**，
     * 返回值却用的是循环**之前**读到的缓存 → 首次调用必然返回 null（然后连带
     * {@link #getCoexistAccChannelAndOrdinal} 一起拿到 {null,null}）。现在直接返回命中值。
     */
    public static String getCoexistAccChannel(String sw, String acc) {
        String exeName = getCoexistAccExe(sw, acc);
        JsonNode cachedChannel = getSwAccData(sw, acc, "channel");
        if (cachedChannel != null && cachedChannel.isTextual()) {
            return cachedChannel.asText();
        }
        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        JsonNode channelsDict = accessor.getRemoteSw(sw, "coexist", "channels");
        if (channelsDict == null || !channelsDict.isObject()) return null;
        String matched = null;
        java.util.Iterator<Map.Entry<String, JsonNode>> it = channelsDict.fields();
        while (it.hasNext()) {
            Map.Entry<String, JsonNode> chEntry = it.next();
            JsonNode wc = chEntry.getValue().get("exe_wildcard");
            if (wc != null && wc.isTextual() && wildcardMatch(exeName, wc.asText())) {
                matched = chEntry.getKey();
                break;
            }
        }
        if (matched != null) updateSwAccData(sw, acc, Map.of("channel", matched));
        return matched;
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
                swAccessor, new AccOpsProvider().toSwProvider(), only);
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

        // 匹配进程到账号（内存映射）—— **并发**扫描：每个 pid 要遍历整个地址空间，串行会明显偏慢
        // （Python 版用 ThreadPoolExecutor(max_workers=8)，这里对齐）
        Map<Integer, String> pidAccMap = new java.util.concurrent.ConcurrentHashMap<>();
        if (!allPids.isEmpty()) {
            int threads = Math.max(1, Math.min(8, allPids.size()));
            java.util.concurrent.ExecutorService pool = java.util.concurrent.Executors.newFixedThreadPool(threads);
            try {
                List<java.util.concurrent.Future<?>> tasks = new ArrayList<>();
                for (int pid : allPids) {
                    tasks.add(pool.submit(() -> {
                        String acc = matchAccountByMmap(pid, dataDir, excludedDirs);
                        if (acc != null) pidAccMap.put(pid, acc);
                    }));
                }
                for (java.util.concurrent.Future<?> t : tasks) {
                    try {
                        t.get();
                    } catch (Exception ignore) {
                        // 单个 pid 扫描失败不影响其它 pid（进程可能刚好退出）
                    }
                }
            } finally {
                pool.shutdown();
            }
        }
        return pidAccMap;
    }

    /**
     * 单个 pid：遍历它的内存映射，找出"属于本平台数据目录下某个账号文件夹"的那条路径，返回账号 ID.
     *
     * <p>对应 Python: `_update_acc_list_by_pid` 里的 `identify_by_file`：
     * 路径以 data_dir 开头 → 按分隔符切段 → 找到等于 data_dir 目录名的那段 → **取它后面一段 = 账号 ID**；
     * 命中 `excluded_dirs` 的段跳过；同一 pid 取**第一条**命中的（与 Python 首次成功即返回一致）。
     *
     * @return 账号 ID；没匹配到返回 null
     */
    static String matchAccountByMmap(int pid, String dataDir, List<String> excludedDirs) {
        String normalizedDataDir = dataDir.replace('\\', '/');
        String dataDirName = new File(dataDir).getName();
        for (String path : com.jfmultichat.swcore.SwNativeOps.INSTANCE
                .enumerateByVirtualQueryEx(pid)) {
            if (path == null) continue;
            String normalized = path.replace('\\', '/');
            if (!normalized.startsWith(normalizedDataDir)) continue;
            String[] parts = normalized.split("/");
            int dataDirIdx = -1;
            for (int i = 0; i < parts.length; i++) {
                if (parts[i].equals(dataDirName)) {
                    dataDirIdx = i;
                    break;
                }
            }
            if (dataDirIdx >= 0 && dataDirIdx + 1 < parts.length) {
                String acc = parts[dataDirIdx + 1];
                if (!excludedDirs.contains(acc)) {
                    return acc;
                }
            }
        }
        return null;
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
            // PID 改存**内存**（用户 2026-10-06 定：pid/hwnd 写文件下次读出来就是过时的）；
            // 配置里历史遗留的 pid 顺手清掉（写 null = 删除该键），避免以后再被读成"实时值"
            AccRuntimeStore.setPid(sw, acc, pid);
            Map<String, Object> accData = new HashMap<>();
            accData.put(AccCoreConstants.AccKey.PID, null);
            accData.put(AccCoreConstants.AccKey.HAS_MUTEX, false);
            updateSwAccData(sw, acc, accData);
        }

        // 从记录加载互斥体
        JsonNode relayNode = getSwAccData(sw, AccCoreConstants.AccKey.RELAY);
        if (relayNode != null && relayNode.isObject() && relayNode.has("pid_mutex")) {
            JsonNode pidMutexNode = relayNode.get("pid_mutex");
            if (pidMutexNode != null && pidMutexNode.isObject()) {
                for (String acc : allAccs) {
                    Integer accPid = AccRuntimeStore.getPid(sw, acc);      // pid 来自内存运行时存储
                    if (accPid != null) {
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

        // 展示名（与窗口标题共用同一套链：自身备注/昵称/别名 → 退化成 id 时用链接账号的名字）
        String displayName = getAccDisplayName(sw, account);

        // 配置状态
        String configStatus = coexist ? account : getSwAccLoginCfgStatus(sw, account);

        // pid 来自内存运行时存储（不再读配置文件）
        Integer pidVal = AccRuntimeStore.getPid(sw, account);
        JsonNode hasMutexNode = getSwAccData(sw, account, "has_mutex");
        JsonNode hotkeyNode = getSwAccData(sw, account, "hotkey");
        JsonNode hiddenNode = getSwAccData(sw, account, "hidden");
        JsonNode autoStartNode = getSwAccData(sw, account, "auto_start");

        details.put(AccCoreConstants.AccKey.IID, sw + "/" + account);
        details.put(AccCoreConstants.AccKey.DISPLAY, displayName);
        details.put(AccCoreConstants.AccKey.CONFIG_STATUS, configStatus);
        details.put(AccCoreConstants.AccKey.PID, pidVal);
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

    /** 建 `SwInfoFuncCore` 的标准写法（accountOps 必须传：共存扫描会写 SwAccData，传 null 会 NPE） */
    private static com.jfmultichat.swcore.SwInfoFuncCore newInfoCore() {
        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        return new com.jfmultichat.swcore.SwInfoFuncCore(
                accessor, com.jfmultichat.swcore.SwNativeOps.INSTANCE, null,
                new AccOpsProvider().toSwProvider());
    }

    /**
     * **账号 → {pid, 主窗口 hwnd}**：全部按 **pid** 找窗口（原生账号与共存账号一视同仁）.
     *
     * <p>⚠️ 2026-10-13 用户更正了我的理解：**原生账号同样能映射** ——
     * 刷新机制（{@link #getSwAccountsLoginStatus} → {@link #resolvePidAccountMap}）通过扫描进程**内存映射**里
     * "数据目录 / 账号文件夹"的路径，本来就能得到 **pid ↔ 账号** 的绑定 ✓；
     * 而"不在**登录期**记录 pid/hwnd"只是**单一职责**（登录只管登录 ✓），不是因为拿不到绑定 ✓。
     *
     * <p>所以这里的链路是：**pid（来自刷新机制，内存）→ 该 pid 的窗口按主窗规则筛 → 唯一命中才算** ✓。
     * 与旧版 `get_main_hwnd_of_accounts`（L1524）判据相同；差别只在**数据来源**：
     * 旧版 pid/main_hwnd 存在配置里 ✗，本版一律**即时取、只进内存**（`AccRuntimeStore`）✓ 不落任何文件 ✓。
     *
     * @return {accId → [pid, hwnd]}；没绑定、或窗口不是唯一命中的账号**不出现**在结果里
     */
    public static Map<String, int[]> getLiveAccountWindows(String sw, List<String> accList) {
        Map<String, int[]> result = new LinkedHashMap<>();
        if (sw == null || accList == null || accList.isEmpty()) return result;
        com.jfmultichat.swcore.SwInfoFuncCore info = newInfoCore();
        for (String acc : accList) {
            Integer pid = AccRuntimeStore.getPid(sw, acc);
            if (pid == null || pid <= 0) continue;
            List<Integer> hwnds = info.getHwndsByPidAndWndType(sw, pid, "main", null);
            if (hwnds != null && hwnds.size() == 1) {              // **唯一命中**才算数（与全局约定一致）
                result.put(acc, new int[]{pid, hwnds.get(0)});
                continue;
            }
            // 规则没给出唯一解 → 走"主窗兜底"（见 tieBreakMainWindow；QQNT 实测就是这个情况）
            int picked = tieBreakMainWindow(sw, info, pid);
            if (picked != 0) {
                result.put(acc, new int[]{pid, picked});
            } else {
                logNoMainWindow(acc, pid, hwnds);
            }
        }
        return result;
    }

    /**
     * **主窗兜底**：规则没给出唯一解时，从该 pid 的候选窗口里挑一个最像"主窗"的.
     *
     * <p>为什么需要（QQNT 实测，2026-10-13）：QQNT 主窗规则 = {@code Chrome_WidgetWin_1} +
     * {@code FirstChild{!ClassNameWildcards:[""]}} —— 但 QQNT 的**隐藏辅助窗口**与主窗**类名相同**、
     * {@code FirstChild} 也满足 ✗（Win32 子窗口几乎都有类名 ✗）→ 4 个候选全中、没有唯一解 ✗。
     * 旧版靠 **UIA 子控件**区分 ✓（`GetFirstChildControl`：隐藏窗口通常**没有 UIA 子控件** ✓），
     * 这是 Win32 侧做不到的 ✓ —— 所以这里给一个**只在多命中时生效**的兜底，而不是去改核心匹配规则
     * （登录等待链路仍然严格"唯一命中"，不受影响 ✓）。
     *
     * <p>判据（依次）：① 可见窗口优先；② 面积最大；③ 枚举顺序第一个。**每次都会打日志**，
     * 方便随时发现"其实是靠兜底选出来的"。
     */
    private static int tieBreakMainWindow(String sw, com.jfmultichat.swcore.SwInfoFuncCore info, int pid) {
        List<Integer> all = com.jfmultichat.swcore.SwNativeOps.getHwndsByPid(pid);
        List<Integer> candidates = new ArrayList<>();
        for (Map<String, Object> rule : info.getWndClassMatchingDicts(sw, "main")) {
            List<Integer> matched = com.jfmultichat.swcore.SwNativeOps.filterHwndsByMatchingDict(all, rule);
            if (matched.size() == 1) return matched.get(0);        // 某条规则给了唯一解 → 直接用
            if (matched.size() > 1) candidates = matched;
        }
        if (candidates.isEmpty()) return 0;
        int best = 0;
        long bestArea = -1;
        boolean bestVisible = false;
        for (int h : candidates) {
            boolean visible = com.jfmultichat.swcore.SwNativeOps.isWindowVisible(h);
            Map<String, Object> d = com.jfmultichat.swcore.SwNativeOps.getHwndDetails(h);
            long w = ((Number) d.getOrDefault("width", 0)).longValue();
            long hh = ((Number) d.getOrDefault("height", 0)).longValue();
            long area = Math.max(0, w) * Math.max(0, hh);
            boolean better = best == 0
                    || (visible && !bestVisible)
                    || (visible == bestVisible && area > bestArea);
            if (better) {
                best = h;
                bestArea = area;
                bestVisible = visible;
            }
        }
        LOG.info("[窗口] pid={} 有 {} 个候选主窗、无唯一命中 → **兜底选中** 0x{}（可见={}, 面积={}）；候选={}",
                pid, candidates.size(), Integer.toHexString(best), bestVisible, bestArea,
                candidates.stream().map(x -> "0x" + Integer.toHexString(x)).toList());
        return best;
    }

    /** 失败诊断（用户 2026-10-13 要求"自己看日志排查"）：把该 pid 的候选窗口类名打出来 */
    private static void logNoMainWindow(String acc, int pid, List<Integer> matched) {
        StringBuilder sb = new StringBuilder();
        for (int h : com.jfmultichat.swcore.SwNativeOps.getHwndsByPid(pid)) {
            Map<String, Object> d = com.jfmultichat.swcore.SwNativeOps.getHwndDetails(h);
            sb.append(" 0x").append(Integer.toHexString(h))
              .append('[').append(d.getOrDefault("class", "")).append(']');
        }
        LOG.info("[窗口] {} (pid={}) 没找到主窗：规则唯一命中数={}；该进程候选窗口：{}",
                acc, pid, matched == null ? 0 : matched.size(), sb);
    }

    /**
     * **账号头像 data URL** —— 与前端账号表**完全同一条链**（单一来源 ✓）.
     *
     * <p>链路（从 {@code JsBridge.getAccAvatarAsync} 抽出来的，两处共用 ✓）：
     * <ol>
     *   <li>先从**截图缓存**恢复本地头像文件（{@link #getAvatarFromCache}）——
     *       这一步就是侧栏最初"头像空白"的原因 ✗（我当时少走了这步 ✓）</li>
     *   <li>共存账号（带 {@code linked_acc}）：自身 → 链接账号本地头像 → 链接账号头像地址 → 文字兜底 ✓</li>
     *   <li>原生账号：本地文件 → URL 下载 → SVG 回退 ✓</li>
     * </ol>
     *
     * @return data URL；没有则空串（**永不返回 null** ✓）
     */
    public static String getAccAvatarDataUrl(String sw, String acc) {
        if (sw == null || acc == null) return "";
        try {
            getAvatarFromCache(sw, java.util.List.of(acc));
            java.util.Map<String, com.fasterxml.jackson.databind.node.ObjectNode> accMap =
                    com.jfmultichat.config.ConfigManager.getInstance().getAccountMap(sw);
            com.fasterxml.jackson.databind.node.ObjectNode selfNode = accMap.get(acc);
            String linkedAcc = (selfNode != null && selfNode.hasNonNull("linked_acc"))
                    ? selfNode.get("linked_acc").asText("") : "";
            String dataUrl;
            if (!linkedAcc.isBlank() && !linkedAcc.equals(acc)) {
                getAvatarFromCache(sw, java.util.List.of(linkedAcc));
                com.fasterxml.jackson.databind.node.ObjectNode linkedNode = accMap.get(linkedAcc);
                String linkedAvatarUrl = (linkedNode != null && linkedNode.hasNonNull("avatar_url"))
                        ? linkedNode.get("avatar_url").asText("") : "";
                dataUrl = com.jfmultichat.utils.AvatarUtils.getCoexistAvatarDataUrl(
                        sw, acc, linkedAcc, linkedAvatarUrl, getAccOriginDisplayName(sw, linkedAcc));
            } else {
                dataUrl = getAccAvatarFromFile(sw, acc);
            }
            return dataUrl == null ? "" : dataUrl;
        } catch (Throwable t) {
            LOG.debug("[头像] 取 data URL 失败 {}/{}: {}", sw, acc, t.getMessage());
            return "";
        }
    }

    /**
     * 获取账号主窗口句柄
     * 对应 Python: get_main_hwnd_of_accounts (L1524-L1547)
     *
     * <p>⚠️ 2026-10-13 重写：原实现是**空壳**（只读配置里的 pid + 一句 `TODO: 需要 JNA 枚举窗口`）✗，
     * 现在改为按时内存里的 pid 即时取窗口（见 {@link #getLiveAccountWindows}）。
     */
    public static Map<String, Integer> getMainHwndOfAccounts(String sw, List<String> accList) {
        Map<String, Integer> result = new LinkedHashMap<>();
        getLiveAccountWindows(sw, accList).forEach((acc, pair) -> result.put(acc, pair[1]));
        return result;
    }

    /**
     * **即时刷新某平台的"账号 → 主窗口"映射**（页面刷新时调用；用户 2026-10-13："那是页面刷新的事情"）.
     *
     * <p>两步：
     * <ol>
     *   <li>走**既有刷新机制** {@link #getSwAccountsLoginStatus}：扫进程内存映射得到 pid ↔ 账号，
     *       pid 写进内存表（{@link #updateAccLoginData} 干的活 ✓）—— 原生账号在这里就有了绑定 ✓</li>
     *   <li>再按 pid 取该进程**唯一**的主窗口 → 写 hwnd；**这一轮没取到的清空**（窗口关了立刻失效 ✓）；
     *       绑定**发生变化**时顺手把窗口标题改成"平台名 - 账号名"（照旧版 `_record_hwnd_and_set_title`，便于任务栏辨认 ✓）</li>
     * </ol>
     *
     * @return 本次扫描到的 {accId → [pid, hwnd]}
     */
    public static Map<String, int[]> refreshLiveWindows(String sw) {
        return refreshLiveWindows(sw, null);
    }

    /**
     * 同上，额外接收**前端表格里的显示名**（{@code accId → 名称}）.
     *
     * <p>用户 2026-10-13 定：窗口标题要用**表格名称列的那个名字** —— 直接沿用前端的取法，
     * 不在 Java 侧再维护一条名字链（否则两套规则迟早不一致 ✗）。前端没给（如首次加载时表格还没数据）
     * 就退回 Java 自己的链（{@link #getAccDisplayName}）。
     */
    public static Map<String, int[]> refreshLiveWindows(String sw, Map<String, String> displayNames) {
        // ① pid ↔ 账号（含原生与共存）——失败不致命：pid 没刷出来就只是这轮没有 hwnd
        List<String> allAccs;
        try {
            allAccs = newInfoCore().getSwAllAccountsExisted(sw, null);
            getSwAccountsLoginStatus(sw);          // 内部会 setPid(...)，并把历史遗留的配置 pid 清掉
        } catch (Throwable t) {
            LOG.warn("[窗口] 刷新登录状态失败: sw={}, err={}", sw, t.getMessage());
            return new LinkedHashMap<>();
        }

        // ② pid → 主窗口（唯一命中优先；多命中走兜底）
        Map<String, int[]> live = getLiveAccountWindows(sw, allAccs);
        for (String acc : allAccs) {
            int[] pair = live.get(acc);
            if (pair == null) {
                if (AccRuntimeStore.getHwnd(sw, acc) != null) {
                    AccRuntimeStore.setHwnd(sw, acc, null);        // 窗口没了 → 立刻解绑
                    LOG.info("[窗口] {} 的窗口已消失，解绑", acc);
                }
                continue;
            }
            long hwnd = pair[1];
            AccRuntimeStore.setHwnd(sw, acc, hwnd);
            // 标题：**每次都比对当前真实标题**，不同才写（幂等 ✓）
            //  —— 这样"名字后来才拿到"（前端首次加载晚于本方法）也能在下一轮自动补上 ✓
            String name = (displayNames != null && displayNames.get(acc) != null
                    && !displayNames.get(acc).isBlank())
                    ? displayNames.get(acc) : getAccDisplayName(sw, acc);
            applyWindowTitle(sw, (int) hwnd, name);
        }
        LOG.info("[窗口] 即时刷新: sw={}, 账号 {} 个, 命中主窗口 {} 个（原生+共存）", sw, allAccs.size(), live.size());
        return live;
    }

    /**
     * 把窗口标题写成"平台名 - 账号名"（旧版 `_record_hwnd_and_set_title` 同款；失败只记 WARN）.
     * <p>幂等：先读**当前真实标题**，一样就不写 —— 所以本方法可以每轮刷新无脑调用 ✓。
     */
    private static void applyWindowTitle(String sw, int hwnd, String accName) {
        try {
            String swDisplay = com.jfmultichat.swcore.SwAccountOps.getSwOriginDisplayName(sw,
                    com.jfmultichat.config.SwConfigProvider.newAccessor());
            String want = swDisplay + " - " + accName;
            String cur = com.jfmultichat.swcore.SwNativeOps.getWindowTitle(hwnd);
            if (want.equals(cur)) return;
            boolean ok = com.jfmultichat.swcore.SwNativeOps.setWindowTitle(hwnd, want);
            LOG.info("[窗口] 改标题 hwnd={}: 「{}」→「{}」: {}", hwnd, cur, want, ok);
        } catch (Throwable t) {
            LOG.warn("[窗口] 改窗口标题失败: hwnd={}, err={}", hwnd, t.getMessage());
        }
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
        // HWND 改存**内存**（用户 2026-10-06 定）；配置里历史遗留的 main_hwnd 顺手清掉
        AccRuntimeStore.setHwnd(sw, acc, (long) hwnd);
        updateSwAccData(sw, acc, java.util.Collections.singletonMap("main_hwnd", null));
        String swDisplay = com.jfmultichat.swcore.SwAccountOps.getSwOriginDisplayName(sw,
                com.jfmultichat.config.SwConfigProvider.newAccessor());
        String accDisplay = getAccOriginDisplayName(sw, acc);
        LOG.info("[窗口] 设置标题: {} - {}", swDisplay, accDisplay);
    }

    /**
     * 解除账号与窗口的绑定
     */
    public static void unlinkHwndOfAccount(String sw, String account) {
        AccRuntimeStore.setHwnd(sw, account, null);                        // 内存里解绑
        // 配置里历史遗留的 main_hwnd 一并清掉（写 null = 删除该键）
        updateSwAccData(sw, account, java.util.Collections.singletonMap("main_hwnd", null));
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
