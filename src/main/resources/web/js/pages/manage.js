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

    // ---- 窗帘偏好持久化 ----
    function loadCurtainPreferences() {
        try {
            var global = JFC.bridge.callJson('getGlobalConfig');
            if (global && global.manage_settings_collapsed) {
                var saved = global.manage_settings_collapsed;
                if (typeof saved === 'object') {
                    Object.keys(saved).forEach(function(k) {
                        settingsCollapsed[k] = !!saved[k];
                    });
                }
            }
        } catch(e) { /* 忽略 */ }
    }

    function saveCurtainPreference(swId, collapsed) {
        settingsCollapsed[swId] = collapsed;
        try {
            var prefs = {};
            Object.keys(settingsCollapsed).forEach(function(k) {
                prefs[k] = settingsCollapsed[k];
            });
            JFC.bridge.callWithArgs('saveGlobalConfig', JSON.stringify({
                manage_settings_collapsed: prefs
            }));
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

    function selectPlatformInternal(swId) {
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
        loadSwConfig(swId);
        loadAccountData(swId);
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

        // 恢复窗帘状态
        var shouldExpand = settingsCollapsed[swId] !== true;
        applyCurtainState(shouldExpand);

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
        flashTitle(trimmed ? '✓ 已保存' : '已重置为默认');
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
                    '<input type="text" id="mg-conf-' + f.key + '" value="' + escapeAttr(val) +
                    '" placeholder="（未设置）" data-field="' + f.key + '">' +
                    '<button class="btn btn-sm" data-path-key="' + f.key + '">浏览</button>' +
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

        // 绑定浏览按钮
        content.querySelectorAll('[data-path-key]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var key = this.getAttribute('data-path-key');
                var currentVal = (getEl('mg-conf-' + key) || {}).value || '';
                browsePath(key, currentVal);
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
    function applyCurtainState(expand) {
        var panel = getEl('manage-settings-panel');
        var handle = getEl('manage-curtain-handle');
        if (!panel || !handle) return;

        if (expand) {
            // 展开
            panel.classList.remove('collapsed');
            panel.style.maxHeight = '';
            handle.innerHTML = '<span class="manage-curtain-arrow">∧</span>' +
                '<span class="manage-curtain-label">⚙ 设置</span>' +
                '<span class="manage-curtain-arrow">∧</span>';
        } else {
            // 收起
            panel.classList.add('collapsed');
            panel.style.maxHeight = '0px';
            handle.innerHTML = '<span class="manage-curtain-arrow">∨</span>' +
                '<span class="manage-curtain-label">⚙ 设置</span>' +
                '<span class="manage-curtain-arrow">∨</span>';
        }
    }

    function toggleSettingsPanel(expand) {
        if (!currentSwId) return;

        var panel = getEl('manage-settings-panel');
        if (!panel) return;

        if (expand) {
            // 展开动画
            panel.classList.remove('collapsed');
            panel.style.maxHeight = panel.scrollHeight + 'px';
            // 动画结束后取消限制
            var onTransitionEnd = function() {
                panel.style.maxHeight = '';
                panel.removeEventListener('transitionend', onTransitionEnd);
            };
            panel.addEventListener('transitionend', onTransitionEnd);
        } else {
            // 收起动画
            panel.style.maxHeight = panel.scrollHeight + 'px';
            requestAnimationFrame(function() {
                panel.style.maxHeight = '0px';
                panel.classList.add('collapsed');
            });
        }

        applyCurtainState(expand);
        saveCurtainPreference(currentSwId, !expand);
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

        // 窗帘把手
        bind('manage-curtain-handle', 'click', function() {
            if (!currentSwId) return;
            var panel = getEl('manage-settings-panel');
            var isCollapsed = panel && panel.classList.contains('collapsed');
            toggleSettingsPanel(!!isCollapsed);  // 反转
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
    }

    return { init: init };
})();
