/**
 * app.js — 应用初始化 + 路由.
 */
JFC.router = (function() {
    'use strict';

    var currentPage = 'login';

    function init() {
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
});
