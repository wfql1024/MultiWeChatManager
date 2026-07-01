/**
 * manage.js — 管理页逻辑.
 * 左栏完全沿用 .nav-sidebar 样式和行为（hover 展开/收起）.
 */
JFC.pages = JFC.pages || {};

JFC.pages.manage = (function() {
    'use strict';

    // ---- 状态 ----
    var currentSwId = null;
    var swConfigData = {};
    var accountData = [];
    var selectedIds = new Set();
    var sortField = 'nickname';
    var sortAsc = true;
    var settingsCollapsed = {};   // swId → bool, 从 local_config.json 持久化
    var iconCache = {};           // swId → iconUrl (base64 data URL)
    var debounceTimers = {};      // field → timerId, 用于防抖保存
    var expandTimer = null;
    var MANAGE_EXPAND_DELAY = 300;
    var DEBOUNCE_MS = 600;        // 输入框防抖延迟
    var isInitialized = false;

    // ---- 辅助函数 ----
    function bind(id, evt, fn) {
        var el = document.getElementById(id);
        if (el) el.addEventListener(evt, fn);
    }

    function getEl(id) {
        return document.getElementById(id);
    }

    function show(elId) {
        var e = getEl(elId);
        if (e) {
            e.style.display = '';
            e.classList.add('active');
        }
    }

    function hide(elId) {
        var e = getEl(elId);
        if (e) {
            e.style.display = 'none';
            e.classList.remove('active');
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function escapeAttr(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    /** 短暂闪烁标题作为反馈 */
    function flashTitle(msg, isError) {
        var el = getEl('manage-detail-title');
        if (!el) return;
        var orig = el.textContent;
        var origColor = el.style.color;
        el.textContent = msg;
        el.style.color = isError ? 'var(--color-danger)' : 'var(--color-success)';
        setTimeout(function() {
            el.textContent = orig;
            el.style.color = origColor;
        }, 1500);
    }

    // ---- 初始化 ----
    function init() {
        if (isInitialized) {
            // 已初始化，只需刷新平台列表
            loadPlatformList();
            return;
        }
        isInitialized = true;

        // 加载持久化的窗帘偏好
        loadCurtainPreferences();
        initManageSidebar();
        loadPlatformList();
        bindManageEvents();
    }

    // ---- 管理页侧栏 hover 展开/收起（完全沿用 nav-sidebar.js） ----
    function initManageSidebar() {
        var sidebar = getEl('manage-platform-sidebar');
        if (!sidebar) return;

        sidebar.addEventListener('mouseenter', function() {
            expandTimer = setTimeout(function() {
                sidebar.classList.add('expanded');
            }, MANAGE_EXPAND_DELAY);
        });

        sidebar.addEventListener('mouseleave', function() {
            clearTimeout(expandTimer);
            expandTimer = null;
            sidebar.classList.remove('expanded');
        });
    }

    // ---- 窗帘偏好持久化（per-platform → LocalSwConfig.json.settings_expanded） ----
    function loadCurtainPreferences() {
        // 改为在 selectPlatform 时按需加载，此处只清空缓存
        settingsCollapsed = {};
    }

    function loadCurtainStateForSw(swId) {
        try {
            var config = JFC.bridge.getSwConfig(swId);
            if (config && config.hasOwnProperty('settings_expanded')) {
                settingsCollapsed[swId] = !config.settings_expanded;
            } else {
                settingsCollapsed[swId] = false; // 无记录时默认展开
            }
        } catch(e) {
            settingsCollapsed[swId] = false;
        }
    }

    function saveCurtainPreference(swId, collapsed) {
        settingsCollapsed[swId] = collapsed;
        try {
            JFC.bridge.updateSwField(swId, 'settings_expanded', JSON.stringify(!collapsed));
        } catch(e) { /* 忽略 */ }
    }

    // ---- 加载平台列表 ----
    function loadPlatformList() {
        // 兜底检查：远程配置缺失则异步下载，失败则跳转设置页
        var ready = JFC.bridge.checkRemoteConfigReady();
        if (!ready || !ready.ready) {
            JFC.ensureRemoteConfigs(function() {
                loadPlatformListInternal();
            });
            return;
        }
        loadPlatformListInternal();
    }

    function loadPlatformListInternal() {
        var data = JFC.bridge.getRemoteSwList();
        if (!data || !data.platforms || data.platforms.length === 0) {
            renderPlatformList([]);
            return;
        }

        // 按 local_sw 中的状态排序：有配置的在前
        var swList = JFC.bridge.getSwList() || [];
        var platforms = data.platforms.slice().sort(function(a, b) {
            var aEnabled = swList.indexOf(a.swId) !== -1;
            var bEnabled = swList.indexOf(b.swId) !== -1;
            if (aEnabled && !bEnabled) return -1;
            if (!aEnabled && bEnabled) return 1;
            return (a.alias || a.swId).localeCompare(b.alias || b.swId, 'zh-CN');
        });

        // 预加载各平台的 inst_path 图标
        preloadPlatformIcons(platforms);
        renderPlatformList(platforms);
    }

    function preloadPlatformIcons(platforms) {
        platforms.forEach(function(p) {
            if (iconCache[p.swId]) return;
            try {
                var config = JFC.bridge.getSwConfig(p.swId);
                if (config && config.inst_path && config.inst_path.toLowerCase().endsWith('.exe')) {
                    loadIconForSwId(p.swId, config.inst_path);
                }
            } catch(e) { /* 忽略 */ }
        });
    }

    function loadIconForSwId(swId, exePath) {
        if (iconCache[swId]) return;
        try {
            var result = JFC.bridge.extractExeIcon(exePath);
            if (result && result.iconUrl) {
                iconCache[swId] = result.iconUrl;
                refreshPlatformIcon(swId);
            }
        } catch(e) { /* 忽略 */ }
    }

    function refreshPlatformIcon(swId) {
        var item = document.querySelector('.nav-item[data-swid="' + swId + '"] .nav-icon');
        if (item && iconCache[swId]) {
            item.innerHTML = '<img src="' + iconCache[swId] + '" alt="" style="width:22px;height:22px;object-fit:contain;">';
        }
    }

    function renderPlatformList(platforms) {
        var container = getEl('manage-platform-list');
        if (!container) return;

        if (platforms.length === 0) {
            container.innerHTML = '<li class="nav-item" style="color:var(--text-muted);font-style:italic;">' +
                '<span class="nav-icon"><span class="manage-temp-icon">...</span></span>' +
                '<span class="nav-label">暂无平台数据</span></li>';
            return;
        }

        var html = '';
        platforms.forEach(function(p) {
            var isActive = p.swId === currentSwId ? ' active' : '';
            var iconHtml;
            if (iconCache[p.swId]) {
                iconHtml = '<img src="' + iconCache[p.swId] + '" alt="" style="width:22px;height:22px;object-fit:contain;">';
            } else {
                iconHtml = getDefaultPlatformIcon(p.swId);
            }
            // 名称显示逻辑: remark > alias > swId (与顶部标题一致)
            var displayName = getPlatformDisplayName(p.swId, p.alias);
            html += '<li class="nav-item' + isActive + '" data-page="manage-sw" data-swid="' + escapeAttr(p.swId) + '">' +
                '<span class="nav-icon">' + iconHtml + '</span>' +
                '<span class="nav-label">' + escapeHtml(displayName) + '</span>' +
                '</li>';
        });
        container.innerHTML = html;

        // 绑定点击
        container.querySelectorAll('.nav-item[data-swid]').forEach(function(item) {
            item.addEventListener('click', function() {
                var swId = this.getAttribute('data-swid');
                if (swId) selectPlatform(swId);
            });
        });
    }

    /** 获取平台显示名称: remark（本地） > alias（远程） > swId（标识） */
    function getPlatformDisplayName(swId, remoteAlias) {
        // 1. 检查内存中的 remark
        if (swConfigData[swId] && swConfigData[swId].remark) {
            return swConfigData[swId].remark;
        }
        // 2. 尝试从 local_sw.json 读取 remark
        try {
            var cfg = JFC.bridge.getSwConfig(swId);
            if (cfg && cfg.remark) {
                // 缓存到内存
                if (!swConfigData[swId]) swConfigData[swId] = {};
                swConfigData[swId].remark = cfg.remark;
                return cfg.remark;
            }
        } catch(e) { /* 忽略 */ }
        // 3. 远程 alias
        if (remoteAlias) return remoteAlias;
        // 4. 原始标识
        return swId;
    }

    // ---- 平台默认图标 ----
    function getDefaultPlatformIcon(swId) {
        return '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
            '<rect x="3" y="3" width="18" height="18" rx="4"/>' +
            '<text x="12" y="16" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">' +
            (swId.charAt(0) || '?').toUpperCase() +
            '</text></svg>';
    }

    // ---- 选择平台 ----
    function selectPlatform(swId) {
        if (currentSwId === swId) return;  // 避免重复加载

        // 兜底检查远程配置
        var ready = JFC.bridge.checkRemoteConfigReady();
        if (!ready || !ready.ready) {
            JFC.ensureRemoteConfigs(function() {
                selectPlatformInternal(swId);
            });
            return;
        }
        selectPlatformInternal(swId);
    }

    /** 切换前记录上一个平台的高度，供切换动画使用 */
    var _prevHeight = 180;

    function selectPlatformInternal(swId) {
        var panel = getEl('manage-settings-panel');
        if (panel && currentSwId) {
            _prevHeight = panel.getBoundingClientRect().height | 0;
        }
        currentSwId = swId;
        selectedIds.clear();
        updateSelectionUI();

        // 更新列表高亮 — 取消"全部"选中，高亮当前平台
        var allItem = getEl('manage-all-nav-item');
        if (allItem) allItem.classList.remove('active');

        var list = getEl('manage-platform-list');
        if (list) {
            list.querySelectorAll('.nav-item[data-swid]').forEach(function(item) {
                item.classList.toggle('active', item.getAttribute('data-swid') === swId);
            });
        }

        // 切换到详情页面
        hide('manage-page-all');
        show('manage-page-detail');

        // 加载数据
        loadCurtainStateForSw(swId);
        loadSwConfig(swId);
        loadAccountData(swId);

        // 自动探测未填路径（后台执行，不阻塞 UI）
        setTimeout(function() { autoDetectUnsetPaths(); }, 100);
    }

    // ---- 加载 Sw 配置 ----
    function loadSwConfig(swId) {
        var config = JFC.bridge.getSwConfig(swId);
        if (!config) return;

        swConfigData[swId] = config;

        // 获取远程平台信息（alias）
        var remoteInfo = getRemotePlatformInfo(swId);

        // 标题显示: remark > alias > swId
        var displayName = config.remark || (remoteInfo && remoteInfo.alias) || swId;
        swConfigData[swId]._alias = remoteInfo ? remoteInfo.alias : null;

        // 更新标题
        setTitleDisplay(displayName);

        // 渲染设置表单
        renderSettingsPanel(config);

        var shouldExpand = settingsCollapsed[swId] !== true;
        var savedH = loadHeightPreference(swId);

        if (shouldExpand) {
            // 展开：先设箭头 + 解除 collapsed，再由 animatePanelHeight 接管高度（避免 applyCurtainState 清除 maxHeight 造成闪屏）
            getEl('manage-settings-panel').classList.remove('collapsed');
            var aUp = document.querySelector('#handle-arrow-up');
            var aDown = document.querySelector('#handle-arrow-down');
            if (aUp) aUp.style.display = '';
            if (aDown) aDown.style.display = 'none';
            animatePanelHeight(savedH, null, _prevHeight);
        } else {
            applyCurtainState(false);
            var aUp2 = document.querySelector('#handle-arrow-up');
            var aDown2 = document.querySelector('#handle-arrow-down');
            if (aUp2) aUp2.style.display = 'none';
            if (aDown2) aDown2.style.display = '';
        }

        if (swId === 'TestSw') startHeightTest(); else stopHeightTest();
        initHeightDrag();
        initHandleSvg();

        // 如果有 inst_path，尝试加载图标
        if (config.inst_path && config.inst_path.toLowerCase().endsWith('.exe') && !iconCache[swId]) {
            loadIconForSwId(swId, config.inst_path);
        }
    }

    /** 获取远程平台的 alias */
    function getRemotePlatformInfo(swId) {
        try {
            var data = JFC.bridge.getRemoteSwList();
            if (data && data.platforms) {
                for (var i = 0; i < data.platforms.length; i++) {
                    if (data.platforms[i].swId === swId) return data.platforms[i];
                }
            }
        } catch(e) { /* 忽略 */ }
        return null;
    }

    /** 设置标题展示（h2），并绑定点击编辑 */
    function setTitleDisplay(name) {
        var titleEl = getEl('manage-detail-title');
        var inputEl = getEl('manage-detail-title-input');
        if (!titleEl) return;

        titleEl.textContent = name;
        titleEl.style.display = '';
        if (inputEl) inputEl.style.display = 'none';

        // 点击 h2 → 进入编辑模式
        titleEl.onclick = function() {
            if (!currentSwId) return;
            titleEl.style.display = 'none';
            if (inputEl) {
                inputEl.value = name;
                inputEl.style.display = '';
                inputEl.focus();
                inputEl.select();
            }
        };
    }

    /** 保存 remark 并更新标题 */
    function saveRemark(value) {
        if (!currentSwId) return;
        var trimmed = value.trim();
        var displayName = trimmed || swConfigData[currentSwId]._alias || currentSwId;

        if (!swConfigData[currentSwId]) swConfigData[currentSwId] = {};
        swConfigData[currentSwId].remark = trimmed;

        // 保存到 local_sw.json
        try {
            JFC.bridge.saveSwConfig(currentSwId, JSON.stringify(swConfigData[currentSwId]));
        } catch(e) { /* 忽略 */ }

        setTitleDisplay(displayName);
        refreshSidebarLabel(currentSwId, displayName);
    }

    /** 刷新侧栏中指定平台的显示名称 */
    function refreshSidebarLabel(swId, name) {
        var item = document.querySelector('.nav-item[data-swid="' + swId + '"] .nav-label');
        if (item) item.textContent = name;
    }

    function renderSettingsPanel(config) {
        var content = getEl('manage-settings-content');
        if (!content) return;

        // 定义字段 — 单列从上到下，仅保留必要的设置项
        var fieldOrder = [
            { key: 'inst_path',     label: '软件路径',       type: 'path', action: null },
            { key: 'data_dir',      label: '数据目录',       type: 'path', action: null },
            { key: 'dll_dir',       label: 'DLL 路径',       type: 'path', action: null },
            { key: 'login_size',    label: '登录窗口尺寸',   type: 'text', action: 'fetch_size' },
            { key: 'click_buttons', label: '点击按钮',       type: 'text', action: null },
        ];

        var html = '<div class="manage-config-grid">';
        fieldOrder.forEach(function(f) {
            var val = config[f.key] != null ? String(config[f.key]) : '';
            html += '<div class="manage-config-group">' +
                '<span class="manage-config-label">' + escapeHtml(f.label) + '</span>';

            if (f.type === 'path') {
                html += '<div class="manage-config-input">' +
                    '<div class="mg-input-dropdown-wrap">' +
                    '<input type="text" id="mg-conf-' + f.key + '" value="' + escapeAttr(val) +
                    '" placeholder="（未设置）" data-field="' + f.key + '">' +
                    '<button class="btn-detect-dropdown" data-detect-key="' + f.key + '">▼</button>' +
                    '</div>' +
                    '</div>';
            } else {
                // text 类型
                html += '<div class="manage-config-input">' +
                    '<input type="text" id="mg-conf-' + f.key + '" value="' + escapeAttr(val) +
                    '" placeholder="（未设置）" data-field="' + f.key + '">';
                if (f.action === 'fetch_size') {
                    html += '<button class="btn btn-sm" data-fetch-key="' + f.key + '">获取</button>';
                }
                html += '</div>';
            }

            html += '</div>';
        });
        html += '</div>';

        content.innerHTML = html;

        // 绑定下拉探测按钮
        content.querySelectorAll('[data-detect-key]').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                var key = this.getAttribute('data-detect-key');
                toggleDetectDropdown(key);
            });
        });

        // 绑定"获取"按钮
        content.querySelectorAll('[data-fetch-key]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var key = this.getAttribute('data-fetch-key');
                if (key === 'login_size') fetchLoginSize();
            });
        });

        // 绑定输入框防抖保存
        content.querySelectorAll('input[type="text"][data-field]').forEach(function(input) {
            input.addEventListener('input', function() {
                var field = this.getAttribute('data-field');
                debounceSaveField(field, this.value);
            });
        });

        // 绑定路径输入框 blur 检查
        content.querySelectorAll('#mg-conf-inst_path, #mg-conf-data_dir, #mg-conf-dll_dir').forEach(function(input) {
            input.addEventListener('blur', function() {
                validatePathInput(this);
            });
            // 下拉面板选路 → 值变化后立即检查
            input.addEventListener('change', function() {
                validatePathInput(this);
            });
            // 页面初始加载时检查已填值
            if (input.value.trim()) {
                setTimeout(function() { validatePathInput(input); }, 200);
            }
        });
    }

    /** 获取登录窗口尺寸（从远程平台配置读取） */
    function fetchLoginSize() {
        if (!currentSwId) return;
        try {
            var data = JFC.bridge.getRemoteSwList();
            if (data && data.remoteRaw && data.remoteRaw[currentSwId]) {
                var remote = data.remoteRaw[currentSwId];
                if (remote.login_size) {
                    var size = String(remote.login_size);
                    var input = getEl('mg-conf-login_size');
                    if (input) input.value = size;
                    saveFieldNow('login_size', size);
                    flashTitle('尺寸已获取');
                    return;
                }
            }
            flashTitle('未找到远程配置中的尺寸', true);
        } catch(e) {
            flashTitle('获取失败', true);
        }
    }

    // ---- 路径自动探测（下拉面板） ----

    /** pathKey → candidates 缓存，切换平台时清空 */
    var detectCache = {};

    function clearDetectCache() { detectCache = {}; }

    /** 来源优先级映射（数字越小优先级越高） */
    var SOURCE_PRIORITY = {
        '进程': 1,
        '内存映射': 2,
        'DLL遍历': 3,
        '注册表': 4,
        '猜测': 5,
        '其他SW': 5
    };

    /** 取路径的"代表优先级" = 所有来源中最高的优先级 */
    function repPriority(entry) {
        if (!entry.sources || entry.sources.length === 0) return 99;
        var best = 99;
        entry.sources.forEach(function(s) {
            var p = SOURCE_PRIORITY[s] || 99;
            if (p < best) best = p;
        });
        return best;
    }

    /** 选择最佳候选: 存在 > 优先级高 > 来源多 > 第一条 */
    function selectBestCandidate(candidates) {
        if (!candidates || candidates.length === 0) return null;
        var best = null;
        candidates.forEach(function(c) {
            if (!best) { best = c; return; }
            // 存在优先
            if (c.exists && !best.exists) { best = c; return; }
            if (!c.exists && best.exists) return;
            // 代表优先级比较
            var cp = repPriority(c);
            var bp = repPriority(best);
            if (cp < bp) { best = c; return; }
            if (cp > bp) return;
            // 来源数量多优先
            var cSrc = (c.sources && c.sources.length) || 0;
            var bSrc = (best.sources && best.sources.length) || 0;
            if (cSrc > bSrc) best = c;
        });
        return best;
    }

    /** 确保 body 下有全局下拉容器 */
    function getDropdownLayer() {
        var layer = document.getElementById('mg-dropdown-layer');
        if (!layer) {
            layer = document.createElement('div');
            layer.id = 'mg-dropdown-layer';
            layer.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;z-index:40;pointer-events:none;';
            document.body.appendChild(layer);
        }
        return layer;
    }

    /** 获取或创建某个 pathKey 的下拉面板（挂载在 body 层） */
    function getOrCreateDropdownPanel(pathKey) {
        var id = 'detect-panel-' + pathKey;
        var panel = document.getElementById(id);
        if (!panel) {
            panel = document.createElement('div');
            panel.id = id;
            panel.className = 'manage-detect-dropdown';
            panel.style.display = 'none';
            panel.style.pointerEvents = 'auto';
            panel.innerHTML = '<div class="detect-dropdown-list" id="detect-list-' + pathKey + '"></div>'
                + '<div class="detect-dropdown-footer" data-browse-key="' + pathKey + '">浏览...</div>';
            getDropdownLayer().appendChild(panel);

            // 绑定浏览
            panel.querySelector('.detect-dropdown-footer').addEventListener('click', function(e) {
                e.stopPropagation();
                var cur = (getEl('mg-conf-' + pathKey) || {}).value || '';
                browsePath(pathKey, cur);
                closeAllDetectDropdowns();
            });
        }
        return panel;
    }

    /** 根据输入框位置定位下拉面板 */
    function positionDropdownPanel(panel, pathKey) {
        var inputWrap = document.querySelector('#mg-conf-' + pathKey)
            && document.querySelector('#mg-conf-' + pathKey).closest('.mg-input-dropdown-wrap');
        if (!inputWrap) return;
        var rect = inputWrap.getBoundingClientRect();
        panel.style.position = 'fixed';
        panel.style.top = rect.bottom + 2 + 'px';
        panel.style.left = rect.left + 'px';
        panel.style.width = rect.width + 'px';
        panel.style.maxHeight = '200px';
    }

    /** 记录当前打开的面板 key，用于 scroll 事件重定位 */
    var openPanelKey = null;

    /** scroll/resize 时重定位面板 */
    function onScrollResize() {
        if (!openPanelKey) return;
        var panel = document.getElementById('detect-panel-' + openPanelKey);
        if (panel && panel.style.display !== 'none') {
            positionDropdownPanel(panel, openPanelKey);
        }
    }

    // 全局 scroll/resize 监听（只绑定一次）
    var scrollBound = false;
    function ensureScrollListener() {
        if (scrollBound) return;
        scrollBound = true;
        window.addEventListener('scroll', onScrollResize, true);
        window.addEventListener('resize', onScrollResize);
    }

    /** 切换下拉面板 */
    function toggleDetectDropdown(pathKey) {
        ensureScrollListener();
        var btn = document.querySelector('[data-detect-key="' + pathKey + '"]');
        var panel = getOrCreateDropdownPanel(pathKey);
        if (!panel || !btn) return;

        // 已展开 → 关闭
        if (panel.style.display !== 'none') {
            closeAllDetectDropdowns();
            return;
        }

        closeAllDetectDropdowns(pathKey);

        // 定位面板到输入框下方
        positionDropdownPanel(panel, pathKey);
        panel.style.display = '';
        btn.classList.add('active');
        openPanelKey = pathKey;

        // 显示加载提示，保留旧缓存（不主动清空）
        var list = document.getElementById('detect-list-' + pathKey);
        if (list) list.innerHTML = '<span class="detect-result-line" style="justify-content:center;color:var(--text-muted);">探测中...</span>';
        if (!currentSwId) return;

        try {
            var cbId = JFC.bridge.registerAsync(function(type, data) {
                if (type !== 'detectPaths') return;
                var newCandidates = (data && !data.error) ? (data[pathKey] || []) : [];
                // 合并新结果与旧缓存：同路径覆盖，新路径追加，旧独有保留
                var oldCache = detectCache[pathKey] || [];
                var mergedMap = {};
                oldCache.forEach(function(c) { mergedMap[c.path] = c; });
                newCandidates.forEach(function(c) { mergedMap[c.path] = c; });
                var merged = Object.values(mergedMap);
                detectCache[pathKey] = merged;
                renderDropdownList(pathKey, merged);
                if (merged.length > 0) {
                    var best = selectBestCandidate(newCandidates.length > 0 ? newCandidates : merged);
                    if (best) {
                        var input = getEl('mg-conf-' + pathKey);
                        if (input && !input.value.trim()) {
                            input.value = best.path;
                            saveFieldNow(pathKey, best.path);
                            validatePathInput(input);
                        }
                    }
                }
            });
            JFC.bridge.detectPathsAsync(currentSwId, cbId, pathKey);
        } catch(e) {
            var flist = document.getElementById('detect-list-' + pathKey);
            if (flist) flist.innerHTML = '<span class="detect-result-line detect-not-exists">[出错]</span>';
        }
    }

    function closeAllDetectDropdowns(exceptKey) {
        if (!exceptKey) openPanelKey = null;
        ['inst_path', 'data_dir', 'dll_dir'].forEach(function(key) {
            if (key === exceptKey) return;
            var panel = document.getElementById('detect-panel-' + key);
            var btn = document.querySelector('[data-detect-key="' + key + '"]');
            if (panel) panel.style.display = 'none';
            if (btn) btn.classList.remove('active');
        });
    }

    function renderDropdownList(pathKey, candidates) {
        var list = document.getElementById('detect-list-' + pathKey);
        if (!list) return;
        if (!candidates || candidates.length === 0) {
            list.innerHTML = '<span class="detect-result-line detect-not-exists">[不存在] （未找到）</span>';
            return;
        }
        // 排序：存在优先 → 来源优先级高优先 → 来源数量多优先
        var sorted = candidates.slice().sort(function(a, b) {
            if (a.exists !== b.exists) return a.exists ? -1 : 1;
            var pa = repPriority(a), pb = repPriority(b);
            if (pa !== pb) return pa - pb;
            var sa = (a.sources && a.sources.length) || 0;
            var sb = (b.sources && b.sources.length) || 0;
            return sb - sa;
        });
        var html = '';
        sorted.forEach(function(c) {
            html += '<div class="detect-result-line" data-candidate="' + escapeAttr(c.path) + '">'
                + (c.exists ? '<span class="detect-exists">[存在]</span>' : '<span class="detect-not-exists">[不存在]</span>')
                + ((c.sources && c.sources.length) ? ' <span class="detect-source">[' + c.sources.join(',') + ']</span>' : '')
                + ' <span class="detect-path">' + escapeHtml(c.path) + '</span>'
                + '</div>';
        });
        list.innerHTML = html;
        list.querySelectorAll('[data-candidate]').forEach(function(line) {
            line.addEventListener('click', function() {
                var path = this.getAttribute('data-candidate');
                var input = getEl('mg-conf-' + pathKey);
                if (input) {
                    input.value = path;
                    removePathHint(input);
                }
                saveFieldNow(pathKey, path);
                closeAllDetectDropdowns();
                // 选路后触发检查
                if (input) validatePathInput(input);
            });
        });
    }

    /** 进入平台时自动探测所有未填路径 */
    function autoDetectUnsetPaths() {
        if (!currentSwId) return;
        clearDetectCache();
        var emptyKeys = [];
        ['inst_path', 'data_dir', 'dll_dir'].forEach(function(key) {
            var input = getEl('mg-conf-' + key);
            if (input && !input.value.trim()) {
                emptyKeys.push(key);
            }
        });
        if (emptyKeys.length === 0) return;

        var cbId = JFC.bridge.registerAsync(function(type, data) {
            if (type !== 'detectPaths') return;
            if (data && !data.error) {
                emptyKeys.forEach(function(k) {
                    var candidates = data[k];
                    detectCache[k] = candidates || [];
                    if (candidates && candidates.length > 0) {
                        var best = selectBestCandidate(candidates);
                        if (best) {
                            var input = getEl('mg-conf-' + k);
                            if (input && !input.value.trim()) {
                                input.value = best.path;
                                saveFieldNow(k, best.path);
                                validatePathInput(input);
                            }
                        }
                    }
                });
            }
        });
        var args = [currentSwId, cbId].concat(emptyKeys);
        JFC.bridge.detectPathsAsync.apply(JFC.bridge, args);
    }

    // ---- 路径输入框失焦检查 ----
    function validatePathInput(input) {
        var key = input.getAttribute('data-field');
        if (!key || !currentSwId) return;
        var val = input.value.trim();
        if (!val) { clearPathHint(input); return; }

        var result = JFC.bridge.checkPath(currentSwId, key, val);
        if (!result) { clearPathHint(input); return; }

        removePathHint(input);
        var hint = document.createElement('span');
        hint.className = 'mg-path-hint';

        if (result.valid) {
            input.style.borderColor = 'var(--color-success)';
            hint.className += ' hint-ok';
            hint.textContent = result.reason || '路径有效';
        } else if (result.exists) {
            input.style.borderColor = '#e6a817';
            hint.className += ' hint-warn';
            hint.textContent = result.reason || '路径不符合预期';
        } else {
            input.style.borderColor = 'var(--color-danger)';
            hint.className += ' hint-err';
            hint.textContent = result.reason || '路径不存在';
        }

        var wrap = input.closest('.mg-input-dropdown-wrap');
        if (wrap) wrap.appendChild(hint);

        // 绿色/橙色自动保存，红色不保存
        if (result.valid || result.exists) {
            saveFieldNow(key, val);
        }
    }

    function removePathHint(input) {
        var wrap = input.closest('.mg-input-dropdown-wrap');
        if (wrap) {
            var old = wrap.querySelector('.mg-path-hint');
            if (old) old.remove();
        }
        input.style.borderColor = '';
    }

    function clearPathHint(input) {
        removePathHint(input);
    }

    // ---- 路径浏览 ----
    function browsePath(key, currentVal) {
        var result = JFC.bridge.browseFolder(currentVal || '');
        if (result) {
            var input = getEl('mg-conf-' + key);
            if (input) input.value = result;
            saveFieldNow(key, result);

            if (key === 'inst_path' && result.toLowerCase().endsWith('.exe')) {
                iconCache[currentSwId] = null;  // 清除旧缓存
                loadIconForSwId(currentSwId, result);
            }
        }
    }

    // ---- 字段保存（防抖 + 即时） ----
    function debounceSaveField(field, value) {
        if (debounceTimers[field]) clearTimeout(debounceTimers[field]);
        debounceTimers[field] = setTimeout(function() {
            saveFieldNow(field, value);
        }, DEBOUNCE_MS);
    }

    function saveFieldNow(field, value) {
        if (!currentSwId) return;
        if (debounceTimers[field]) {
            clearTimeout(debounceTimers[field]);
            delete debounceTimers[field];
        }

        // 更新内存
        if (!swConfigData[currentSwId]) swConfigData[currentSwId] = {};
        swConfigData[currentSwId][field] = value;

        try {
            JFC.bridge.saveSwConfig(currentSwId, JSON.stringify(swConfigData[currentSwId]));
        } catch(e) { /* 忽略 */ }

        if (field === 'inst_path' && value && value.toLowerCase().endsWith('.exe')) {
            iconCache[currentSwId] = null;
            loadIconForSwId(currentSwId, value);
        }
    }

    // ---- 窗帘折叠/展开 ----
    /* ===== 把手形状参数（已调优，勿改） =====
     * 公式: fy(x) = A * (atan(Ω * |x| + φ) + Y)
     * 填充区域: 曲线与 y=0（绘图区顶部/面板底边）围成的封闭区域
     */
    var HANDLE_O = 0.5;    // Ω — 横向拉伸
    var HANDLE_A = 5;      // A — 竖直压扁
    var HANDLE_P = -15;    // φ — 宽度一半（负值使拐点位于原点附近）
    var HANDLE_Y = -1.2;   // Y — 帽沿贴近顶部 (略小于 π/2≈1.57)
    /* =================================== */

    /** 构建全宽 SVG 把手曲线
     *  单位: px, 1:1 无缩放
     *  坐标系: 原点(0,0)=绘图区顶部中央, x右正, y上正
     *  SVG 转换: SVG_x = originX + x,  SVG_y = originY - y
     *  封闭区域: y=0(顶部) 与 曲线 之间，超出 viewBox 的部分被裁剪 */
    function buildHandleCurveD(halfW) {
        var O = HANDLE_O, A = HANDLE_A, P = HANDLE_P, Y = HANDLE_Y;
        var hw = halfW || 300;

        // fy(x) = A * (atan(Ω * |x| + φ) + Y) — 数学坐标 (y上正)
        function fy(x) { return A * (Math.atan(O * Math.abs(x) + P) + Y); }

        // 坐标转换: math → SVG, scale=1:1
        function sx(mx) { return mx; }
        function sy(my) { return -my; }   // originY=0 → SVG y=0, y上正 → SVG y下正

        var d = '', steps = 120;

        // 裁剪: SVG viewBox 自动裁剪超出部分

        // 封闭区域 = y≥0 与 曲线之间
        // 路径: 左上→右上(沿y=0)→右下(沿右竖边)→沿曲线→左下(沿左竖边)
        d += 'M' + (-hw) + ',0';             // 左上角
        d += ' L' + hw + ',0';               // 右上角 (沿 y=0)
        d += ' L' + hw + ',' + sy(fy(hw)).toFixed(2);  // 右端降至曲线
        // 沿曲线从右到左
        for (var i = steps; i >= -steps; i--) {
            var mx = i * hw / steps;
            d += ' L' + sx(mx).toFixed(1) + ',' + sy(fy(mx)).toFixed(2);
        }
        d += ' L' + (-hw) + ',0';            // 左端升至左上
        d += ' Z';
        return d;
    }

    // ---- 设置区域高度拖动 ----
    function initHandleSvg() {
        var svg = getEl('manage-curtain-handle');
        if (!svg) return;
        var container = svg.parentElement;
        var pw = container ? container.clientWidth : 600;
        var halfW = Math.round(pw / 2);
        svg.setAttribute('viewBox', (-halfW) + ' 0 ' + (2*halfW) + ' 20');
        var path = svg.querySelector('#handle-curve');
        if (path && !path.getAttribute('d')) {
            path.setAttribute('d', buildHandleCurveD(halfW));
        }
    }

    // ---- 设置区域高度拖动 ----
    var _dragStartY = 0, _dragStartH = 0, _dragged = false;

    function initHeightDrag() {
        var left = document.querySelector('#handle-drag-left');
        var right = document.querySelector('#handle-drag-right');
        if (!left && !right) return;
        if (left && left._dragBound) return;
        if (right && right._dragBound) return;

        function onDown(e) {
            if (e.button !== 0) return;
            e.preventDefault();
            e.stopPropagation();
            var panel = getEl('manage-settings-panel');
            if (!panel) return;
            var ph = parseInt(panel.style.maxHeight) || panel.scrollHeight || 180;
            if (ph < 50) ph = panel.scrollHeight || 180;
            _dragStartY = e.clientY;
            _dragStartH = ph;
            _dragged = false;
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        }
        function onMove(e) {
            if (Math.abs(e.clientY - _dragStartY) < 3) return;
            _dragged = true;
            var panel = getEl('manage-settings-panel');
            if (!panel) return;
            var content = getEl('manage-settings-content');
            var maxH = content ? content.scrollHeight + 40 : 600;
            var minH = 100;
            var newH = Math.max(minH, Math.min(maxH, _dragStartH - (_dragStartY - e.clientY)));
            panel.style.transition = 'none';
            panel.style.maxHeight = newH + 'px';
            if (content) content.style.maxHeight = (newH - 20) + 'px';
            initHandleSvg();
        }
        function onUp(e) {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            var panel = getEl('manage-settings-panel');
            if (panel) { panel.style.transition = 'max-height 0.3s ease'; initHandleSvg(); }
            if (_dragged) {
                e.stopPropagation();
                var h = panel ? (parseInt(panel.style.maxHeight) || panel.scrollHeight || 180) : 180;
                if (currentSwId) saveHeightPreference(currentSwId, h);
            }
        }
        if (left) { left._dragBound = true; left.addEventListener('mousedown', onDown); }
        if (right) { right._dragBound = true; right.addEventListener('mousedown', onDown); }

        // 仅中央点击区 hover 时着色箭头
        var clickZone = document.querySelector('#handle-click-zone');
        var svg = document.querySelector('#manage-curtain-handle');
        if (clickZone && svg) {
            clickZone.addEventListener('mouseenter', function() { svg.classList.add('click-hover'); });
            clickZone.addEventListener('mouseleave', function() { svg.classList.remove('click-hover'); });
        }
    }

    /** 统一的设置区域高度动画：当前高度 → targetH，双向对称 */
    function animatePanelHeight(targetHeight, callback, fromHeight) {
        var panel = getEl('manage-settings-panel');
        if (!panel) return;

        var currentHeight = fromHeight || (panel.getBoundingClientRect().height | 0);
        console.log('[动画测试] 高度从 ' + currentHeight + ' → ' + targetHeight);

        panel.style.transition = 'none';
        panel.style.maxHeight = currentHeight + 'px';
        panel.offsetHeight;

        requestAnimationFrame(function () {
            // 清除内容限制，让面板的 maxHeight 完全控制可见区域
            var content = getEl('manage-settings-content');
            if (content) content.style.maxHeight = 'none';

            panel.style.transition = 'max-height 0.3s ease';
            panel.style.maxHeight = targetHeight + 'px';

            var done = function (e) {
                if (e.propertyName !== 'max-height') return;
                panel.removeEventListener('transitionend', done);
                if (callback) callback();
            };

            panel.addEventListener('transitionend', done);
        });
    }

    // ==== 调试用：WeChat 平台自动随机高度测试 ====
    var _testTimer = null;
    function startHeightTest() {
        stopHeightTest();
        _testTimer = setInterval(function() {
            if (currentSwId !== 'TestSw') return;
            var h = Math.floor(100 + Math.random() * 200); // 100~300
            animatePanelHeight(h);
        }, 1000);
    }
    function stopHeightTest() {
        if (_testTimer) { clearInterval(_testTimer); _testTimer = null; }
    }

    function saveHeightPreference(swId, h) {
        try {
            JFC.bridge.updateSwField(swId, 'settings_height', JSON.stringify(Math.round(h)));
        } catch(e) {}
    }

    function loadHeightPreference(swId) {
        try {
            var config = JFC.bridge.getSwConfig(swId);
            if (config && config.settings_height) {
                return parseInt(config.settings_height);
            }
        } catch(e) {}
        return 180; // 默认高度
    }

    function applyCurtainState(expand) {
        var panel = getEl('manage-settings-panel');
        if (!panel) return;

        // 双 RAF 等待 WebView 完成新内容布局
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                initHandleSvg();
            });
        });

        var arrowUp = document.querySelector('#handle-arrow-up');
        var arrowDown = document.querySelector('#handle-arrow-down');
        if (expand) {
            panel.classList.remove('collapsed');
            panel.style.maxHeight = '';
            var content = getEl('manage-settings-content');
            if (content) content.style.maxHeight = '';
            if (arrowUp) arrowUp.style.display = '';
            if (arrowDown) arrowDown.style.display = 'none';
        } else {
            panel.classList.add('collapsed');
            panel.style.maxHeight = '0px';
            if (arrowUp) arrowUp.style.display = 'none';
            if (arrowDown) arrowDown.style.display = '';
        }
    }

    function toggleSettingsPanel(expand) {
        if (!currentSwId) return;
        var panel = getEl('manage-settings-panel');
        if (!panel) return;

        var arrowUp = document.querySelector('#handle-arrow-up');
        var arrowDown = document.querySelector('#handle-arrow-down');

        if (expand) {
            panel.classList.remove('collapsed');
            var realH = parseInt(panel.style.maxHeight) || panel.scrollHeight || 180;
            // 如果之前是收起状态（高度0），目标至少是默认展开高度
            if (realH < 100) realH = panel.scrollHeight || 180;
            panel.style.transition = 'none';
            panel.style.maxHeight = '0px';
            panel.offsetHeight;
            if (arrowUp) arrowUp.style.display = '';
            if (arrowDown) arrowDown.style.display = 'none';
            requestAnimationFrame(function() {
                panel.style.transition = 'max-height 0.3s ease';
                panel.style.maxHeight = realH + 'px';
                var done = function() {
                    panel.style.maxHeight = '';
                    panel.removeEventListener('transitionend', done);
                    initHandleSvg();
                };
                panel.addEventListener('transitionend', done);
            });
        } else {
            var curH = parseInt(panel.style.maxHeight) || panel.scrollHeight || 180;
            panel.style.maxHeight = curH + 'px';
            panel.offsetHeight;
            if (arrowUp) arrowUp.style.display = 'none';
            if (arrowDown) arrowDown.style.display = '';
            requestAnimationFrame(function() {
                panel.style.transition = 'max-height 0.3s ease';
                panel.style.maxHeight = '0px';
                panel.classList.add('collapsed');
                var done2 = function() {
                    panel.removeEventListener('transitionend', done2);
                    initHandleSvg();
                };
                panel.addEventListener('transitionend', done2);
            });
        }

        saveCurtainPreference(currentSwId, !expand);
        // 展开时保存当前高度
        if (expand) {
            var h = parseInt(panel.style.maxHeight) || panel.scrollHeight || 180;
            saveHeightPreference(currentSwId, h);
        }
    }

    // ---- 加载账号数据 ----
    function loadAccountData(swId) {
        var data = JFC.bridge.getSwDetailData(swId);
        if (!data || !data.accounts) {
            accountData = [];
            renderAccountTable([]);
            return;
        }

        accountData = data.accounts.map(function(acc) {
            // 标准化字段类型
            return {
                id: acc.id || '',
                nickname: acc.nickname || '',
                avatar_url: acc.avatar_url || '',
                hidden: acc.hidden === true || acc.hidden === 'true',
                disabled: acc.disabled === true || acc.disabled === 'true',
                login_time: acc.login_time || acc.last_login || '',
                remark: acc.remark || '',
                // 保留原始字段以便后续使用
                _raw: acc
            };
        });
        renderAccountTable(accountData);
    }

    function renderAccountTable(accounts) {
        var tbody = getEl('manage-account-tbody');
        if (!tbody) return;

        accounts = sortAccounts(accounts);

        if (accounts.length === 0) {
            tbody.innerHTML = '<tr class="manage-empty-row"><td colspan="6">' +
                '<div class="manage-empty-state">暂无账号数据</div></td></tr>';
            return;
        }

        var html = '';
        accounts.forEach(function(acc) {
            var id = acc.id;
            var nickname = acc.nickname;
            var avatarUrl = acc.avatar_url;
            var hidden = acc.hidden;
            var disabled = acc.disabled;
            var isSelected = selectedIds.has(id);

            // 头像
            var avatarHtml;
            if (avatarUrl) {
                avatarHtml = '<img src="' + escapeAttr(avatarUrl) + '" alt="" onerror="this.parentElement.innerHTML=\'<span class=manage-avatar-placeholder>' +
                    escapeHtml((nickname || id || '?').charAt(0).toUpperCase()) + '</span>\';">';
            } else {
                var initial = (nickname || id || '?').charAt(0).toUpperCase();
                avatarHtml = '<span class="manage-avatar-placeholder">' + escapeHtml(initial) + '</span>';
            }

            // 状态徽章
            var stateBadge;
            if (disabled) {
                stateBadge = '<span class="manage-state-badge state-disabled">禁用</span>';
            } else if (hidden) {
                stateBadge = '<span class="manage-state-badge state-hidden">隐藏</span>';
            } else {
                stateBadge = '<span class="manage-state-badge state-visible">正常</span>';
            }

            // 行操作按钮
            var actionsHtml = '<div class="manage-row-actions">' +
                '<button class="btn btn-sm mg-acc-action" data-action="toggle-hidden" data-id="' + escapeAttr(id) + '">' +
                (hidden ? '显示' : '隐藏') +
                '</button>' +
                '<button class="btn btn-sm mg-acc-action" data-action="delete" data-id="' + escapeAttr(id) + '" style="color:var(--color-danger);">删除</button>' +
                '</div>';

            html += '<tr data-acc-id="' + escapeAttr(id) + '" class="' + (isSelected ? 'selected' : '') + '">' +
                '<td class="manage-col-check"><input type="checkbox"' +
                    (isSelected ? ' checked' : '') +
                    ' data-acc-id="' + escapeAttr(id) + '"></td>' +
                '<td class="manage-col-avatar"><div class="manage-account-avatar">' + avatarHtml + '</div></td>' +
                '<td class="manage-nickname-cell">' + escapeHtml(nickname) + '</td>' +
                '<td class="manage-id-cell" title="' + escapeAttr(id) + '">' + escapeHtml(id) + '</td>' +
                '<td>' + stateBadge + '</td>' +
                '<td>' + actionsHtml + '</td>' +
                '</tr>';
        });

        tbody.innerHTML = html;
        bindAccountEvents();
    }

    function sortAccounts(accounts) {
        return accounts.slice().sort(function(a, b) {
            var va = a[sortField];
            var vb = b[sortField];
            // 处理 null/undefined
            if (va == null) va = '';
            if (vb == null) vb = '';
            if (typeof va === 'boolean') va = va ? '1' : '0';
            if (typeof vb === 'boolean') vb = vb ? '1' : '0';
            if (typeof va === 'string' && typeof vb === 'string') {
                var cmp = va.localeCompare(vb, 'zh-CN');
                return sortAsc ? cmp : -cmp;
            }
            return 0;
        });
    }

    function bindAccountEvents() {
        var tbody = getEl('manage-account-tbody');
        if (!tbody) return;

        // 全选复选框
        var selectAll = getEl('manage-select-all');
        if (selectAll) {
            var allIds = accountData.map(function(a) { return a.id; });
            var allSelected = allIds.length > 0 && allIds.every(function(id) { return selectedIds.has(id); });
            selectAll.checked = allSelected;
            // 移除旧监听器（避免重复绑定）
            selectAll.replaceWith(selectAll.cloneNode(true));
            selectAll = getEl('manage-select-all');
            selectAll.addEventListener('change', function() {
                if (this.checked) {
                    accountData.forEach(function(a) { selectedIds.add(a.id); });
                } else {
                    selectedIds.clear();
                }
                renderAccountTable(accountData);
                updateSelectionUI();
            });
        }

        // 行点击选中
        tbody.querySelectorAll('tr[data-acc-id]').forEach(function(row) {
            row.addEventListener('click', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON' ||
                    e.target.closest('.mg-acc-action')) return;
                var id = this.getAttribute('data-acc-id');
                if (selectedIds.has(id)) selectedIds.delete(id);
                else selectedIds.add(id);
                renderAccountTable(accountData);
                updateSelectionUI();
            });
        });

        // checkbox 选中
        tbody.querySelectorAll('input[type="checkbox"][data-acc-id]').forEach(function(cb) {
            cb.addEventListener('change', function(e) {
                e.stopPropagation();
                var id = this.getAttribute('data-acc-id');
                if (this.checked) selectedIds.add(id);
                else selectedIds.delete(id);
                updateSelectionUI();
            });
        });

        // 行操作按钮
        tbody.querySelectorAll('.mg-acc-action').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                handleAccountAction(this.getAttribute('data-action'), this.getAttribute('data-id'));
            });
        });

        // 表头排序
        var table = tbody.closest('table');
        if (table) {
            table.querySelectorAll('th[data-sort]').forEach(function(th) {
                // 避免重复绑定
                var newTh = th.cloneNode(true);
                th.parentNode.replaceChild(newTh, th);
                newTh.addEventListener('click', function() {
                    var field = this.getAttribute('data-sort');
                    if (sortField === field) sortAsc = !sortAsc;
                    else { sortField = field; sortAsc = true; }
                    renderAccountTable(accountData);
                });
            });
        }
    }

    function handleAccountAction(action, accountId) {
        if (!currentSwId) return;

        if (action === 'toggle-hidden') {
            var acc = accountData.find(function(a) { return a.id === accountId; });
            if (acc) {
                acc.hidden = !acc.hidden;
                JFC.bridge.saveAccount(currentSwId, accountId, JSON.stringify({ hidden: acc.hidden }));
                renderAccountTable(accountData);
            }
        } else if (action === 'delete') {
            if (!confirm('确定要删除账号 "' + accountId + '" 吗？此操作不可撤销。')) return;
            var result = JFC.bridge.deleteAccount(currentSwId, accountId);
            if (result && result.success) {
                accountData = accountData.filter(function(a) { return a.id !== accountId; });
                selectedIds.delete(accountId);
                renderAccountTable(accountData);
                updateSelectionUI();
                flashTitle('已删除');
            } else {
                flashTitle('删除失败', true);
            }
        }
    }

    function updateSelectionUI() {
        var toolbar = getEl('manage-account-toolbar');
        var countEl = getEl('manage-selection-count');
        if (!toolbar) return;

        var count = selectedIds.size;
        if (count > 0) {
            show('manage-account-toolbar');
            if (countEl) countEl.textContent = '已选 ' + count + ' 项';
        } else {
            hide('manage-account-toolbar');
        }
    }

    // ---- 事件绑定 ----
    function bindManageEvents() {
        // "全部"按钮
        var allItem = getEl('manage-all-nav-item');
        if (allItem) {
            allItem.addEventListener('click', function() {
                hide('manage-page-detail');
                show('manage-page-all');
                currentSwId = null;
                selectedIds.clear();
                updateSelectionUI();

                // 高亮"全部"，取消所有平台高亮
                this.classList.add('active');
                var items = getEl('manage-platform-list').querySelectorAll('.nav-item[data-swid]');
                items.forEach(function(item) { item.classList.remove('active'); });
            });
        }

        // 标题输入框 — Enter 保存，Esc 取消
        bind('manage-detail-title-input', 'keydown', function(e) {
            if (e.key === 'Enter') {
                saveRemark(this.value);
            } else if (e.key === 'Escape') {
                // 取消编辑
                var displayName = (swConfigData[currentSwId] && swConfigData[currentSwId].remark)
                    || (swConfigData[currentSwId] && swConfigData[currentSwId]._alias) || currentSwId;
                setTitleDisplay(displayName);
            }
        });
        bind('manage-detail-title-input', 'blur', function() {
            saveRemark(this.value);
        });

        // 窗帘把手 — 绑在可接收事件的热区 rect 上（SVG 自身 pointer-events:none）
        bind('handle-click-zone', 'click', function() {
            if (!currentSwId) return;
            var panel = getEl('manage-settings-panel');
            var isCollapsed = panel && panel.classList.contains('collapsed');
            toggleSettingsPanel(!!isCollapsed);
        });

        // 批量隐藏
        bind('manage-batch-hide', 'click', function() {
            if (selectedIds.size === 0) return;
            var count = selectedIds.size;
            if (!confirm('确定要隐藏选中的 ' + count + ' 个账号吗？')) return;
            var fields = { hidden: true };
            selectedIds.forEach(function(id) {
                var acc = accountData.find(function(a) { return a.id === id; });
                if (acc) acc.hidden = true;
                JFC.bridge.saveAccount(currentSwId, id, JSON.stringify(fields));
            });
            selectedIds.clear();
            renderAccountTable(accountData);
            updateSelectionUI();
            flashTitle('已隐藏 ' + count + ' 项');
        });

        // 批量显示
        bind('manage-batch-show', 'click', function() {
            if (selectedIds.size === 0) return;
            var count = selectedIds.size;
            var fields = { hidden: false };
            selectedIds.forEach(function(id) {
                var acc = accountData.find(function(a) { return a.id === id; });
                if (acc) acc.hidden = false;
                JFC.bridge.saveAccount(currentSwId, id, JSON.stringify(fields));
            });
            selectedIds.clear();
            renderAccountTable(accountData);
            updateSelectionUI();
            flashTitle('已显示 ' + count + ' 项');
        });

        // 批量删除
        bind('manage-batch-delete', 'click', function() {
            if (selectedIds.size === 0) return;
            var count = selectedIds.size;
            if (!confirm('确定要删除选中的 ' + count + ' 个账号吗？此操作不可撤销。')) return;
            selectedIds.forEach(function(id) {
                JFC.bridge.deleteAccount(currentSwId, id);
            });
            accountData = accountData.filter(function(a) { return !selectedIds.has(a.id); });
            selectedIds.clear();
            renderAccountTable(accountData);
            updateSelectionUI();
            flashTitle('已删除 ' + count + ' 项');
        });

        // 点击页面空白处关闭所有探测下拉面板
        document.addEventListener('click', function(e) {
            var target = e.target;
            // 检查点击是否在任何下拉面板或下拉按钮内
            var insideDropdown = target.closest && (
                target.closest('.manage-detect-dropdown') ||
                target.closest('[data-detect-key]'));
            if (!insideDropdown) {
                closeAllDetectDropdowns();
            }
        });
    }

    return { init: init };
})();
