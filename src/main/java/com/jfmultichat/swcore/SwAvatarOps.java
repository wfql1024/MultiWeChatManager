package com.jfmultichat.swcore;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedInputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * 头像操作 — 截取和保存用户头像
 * <p>
 * 对应 Python: SwInfoFuncCore.try_capt_avatar_for_sw_when,
 * start_capt_thread, start_thread_to_copy_curr_avatar,
 * get_today_capt_avatars
 *
 * 依赖: SwRectCalculator, SwConfigAccessor
 */
public final class SwAvatarOps {

    private static final Logger LOG = LoggerFactory.getLogger(SwAvatarOps.class);
    private SwAvatarOps() {}

    private static final String AVATAR_CACHE_SUFFIX = "avatar_cache";
    private static final String PERIOD_LOGIN = "login";

    /**
     * 截取用户头像
     * 对应 Python: try_capt_avatar_for_sw_when (L1969-L2004)
     * <p>
     * 需要 JNA 实现 GDI/MSS 截图。此处提供路径计算和框架。
     *
     * @param sw         软件标识
     * @param period     时期（"login" 等）
     * @param hwnd       窗口句柄（需要 JNA）
     * @param accessor   配置访问器
     * @param nativeOps  原生操作器（截图）
     */
    public static void tryCaptAvatarForSwWhen(
            String sw, String period, int hwnd,
            SwConfigAccessor accessor, SwNativeOps nativeOps) {

        // 获取适配字典
        JsonNode adaptationDicts = accessor.getRemoteSw(sw,
                SwCoreConstants.RemoteSwKey.AUTO_GET,
                SwCoreConstants.RemoteSwKey.AVATAR,
                period);

        if (adaptationDicts == null || !adaptationDicts.isArray()) {
            LOG.warn("[头像] 没有适配字典: sw={}, period={}", sw, period);
            return;
        }

        // 获取 PID
        int pid = getWindowPid(hwnd);
        if (pid == -1) {
            LOG.warn("[头像] 无法获取窗口 PID: hwnd={}", hwnd);
            return;
        }

        // 构建缓存目录
        String tempDir = System.getProperty("java.io.tmpdir");
        String cacheDir = tempDir + "/" + AVATAR_CACHE_SUFFIX;
        String datestamp = new java.text.SimpleDateFormat("yyyyMMdd").format(new Date());
        String timestamp = new java.text.SimpleDateFormat("HHmmSS_SSS").format(new Date());
        String captDir = cacheDir + "/" + pid + "_" + datestamp;
        String captPath = captDir + "/" + timestamp + ".png";

        java.nio.file.Path dirPath = java.nio.file.Path.of(captDir);
        if (!Files.exists(dirPath)) {
            try {
                Files.createDirectories(dirPath);
            } catch (IOException e) {
                LOG.error("[头像] 创建目录失败: {}", e.getMessage());
                return;
            }
        }

        // 遍历适配字典
        for (JsonNode ad : adaptationDicts) {
            if (!ad.isObject()) continue;

            JsonNode locateConfig = ad.get("locate");
            JsonNode cutConfig = ad.get("cut");
            if (cutConfig == null) continue;

            int lCut = cutConfig.has("l") ? cutConfig.get("l").asInt() : 0;
            int tCut = cutConfig.has("t") ? cutConfig.get("t").asInt() : 0;
            int rCut = cutConfig.has("r") ? cutConfig.get("r").asInt() : 0;
            int bCut = cutConfig.has("b") ? cutConfig.get("b").asInt() : 0;
            Integer widthCut = cutConfig.has("w") && !cutConfig.get("w").isNull()
                    ? cutConfig.get("w").asInt() : null;
            Integer heightCut = cutConfig.has("h") && !cutConfig.get("h").isNull()
                    ? cutConfig.get("h").asInt() : null;

            // 获取窗口大小
            int[] winSize = getWindowSize(hwnd);
            if (winSize == null) continue;
            int targetWidth = winSize[0];
            int targetHeight = winSize[1];

            // 计算截图区域
            SwRectCalculator.Rect rect = SwRectCalculator.calcRect(
                    targetWidth, targetHeight,
                    lCut, tCut, rCut, bCut,
                    widthCut != null ? widthCut : 0,
                    heightCut != null ? heightCut : 0);

            // 执行截图
            // TODO: 调用 GDI/MSS 截图
            // image_utils.gdi_capture_in_wnd(hwnd, rect.x, rect.y, rect.width, rect.height, captPath)
            LOG.info("[头像] 截图区域: {} -> {}", rect, captPath);
        }
    }

