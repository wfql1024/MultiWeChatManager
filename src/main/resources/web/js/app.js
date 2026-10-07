/**
 * app.js — 应用初始化 + 路由.
 */
JFC.router = (function() {
    'use strict';

    var currentPage = null;

    /** 刷新不应期（防连点）：毫秒 */
    var REFRESH_COOLDOWN_MS = 2000;
    /** 上次真正执行刷新的时间戳 */
    var lastRefreshAt = 0;

    function init() {
        // 当前页以 DOM 为准（index.html 里 page-main 默认 active）：
        // 否则"刷新当前页"会按硬编码的 login 跳到错误页面
        currentPage = detectActivePage() || 'main';

        // 检查远程配置是否就位
        checkRemoteConfigReady();

        // 应用 SVG 图标到导航
        if (JFC.icons) {
            JFC.icons.applyToNav();
        }

        // 检查 Java Bridge
        if (JFC.bridge && JFC.bridge.isAvailable()) {
            console.log('[app] Java Bridge ready');
            var pong = JFC.bridge.ping();
            console.log('[app] ping: ' + pong);
        } else {
            console.log('[app] Running without Java Bridge (browser mode)');
        }

        // 默认显示管理页

        // 测量侧栏图标中心位置，报告给 Java 对齐标题栏 logo
        setTimeout(function() {
            var firstIcon = document.querySelector('#nav-sidebar .nav-icon');
            if (firstIcon && JFC.bridge && JFC.bridge.isAvailable()) {
                var rect = firstIcon.getBoundingClientRect();
                var centerX = rect.left + rect.width / 2;
                JFC.bridge.callWithArgs('reportSidebarIconCenter', centerX);
            }
        }, 500);
    }

    /** 读取当前真正显示的页面（.page.active 的 id 去掉 page- 前缀） */
    function detectActivePage() {
        var active = document.querySelector('.page.active');
        return active && active.id ? active.id.replace(/^page-/, '') : null;
    }

    function navigate(page) {
        currentPage = page;

        // 切换页面
        var pages = document.querySelectorAll('.page');
        pages.forEach(function(p) {
            p.classList.remove('active');
        });

        var target = document.getElementById('page-' + page);
        if (target) {
            target.classList.add('active');
        }

        // 更新导航激活状态
        if (JFC.components.navSidebar) {
            JFC.components.navSidebar.setActive(page);
        }

        // 进入设置页时初始化
        if (page === 'settings' && JFC.pages.settings) {
            JFC.pages.settings.init();
        }

        // 进入管理页时初始化
        if (page === 'manage' && JFC.pages.manage) {
            JFC.pages.manage.init();
        }

        // 进入主页面时初始化
        if (page === 'main' && JFC.pages.main) {
            JFC.pages.main.init();
        }
    }

    /**
     * 刷新当前页.
     * 先识别"现在显示的是哪个页面"，再调用该页面自己的刷新入口（复用各自既有的加载链，
     * 不新增第二条渲染路径）；没有刷新入口的页面退化为重新导航一次。
     *
     * **2 秒不应期（防连点）**：刷新会重跑整条加载链（含 Java 侧后台维护），连点没有意义，
     * 只会互相打架。不应期放在这一个入口里 → 刷新按钮与"再次点击当前平台"两条路共用同一道闸。
     */
    function refresh() {
        var now = Date.now();
        if (now - lastRefreshAt < REFRESH_COOLDOWN_MS) {
            console.log('[router] refresh ignored (cooldown ' + REFRESH_COOLDOWN_MS + 'ms)');
            return false;                    // 被不应期挡下：调用方据此决定要不要给"已刷新"反馈
        }
        lastRefreshAt = now;

        if (!currentPage) currentPage = detectActivePage() || 'main';
        if (currentPage === 'main' && JFC.pages.main && JFC.pages.main.refresh) {
            JFC.pages.main.refresh();
            return true;
        }
        if (currentPage === 'settings' && JFC.pages.settings && JFC.pages.settings.refresh) {
            JFC.pages.settings.refresh();
            return true;
        }
        navigate(currentPage);
        return true;
    }

    return { init: init, navigate: navigate, refresh: refresh,
             current: function() { return currentPage; } };
})();

