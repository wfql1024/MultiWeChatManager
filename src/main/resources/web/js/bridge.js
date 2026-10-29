/**
 * bridge.js — JS ↔ Java 桥接封装.
 * 全局命名空间: JFC (JhiFengChat)
 */
var JFC = window.JFC || {};

JFC.bridge = (function() {
    'use strict';

    /** 检查 javaObject 是否可用 */
    function isAvailable() {
        return typeof window.javaObject !== 'undefined' && window.javaObject !== null;
    }

    /** 调用 Java 方法 */
    function call(method) {
        if (isAvailable() && typeof window.javaObject[method] === 'function') {
            return window.javaObject[method]();
        }
        console.log('[bridge] call: ' + method);
        return null;
    }

    /** 调用 Java 方法并传参 */
    function callWithArgs(method) {
        var args = Array.prototype.slice.call(arguments, 1);
        if (isAvailable() && typeof window.javaObject[method] === 'function') {
            return window.javaObject[method].apply(window.javaObject, args);
        }
        console.log('[bridge] call: ' + method, args);
        return null;
    }

    /** 调用 Java 方法并解析返回的 JSON */
    function callJson(method) {
        var raw = call(method);
        if (raw && typeof raw === 'string') {
            try { return JSON.parse(raw); } catch(e) {}
        }
        return null;
    }

    /** 调用 Java 方法（带参）并解析返回的 JSON */
    function callJsonWithArgs(method) {
        var args = Array.prototype.slice.call(arguments, 1);
        var raw = callWithArgs.apply(null, [method].concat(args));
        if (raw && typeof raw === 'string') {
            try { return JSON.parse(raw); } catch(e) {}
        }
        return null;
    }

    // ---- 异步回调系统 ----
    // Java 后台线程完成后会调用 JFC.bridge._handleAsync(type, cbId, jsonStr)
    var _pendingCallbacks = {};
    var _nextCbId = 1;

    /** 注册异步回调，返回 cbId */
    function registerAsync(fn) {
        var id = _nextCbId++;
        _pendingCallbacks[id] = fn;
        return id;
    }

    /** Java 推送异步结果时调用（不要手动调用） */
    function _handleAsync(type, cbId, jsonStr) {
        console.log('[bridge] async result: ' + type + ' #' + cbId);
        var fn = _pendingCallbacks[cbId];
        if (fn) {
            delete _pendingCallbacks[cbId];
            var data = null;
            if (jsonStr && typeof jsonStr === 'string') {
                try { data = JSON.parse(jsonStr); } catch(e) {}
            }
            fn(type, data);
        }
    }

    // 暴露
    return {
        isAvailable: isAvailable,
        call: call,
        callWithArgs: callWithArgs,
        callJson: callJson,
        callJsonWithArgs: callJsonWithArgs,
        registerAsync: registerAsync,
        _handleAsync: _handleAsync,   // Java 通过 executeScript 调用
        // Java 主动推送账号数据变更（定向更新单行/格），勿手动调用
        _onAccChanged: function(jsonStr) {
            var data = null;
            if (jsonStr && typeof jsonStr === 'string') {
                try { data = JSON.parse(jsonStr); } catch(e) {}
            }
            if (data && JFC.pages && JFC.pages.main && JFC.pages.main.onAccountChanged) {
                JFC.pages.main.onAccountChanged(data);
            }
        },
        // Java Scene 捕获到组合键后推送（快捷键录入兜底通道），勿手动调用
        _onHotkeyCapture: function(jsonStr) {
            var combo = null;
            if (jsonStr && typeof jsonStr === 'string') {
                try { combo = JSON.parse(jsonStr); } catch(e) {}
            }
            if (combo && JFC.pages && JFC.pages.main && JFC.pages.main.onHotkeyCapture) {
                JFC.pages.main.onHotkeyCapture(combo);
            }
        },

        // ---- 窗口控制 ----
        ping: function() { return call('ping'); },
        minimize: function() { call('minimize'); },
        toggleMaximize: function() { call('toggleMaximize'); },
        close: function() { call('close'); },

        // ---- 数据访问 ----
        getSwList: function() { return callJson('getSwList'); },
        getAccountList: function(swId) { return callJsonWithArgs('getAccountList', swId); },
        getTheme: function() { return call('getTheme'); },
        setTheme: function(theme) { callWithArgs('setTheme', theme); },
        saveTheme: function(theme) { callWithArgs('saveTheme', theme); },

        // ---- 配置页 ----
        getDefaultUserDir: function() { return call('getDefaultUserDir'); },
        getConfigData: function() { return callJson('getConfigData'); },
        getProxyPresets: function() { return callJson('getProxyPresets'); },
        saveConfigData: function(json) { return callJsonWithArgs('saveConfigData', json); },
        applyProxyConfig: function(json) { return callJsonWithArgs('applyProxyConfig', json); },
        isDevMode: function() { return call('isDevMode') === true; },
        getDefaultUrls: function() { return callJson('getDefaultUrls'); },
        validatePath: function(p) { return callJsonWithArgs('validatePath', p); },
        browseFolder: function(p) { return callWithArgs('browseFolder', p); },
        getCommitInfo: function() { return callJson('getCommitInfo'); },
        openLogDir: function() { call('openLogDir'); },
        openUserDataDir: function() { call('openUserDataDir'); },
        getLogDir: function() { return call('getLogDir'); },

        // ---- 管理页 ----
        getRemoteSwList: function() { return callJson('getRemoteSwList'); },
        checkRemoteConfigReady: function() { return callJson('checkRemoteConfigReady'); },
        downloadRemoteConfigs: function() { return callJson('downloadRemoteConfigs'); },
        tryEnsureRemoteConfigsAsync: function(fn) {
            callWithArgs('tryEnsureRemoteConfigsAsync', String(registerAsync(fn)));
        },
        getSwConfig: function(swId) { return callJsonWithArgs('getSwConfig', swId); },
        saveSwConfig: function(swId, configJson) { return callJsonWithArgs('saveSwConfig', swId, configJson); },
        getSwDetailData: function(swId) { return callJsonWithArgs('getSwDetailData', swId); },
        // 原生程序表：平台主程序（inst_path 指向的 exe）名称/路径/版本
        getSwProgramData: function(swId) { return callJsonWithArgs('getSwProgramData', swId); },
        // 平台图标（程序图标）：优先用缓存的 {userData}/{sw}/{sw}.png，缺图/软件路径变更时才重新提取
        getSwIcon: function(swId) { return callJsonWithArgs('getSwIcon', swId); },
        // only: "origin"=原生账号, "coexist"=共存账号, 不传=全部
        getSwExistedAccounts: function(swId, only) {
            return callJsonWithArgs('getSwExistedAccounts', swId, only || '');
        },
        notifyPlatformEntered: function(swId) { callWithArgs('notifyPlatformEntered', swId); },
        // 快捷键录入捕获开关（Java Scene 级 EventFilter 兜底）
        notifyHotkeyCapture: function(active) { callWithArgs('notifyHotkeyCapture', !!active); },
        // 账号级登录（原生账号，异步）：每个账号开一个登录窗 + 自动点"登录" + 等窗口关闭
        loginAccountsAsync: function(swId, accIds, fn) {
            callWithArgs('loginAccountsAsync', swId, JSON.stringify(accIds || []), String(registerAsync(fn)));
        },
        // 共存账号登录（异步）：**不替换登录配置** —— 共存账号 id 本身就是程序目录下的副本 exe 名，按它启动即可
        loginCoexistAccountsAsync: function(swId, accIds, fn) {
            callWithArgs('loginCoexistAccountsAsync', swId, JSON.stringify(accIds || []), String(registerAsync(fn)));
        },
        // 获取登录窗口尺寸（读当前真实的登录窗口，格式 "宽*高"）；返回 {success, size?, error?}
        fetchLoginSize: function(swId) { return callJsonWithArgs('fetchLoginSize', swId); },
        // 点"登录"（程序行）→ 查杀该平台全部互斥体 + 降权启动平台程序（count = 启动几个实例，空/非数字=1）
        launchPlatformProgram: function(swId, count) { return callJsonWithArgs('launchPlatformProgram', swId, String(count == null ? '' : count)); },
        // 异步版：整段"查杀 + 启动"循环放后台线程跑（界面不卡），完成后回调（结果同同步版结构）
        launchPlatformProgramAsync: function(swId, count, fn) {
            callWithArgs('launchPlatformProgramAsync', swId, String(count == null ? '' : count), String(registerAsync(fn)));
        },
        // 运行时数据（PID/HWND）：纯内存，每次进入平台/刷新时重新取（不落配置文件）
        getAccRuntimeMap: function(swId) { return callJsonWithArgs('getAccRuntimeMap', swId); },
        // **即时刷新**账号主窗口（HWND）：异步（Java 侧扫完推回，避免卡 UI 线程）；
        // names = {accId: 表格里的显示名}（Java 用它改窗口标题 ✓ 不在 Java 侧再维护一条名字链）
        // 回调 fn(type, data) 的 data = {success, swId, accounts:{accId:{pid,hwnd}}}
        refreshAccWindowsAsync: function(swId, names, fn) {
            callWithArgs('refreshAccWindowsAsync', swId, JSON.stringify(names || {}), String(registerAsync(fn)));
        },
        // 点 HWND 打开窗口（恢复 + 置前；返回 {ok, reason?}）
        switchToAccWindow: function(swId, accId) {
            return callJsonWithArgs('switchToAccWindow', swId, String(accId == null ? '' : accId));
        },
        // ===== 补丁管理（增强功能）=====
        // 程序行计划：{version, coexist_mode, coexist:[...], multirun:[...], revoke:[...]}
        getSwPatchPlan: function(swId, fn) {
            callWithArgs('getSwPatchPlanAsync', swId, String(registerAsync(fn)));
        },
        // 共存账号行计划：{revoke:[...]}（作用在该实例的克隆 dll 上）
        getAccPatchPlan: function(swId, accId, fn) {
            callWithArgs('getAccPatchPlanAsync', swId, accId, String(registerAsync(fn)));
        },
        // 切换补丁：accId 传空串 = 原生程序
        switchPatch: function(swId, mode, channel, accId, fn) {
            callWithArgs('switchPatchAsync', swId, mode, channel, accId || '', String(registerAsync(fn)));
        },
        createCoexistAccount: function(swId, channel, fn) {
            callWithArgs('createCoexistAccountAsync', swId, channel, String(registerAsync(fn)));
        },
        deleteCoexistAccount: function(swId, accId, fn) {
            callWithArgs('deleteCoexistAccountAsync', swId, accId, String(registerAsync(fn)));
        },
        rebuildCoexistAccount: function(swId, accId, fn) {
            callWithArgs('rebuildCoexistAccountAsync', swId, accId, String(registerAsync(fn)));
        },
        rescanPatches: function(swId, fn) {
            callWithArgs('rescanPatchesAsync', swId, String(registerAsync(fn)));
        },
        // 共存表头计划（渠道 + 当前选中方案）
        getCoexistPlan: function(swId, fn) {
            callWithArgs('getCoexistPlanAsync', swId, String(registerAsync(fn)));
        },
        // 共存表扫描（force=true 全部渠道重扫）
        scanCoexist: function(swId, force, fn) {
            callWithArgs('scanCoexistAsync', swId, force ? 'true' : 'false', String(registerAsync(fn)));
        },
        // 只读缓存地取某模式计划（切换补丁后局部刷新，不触发扫描）
        getModePlan: function(swId, mode, fn) {
            callWithArgs('getModePlanAsync', swId, mode, String(registerAsync(fn)));
        },
        // 启用/禁用渠道（管理态）：只影响该模式，启用时补扫该渠道
        setChannelEnabled: function(swId, mode, channel, enabled, fn) {
            callWithArgs('setChannelEnabledAsync', swId, mode, channel,
                enabled ? 'true' : 'false', String(registerAsync(fn)));
        },
        // 共存账号行：扫描（force=true 强制重扫该模式；扫描用原生文件，查询用本行克隆文件）
        scanAccPatch: function(swId, accId, force, fn) {
            callWithArgs('scanAccPatchAsync', swId, accId, force ? 'true' : 'false', String(registerAsync(fn)));
        },
        // 扫描（跳过已有缓存；会重试上次失败的渠道）
        scanPatches: function(swId, fn) {
            callWithArgs('scanPatchesAsync', swId, String(registerAsync(fn)));
        },
        setCoexistMode: function(swId, channel) {
            callWithArgs('setCoexistMode', swId, channel);
        },
        // ===== 侧栏（窗口切换器）设置：贴边 / 对齐 / 长度模式 / 主窗口按钮位置 =====
        getSidebarPrefs: function() { return callJsonWithArgs('getSidebarPrefs'); },
        setSidebarPrefs: function(prefs) { return callJsonWithArgs('setSidebarPrefs', JSON.stringify(prefs || {})); },
    /** 用户 2026-10-17 第 3 条：设置页"所见即所得"演示态（没有平台窗口时由侧栏生成虚拟图标 ✓） */
    setSidebarDemo: function(on) { return callJsonWithArgs('setSidebarDemo', on ? 'true' : 'false'); },
        // ===== 任务中心（右上角）：长耗时流程的可见性 + 取消 =====
        // 返回 JSON 数组字符串（任务列表）；由 task-center.js 解析渲染
        getTaskList: function() { return call('getTaskList'); },
        // 协作式取消：返回 {ok:true} 只代表"请求已受理"，任务跑到下一个安全检查点才停
        cancelTask: function(taskId) { return callJsonWithArgs('cancelTask', String(taskId == null ? '' : taskId)); },
        cancelAllTasks: function() { return callJsonWithArgs('cancelAllTasks'); },
        // 任务统计（按流程聚合 + 最近明细）——「任务与统计」页用
        getTaskStats: function() { return call('getTaskStats'); },
        // 注：标题栏角标**不从这里更新** —— 它由 Java 侧 MainWindow 直接订阅 TaskRegistry（单一写入点）
        getAccAvatarAsync: function(swId, accountId, fn) {
            callWithArgs('getAccAvatarAsync', swId, accountId, String(registerAsync(fn)));
        },
        // 手动指定头像（弹文件选择器，Java 侧转 JPEG 写入本地头像文件）；返回 {success, dataUrl?}
        pickAccAvatar: function(swId, accountId) { return callJsonWithArgs('pickAccAvatar', swId, accountId); },
        // 移除本地头像文件（同时清 avatar_url）；返回 {success}
        removeAccAvatar: function(swId, accountId) { return callJsonWithArgs('removeAccAvatar', swId, accountId); },
        updateSwField: function(swId, field, value) { return callJsonWithArgs('updateSwField', swId, field, value); },
        saveAccount: function(swId, accountId, fieldsJson) { return callJsonWithArgs('saveAccount', swId, accountId, fieldsJson); },
        deleteAccount: function(swId, accountId) { return callJsonWithArgs('deleteAccount', swId, accountId); },
        // 重置账号：清空 SwAccData 里该账号的节点（保留空节点）；前端重置成功后自行重载数据
        resetAccount: function(swId, accountId) { return callJsonWithArgs('resetAccount', swId, accountId); },
        extractExeIcon: function(exePath) { return callJsonWithArgs('extractExeIcon', exePath); },
        getGlobalConfig: function() { return callJson('getGlobalConfig'); },
        saveGlobalConfig: function(json) { callWithArgs('saveGlobalConfig', json); },

        // ---- 异步操作（不阻塞UI） ----
        testUrlAsync: function(url, fn) {
            callWithArgs('testRemoteUrlAsync', url, String(registerAsync(fn)));
        },
        fetchUpdateAsync: function(fn) {
            callWithArgs('fetchUpdateDataAsync', String(registerAsync(fn)));
        },
        fetchThanksAsync: function(fn) {
            callWithArgs('fetchThanksDataAsync', String(registerAsync(fn)));
        },
        fetchAboutAsync: function(fn) {
            callWithArgs('fetchAboutDataAsync', String(registerAsync(fn)));
        },

        // ---- 路径探测 ----
        // pathKeys 可选，不传则默认探测全部三项；通过 JSON 字符串传递给 Java
        checkPath: function(swId, pathType, path) {
            return callJsonWithArgs('checkPath', swId, pathType, path);
        },
        checkDataDirConflict: function(newPath) {
            return callJsonWithArgs('checkDataDirConflict', newPath);
        },
        detectPathsAsync: function(swId, cbId) {
            var pathKeys = [];
            for (var i = 2; i < arguments.length; i++) pathKeys.push(arguments[i]);
            callWithArgs('detectPathsAsync', swId, String(cbId), JSON.stringify(pathKeys));
        }
    };
})();
