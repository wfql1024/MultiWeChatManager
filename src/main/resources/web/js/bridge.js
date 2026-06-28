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
        isDevMode: function() { return call('isDevMode') === true; },
        getDefaultUrls: function() { return callJson('getDefaultUrls'); },
        validatePath: function(p) { return callJsonWithArgs('validatePath', p); },
        browseFolder: function(p) { return callWithArgs('browseFolder', p); },
        getCommitInfo: function() { return callJson('getCommitInfo'); },

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
        updateSwField: function(swId, field, value) { return callJsonWithArgs('updateSwField', swId, field, value); },
        saveAccount: function(swId, accountId, fieldsJson) { return callJsonWithArgs('saveAccount', swId, accountId, fieldsJson); },
        deleteAccount: function(swId, accountId) { return callJsonWithArgs('deleteAccount', swId, accountId); },
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
        detectPathsAsync: function(swId, cbId) {
            var pathKeys = [];
            for (var i = 2; i < arguments.length; i++) pathKeys.push(arguments[i]);
            callWithArgs('detectPathsAsync', swId, String(cbId), JSON.stringify(pathKeys));
        }
    };
})();
