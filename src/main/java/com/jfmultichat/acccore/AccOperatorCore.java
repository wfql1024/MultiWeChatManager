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
            return new String[]{"false", "未知操作类型: " + method};
        }

        SwConfigAccessor accessor = SwConfigProvider.newAccessor();
        JsonNode configAddresses = accessor.getRemoteSw(sw, "config_addresses");
        if (configAddresses == null || !configAddresses.isArray() || configAddresses.isEmpty()) {
            return new String[]{"false", "无法获取登录配置文件地址"};
        }

        // 构建 平台原配置 → 账号配置 的映射
        // ⚠️ 必须用 SwPathResolver 解析（config_addresses 里是 {data_dir} 这类**变量模板**）——
        //    原先直接 new File(addr) → 路径根本不存在 → 一个都复制不了 → "配置操作失败"（2026-10-07 修）
        Map<String, String> originToAcc = new LinkedHashMap<>();
        for (JsonNode addr : configAddresses) {
            if (!addr.isTextual()) continue;
            String originPath = com.jfmultichat.swcore.SwPathResolver
                    .resolveSwPath(sw, addr.asText(), accessor);
            if (originPath == null || originPath.isBlank()) continue;
            originPath = originPath.replace('\\', '/');
            File originFile = new File(originPath);
            String accPath = new File(originFile.getParent(), acc + "_" + originFile.getName())
                    .getPath().replace('\\', '/');
            originToAcc.put(originPath, accPath);
        }
        if (originToAcc.isEmpty()) {
            return new String[]{"false", "无法解析登录配置文件路径"};
        }

        // 移除配置项：use → 先删**平台原配置**（后面用账号配置顶上去）；add/del → 删**账号配置**
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
                return new String[]{"false", "移除配置项目时发生错误：" + e.getMessage()};
            }
        }

        if ("del".equals(method)) {
            return new String[]{"true", "删除配置成功"};
        }

        // 拷贝配置项：**use = 账号配置 → 平台配置**（让平台用这个账号登进去）；add = 平台配置 → 账号配置
        List<String> successPaths = new ArrayList<>();
        for (Map.Entry<String, String> entry : originToAcc.entrySet()) {
            String sourcePath = "use".equals(method) ? entry.getValue() : entry.getKey();
            String destPath = "use".equals(method) ? entry.getKey() : entry.getValue();
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
                } else {
                    // 源不存在 = 该账号**没有自己的登录配置** → 硬失败（别装作成功）
                    LOG.warn("[配置] 配置项目异常（源不存在）: {} -> {}", sourcePath, destPath);
                    return new String[]{"false", "该账号没有对应的登录配置文件：" + sourcePath};
                }
            } catch (Exception e) {
                LOG.warn("[配置] 复制失败 {} -> {}: {}", sourcePath, destPath, e.getMessage());
                return new String[]{"false", "复制配置文件时发生错误：" + e.getMessage()};
            }
        }
        LOG.info("[配置] {} 操作完成: {} 项 -> {}", method, successPaths.size(), successPaths);
        return new String[]{"true", "成功"};
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
            // pid 来自**内存**运行时存储（pid/hwnd 不再写配置文件）
            Integer pidVal = AccRuntimeStore.getPid(sw, account);
            if (pidVal == null) continue;
            int pid = pidVal;

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
                // pid 从内存存储清除；配置里历史遗留的 pid 一并清掉（写 null = 删除该键）
                AccRuntimeStore.clearPid(sw, account);
                java.util.Map<String, Object> cleared = new java.util.HashMap<>();
                cleared.put("pid", null);
                cleared.put("has_mutex", false);
                ACC_ACCESSOR.updateSwAccData(sw, account, cleared);
            }
        }
        return quited;
    }

    /**
     * 切换至账号窗口（点 HWND 单元格就调它）
     * 对应 Python: switch_to_sw_account_wnd (L524-L540)
     *
     * <p>旧版实现：微信特例 —— 窗口可见就 {@code restore_window}；**不可见**（藏到后台）则
     * "恢复窗口 → 等 0.2 秒 → 在 (8,8) 双击两下"把它激活；其它平台只恢复置前。
     * 本版逐条照做（见 {@code SwNativeOps.restoreWindowAndActivate}）。
     *
     * <p>窗口已经不存在时顺带把内存里的绑定清掉（即时语义：hwnd 失效就该立刻消失，不留死值 ✓）。
     *
     * @return true = 已尝试激活；false = 没有绑定 或 窗口已失效
     */
    public static boolean switchToSwAccountWnd(String sw, String acc) {
        Long hwndVal = AccRuntimeStore.getHwnd(sw, acc);
        if (hwndVal == null) {
            LOG.info("[窗口] {} 没有绑定主窗口（可能是原生账号，或该副本程序没在运行）", acc);
            return false;
        }
        int hwnd = hwndVal.intValue();
        if (!com.jfmultichat.swcore.SwNativeOps.isWindow(hwnd)) {
            AccRuntimeStore.setHwnd(sw, acc, null);
            LOG.info("[窗口] {} 的窗口已失效，清除绑定: hwnd={}", acc, hwnd);
            return false;
        }
        boolean ok = com.jfmultichat.swcore.SwNativeOps.restoreWindowAndActivate(sw, hwnd);
        LOG.info("[窗口] 切换至账号窗口: sw={}, acc={}, hwnd={}, 成功={}", sw, acc, hwnd, ok);
        return ok;
    }

    // ==================== 互斥体操作 ====================

    /**
     * 关闭指定账号的互斥体句柄
     * 对应 Python: kill_mutex_of_acc (L848-L866)
     */
    /**
     * 关闭指定账号的互斥体句柄
     * 对应 Python: kill_mutex_of_acc (L848-L866)
     *
     * <p>实现（Python 用 `pywinhandle_find_handles_by_pids_and_handle_name_wildcards` + `pywinhandle_close_handles`）：
     * 拿该账号进程的 pid → 按平台的 `mutex_handle_wildcards` 在该进程里查句柄名 → 命中就关闭；
     * 关到至少一个才把 `has_mutex` 置 false（不再"假成功"）。
     */
    public static boolean killMutexOfAcc(String sw, String acc) {
        // pid 来自**内存**运行时存储
        Integer pidVal = AccRuntimeStore.getPid(sw, acc);
        if (pidVal == null) return false;
        int pid = pidVal;

        SwConfigAccessor accessor = com.jfmultichat.config.SwConfigProvider.newAccessor();
        List<String> wildcards = accessor.getRemoteSwAsList(sw,
                "mutex_handle_wildcards", Collections.emptyList());
        if (wildcards.isEmpty()) {
            LOG.info("[互斥体] {} 未配置 mutex_handle_wildcards，无需查杀（acc={}）", sw, acc);
            return false;
        }
        int closed = com.jfmultichat.swcore.WinHandleOps.killHandlesByName(
                Collections.singletonList(pid), wildcards);
        if (closed > 0) {
            ACC_ACCESSOR.updateSwAccData(sw, acc, Map.of("has_mutex", false));
            LOG.info("[互斥体] 已关闭 {} 个句柄: sw={}, acc={}, pid={}", closed, sw, acc, pid);
            return true;
        }
        LOG.info("[互斥体] 未命中可关闭的句柄: sw={}, acc={}, pid={}", sw, acc, pid);
        return false;
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

    // ==================== 账号级登录 ====================

    /**
     * **账号级登录（原生账号）** —— 全自动：开登录窗 → 自动点"登录"按钮 → 等窗口关闭.
     *
     * <p>照旧版 `acc_func_core._login_accounts` + `_thread_to_click_all_login_buttons_and_wait_refresh`：
     * <ol>
     *   <li>每个账号开一个登录窗（{@code SwOperatorCore.openSwAndReturnHwnd}：
     *       查杀互斥体 → 降权启动 → 等该 pid 出现登录窗）</li>
     *   <li>等 0.5s 让窗口画好，按窗口宽高 × 配置比例点击"登录"按钮
     *       （远程配置 {@code auto_click.login_btn.location} = [fx, fy]，默认 0.5 / 0.75）；
     *       平台随后用**该账号自己的登录配置文件**登进去</li>
     *   <li>等所有登录窗关闭（= 登录完成）</li>
     * </ol>
     *
     * <p>还没做的（v2）：按**控件名**精确点击 —— 旧版用 UIA 在登录窗里找控件中心，
     * 名单 = 远程 {@code ctrl_names} + 本地 {@code click_btns}；需要 UIA 树搜索，是另外一块。
     *
     * @return 每个账号一项：{accId, hwnd 或 0, pid 或 0, 说明}
     */
    public static List<String[]> loginOrigin(String sw, List<String> accIds) {
        List<String[]> results = new ArrayList<>();
        if (accIds == null || accIds.isEmpty()) return results;
        SwConfigAccessor accessor = SwConfigProvider.newAccessor();
        com.jfmultichat.core.task.TaskContext.phase("准备（预摆位）", "准备");

        // 点击比例：远程配置 auto_click.login_btn.location = [fx, fy]
        double fx = 0.5, fy = 0.75;
        try {
            JsonNode loc = accessor.getRemoteSw(sw, "auto_click", "login_btn", "location");
            if (loc != null && loc.isArray() && loc.size() >= 2) {
                fx = loc.get(0).asDouble(0.5);
                fy = loc.get(1).asDouble(0.75);
            }
        } catch (Exception e) {
            LOG.warn("[登录] 读 auto_click.login_btn.location 失败，用默认 0.5/0.75: {}", e.getMessage());
        }

        // ===== 摆位：**一开始就按账号总数算好**每个窗口该在哪 =====
        //（用户 2026-10-07：出现的窗口要立即摆位；等超时的窗口就把格子空着。
        //  所以位置必须在开窗**之前**算好，不能用"开成功的数量"去算 —— 那样后面每个都会前移）
        int[] screen = com.jfmultichat.swcore.SwNativeOps.getScreenSize();
        int wndW = 0, wndH = 0;
        try {
            String size = accessor.getSwSettingAsString(sw, "login_size", "");
            if (size != null && size.contains("*")) {
                String[] parts = size.split("\\*");
                wndW = Integer.parseInt(parts[0].trim());
                wndH = Integer.parseInt(parts[1].trim());
            }
        } catch (Exception e) {
            LOG.warn("[登录] 解析 login_size 失败: {}", e.getMessage());
        }
        if (wndW <= 0 || wndH <= 0) {
            // 兜底与旧版一致：屏幕宽/6 × 屏幕高/3
            wndW = Math.max(1, screen[0] / 6);
            wndH = Math.max(1, screen[1] / 3);
        }
        List<int[]> positions = com.jfmultichat.swcore.SwNativeOps.layoutWndPositions(
                accIds.size(), wndW, wndH, screen[0], screen[1]);
        LOG.info("[登录] 预摆位 {} 个格子（单窗 {}x{}，屏幕 {}x{}）: {}",
                positions.size(), wndW, wndH, screen[0], screen[1], positions);

        // ===== 阶段一：逐个「查杀互斥体 → 替换配置 → 开窗 → **立即摆位**」 =====
        // 任何一个失败都只记录、绝不中断（旧版：无论前面出现啥情况都要把配置替换完、窗口全开出来）
        List<String> okAccIds = new ArrayList<>();
        List<Integer> okHwnds = new ArrayList<>();
        // 统计口径（用户 2026-10-12 定，取代旧版"总时长÷应开窗数"）：
        //   · **轮次** = 开窗循环进行到第几个（成功、失败、超时都算一轮）——中途取消也照样算已进行的轮次 ✓
        //   · **时长** = 从开始到"**最后一次成功开窗**"的用时（覆盖式记录 → 取消也保留 ✓）
        //   · 单窗平均 = 时长 ÷ 轮次；三轮指标（末次/最短/最长）与总平均（Σ时长 ÷ Σ轮次）由统计层算
        long openStartMs = System.currentTimeMillis();
        int rounds = 0;
        for (int idx = 0; idx < accIds.size(); idx++) {
            String accId = accIds.get(idx);
            // ★ 安全点：任务中心可以在"账号之间"取消（取消 → 抛出并弹回任务边界，不再开下一个）
            com.jfmultichat.core.task.TaskContext.checkpoint();
            // 轮次计数：**本轮已计入**（无论后面成功/失败/取消）→ 覆盖式写入，取消也能留下 ✓
            rounds++;
            com.jfmultichat.core.task.TaskContext.metricSet("开窗轮次", rounds);
            // 阶段文字**带序号**（精确到第几个账号）；统计键**不带序号**（同类阶段合并成一条）
            com.jfmultichat.core.task.TaskContext.phase(
                    "账号 " + (idx + 1) + "/" + accIds.size() + "：开窗", "开窗");
            // ① 查杀互斥体交给 launchOneInstance **内化**（用户 2026-10-11 定的方向：
            //    "所有创建新实例的流程都免不了要查杀" → 内化后调用方就不可能漏做；
            //    这里不再自己杀，避免"外杀一次 + 内杀一次"的重复扫描）
            // ② 替换配置：把平台当前登录配置换成**该账号自己的那份**
            try {
                String[] use = operateAccConfig("use", sw, accId);
                boolean ok = use != null && "true".equalsIgnoreCase(String.valueOf(use[0]));
                LOG.info("[登录] {} 替换登录配置: {}", accId, use == null ? "无返回" : use[1]);
                if (!ok) {
                    results.add(new String[]{accId, "0", "0", "替换登录配置失败：" + (use == null ? "" : use[1])});
                    continue;                       // 记下问题，格子空着，继续下一个账号
                }
            } catch (Exception e) {
                LOG.warn("[登录] {} 替换登录配置异常: {}", accId, e.getMessage());
                results.add(new String[]{accId, "0", "0", "替换登录配置异常：" + e.getMessage()});
                continue;
            }
            // ③ 开登录窗（降权启动 → 等该 pid 的登录窗出现，最多 20s）
            int[] opened;
            try {
                opened = com.jfmultichat.swcore.SwOperatorCore.openSwAndReturnHwnd(
                        sw, null, accessor, com.jfmultichat.swcore.SwNativeOps.INSTANCE);
            } catch (Exception e) {
                LOG.warn("[登录] {} 打开窗口异常: {}", accId, e.getMessage());
                results.add(new String[]{accId, "0", "0", "打开窗口异常：" + e.getMessage()});
                continue;
            }
            if (opened[0] == 0) {
                results.add(new String[]{accId, "0", "0", "打开登录窗口失败或超时未检测到窗口"});
                continue;                           // 超时 → 这个格子就空着（位置不重排）
            }
            // ④ **窗口一出现就立刻摆位**（用预先算好的第 idx 个格子；失败/超时的格子自然留空）
            if (idx < positions.size()) {
                com.jfmultichat.swcore.SwNativeOps.moveWindow(
                        opened[0], positions.get(idx)[0], positions.get(idx)[1]);
            }
            okAccIds.add(accId);
            okHwnds.add(opened[0]);
            results.add(new String[]{accId, String.valueOf(opened[0]), String.valueOf(opened[1]), ""});
            // 覆盖式记录"到最后一次成功开窗为止"的用时（取消时保留最后一次成功值 ✓）
            com.jfmultichat.core.task.TaskContext.metricSet(
                    "开窗时长ms", System.currentTimeMillis() - openStartMs);
        }

        // ===== 阶段二：**全部打开并摆位之后**，才统一逐个点击"登录"按钮（同样允许失败） =====
        // 只补一个信息性指标（成功开窗数）；时长/轮次已在循环里覆盖式记录 ✓
        com.jfmultichat.core.task.TaskContext.metric("成功开窗数", okHwnds.size());
        for (int i = 0; i < okHwnds.size(); i++) {
            int hwnd = okHwnds.get(i);
            // ★ 安全点：点击阶段也能取消（每点一个之前检查）
            com.jfmultichat.core.task.TaskContext.checkpoint();
            com.jfmultichat.core.task.TaskContext.phase(
                    "点击登录 " + (i + 1) + "/" + okHwnds.size(), "点击登录");
            try {
                Thread.sleep(500);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            Map<String, Object> details = com.jfmultichat.swcore.SwNativeOps.getHwndDetails(hwnd);
            int w = ((Number) details.getOrDefault("width", 0)).intValue();
            int h = ((Number) details.getOrDefault("height", 0)).intValue();
            if (w <= 0 || h <= 0) {
                LOG.warn("[登录] {} 的窗口尺寸为 0，跳过点击", okAccIds.get(i));
                continue;
            }
            com.jfmultichat.swcore.SwNativeOps.clickInWindow(hwnd, (int) (w * fx), (int) (h * fy));
        }

        // ===== 阶段三：等所有登录窗关闭（= 登录完成）；超时也继续（窗口可能已经变成主窗） =====
        // 60s → 20s：这一步只是"收尾观察"，不该让任务中心长时间停在"进行中"（用户 2026-10-12 探讨定）；
        // 它现在是**可取消**的（waitHwndsClose 内部有检查点）。
        if (!okHwnds.isEmpty()) {
            // 阶段文字去掉"可取消"字样（旁边有取消按钮 = 当然可取消，用户 2026-10-12 指出）
            com.jfmultichat.core.task.TaskContext.phase("等待窗口关闭", "等待窗口关闭");
            com.jfmultichat.core.task.TaskContext.progress(okHwnds.size(), okHwnds.size());
            boolean allClosed = com.jfmultichat.swcore.SwNativeOps.waitHwndsClose(okHwnds, 20);
            LOG.info("[登录] {} 个账号：登录窗口{}", okHwnds.size(), allClosed ? "已全部关闭" : "超时仍未全关");
        }
        return results;
    }

    /**
     * **共存账号登录** —— 与 {@link #loginOrigin} 的**唯一区别：不替换、也不读登录配置**.
     *
     * <p>对应旧版 `acc_func_core.py::_open_acc_return_hwnd_and_pid`（L92-L104）的共存分支：
     * <pre>
     * if AccInfoFuncCore.is_acc_coexist(sw, acc):
     *     # 共存程序账号: 尝试查找有无同名打开进程, 有则需要去除互斥体, 共存账号无需替换配置文件
     *     sw_proc, sub_proc = SwOperatorCore.open_sw(sw, exe=acc)     ← 只按 exe 名启动
     * else:
     *     cls.operate_acc_config('use', sw, acc)                      ← 原生才替换配置
     *     sw_proc, sub_proc = SwOperatorCore.open_sw(sw)
     * </pre>
     *
     * <p>为什么共存不需要配置（用户 2026-10-12 强调）：共存程序是**程序目录下的一份副本 exe**，
     * 各自带自己的登录态；所以"**账号 id 本身就是 exe 名**"（{@code AccInfoFuncCore.getCoexistAccExe}
     * 直接返回 acc 本身）→ 按它启动即可，**不必也不能替换平台配置** ——
     * 这正是共存登录稳定、且被主推的根本原因。
     *
     * <p>其余（预摆位、一出现就挪位、全部开完再统一点击、等窗口关闭、统计口径、取消检查点）
     * 与原生登录**完全一致**，共用同一套 `TaskContext` 约定。
     *
     * @return 每个账号一项：{accId, hwnd 或 0, pid 或 0, 说明}
     */
    public static List<String[]> loginCoexist(String sw, List<String> accIds) {
        List<String[]> results = new ArrayList<>();
        if (accIds == null || accIds.isEmpty()) return results;
        SwConfigAccessor accessor = SwConfigProvider.newAccessor();
        com.jfmultichat.core.task.TaskContext.phase("准备（预摆位）", "准备");

        // 点击比例：与原生登录共用同一份远程配置 auto_click.login_btn.location = [fx, fy]
        double fx = 0.5, fy = 0.75;
        try {
            JsonNode loc = accessor.getRemoteSw(sw, "auto_click", "login_btn", "location");
            if (loc != null && loc.isArray() && loc.size() >= 2) {
                fx = loc.get(0).asDouble(0.5);
                fy = loc.get(1).asDouble(0.75);
            }
        } catch (Exception e) {
            LOG.warn("[共存登录] 读 auto_click.login_btn.location 失败，用默认 0.5/0.75: {}", e.getMessage());
        }

        // 摆位：与原生登录同一套（开窗前按账号总数算好格子；失败/超时的格子留空、不重排）
        int[] screen = com.jfmultichat.swcore.SwNativeOps.getScreenSize();
        int wndW = 0, wndH = 0;
        try {
            String size = accessor.getSwSettingAsString(sw, "login_size", "");
            if (size != null && size.contains("*")) {
                String[] parts = size.split("\\*");
                wndW = Integer.parseInt(parts[0].trim());
                wndH = Integer.parseInt(parts[1].trim());
            }
        } catch (Exception e) {
            LOG.warn("[共存登录] 解析 login_size 失败: {}", e.getMessage());
        }
        if (wndW <= 0 || wndH <= 0) {
            wndW = Math.max(1, screen[0] / 6);
            wndH = Math.max(1, screen[1] / 3);
        }
        List<int[]> positions = com.jfmultichat.swcore.SwNativeOps.layoutWndPositions(
                accIds.size(), wndW, wndH, screen[0], screen[1]);
        LOG.info("[共存登录] 预摆位 {} 个格子（单窗 {}x{}，屏幕 {}x{}）: {}",
                positions.size(), wndW, wndH, screen[0], screen[1], positions);

        // ===== 阶段一：逐个「开共存程序 → 立即摆位」（**无配置替换** ✓） =====
        List<String> okAccIds = new ArrayList<>();
        List<Integer> okHwnds = new ArrayList<>();
        // 统计口径与原生登录一致（见 loginOrigin）：轮次 = 进行到第几个；时长 = 到最后一次成功开窗
        long openStartMs = System.currentTimeMillis();
        int rounds = 0;
        for (int idx = 0; idx < accIds.size(); idx++) {
            String accId = accIds.get(idx);
            // ★ 安全点：任务中心可以在"账号之间"取消
            com.jfmultichat.core.task.TaskContext.checkpoint();
            rounds++;
            com.jfmultichat.core.task.TaskContext.metricSet("开窗轮次", rounds);
            com.jfmultichat.core.task.TaskContext.phase(
                    "共存账号 " + (idx + 1) + "/" + accIds.size() + "：开窗", "开窗");
            // ★★ 与 loginOrigin 的唯一实质差异：这里**没有** operateAccConfig("use", ...) ★★
            int[] opened;
            try {
                opened = com.jfmultichat.swcore.SwOperatorCore.openSwAndReturnHwnd(
                        sw, accId, accessor, com.jfmultichat.swcore.SwNativeOps.INSTANCE);
            } catch (Exception e) {
                LOG.warn("[共存登录] {} 打开窗口异常: {}", accId, e.getMessage());
                results.add(new String[]{accId, "0", "0", "打开窗口异常：" + e.getMessage()});
                continue;
            }
            if (opened[0] == 0) {
                LOG.warn("[共存登录] {} 打开登录窗口失败或超时", accId);
                results.add(new String[]{accId, "0", "0", "打开登录窗口失败或超时未检测到窗口"});
                continue;                           // 格子空着，继续下一个
            }
            if (idx < positions.size()) {
                com.jfmultichat.swcore.SwNativeOps.moveWindow(
                        opened[0], positions.get(idx)[0], positions.get(idx)[1]);
            }
            okAccIds.add(accId);
            okHwnds.add(opened[0]);
            results.add(new String[]{accId, String.valueOf(opened[0]), String.valueOf(opened[1]), ""});
            com.jfmultichat.core.task.TaskContext.metricSet(
                    "开窗时长ms", System.currentTimeMillis() - openStartMs);
        }

        // ===== 阶段二：全部打开并摆位后，才统一逐个点击"登录" =====
        // （旧版账号级登录 `_login_accounts` 对**所有**窗口统一点击，共存号也一样；程序表那种"手动登录"不点）
        com.jfmultichat.core.task.TaskContext.metric("成功开窗数", okHwnds.size());
        for (int i = 0; i < okHwnds.size(); i++) {
            int hwnd = okHwnds.get(i);
            com.jfmultichat.core.task.TaskContext.checkpoint();
            com.jfmultichat.core.task.TaskContext.phase(
                    "点击登录 " + (i + 1) + "/" + okHwnds.size(), "点击登录");
            try {
                Thread.sleep(500);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            Map<String, Object> details = com.jfmultichat.swcore.SwNativeOps.getHwndDetails(hwnd);
            int w = ((Number) details.getOrDefault("width", 0)).intValue();
            int h = ((Number) details.getOrDefault("height", 0)).intValue();
            if (w <= 0 || h <= 0) {
                LOG.warn("[共存登录] {} 的窗口尺寸为 0，跳过点击", okAccIds.get(i));
                continue;
            }
            com.jfmultichat.swcore.SwNativeOps.clickInWindow(hwnd, (int) (w * fx), (int) (h * fy));
        }

        // ===== 阶段三：等所有登录窗关闭（20s 上限、可取消） =====
        if (!okHwnds.isEmpty()) {
            com.jfmultichat.core.task.TaskContext.phase("等待窗口关闭", "等待窗口关闭");
            com.jfmultichat.core.task.TaskContext.progress(okHwnds.size(), okHwnds.size());
            boolean allClosed = com.jfmultichat.swcore.SwNativeOps.waitHwndsClose(okHwnds, 20);
            LOG.info("[共存登录] {} 个账号：登录窗口{}", okHwnds.size(), allClosed ? "已全部关闭" : "超时仍未全关");
        }
        return results;
    }
}
