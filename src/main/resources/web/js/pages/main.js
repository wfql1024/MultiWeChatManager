/**
 * manage.js — 管理页逻辑.
 * 左栏完全沿用 .nav-sidebar 样式和行为（hover 展开/收起）.
 */
JFC.pages = JFC.pages || {};

JFC.pages.main = (function() {
    'use strict';

    // ---- 状态 ----
    var currentSwId = null;
    var swConfigData = {};
    var curtainGlobal = null;     // 设置区域展开/高度：全局统一（LocalGlobalConfig）{height, collapsed}
    var iconCache = {};           // swId → iconUrl (base64 data URL)
    var debounceTimers = {};      // field → timerId, 用于防抖保存
    var expandTimer = null;
    var MANAGE_EXPAND_DELAY = 300;
    var DEBOUNCE_MS = 600;        // 输入框防抖延迟
    var isInitialized = false;

    // ---- 四个可复用表实例（原生程序/原生账号/共存账号/无效账号） ----
    // 列定义: {key,label,mandatory,sortable,defVisible,defWidth,fixed}
    //   mandatory = 必选列（列头右键菜单锁定）; fixed = 固定宽度（不可拖拽/自适应）
    var TABLE_COLUMNS = {
        // 账号类表（原生/共存）
        account: [
            { key: 'check',        label: '勾选框',   mandatory: true,  defVisible: true,  defWidth: 40,  fixed: true  },
            { key: 'avatar',       label: '',         mandatory: true,  defVisible: true,  defWidth: 56,  fixed: true  },
            { key: 'display_name', label: '名称',      mandatory: true,  sortable: true, defVisible: true,  defWidth: 200 },
            { key: 'hotkey',       label: '快捷键',   mandatory: true,  defVisible: true,  defWidth: 110 },
            { key: 'id',           label: 'ID',       mandatory: false, sortable: true, defVisible: true,  defWidth: 150, cellClass: 'manage-id-cell' },
            { key: 'alias',        label: '平台内ID', mandatory: false, sortable: true, defVisible: false, defWidth: 140, cellClass: 'manage-alias-cell' },
            { key: 'nickname',     label: '昵称',     mandatory: false, sortable: true, defVisible: false, defWidth: 140, cellClass: 'manage-nickname-data-cell' }
        ],
        // 程序类表（原生程序）：头像(程序图标) / 名称 / 版本（必显）/ 路径（默认隐藏）
        // 头像列与账号表同款，保证行高一致（32px 头像 + 内边距）
        program: [
            { key: 'check',   label: '勾选框', mandatory: true,  defVisible: true,  defWidth: 40, fixed: true },
            { key: 'avatar',  label: '',       mandatory: true,  defVisible: true,  defWidth: 56, fixed: true },
            { key: 'name',    label: '名称',   mandatory: true,  sortable: true, defVisible: true,  defWidth: 220 },
            { key: 'version', label: '版本',   mandatory: true,  sortable: true, defVisible: true,  defWidth: 120 },
            { key: 'path',    label: '路径',   mandatory: false, sortable: true, defVisible: false, defWidth: 360 }
        ]
    };
    // 共存账号 = 账号列 + 「最后登录账号」（linked_acc：该共存 exe 当前关联/最后登录的原生账号）；非必选、默认显示
    TABLE_COLUMNS.coexist = TABLE_COLUMNS.account.concat([
        { key: 'linked_acc', label: '最后登录账号', mandatory: false, sortable: true, defVisible: true, defWidth: 170, cellClass: 'manage-linked-acc-cell' }
    ]);
    var accountTables = {};
    var sectionScrollbar = null;   // 账号区域纵向 overlay 滚动条（attachScrollbar 返回）
    var settingsScrollbar = null;  // 设置区域纵向 overlay 滚动条

    // ---- 辅助函数 ----
    function bind(id, evt, fn) {
        var el = getEl(id);
        if (el) el.addEventListener(evt, fn);
    }

    function getEl(id) {
        return document.querySelector('#page-main #' + id) || document.getElementById(id);
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


    // ---- 初始化 ----
    function init() {
        if (isInitialized) {
            loadPlatformList();
            return;
        }
        isInitialized = true;

        // 初始化三个可复用表实例（原生程序/原生账号/共存账号）
        initAccountTables();
        cleanLegacyGlobalConfig();   // 清理 LocalGlobalConfig 中已废弃的冗余节点（需在表实例就绪后跑）
        initManageSidebar();
        initAccountWheelCollapse();
        loadPlatformList();
        bindManageEvents();
    }

    /**
     * 账号区域"有效滚动" → 自动收起设置区域.
     *
     * <p>有效 = 滚轮真的滚动了账号区域（`scrollTop` 发生变化）。若账号区域根本没有纵向滚动条、
     * 或已滚到边界，`scrollTop` 不变 → 视为无效滚动，不收起重置。
     * 收起走 `toggleSettingsPanel(false)`：已启用平台会写全局记录，未启用（设置不完备）平台只本地收起、不记录。
     */
    function initAccountWheelCollapse() {
        var area = document.querySelector('#page-main .account-area-inner') ||
                   document.querySelector('.account-area-inner');
        if (!area || area._wheelCollapseBound) return;
        area._wheelCollapseBound = true;
        area.addEventListener('wheel', function() {
            if (!currentSwId || isSettingsCollapsed()) return;
            var before = area.scrollTop;
            // 原生滚动属于事件的默认动作：下一轮事件循环再比对 scrollTop 才能判断"是否真的滚动了"
            setTimeout(function() {
                if (!currentSwId || isSettingsCollapsed()) return;
                if (area.scrollTop === before) return;   // 没有滚动条 / 已到边界 → 无效滚动
                toggleSettingsPanel(false);
            }, 0);
        }, { passive: true });
    }

    /**
     * 清理 LocalGlobalConfig.json 中**已无任何读写代码**的历史遗留节点.
     *
     * <p>（值传 null = 删除该字段，由 JsBridge.saveGlobalConfig → ConfigManager.updateGlobalConfig 实现）
     *  · `manage_settings_height` / `manage_settings_collapsed`：早期"全局设置区高度/各平台收起态"记录，
     *    已被 `settings_height` / `settings_expanded` 取代，代码里连常量都删了
     *  · `account_columns.<表id>` 扁平键：曾错写为扁平键的列配置（读取端只认嵌套结构）
     *  · `account_columns.visible` / `account_columns.width`：更早版本把单表配置直接挂在 account_columns 下
     *  · `account_columns.<已删除的表>`（如 invalid_acc）：表已不存在
     */
    function cleanLegacyGlobalConfig() {
        try {
            var g = JFC.bridge.getGlobalConfig() || {};
            var dead = { manage_settings_height: null, manage_settings_collapsed: null };

            // 顶层扁平键（account_columns.<表id>）
            Object.keys(g).forEach(function(k) {
                if (k.indexOf('account_columns.') === 0) dead[k] = null;
            });

            // account_columns 内部：剔除历史结构（visible/width）与已删除的表
            var ac = g.account_columns;
            if (ac) {
                var validIds = {};
                Object.keys(accountTables).forEach(function(id) { validIds[id] = true; });
                var pruned = {};
                Object.keys(ac).forEach(function(k) {
                    if (k === 'visible' || k === 'width') return;   // 更早版本的历史结构
                    if (!validIds[k]) return;                       // 表已删除
                    pruned[k] = ac[k];
                });
                if (Object.keys(pruned).length !== Object.keys(ac).length) {
                    dead.account_columns = pruned;                  // 有变化才整体覆盖
                }
            }

            JFC.bridge.saveGlobalConfig(JSON.stringify(dead));
        } catch (e) { /* 清理失败不影响使用 */ }
    }

    // ---- 初始化三个可复用表（组件 JFC.AccountTable） ----
    // 无效账号（SwAccData 有记录但磁盘不存在）不再单独成表，而是并入原生/共存表，置底 + 灰字 + "失效"标签
    function initAccountTables() {
        var defs = [
            { key: 'origin_prog', title: '原生程序', columns: TABLE_COLUMNS.program, enableHotkey: false, defaultSortField: 'name' },
            { key: 'origin_acc',  title: '原生账号', columns: TABLE_COLUMNS.account, enableHotkey: true,  defaultSortField: 'display_name' },
            { key: 'coexist_acc', title: '共存账号', columns: TABLE_COLUMNS.coexist, enableHotkey: true,  defaultSortField: 'display_name' }
        ];
        var containers = {
            origin_prog: 'acc-table-native-prog',
            origin_acc: 'acc-table-native-acc',
            coexist_acc: 'acc-table-coexist-acc'
        };
        defs.forEach(function(def) {
            accountTables[def.key] = new JFC.AccountTable({
                id: def.key,
                title: def.title,
                container: document.getElementById(containers[def.key]),
                columns: def.columns,
                enableHotkey: def.enableHotkey,
                defaultSortField: def.defaultSortField,
                getSwId: function() { return currentSwId; }
            });
        });

        // 账号区域纵向 overlay 滚动条（与表内横向同款：细、无箭头、随主题；原生有箭头且不随主题）
        var innerArea = document.querySelector('.account-area-inner');
        if (innerArea) {
            sectionScrollbar = JFC.AccountTable.attachScrollbar(innerArea, 'y');
            // 表内容变化（数据加载/渲染）时自动刷新
            try {
                var mo = new MutationObserver(function() { sectionScrollbar.update(); });
                mo.observe(innerArea, { childList: true, subtree: true, attributes: true, attributeFilter: ['style'] });
            } catch (e) { /* 轮询兜底 */ }
        }

        // 设置区域纵向滚动条（与账号区域同款，统一风格）
        var settingsContent = document.getElementById('manage-settings-content');
        if (settingsContent) {
            settingsScrollbar = JFC.AccountTable.attachScrollbar(settingsContent, 'y');
            // 设置内容动态渲染，变化时自动刷新
            try {
                var mo2 = new MutationObserver(function() { if (settingsScrollbar) settingsScrollbar.update(); });
                mo2.observe(settingsContent, { childList: true, subtree: true, attributes: true, attributeFilter: ['style'] });
            } catch (e) { /* rAF 兜底 */ }
        }
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

    // ---- 设置区域展开/收起 + 高度：全局统一（LocalGlobalConfig.settings_height / settings_expanded） ----
    // 规则（2026-10-05 改造）：
    //  · 高度与展开/收起态都是【全局一份】，任一平台切换/拖动/点击都写回同一记录，所有平台共用
    //  · 例外：设置不完备的平台（"未启用平台"）强制展开，其展开/收起【不写全局记录】；高度拖动照常同步全局
    //  · 旧版按平台记录（LocalSwConfig.<sw>.settings_height / .settings_expanded）仅用于一次性迁移
    var CURTAIN_DEFAULT_HEIGHT = 180;
    /** 三个路径类设置项（也是"绿框"状态的三个 key） */
    var PATH_FIELD_KEYS = ['inst_path', 'data_dir', 'dll_dir'];
    /** swId → { inst_path: bool, data_dir: bool, dll_dir: bool }：路径检查流程写入，窗帘判断只读 */
    var swPathGreen = {};
    /** 上次算出来的"该平台是否启用"（只有启用状态发生变化时才需要重渲染） */
    var swEnabledKnown = {};
    /** 上一次真正渲染出来的状态（唯一渲染依据的"上一帧"，用于决定是否动画、从哪开始） */
    var _lastRender = { shown: false, expanded: false, byRecord: false, height: 0 };
    /** 同步跑绿框检查期间，抑制"完备性变化"触发的重渲染 */
    var _suppressCurtainEnforce = false;

    function loadCurtainGlobal(swId) {
        if (curtainGlobal) return curtainGlobal;
        curtainGlobal = { height: CURTAIN_DEFAULT_HEIGHT, collapsed: false };
        try {
            var g = JFC.bridge.getGlobalConfig() || {};
            var h = parseInt(g.settings_height, 10);
            if (h > 0) curtainGlobal.height = h;
            if (g.hasOwnProperty('settings_expanded')) curtainGlobal.collapsed = !g.settings_expanded;
            // 一次性迁移：全局还没有高度记录时，沿用旧版当前平台记录的高度
            if (!(h > 0) && swId) {
                var swCfg = JFC.bridge.getSwConfig(swId) || {};
                var legacyH = parseInt(swCfg.settings_height, 10);
                if (legacyH > 0) {
                    curtainGlobal.height = legacyH;
                    saveCurtainGlobalHeight(legacyH);
                }
            }
        } catch (e) { /* 用默认值 */ }
        return curtainGlobal;
    }

    function saveCurtainGlobalHeight(h) {
        if (!curtainGlobal) curtainGlobal = { height: CURTAIN_DEFAULT_HEIGHT, collapsed: false };
        curtainGlobal.height = Math.round(h);
        try { JFC.bridge.saveGlobalConfig(JSON.stringify({ settings_height: curtainGlobal.height })); } catch (e) { }
    }

    function saveCurtainGlobalExpanded(expanded) {
        if (!curtainGlobal) curtainGlobal = { height: CURTAIN_DEFAULT_HEIGHT, collapsed: false };
        curtainGlobal.collapsed = !expanded;
        try { JFC.bridge.saveGlobalConfig(JSON.stringify({ settings_expanded: !!expanded })); } catch (e) { }
    }

    /**
     * 平台设置是否完备（完备 = "启用平台"）.
     *
     * <p>单一职责：本函数**只读取**三个路径项的"绿框"状态；
     * 绿框与否由路径检查流程（`validatePathInput` → `JFC.bridge.checkPath`）判定并记录在 `swPathGreen`。
     * 三项都绿 = 启用；任一项非绿 = 未启用（强制展开，且展开/收起不影响全局记录）。
     * 尚未检查过的平台按"启用"处理，等检查结果回来再由 `enforceCurtainForCompleteness()` 兜底强制展开。
     */
    function isSwSettingsComplete(swId) {
        var st = swPathGreen[swId];
        if (!st) return true;
        for (var i = 0; i < PATH_FIELD_KEYS.length; i++) {
            if (st[PATH_FIELD_KEYS[i]] !== true) return false;
        }
        return true;
    }

    /** 记录/更新某平台某个路径项的绿框状态（由路径检查流程调用） */
    function setPathGreen(swId, key, green) {
        if (!swId || PATH_FIELD_KEYS.indexOf(key) === -1) return;
        if (!swPathGreen[swId]) swPathGreen[swId] = {};
        swPathGreen[swId][key] = green === true;
        // 只有"启用 ↔ 未启用"发生变化时才需要重渲染（避免每次失焦检查都把面板重新撑开/收起）
        var enabled = isSwSettingsComplete(swId);
        if (swEnabledKnown[swId] !== undefined && swEnabledKnown[swId] !== enabled) {
            enforceCurtainForCompleteness();
        }
        swEnabledKnown[swId] = enabled;
    }

    /**
     * ===== 设置区域展开/收起/高度的**唯一渲染依据**（2026-10-05 重构）=====
     *
     * 期望状态（desiredCurtainState）由两样东西推导，别处不再各自为政：
     *   1) 全局记录（LocalGlobalConfig 的 settings_height / settings_expanded）——所有平台共用
     *   2) 例外：未启用平台（三个路径不全是绿框）**每次渲染都无视记录强制展开**；用户在本次访问里
     *      临时收起只在"这一次渲染"生效（`applyCurtainRender(true/false)` 的 override），
     *      **不写记录、也不留本地状态**，下次渲染依旧强制展开
     *
     * 规则：**所有渲染只走 applyCurtainRender()；启用平台的状态变更一律先写记录再渲染** ——
     * 不再有第二条写入面板高度/类名的路径互相撕扯。
     */
    function desiredCurtainState(swId) {
        var g = loadCurtainGlobal(swId);
        var enabled = isSwSettingsComplete(swId);
        return {
            enabled: enabled,
            forced: !enabled,
            // 未启用平台：**每次渲染都无视记录强制展开**（本地怎么改都不写记录，下次渲染又回到展开）
            expanded: enabled ? !g.collapsed : true,
            height: g.height
        };
    }

    /** 设置区域的两个方向箭头 */
    function setCurtainArrows(expanded) {
        var up = document.querySelector('#page-main #handle-arrow-up');
        var down = document.querySelector('#page-main #handle-arrow-down');
        if (up) up.style.display = expanded ? '' : 'none';
        if (down) down.style.display = expanded ? 'none' : '';
    }

    /** 应用"收起"外观（类 + 箭头 + 高度 0）；分割线光标由 body 类经 MutationObserver 同步 */
    function applyCollapsedCurtain() {
        var panel = getEl('manage-settings-panel');
        if (!panel) return;
        // 双 RAF 等待 WebView 完成新内容布局
        requestAnimationFrame(function() {
            requestAnimationFrame(function() { initHandleSvg(); });
        });
        panel.classList.add('collapsed');
        panel.style.maxHeight = '0px';
        setCurtainArrows(false);
    }

    /** 按"期望状态"渲染（唯一的 DOM 写入点；状态没变化时直接返回，不重放动画）
     *  @param overrideExpanded 仅本次渲染生效的展开态（未启用平台允许用户在本次访问里临时收起） */
    function applyCurtainRender(overrideExpanded) {
        var panel = getEl('manage-settings-panel');
        if (!panel || !currentSwId) return;
        var st = desiredCurtainState(currentSwId);
        var prev = _lastRender;
        var expanded = (typeof overrideExpanded === 'boolean') ? overrideExpanded : st.expanded;

        // 状态与上一帧完全一致 → 什么都不做（避免重复动画/无谓重排）
        if (prev.shown && prev.expanded === expanded &&
            (expanded ? Math.round(prev.height) === Math.round(st.height) : true)) {
            return;
        }

        if (!expanded) {
            applyCollapsedCurtain();
            _lastRender = { shown: true, expanded: false, byRecord: !st.forced, height: 0 };
            return;
        }

        panel.classList.remove('collapsed');
        setCurtainArrows(true);

        var animate = false, fromHeight = 0;
        if (prev.shown) {
            if (!prev.expanded && !prev.byRecord) {
                animate = false;                                      // 上次是"未启用平台的本地收起" → 直接落位
            } else {
                animate = true;
                fromHeight = prev.expanded ? prev.height : 0;          // 记录本身是收起 → 从 0 平滑展开（4.3）
            }
        }
        if (animate) animatePanelHeight(st.height, null, fromHeight);
        else applyPanelHeight(st.height);
        _lastRender = { shown: true, expanded: true, byRecord: !st.forced, height: st.height };
    }

    /** 切换展开/收起：启用平台先写记录再渲染；未启用平台只"这一次渲染"生效（不写任何持久状态） */
    function setCurtainExpanded(expand) {
        if (!currentSwId) return;
        if (isSwSettingsComplete(currentSwId)) {
            saveCurtainGlobalExpanded(expand);       // 启用平台：先写记录，再按记录渲染
            applyCurtainRender();
        } else {
            // 未启用平台：不写记录、也不留本地状态 —— 下次渲染依旧强制展开
            applyCurtainRender(expand);
        }
    }

    /** 拖动改变高度：写记录 + 立即按记录渲染 */
    function setCurtainHeight(h) {
        saveCurtainGlobalHeight(h);
        applyPanelHeight(h);
        _lastRender.height = Math.max(0, Math.round(h || 0));
    }

    /** 路径检查结果更新后调用：完备性可能变了 → 按期望状态重渲染（幂等） */
    function enforceCurtainForCompleteness() {
        if (_suppressCurtainEnforce) return;
        applyCurtainRender();
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

        // 恢复上次显示的平台：存在则直接进入平台页（不再停在"点击平台"的占位页）
        if (!currentSwId) {
            var lastSw = null;
            try {
                var g = JFC.bridge.getGlobalConfig();
                lastSw = g && g.last_sw_id ? g.last_sw_id : null;
            } catch (e) { /* 无配置则忽略 */ }
            var exists = lastSw && platforms.some(function(p) { return p.swId === lastSw; });
            if (exists) {
                currentSwId = null;          // 确保 selectPlatform 不会被"重复加载"拦截
                selectPlatform(lastSw);
            }
        }
    }

    function preloadPlatformIcons(platforms) {
        platforms.forEach(function(p) {
            if (iconCache[p.swId]) return;
            loadIconForSwId(p.swId);
        });
    }

    /** 平台图标：Java 侧优先用缓存的 {userData}/{sw}/{sw}.png，缺图或软件路径变更时才重新提取 */
    function loadIconForSwId(swId, exePath) {
        if (iconCache[swId]) return;
        try {
            var result = JFC.bridge.getSwIcon(swId);
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
        if (platforms.length === 0) {
            var emptyHtml = '<li class="nav-item" style="color:var(--text-muted);font-style:italic;">' +
                '<span class="nav-icon"><span class="manage-temp-icon">...</span></span>' +
                '<span class="nav-label">暂无平台数据</span></li>';
            var c = getEl('manage-platform-list'); if (c) c.innerHTML = emptyHtml;
            var n = getEl('nav-platform-list'); if (n) n.innerHTML = emptyHtml;
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
            var displayName = getPlatformDisplayName(p.swId, p.alias);
            html += '<li class="nav-item' + isActive + '" data-swid="' + escapeAttr(p.swId) + '">' +
                '<span class="nav-icon">' + iconHtml + '</span>' +
                '<span class="nav-label">' + escapeHtml(displayName) + '</span>' +
                '</li>';
        });
        var container = getEl('manage-platform-list');
        if (container) container.innerHTML = html;
        var navContainer = getEl('nav-platform-list');
        if (navContainer) navContainer.innerHTML = html;

        // 绑定点击
        if (container) {
            container.querySelectorAll('.nav-item[data-swid]').forEach(function(item) {
                item.addEventListener('click', function() {
                    var swId = this.getAttribute('data-swid');
                    if (swId) selectPlatform(swId);
                });
            });
        }
        if (navContainer) {
            navContainer.querySelectorAll('.nav-item[data-swid]').forEach(function(item) {
                item.addEventListener('click', function() {
                    var swId = this.getAttribute('data-swid');
                    if (swId) { JFC.router.navigate('main'); selectPlatform(swId); }
                });
            });
        }
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

    function selectPlatformInternal(swId) {
        // 通知 Java：进入平台页 → 自动触发数据维护（登录态/PID/互斥体等，后台执行）
        JFC.bridge.notifyPlatformEntered(swId);
        currentSwId = swId;
        // 记住最后显示的平台（下次启动直接进入该平台页）
        try { JFC.bridge.saveGlobalConfig(JSON.stringify({ last_sw_id: swId })); } catch (e) { /* 忽略 */ }
        // 清空所有表的选中状态
        Object.keys(accountTables).forEach(function(k) { accountTables[k].clearSelection(); });

        // 更新列表高亮 — 取消"全部"选中，高亮当前平台（page-main侧栏 + 主侧栏）
        var allItem = getEl('manage-all-nav-item');
        if (allItem) allItem.classList.remove('active');
        var navAllItem = document.getElementById('nav-all-item');
        if (navAllItem) navAllItem.classList.remove('active');

        var list = getEl('manage-platform-list');
        if (list) {
            list.querySelectorAll('.nav-item[data-swid]').forEach(function(item) {
                item.classList.toggle('active', item.getAttribute('data-swid') === swId);
            });
        }
        var navList = document.getElementById('nav-platform-list');
        if (navList) {
            navList.querySelectorAll('.nav-item[data-swid]').forEach(function(item) {
                item.classList.toggle('active', item.getAttribute('data-swid') === swId);
            });
        }

        // 切换到详情页面
        hide('manage-page-all');
        show('manage-page-detail');

        // 加载数据
        loadSwConfig(swId);
        loadAccountData(swId);
        // 进入平台页即刷新设置区域滚动条（覆盖内容填充与展开动画时序，不依赖用户调整高度才显示）
        if (settingsScrollbar) {
            settingsScrollbar.update();
            [120, 350, 800, 1500].forEach(function(d) {
                setTimeout(function() { if (settingsScrollbar) settingsScrollbar.update(); }, d);
            });
        }

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

        // 先同步跑一遍三个路径的"绿框"检查（checkPath 是同步桥调用）：
        // 让"是否启用"在渲染前就确定，避免"先按记录渲染、200ms 后检查结果回来又强制展开"的闪烁
        _suppressCurtainEnforce = true;
        PATH_FIELD_KEYS.forEach(function(key) {
            var input = getEl('mg-conf-' + key);
            if (input) validatePathInput(input);
        });
        _suppressCurtainEnforce = false;

        // 渲染的唯一依据 = 期望状态（全局记录 + 未启用平台的强制展开）
        applyCurtainRender();

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
                        return;
                }
            }
        } catch(e) {
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

    // ---- 路径输入框失焦检查（"绿框"的判定就在这里，窗帘状态只读取结果） ----
    function validatePathInput(input) {
        var key = input.getAttribute('data-field');
        if (!key || !currentSwId) return;
        var val = input.value.trim();
        if (!val) { clearPathHint(input); setPathGreen(currentSwId, key, false); return; }

        var result = JFC.bridge.checkPath(currentSwId, key, val);
        if (!result) { clearPathHint(input); setPathGreen(currentSwId, key, false); return; }

        removePathHint(input);
        var hint = document.createElement('span');
        hint.className = 'mg-path-hint';

        // 同时用类名标记状态（input-ok = 绿框），供其它流程只读判断
        input.classList.remove('input-ok', 'input-warn', 'input-error');
        if (result.valid) {
            input.style.borderColor = 'var(--color-success)';
            input.classList.add('input-ok');
            hint.className += ' hint-ok';
            hint.textContent = result.reason || '路径有效';
        } else if (result.exists) {
            input.style.borderColor = '#e6a817';
            input.classList.add('input-warn');
            hint.className += ' hint-warn';
            hint.textContent = result.reason || '路径不符合预期';
        } else {
            input.style.borderColor = 'var(--color-danger)';
            input.classList.add('input-error');
            hint.className += ' hint-err';
            hint.textContent = result.reason || '路径不存在';
        }
        setPathGreen(currentSwId, key, result.valid === true);

        var wrap = input.closest('.mg-input-dropdown-wrap');
        if (wrap) wrap.appendChild(hint);

        // 绿色/橙色自动保存，红色不保存
        if (result.valid || result.exists) {
            saveFieldNow(key, val);
        }

        // 检查结果可能揭示"未启用"（例如刚进入平台时结果还没回来）→ 强制展开
        enforceCurtainForCompleteness();
    }

    function removePathHint(input) {
        var wrap = input.closest('.mg-input-dropdown-wrap');
        if (wrap) {
            var old = wrap.querySelector('.mg-path-hint');
            if (old) old.remove();
        }
        input.style.borderColor = '';
        input.classList.remove('input-ok', 'input-warn', 'input-error');
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
        // SVG 是 width:100% + preserveAspectRatio="none"：viewBox 宽度必须与元素宽度一致，
        // 否则把手会被横向拉伸/压缩（窗口最大化后把手变宽就是这个原因）→ 每次尺寸变化都重设。
        svg.setAttribute('viewBox', (-halfW) + ' 0 ' + (2*halfW) + ' 20');
        var path = svg.querySelector('#handle-curve');
        if (path) {
            path.setAttribute('d', buildHandleCurveD(halfW));
        }
    }

    // ---- 设置区域高度拖动 ----
    var _dragStartY = 0, _dragStartH = 0, _dragged = false;

    /** 是否处于收起状态（收起时不允许拖动底部分割线，只能点把手展开） */
    function isSettingsCollapsed() {
        var panel = getEl('manage-settings-panel');
        return !!(panel && panel.classList.contains('collapsed'));
    }

    /**
     * 同步"收起"状态到 body（CSS 据此切换分割线拖动区的光标：展开 ns-resize / 收起 default）。
     *
     * <p>用 MutationObserver 监听面板的 collapsed 类：面板状态在多处被改动
     * （applyCurtainState / toggleSettingsPanel / 切换平台…），逐个改光标容易漏，
     * 这里统一由状态类驱动，绝不会出现"收起/展开光标都一样"的错位。
     */
    function installCurtainStateClassSync() {
        var panel = getEl('manage-settings-panel');
        if (!panel) return;
        document.body.classList.toggle('curtain-collapsed', isSettingsCollapsed());
        if (panel._curtainSyncBound) return;
        panel._curtainSyncBound = true;
        try {
            var mo = new MutationObserver(function() {
                document.body.classList.toggle('curtain-collapsed', isSettingsCollapsed());
            });
            mo.observe(panel, { attributes: true, attributeFilter: ['class', 'style'] });
        } catch (e) { /* 老 WebView 无 MutationObserver：至少初始状态是对的 */ }
    }

    function initHeightDrag() {
        var left = document.querySelector('#page-main #handle-drag-left');
        var right = document.querySelector('#page-main #handle-drag-right');
        if (!left && !right) return;
        if (left && left._dragBound) return;
        if (right && right._dragBound) return;

        // 窗口尺寸变化 → 同步把手 viewBox（否则 width:100% 的 SVG 会被横向拉伸/压缩）
        window.addEventListener('resize', function() { initHandleSvg(); });
        installCurtainStateClassSync();

        function onDown(e) {
            if (e.button !== 0) return;
            // 收起状态：不允许拖动分割线（此时面板高度为 0，拖动会瞬间跳到最小高度、与鼠标脱节）
            if (isSettingsCollapsed()) return;
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
            applyPanelHeight(newH);
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
                setCurtainHeight(h);   // 写记录 + 同步渲染状态
            }
        }
        if (left) { left._dragBound = true; left.addEventListener('mousedown', onDown); }
        if (right) { right._dragBound = true; right.addEventListener('mousedown', onDown); }

        // 仅中央点击区 hover 时着色箭头
        var clickZone = document.querySelector('#page-main #handle-click-zone');
        var svg = document.querySelector('#page-main #manage-curtain-handle');
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
            // 动画期间清除内容区 max-height 锁（让面板的 maxHeight 完全控制可见区域，面板才能撑高）
            var content = getEl('manage-settings-content');
            if (content) content.style.maxHeight = 'none';

            panel.style.transition = 'max-height 0.3s ease';
            panel.style.maxHeight = targetHeight + 'px';

            // 动画结束后恢复内容区 max-height 限制（否则 content 高度=内容高，永不溢出、滚动条不出现）
            // JavaFX transitionend 不可靠，用 setTimeout 兜底
            setTimeout(function() {
                applyPanelHeight(targetHeight);
                if (callback) callback();
            }, 400);
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

    /**
     * 统一的"设置区域高度"应用：面板与内容区**取同一个高度值**。
     *
     * <p>踩坑记录（2026-10-05 实测 JavaFX WebView）：
     * 曾经给内容区写死 `面板高 - 20` 作为"预留"，而动画期间内容区是解除上限的，
     * 于是动画能涨到 `H`、停下来却回落到 `H - 20` →
     * 切换平台时表现为"没动画也闪一下 / 有动画先冲到 H+20 再弹回"。
     * 实测结论：面板与内容区同值即可，靠内容区自己的 `overflow-y:auto` 出滚动条（写死偏移量只会造成不一致）。
     */
    function applyPanelHeight(panelH) {
        var panel = getEl('manage-settings-panel');
        var content = getEl('manage-settings-content');
        var h = Math.max(0, Math.round(panelH || 0));
        if (panel) panel.style.maxHeight = h + 'px';
        if (content) content.style.maxHeight = h + 'px';
        return h;
    }

    /** 点把手：切换展开/收起（先改事实来源，再统一渲染） */
    function toggleSettingsPanel(expand) {
        setCurtainExpanded(expand);
    }

    // ---- 加载账号/程序数据 ----
    function loadAccountData(swId) {
        // 详情来源：SwAccData（两个账号表共用）
        var detailMap = {};
        var data = JFC.bridge.getSwDetailData(swId);
        if (data && data.accounts) {
            data.accounts.forEach(function(a) { detailMap[a.id] = a; });
        }

        // 原生账号 = 数据目录下的账号子目录；共存账号 = 安装目录下的共存 exe
        var originIds = JFC.bridge.getSwExistedAccounts(swId, 'origin') || [];
        var coexistIds = JFC.bridge.getSwExistedAccounts(swId, 'coexist') || [];
        var originRows = buildAccountRows(originIds, detailMap, false);
        var coexistRows = buildAccountRows(coexistIds, detailMap, true);

        // 无效账号 = SwAccData 中所有账号 − 原生账号 − 共存账号
        // 按自身类型（共存 exe / 原生账号）并入对应表：置底 + 灰字 + "失效"标签
        var known = {};
        originIds.forEach(function(id) { known[id] = true; });
        coexistIds.forEach(function(id) { known[id] = true; });
        Object.keys(detailMap).forEach(function(id) {
            if (known[id]) return;
            var isCoexist = isCoexistAccount(detailMap[id], id);
            var rows = buildAccountRows([id], detailMap, isCoexist);
            if (!rows.length) return;
            rows[0].invalid = true;
            (isCoexist ? coexistRows : originRows).push(rows[0]);
        });

        accountTables.origin_acc.setData(originRows);
        accountTables.coexist_acc.setData(coexistRows);

        // 原生程序表：软件路径对应的那个程序（图标/名称/版本/路径）
        var prog = JFC.bridge.getSwProgramData(swId);
        var progRows = [];
        if (prog && (prog.name || prog.path)) {
            progRows.push({
                id: prog.path || prog.name,
                display_name: prog.name || '',      // 无图标时的文字头像取首字母
                avatar_data: programIcon(swId),
                name: prog.name || '',
                version: prog.version || '',
                path: prog.path || ''
            });
        }
        accountTables.origin_prog.setData(progRows);

        // 异步加载头像（本地文件 → URL下载 → SVG 回退）
        originRows.forEach(function(acc) { requestAccountAvatar(swId, acc, accountTables.origin_acc); });
        coexistRows.forEach(function(acc) { requestAccountAvatar(swId, acc, accountTables.coexist_acc); });

        // 刷新账号区域纵向滚动条（内容高度变化后）
        if (sectionScrollbar) {
            sectionScrollbar.update();
            setTimeout(function() { if (sectionScrollbar) sectionScrollbar.update(); }, 60);
        }
    }

    /** 程序图标（原生程序表头像列）：与左栏同源，走 Java 侧的 PNG 缓存（{userData}/{sw}/{sw}.png） */
    function programIcon(swId) {
        if (iconCache[swId]) return iconCache[swId];
        if (!swId || !window.JFC.bridge) return '';
        try {
            var res = JFC.bridge.getSwIcon(swId);
            if (res && res.iconUrl) {
                iconCache[swId] = res.iconUrl;
                return res.iconUrl;
            }
        } catch (e) { /* 提取失败则无图标（文字占位） */ }
        return '';
    }

    /** 判断 SwAccData 中的账号属于共存账号还是原生账号（用于无效账号归类）.
     *  共存账号节点的特征是带 linked_acc 字段（ensureCoexistAccFormatted 会补齐）；
     *  兜底再按 id 是否为 exe 名判断。 */
    function isCoexistAccount(acc, id) {
        if (acc && Object.prototype.hasOwnProperty.call(acc, 'linked_acc')) return true;
        return /\.exe$/i.test(id || '');
    }

    // ---- 账号 ID 列表 + SwAccData 详情 → 表行数据（原生/共存共用） ----
    // followLinkedAcc = 共存账号：自身只认 remark，昵称/平台内ID/头像一律取 linked_acc 指向的账号
    //   名称回退链：自身 remark > 链接账号 nickname > 链接账号 alias > 链接账号 id > 自身 id
    //   （原生账号：Java 端 getAccOriginDisplayName 已算好 remark > nickname > alias > id）
    function buildAccountRows(ids, detailMap, followLinkedAcc) {
        return ids.map(function(id) {
            var acc = detailMap[id] || {};
            var linkedAccId = followLinkedAcc ? (acc.linked_acc || '') : '';
            var linked = (linkedAccId && detailMap[linkedAccId]) ? detailMap[linkedAccId] : null;
            var src = linked || {};   // 共存账号的昵称/平台内ID/头像来源
            var name = followLinkedAcc
                ? (acc.remark || src.nickname || src.alias || linkedAccId || id)
                : (acc.display_name || '');
            // 标准化字段类型；未记录的新账号显示为空白详情
            return {
                id: id,
                nickname: followLinkedAcc ? (src.nickname || '') : (acc.nickname || ''),
                alias: followLinkedAcc ? (src.alias || '') : (acc.alias || ''),
                hotkey: acc.hotkey || '',
                display_name: name,
                avatar_url: followLinkedAcc ? (src.avatar_url || '') : (acc.avatar_url || ''),
                hidden: acc.hidden === true || acc.hidden === 'true',
                disabled: acc.disabled === true || acc.disabled === 'true',
                login_time: acc.login_time || acc.last_login || '',
                remark: acc.remark || '',
                // 共存账号特有：关联/最后登录的原生账号
                linked_acc: linkedAccId,
                // 保留原始字段以便后续使用
                _raw: acc
            };
        });
    }

    // ---- 异步头像加载 ----
    // 参考 acccore AccInfoFuncCore.getAvatarFromCache + getAccAvatarFromFile
    function requestAccountAvatar(swId, acc, table) {
        if (acc.avatar_data || acc._avatarFetching) return;
        acc._avatarFetching = true;
        JFC.bridge.getAccAvatarAsync(swId, acc.id, function(type, data) {
            acc._avatarFetching = false;
            if (data && data.dataUrl) {
                acc.avatar_data = data.dataUrl;
                var target = table || accountTables.origin_acc;
                if (target) target.updateAvatar(acc.id, data.dataUrl);
            }
        });
    }

    // ---- 事件驱动：Java 推送账号数据变更 → 路由到各表定向刷新（组件内处理） ----
    function onAccountChanged(p) {
        Object.keys(accountTables).forEach(function(k) {
            accountTables[k].onAccountChanged(p);
        });
    }

    // ---- Java Scene 捕获的组合键 → 路由到正在编辑快捷键的表 ----
    function onHotkeyCapture(combo) {
        Object.keys(accountTables).forEach(function(k) {
            accountTables[k].onHotkeyCapture(combo);
        });
    }

    // 表格渲染/事件/列配置/菜单/拖拽/快捷键等逻辑已迁移至 js/components/account-table.js



    // ---- 事件绑定 ----
    function bindManageEvents() {
        // "全部"按钮
        var allItem = getEl('manage-all-nav-item');
        if (allItem) {
            allItem.addEventListener('click', function() {
                hide('manage-page-detail');
                show('manage-page-all');
                currentSwId = null;
                // 清空所有表的选中状态
                Object.keys(accountTables).forEach(function(k) { accountTables[k].clearSelection(); });

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
            // 点击菜单外区域关闭右键菜单
            if (!target.closest || !target.closest('#account-col-menu') && !target.closest('#account-row-menu')) {
                JFC.AccountTable.closeMenus();
            }
        });

        // Esc 关闭右键菜单 / 取消快捷键编辑
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                JFC.AccountTable.closeMenus();
                Object.keys(accountTables).forEach(function(k) { accountTables[k].cancelHotkeyEdit(); });
            }
        });
    }

    return { init: init, onAccountChanged: onAccountChanged, onHotkeyCapture: onHotkeyCapture };
})();

