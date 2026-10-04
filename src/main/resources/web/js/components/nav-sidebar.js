/**
 * nav-sidebar.js — 左导航侧栏组件.
 * 功能: 静止悬停展开（鼠标在区域内且静止超过 2 秒）+ 页面路由切换.
 */
JFC.components = JFC.components || {};

JFC.components.navSidebar = (function() {
    'use strict';

    var sidebar = null;
    var expandTimer = null;
    /** 静止展开延时：鼠标停下超过该时长才展开 */
    var EXPAND_DELAY = 1000; // ms
    /** 位移阈值：小于该值视为手抖/微动，不重新计时（否则鼠标几乎不可能真正"静止"） */
    var MOVE_THRESHOLD = 6;  // px
    var lastX = 0;
    var lastY = 0;

    /** 重新计时：EXPAND_DELAY 后若鼠标仍在区域内且未明显移动，则展开. */
    function scheduleExpand() {
        clearTimeout(expandTimer);
        expandTimer = setTimeout(function() {
            expandTimer = null;
            if (sidebar) sidebar.classList.add('expanded');
        }, EXPAND_DELAY);
    }

    /** 收起侧栏 */
    function collapse() {
        clearTimeout(expandTimer);
        expandTimer = null;
        if (sidebar) sidebar.classList.remove('expanded');
    }

    function init() {
        sidebar = document.getElementById('nav-sidebar');
        if (!sidebar) return;

        // ---- 静止悬停展开 / 移出收起 ----
        sidebar.addEventListener('mouseenter', function(e) {
            lastX = e.clientX;
            lastY = e.clientY;
            scheduleExpand();
        });

        sidebar.addEventListener('mousemove', function(e) {
            if (sidebar.classList.contains('expanded')) return;
            if (Math.abs(e.clientX - lastX) < MOVE_THRESHOLD &&
                Math.abs(e.clientY - lastY) < MOVE_THRESHOLD) {
                return;   // 微动：保持计时
            }
            lastX = e.clientX;
            lastY = e.clientY;
            scheduleExpand();   // 明显移动：重新计时
        });

        sidebar.addEventListener('mouseleave', collapse);

        // ---- 兜底 1：文档级 mousemove ----
        // 点击平台后账号列表加载会卡一下，期间的 mouseleave 可能被吞掉，
        // 侧栏就会一直保持展开（只有再次进出才收回）。这里补上文档级监听：
        // 指针在侧栏外移动且侧栏已展开 → 立即收起。
        document.addEventListener('mousemove', function(e) {
            lastX = e.clientX;
            lastY = e.clientY;
            if (sidebar && sidebar.classList.contains('expanded') && !sidebar.contains(e.target)) {
                collapse();
            }
        }, true);

        // ---- 兜底 2：展开期间定时校验 ----
        // 鼠标停住不动、事件完全丢失时也能收起：用 elementFromPoint 看指针是否还在侧栏内。
        setInterval(function() {
            if (!sidebar || !sidebar.classList.contains('expanded')) return;
            var el = document.elementFromPoint(lastX, lastY);
            if (!el || !sidebar.contains(el)) collapse();
        }, 400);

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
