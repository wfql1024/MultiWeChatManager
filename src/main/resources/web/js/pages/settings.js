/**
 * settings.js — 设置页.
 * 左侧: 更新 / 外观 / 关于
 * 右侧: 对应内容区切换
 */
JFC.pages = JFC.pages || {};

JFC.pages.settings = (function() {
    'use strict';

    var currentSection = 'appearance';
    var currentTheme = 'auto';

    function init() {
        // 设置导航点击
        var items = document.querySelectorAll('#settings-nav li');
        items.forEach(function(item) {
            item.addEventListener('click', function() {
                var section = this.getAttribute('data-setting');
                showSection(section);
            });
        });

        // 主题切换按钮
        initThemeButtons();

        showSection('appearance');
    }

    function initThemeButtons() {
        // 读取已应用的主题（从 html data-theme 属性）
        var activeTheme = document.documentElement.getAttribute('data-theme') || 'auto';
        setTheme(activeTheme);

        var btns = document.querySelectorAll('#theme-segmented .theme-seg-btn');
        btns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                var theme = this.getAttribute('data-theme');
                setTheme(theme);
            });
        });
    }

    function setTheme(theme) {
        currentTheme = theme;
        var btns = document.querySelectorAll('#theme-segmented .theme-seg-btn');
        btns.forEach(function(btn) {
            var t = btn.getAttribute('data-theme');
            if (t === theme) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 通过 JS Bridge 通知 Java 层切换主题
        if (JFC.bridge && JFC.bridge.isAvailable()) {
            JFC.bridge.callWithArgs('setTheme', theme);
        }
        console.log('[settings] Theme set to: ' + theme);

        // 应用 data-theme 属性到 html 标签
        document.documentElement.setAttribute('data-theme', theme);
    }

    function showSection(name) {
        currentSection = name;

        var items = document.querySelectorAll('#settings-nav li');
        items.forEach(function(item) {
            var s = item.getAttribute('data-setting');
            item.classList.toggle('active', s === name);
        });

        var sections = document.querySelectorAll('#settings-content > div');
        sections.forEach(function(div) {
            div.style.display = 'none';
        });

        var target = document.getElementById('settings-section-' + name);
        if (target) {
            target.style.display = '';
        }
    }

    return { init: init, showSection: showSection, setTheme: setTheme };
})();
