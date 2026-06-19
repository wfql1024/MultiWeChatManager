/**
 * nav-sidebar.js — 左导航侧栏组件.
 * 功能: hover 延迟展开 + 页面路由切换.
 */
JFC.components = JFC.components || {};

JFC.components.navSidebar = (function() {
    'use strict';

    var sidebar = null;
    var expandTimer = null;
    var EXPAND_DELAY = 300; // ms

    function init() {
        sidebar = document.getElementById('nav-sidebar');
        if (!sidebar) return;

        // ---- Hover 展开/收起 ----
        sidebar.addEventListener('mouseenter', function() {
            expandTimer = setTimeout(function() {
                sidebar.classList.add('expanded');
            }, EXPAND_DELAY);
        });

        sidebar.addEventListener('mouseleave', function() {
            clearTimeout(expandTimer);
            expandTimer = null;
            sidebar.classList.remove('expanded');
        });

        // ---- 导航项点击 ----
        var items = sidebar.querySelectorAll('.nav-item');
        items.forEach(function(item) {
            item.addEventListener('click', function() {
                var page = this.getAttribute('data-page');
                JFC.router.navigate(page);

                // 点击后收起的条件：不是"设置"页（设置页有自己的侧栏，保持展开）
                // 实际上点击后应该保持状态，让用户自己移开鼠标来收起
            });
        });
    }

    function setActive(page) {
        if (!sidebar) return;
        var items = sidebar.querySelectorAll('.nav-item');
        items.forEach(function(item) {
            var itemPage = item.getAttribute('data-page');
            if (itemPage === page) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    return { init: init, setActive: setActive };
})();
