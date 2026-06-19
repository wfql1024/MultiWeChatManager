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
        // Fallback: mimic behavior for testing in browser
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

    // 暴露常用方法
    return {
        isAvailable: isAvailable,
        call: call,
        callWithArgs: callWithArgs,
        ping: function() { return call('ping'); },
        minimize: function() { call('minimize'); },
        toggleMaximize: function() { call('toggleMaximize'); },
        close: function() { call('close'); }
    };
})();