// ========== DOM Ready ==========
document.addEventListener('DOMContentLoaded', function() {
    // 初始化组件
    if (JFC.components.navSidebar) {
        JFC.components.navSidebar.init();
    }

    // 启动路由
    JFC.router.init();

    // 配置缺失遮罩按钮
    var btnSettings = document.getElementById('config-missing-btn-settings');
    if (btnSettings) {
        btnSettings.addEventListener('click', function() {
            JFC.router.navigate('settings');
        });
    }
    var btnRetry = document.getElementById('config-missing-btn-retry');
    if (btnRetry) {
        btnRetry.addEventListener('click', function() {
            JFC.router.init();
        });
    }
});

// ---- Toast 通知系统 ----

/** 确保 toast 容器存在 */
function getToastContainer() {
    var c = document.getElementById('toast-container');
    if (!c) {
        c = document.createElement('div');
        c.id = 'toast-container';
        c.className = 'toast-container';
        document.body.appendChild(c);
    }
    return c;
}

/**
 * 右下角红色错误提示（自动淡出，**不带 × 关闭按钮** —— 用户 2026-10-07 定：这类通知不该要人手动关）.
 * @param {string} msg 消息文本（可含简单 HTML）
 * @param {number} duration 显示毫秒数，默认 4000
 */
JFC.toastError = function(msg, duration) {
    showToast(msg, 'toast-error', duration || 4000);
};

/**
 * 右下角绿色成功提示（同样自动淡出、无关闭按钮）.
 */
JFC.toastSuccess = function(msg, duration) {
    showToast(msg, 'toast-success', duration || 3000);
};

/**
 * 右下角提示的统一实现：进场 0.25s、停留 duration、退场 0.3s **渐变消失**后自行移除.
 * 全程不需要用户操作（与"必须点 × 才消失"的那种提示区分开）。
 */
function showToast(msg, cls, duration) {
    var container = getToastContainer();
    var toast = document.createElement('div');
    toast.className = 'toast ' + cls;
    toast.innerHTML = '<span>' + msg + '</span>';
    container.appendChild(toast);
    setTimeout(function() {
        if (!toast.parentElement) return;
        toast.classList.add('toast-out');                 // 渐隐（CSS 动画）
        setTimeout(function() {
            if (toast.parentElement) toast.remove();
        }, 320);
    }, duration);
}

// ---- 页面进度条（内容区顶部主题色小横条） ----

/**
 * 轻量进度提示：内容区顶部的主题色小横条（不定长滑动）.
 * 页面在"开始加载数据"时 show()、装载完 hide()；为避免一闪而过，最短显示 MIN_MS.
 */
JFC.progress = (function() {
    'use strict';

    var el = null;
    var hideTimer = null;
    var shownAt = 0;
    var MIN_MS = 400;

    function target() {
        if (!el) el = document.getElementById('page-progress');
        return el;
    }

    function show() {
        var e = target();
        if (!e) return;
        clearTimeout(hideTimer);
        hideTimer = null;
        if (!e.classList.contains('active')) {
            shownAt = Date.now();
            e.classList.add('active');
        }
    }

    function hide() {
        var e = target();
        if (!e) return;
        var wait = Math.max(0, MIN_MS - (Date.now() - shownAt));
        clearTimeout(hideTimer);
        hideTimer = setTimeout(function() {
            hideTimer = null;
            if (e.classList.contains('active')) e.classList.remove('active');
        }, wait);
    }

    return { show: show, hide: hide };
})();

// ---- 文本小工具 ----

/**
 * 文本宽度/取字工具（供头像文字兜底使用）.
 *
 * <p>用户规则（2026-10-05）：账号头像的文字兜底取**名称末尾 4 个字符宽**，中文/全角一个字算 **2** 个字符宽。
 * 例：「极峰多聊测试」→「测试」；「wxid_ab12cd」→「2cd」；「张三wx」→「三wx」。
 * 只用于**账号**头像；平台/程序图标兜底（`getDefaultPlatformIcon`、程序表占位）仍是首字符。
 */