    /**
     * 启动头像截取线程
     * 对应 Python: start_capt_thread (L2006-L2021)
     *
     * @param sw         软件标识
     * @param period     时期
     * @param hwnd       窗口句柄
     * @param times      截取次数
     * @param gap        间隔秒数
     * @param accessor   配置访问器
     * @param nativeOps  原生操作器
     */
    public static void startCaptThread(String sw, String period, int hwnd,
                                        int times, double gap,
                                        SwConfigAccessor accessor, SwNativeOps nativeOps) {
        Thread thread = new Thread(() -> {
            for (int i = 0; i < times; i++) {
                try {
                    tryCaptAvatarForSwWhen(sw, period, hwnd, accessor, nativeOps);
                } catch (Exception e) {
                    LOG.warn("[头像] 截取失败: {}", e.getMessage());
                }
                try {
                    Thread.sleep((long) (gap * 1000));
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }, "avatar-capture-" + sw);
        thread.setDaemon(true);
        thread.start();
    }

    /**
     * 启动线程复制当前头像
     * 对应 Python: start_thread_to_copy_curr_avatar (L2023-L2042)
     *
     * @param sw       软件标识
     * @param hwnd     窗口句柄
     * @param accessor 配置访问器
     */
    public static void startThreadToCopyCurrAvatar(String sw, int hwnd, SwConfigAccessor accessor) {
        Thread thread = new Thread(() -> {
            try {
                int pid = getWindowPid(hwnd);
                String tempDir = System.getProperty("java.io.tmpdir");
                String cacheDir = tempDir + "/" + AVATAR_CACHE_SUFFIX;
                String datestamp = new java.text.SimpleDateFormat("yyyyMMdd").format(new Date());
                String captDir = cacheDir + "/" + pid + "_" + datestamp;

                Path dirPath = Path.of(captDir);
                if (!Files.exists(dirPath)) Files.createDirectories(dirPath);

                // TODO: 获取当前登录账号的头像路径
                // source_paths = FuncTool.get_sw_func_impl(SwInfoFuncImpl, sw).get_curr_login_acc_avatar_paths()
                // for src in source_paths:
                //     shutil.copy2(src, dest_path)

                LOG.info("[头像] 复制当前头像: sw={}, pid={}", sw, pid);
            } catch (Exception e) {
                LOG.error("[头像] 复制头像失败: {}", e.getMessage());
            }
        }, "avatar-copy-" + sw);
        thread.setDaemon(true);
        thread.start();
    }

    /**
     * 获取今天的截图头像列表
     * 对应 Python: get_today_capt_avatars (L2044-L2060)
     *
     * @param pid 进程 PID
     * @return 截图文件路径列表
     */
    public static List<String> getTodayCaptAvatars(int pid) {
        String todayPrefix = new java.text.SimpleDateFormat("yyyyMMdd").format(new Date());
        String pidPrefix = pid + "_";
        String tempDir = System.getProperty("java.io.tmpdir");
        String avatarCacheDir = tempDir + "/" + AVATAR_CACHE_SUFFIX;

        List<String> result = new ArrayList<>();
        Path cachePath = Path.of(avatarCacheDir);
        if (!Files.exists(cachePath)) return result;

        try (var stream = Files.list(cachePath)) {
            stream.map(p -> p.getFileName().toString())
                    .filter(name -> name.startsWith(pidPrefix)
                            && name.substring(pidPrefix.length()).startsWith(todayPrefix))
                    .map(name -> avatarCacheDir + "/" + name)
                    .forEach(result::add);
        } catch (Exception e) {
            LOG.warn("[头像] 扫描缓存目录失败: {}", e.getMessage());
        }

        return result;
    }

    // ==================== 辅助方法 ====================

    /**
     * 从窗口句柄获取 PID
     * 需要 JNA: GetWindowThreadProcessId
     */
    private static int getWindowPid(int hwnd) {
        // TODO: JNA 调用 GetWindowThreadProcessId
        LOG.debug("[头像] 获取 PID: hwnd={} (Stub)", hwnd);
        return -1;
    }

    /**
     * 获取窗口大小
     * 需要 JNA: GetWindowRect
     */
    private static int[] getWindowSize(int hwnd) {
        // TODO: JNA 调用 GetWindowRect
        LOG.debug("[头像] 获取窗口大小: hwnd={} (Stub)", hwnd);
        return null;
    }
}
