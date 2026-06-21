/**
 * app.js — 应用初始化 + 路由.
 */
JFC.router = (function() {
    'use strict';

    var currentPage = 'login';

    function init() {
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

        // 默认显示登录页
        navigate('login');

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
    }

    /** 刷新当前页 */
    function refresh() {
        navigate(currentPage);
    }

    return { init: init, navigate: navigate, refresh: refresh };
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
 * 右下角红色错误提示.
 * @param {string} msg 消息文本
 * @param {number} duration 显示毫秒数，默认 4000
 */
JFC.toastError = function(msg, duration) {
    var container = getToastContainer();
    var toast = document.createElement('div');
    toast.className = 'toast toast-error';
    toast.innerHTML = '<span>' + msg + '</span>' +
        '<button class="toast-close" onclick="this.parentElement.remove()">✕</button>';
    container.appendChild(toast);
    var t = duration || 4000;
    setTimeout(function() {
        if (toast.parentElement) toast.remove();
    }, t);
};

/**
 * 右下角绿色成功提示.
 */
JFC.toastSuccess = function(msg, duration) {
    var container = getToastContainer();
    var toast = document.createElement('div');
    toast.className = 'toast toast-success';
    toast.innerHTML = '<span>' + msg + '</span>' +
        '<button class="toast-close" onclick="this.parentElement.remove()">✕</button>';
    container.appendChild(toast);
    setTimeout(function() {
        if (toast.parentElement) toast.remove();
    }, duration || 3000);
};

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