JFC.text = (function() {
    'use strict';

    /** 是否宽字符（CJK / 假名 / 谚文 / 全角 / 代理对），算 2 宽 */
    function isWide(code) {
        return (code >= 0x1100 && code <= 0x115F) ||
               (code >= 0xD800 && code <= 0xDFFF) ||   // 代理对（扩展 B 区及以后的汉字）
               (code >= 0x2E80 && code <= 0xA4CF) ||
               (code >= 0xAC00 && code <= 0xD7A3) ||
               (code >= 0xF900 && code <= 0xFAFF) ||
               (code >= 0xFE30 && code <= 0xFE6F) ||
               (code >= 0xFF00 && code <= 0xFF60) ||
               (code >= 0xFFE0 && code <= 0xFFE6) ||
               (code >= 0x20000 && code <= 0x3FFFD);
    }

    /** 字符串的视觉宽度（宽字符 2、其它 1） */
    function visualUnits(s) {
        if (!s) return 0;
        var units = 0;
        for (var i = 0; i < s.length; i++) {
            var c = s.charCodeAt(i);
            if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) {   // 代理对（扩展 B 区汉字）
                units += 2;
                i++;
                continue;
            }
            units += isWide(c) ? 2 : 1;
        }
        return units;
    }

    /** 取末尾 n 个"字符宽"（中文按 2 宽） */
    function tailUnits(s, n) {
        if (!s) return '';
        var units = 0;
        var i = s.length;
        while (i > 0) {
            var end = i;
            var c = s.charCodeAt(i - 1);
            if (c >= 0xDC00 && c <= 0xDFFF && i - 2 >= 0) {          // 低代理 → 连同高代理一起取
                c = s.charCodeAt(i - 2);
                i -= 2;
            } else {
                i -= 1;
            }
            var w = isWide(c) ? 2 : 1;
            if (units + w > n) { i = end; break; }
            units += w;
        }
        return s.substring(i) || s.substring(s.length - 1);
    }

    return { isWide: isWide, visualUnits: visualUnits, tailUnits: tailUnits };
})();

// ---- 按键名映射（JavaFX WebView 的实际行为适配） ----
//
// 实测（JavaFX WebView / WebKit）：可打印字符的 keydown 事件里
//   **event.key 是空字符串**、event.code 也是空字符串，只有 keyCode/which 正确
//   （a→65、1→49、空格→32、F5→116，Ctrl+A→65），而修饰键的 event.key 有值（"Alt"/"Shift"）。
// 所以键名一律以 keyCode 为主、event.key 作辅助（浏览器里调试时 key 更准），
// 命名与 Java 侧 JsBridge.keyNameOf 保持一致，避免同一个组合出现两种写法。
JFC.keys = (function() {
    'use strict';

    // Windows 虚拟键码 → 键名（与 Java 侧 keyNameOf 对齐）
    var NAMED = {
        3: 'Cancel', 8: 'Backspace', 9: 'Tab', 13: 'Enter', 19: 'Pause', 20: 'CapsLock',
        27: 'Esc', 32: 'Space', 33: 'PageUp', 34: 'PageDown', 35: 'End', 36: 'Home',
        37: 'Left', 38: 'Up', 39: 'Right', 40: 'Down', 45: 'Insert', 46: 'Delete',
        91: 'Win', 92: 'Win', 93: 'ContextMenu', 106: 'Numpad*', 107: 'Numpad+',
        109: 'Numpad-', 110: 'Numpad.', 111: 'Numpad/', 144: 'NumLock', 145: 'ScrollLock',
        186: ';', 187: '=', 188: ',', 189: '-', 190: '.', 191: '/', 192: '`',
        219: '[', 220: '\\', 221: ']', 222: "'"
    };

    /** 取键码（keyCode 优先，回退 which） */
    function keyCodeOf(ev) {
        return ev.keyCode || ev.which || 0;
    }

    /**
     * 由一个键码取规范键名（可打印键返回大写字母/数字/符号，与 Java 侧 code.getName() 一致）；
     * 取不到返回空串。快捷键录入的"松键确认"就是拿 keyCode 反查名字来拼组合键。
     */
    function nameOfCode(code) {
        if (code >= 48 && code <= 57) return String.fromCharCode(code);          // 0-9
        if (code >= 65 && code <= 90) return String.fromCharCode(code);          // A-Z（始终大写）
        if (code >= 96 && code <= 105) return 'Numpad' + (code - 96);            // 小键盘 0-9
        if (code >= 112 && code <= 123) return 'F' + (code - 111);               // F1-F12
        if (NAMED[code]) return NAMED[code];
        return '';
    }

    /**
     * 单个键的规范名；取不到返回空串（调用方忽略该键）.
     * keyCode 为主（WebView 里 event.key 为空），key 作浏览器环境兜底。
     */
    function nameOf(ev) {
        var name = nameOfCode(keyCodeOf(ev));
        if (name) return name;
        var k = ev.key;
        if (k && k !== 'Unidentified') {
            if (k === 'Escape') return 'Esc';
            if (k.length === 1) return k.toUpperCase();
            return k;
        }
        return '';
    }

    /** 修饰键前缀（顺序与 Java 侧 formatHotkey 一致：Ctrl+Alt+Shift+Win） */
    function modifiersOf(ev) {
        var parts = [];
        if (ev.ctrlKey) parts.push('Ctrl');
        if (ev.altKey) parts.push('Alt');
        if (ev.shiftKey) parts.push('Shift');
        if (ev.metaKey) parts.push('Win');
        return parts;
    }

    /** 是否是"纯修饰键"按下（只更新预览、不作为组合的末键） */
    function isModifierOnly(ev) {
        var code = keyCodeOf(ev);
        return code === 16 || code === 17 || code === 18 || code === 91 || code === 92;
    }

    /** 组合键字符串，如 "Ctrl+Alt+K"；取不到键名返回空串 */
    function comboOf(ev) {
        var name = nameOf(ev);
        if (!name) return '';
        return modifiersOf(ev).concat([name]).join('+');
    }

    return { nameOf: nameOf, nameOfCode: nameOfCode, comboOf: comboOf, modifiersOf: modifiersOf,
             isModifierOnly: isModifierOnly, keyCodeOf: keyCodeOf };
})();

// ---- 统一确认弹窗 ----
//
// 为什么自建：实测 **JavaFX WebView 里 window.confirm() 没有 handler 时默认返回 false**
// （alert() 也什么都不显示）→ 用它做"删除确认"等于永远被取消，而且用户看不到任何提示。
// 所以确认框改成页面内 HTML 弹窗：可主题化、可键盘操作（Esc 取消 / Enter 确定）、不打断 WebView 焦点。
JFC.modal = (function() {
    'use strict';

    var mask = null;
    var keyHandler = null;

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function close() {
        if (keyHandler) { document.removeEventListener('keydown', keyHandler, true); keyHandler = null; }
        if (mask && mask.parentElement) mask.parentElement.removeChild(mask);
        mask = null;
    }

    /**
     * 确认框.
     * @param {Object}   opts     {title, message, okText, cancelText, danger}
     * @param {Function} onResult 回调(ok: boolean)
     */
    function confirm(opts, onResult) {
        var o = opts || {};
        close();                                  // 同时只允许一个确认框

        mask = document.createElement('div');
        mask.className = 'modal-mask';
        mask.innerHTML =
            '<div class="modal-card" role="dialog" aria-modal="true">' +
                '<div class="modal-title">' + escapeHtml(o.title || '确认') + '</div>' +
                '<div class="modal-message">' + escapeHtml(o.message || '') + '</div>' +
                '<div class="modal-actions">' +
                    '<button type="button" class="btn btn-sm modal-cancel">' +
                        escapeHtml(o.cancelText || '取消') + '</button>' +
                    '<button type="button" class="btn btn-sm modal-ok' + (o.danger ? ' danger' : '') + '">' +
                        escapeHtml(o.okText || '确定') + '</button>' +
                '</div>' +
            '</div>';
        document.body.appendChild(mask);

        var okBtn = mask.querySelector('.modal-ok');
        var cancelBtn = mask.querySelector('.modal-cancel');

        function done(ok) {
            close();
            if (onResult) onResult(ok);
        }

        okBtn.addEventListener('click', function() { done(true); });
        cancelBtn.addEventListener('click', function() { done(false); });
        mask.addEventListener('mousedown', function(e) {
            if (e.target === mask) done(false);    // 点遮罩空白处 = 取消（点卡片内部不算）
        });

        // Esc/Enter：这里也必须用 keyCode（WebView 里 event.key 为空，见 JFC.keys 注释）
        keyHandler = function(e) {
            var code = JFC.keys.keyCodeOf(e);
            if (code === 27) { e.preventDefault(); e.stopPropagation(); done(false); }
            else if (code === 13) { e.preventDefault(); e.stopPropagation(); done(true); }
        };
        document.addEventListener('keydown', keyHandler, true);

        okBtn.focus();
    }

    /**
     * 自定义内容弹窗（头像预览等）：卡片里放任意 HTML，底部一排按钮.
     * @param {Object} opts {title, bodyHtml, center:true 则标题与按钮都居中, actions:[{text,title,cls,onClick}]}
     *        onClick 返回 false 表示"不自动关闭"（调用方自己控制）
     * @return {Object} {close}
     */
    function custom(opts) {
        var o = opts || {};
        close();                                  // 同时只允许一个弹窗

        var actions = o.actions || [];
        var btns = actions.map(function(a, i) {
            return '<button type="button" class="btn btn-sm modal-action' + (a.cls ? ' ' + a.cls : '') +
                '" data-idx="' + i + '"' + (a.title ? ' title="' + escapeHtml(a.title) + '"' : '') + '>' +
                escapeHtml(a.text || '') + '</button>';
        }).join('');

        mask = document.createElement('div');
        mask.className = 'modal-mask';
        mask.innerHTML =
            '<div class="modal-card' + (o.center ? ' center' : '') + '" role="dialog" aria-modal="true">' +
                '<div class="modal-title">' + escapeHtml(o.title || '') + '</div>' +
                '<div class="modal-body">' + (o.bodyHtml || '') + '</div>' +
                '<div class="modal-actions">' + btns + '</div>' +
            '</div>';
        document.body.appendChild(mask);

        mask.querySelectorAll('.modal-action').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var a = actions[parseInt(this.getAttribute('data-idx'), 10)];
                var keepOpen = (a && a.onClick) ? a.onClick() : true;
                if (keepOpen === false) return;
                close();
            });
        });
        mask.addEventListener('mousedown', function(e) {
            if (e.target === mask) close();
        });
        keyHandler = function(e) {
            if (JFC.keys.keyCodeOf(e) === 27) { e.preventDefault(); e.stopPropagation(); close(); }
        };
        document.addEventListener('keydown', keyHandler, true);

        var first = mask.querySelector('.modal-action');
        if (first) first.focus();
        return { close: close };
    }

    return { confirm: confirm, custom: custom, close: close };
})();

// ---- 远程配置就绪检查 ----
function checkRemoteConfigReady() {
    var ready = JFC.bridge.checkRemoteConfigReady();
    if (!ready || ready.ready) return;

    // 有缺失 → 尝试下载（同步阻塞，仅首次启动时使用）
    console.log('[app] Remote configs missing, attempting auto-download...');
    JFC.bridge.downloadRemoteConfigs();

    // 重新检查
    ready = JFC.bridge.checkRemoteConfigReady();
    if (!ready || ready.ready) return;

    // 仍然缺失 → 红色 toast + 强制跳转配置页
    JFC.toastError('远程配置下载失败，请完善远程配置源', 5000);
    forceGotoSettingsConfig();
}

/**
 * 确保远程配置就位的统一入口（供所有页面调用）.
 * 先同步检查，缺失则异步下载，最终回调 true（就绪）或 false（失败）.
 * 失败时红色 toast 提示 + 强制跳转设置页"配置".
 *
 * @param {Function} onReady 配置就绪后的回调
 */
JFC.ensureRemoteConfigs = function(onReady) {
    var ready = JFC.bridge.checkRemoteConfigReady();
    if (ready && ready.ready) {
        if (onReady) onReady();
        return;
    }

    // 缺失 → 异步下载
    JFC.bridge.tryEnsureRemoteConfigsAsync(function(type, result) {
        if (result && result.ready) {
            if (onReady) onReady();
        } else {
            JFC.toastError('远程配置下载失败，请完善远程配置源', 5000);
            forceGotoSettingsConfig();
        }
    });
};

/**
 * 强制跳转到设置页的"配置"子页.
 */
function forceGotoSettingsConfig() {
    if (JFC.router) JFC.router.navigate('settings');
    if (JFC.pages && JFC.pages.settings) {
        JFC.pages.settings.init();
        JFC.pages.settings.showSection('config');
    }
}
