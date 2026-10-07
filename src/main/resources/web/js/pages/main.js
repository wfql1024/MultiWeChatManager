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
    //   loginOnly = **只在登录态出现**的列（PID / HWND）：登录态必显、管理态整列不显示，
    //               且它的显隐**不写进** account_columns 配置（纯会话状态）
    var TABLE_COLUMNS = {
        // 账号类表（原生/共存）
        account: [
            { key: 'check',        label: '勾选框',   mandatory: true,  pinned: true, sortable: false, defVisible: true,  defWidth: 40,  fixed: true  },
            { key: 'avatar',       label: '',         mandatory: true,  pinned: true, sortable: false, defVisible: true,  defWidth: 56,  fixed: true  },
            { key: 'display_name', label: '名称',      mandatory: true,  pinned: true, sortable: true, defVisible: true,  defWidth: 200 },
            // ↓ 登录态专列：紧挨名称列右侧（用户 2026-10-06 定）。
            //   **非必显**（用户后来要求"给用户最高自由"）：默认显示，但可在登录态的列菜单里自行隐藏
            { key: 'pid',          label: 'PID',      mandatory: false, sortable: true, sortType: 'number', loginOnly: true, defVisible: true, defWidth: 90 },
            { key: 'hwnd',         label: 'HWND',     mandatory: false, sortable: true, sortType: 'number', loginOnly: true, defVisible: true, defWidth: 100 },
            // 快捷键列改为**非必显**（可被列头菜单隐藏），默认显示；可排序（与其他列一视同仁，无特殊对待）
            { key: 'hotkey',       label: '快捷键',   mandatory: false, sortable: true, defVisible: true,  defWidth: 110 },
            { key: 'id',           label: 'ID',       mandatory: false, sortable: true, defVisible: true,  defWidth: 150, cellClass: 'manage-id-cell' },
            { key: 'alias',        label: '平台内ID', mandatory: false, sortable: true, defVisible: false, defWidth: 140, cellClass: 'manage-alias-cell' },
            { key: 'nickname',     label: '昵称',     mandatory: false, sortable: true, defVisible: false, defWidth: 140, cellClass: 'manage-nickname-data-cell' }
        ],
        // 程序类表（原生程序）：头像(程序图标) / 名称 / 版本 / 快捷键 / 路径（默认隐藏）
        // 头像列与账号表同款，保证行高一致（32px 头像 + 内边距）
        // **名称列与账号表完全统一**（同一 key = display_name → 复用可编辑名称单元格：1 级色 / 字号+1 / 加粗 / 中英分段）
        // **没有 PID/HWND 列**（用户 2026-10-07：程序只是个启动器，不算具体账号）
        program: [
            { key: 'check',        label: '勾选框', mandatory: true,  pinned: true, sortable: false, defVisible: true,  defWidth: 40, fixed: true },
            { key: 'avatar',       label: '',       mandatory: true,  pinned: true, sortable: false, defVisible: true,  defWidth: 56, fixed: true },
            { key: 'display_name', label: '名称',   mandatory: true,  pinned: true, sortable: true, defVisible: true,  defWidth: 220 },
            { key: 'version',      label: '版本',   mandatory: false, sortable: true, defVisible: true,  defWidth: 120 },
            { key: 'hotkey',       label: '快捷键', mandatory: false, sortable: true, defVisible: true,  defWidth: 110 },
            { key: 'path',         label: '路径',   mandatory: false, sortable: true, defVisible: false, defWidth: 360 }
        ]
    };
    // 共存账号 = 账号列 + 「最后登录账号」（linked_acc：该共存 exe 当前关联/最后登录的原生账号）；非必选、默认显示
    TABLE_COLUMNS.coexist = TABLE_COLUMNS.account.concat([
        { key: 'linked_acc', label: '最后登录账号', mandatory: false, sortable: true, defVisible: true, defWidth: 170, cellClass: 'manage-linked-acc-cell' }
    ]);
    var accountTables = {};
    /**
     * 平台页形态（用户 2026-10-06 定）：'login'（登录态，**每次进入软件默认**）| 'manage'（管理态）。
     * 同一页两种形态，由右上角二元滑块按钮切换；**会话内全局、不写配置**（设置区的展开记录不受影响）。
     */
    var pageMode = 'login';

    /**
     * **运行时账号数据**（PID / HWND）—— 只存内存，**不写任何配置文件**，生命周期随程序（用户 2026-10-06 定）.
     *
     * <p>结构：`{ swId: { accId: { pid, hwnd } } }`。渲染时注入到行数据（`pid` / `hwnd` 两列，仅登录态显示）；
     * 更新统一走 {@link setAccRuntime}（唯一写入点 → 写入后定向刷新那两格）。
     * 由登录流程 / 登录状态刷新调用（登录机制接入后即可充满）。
     */
    var accRuntimeMap = {};

    /** 取某平台某账号的运行时数据（无则返回空对象，永不返回 null） */
    function getAccRuntime(swId, accId) {
        var bySw = accRuntimeMap[swId];
        return (bySw && bySw[accId]) || {};
    }

    /**
     * 写入/更新某账号的运行时数据并**定向刷新**界面（唯一写入点）.
     *
     * @param {string} swId  平台
     * @param {string} accId 账号
     * @param {Object} patch {pid?, hwnd?}（只覆盖传入的字段）
     */
    function setAccRuntime(swId, accId, patch) {
        if (!swId || !accId || !patch) return;
        if (!accRuntimeMap[swId]) accRuntimeMap[swId] = {};
        var cur = accRuntimeMap[swId][accId] || {};
        var changed = {};
        ['pid', 'hwnd'].forEach(function(k) {
            if (patch[k] === undefined) return;
            var v = patch[k] === null ? '' : String(patch[k]);
            if (cur[k] !== v) { cur[k] = v; changed[k] = v; }
        });
        accRuntimeMap[swId][accId] = cur;
        if (!Object.keys(changed).length) return;
        // 定向刷新：三张表里对应的那一行的 pid/hwnd 两格（组件已支持任意字段的就地更新）
        Object.keys(accountTables).forEach(function(k) {
            accountTables[k].onAccountChanged({ accountId: accId, changed: changed });
        });
    }

    /** 清掉某平台的运行时数据（例如平台切换时重置；仅内存） */
    function clearAccRuntime(swId) {
        if (swId) delete accRuntimeMap[swId];
        else accRuntimeMap = {};
    }

    /**
     * 从 Java 侧**重新拉取**某平台的运行时数据（PID/HWND）并写入内存 Map.
     *
     * <p>为什么每次重取：pid/hwnd 讲究实时性，写文件读出来就是过时的（用户 2026-10-06 定）。
     * 进入平台、手动刷新时各调一次；Java 侧推送（`onAccountChanged` 带 pid/main_hwnd）也会就地更新。
     */
    function fetchAccRuntime(swId) {
        if (!swId || !window.JFC || !JFC.bridge) return;
        var res = null;
        try { res = JFC.bridge.getAccRuntimeMap(swId); } catch (e) { return; }
        if (!res || !res.accounts) return;
        if (!accRuntimeMap[swId]) accRuntimeMap[swId] = {};
        Object.keys(res.accounts).forEach(function(accId) {
            var item = res.accounts[accId] || {};
            accRuntimeMap[swId][accId] = {
                pid: (item.pid === null || item.pid === undefined) ? '' : String(item.pid),
                hwnd: (item.hwnd === null || item.hwnd === undefined) ? '' : String(item.hwnd)
            };
        });
    }
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
        applyPageMode(pageMode);     // 应用当前页面形态（管理态/登录态）到界面与各表
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
            // 原生程序表也要能录快捷键（列已加入 TABLE_COLUMNS.program），故 enableHotkey: true
            { key: 'origin_prog', title: '原生程序', columns: TABLE_COLUMNS.program, enableHotkey: true,  defaultSortField: 'display_name' },
            { key: 'origin_acc',  title: '原生账号', columns: TABLE_COLUMNS.account, enableHotkey: true,  defaultSortField: 'display_name' },
            { key: 'coexist_acc', title: '共存账号', columns: TABLE_COLUMNS.coexist, enableHotkey: true,  defaultSortField: 'display_name' }
        ];
        var containers = {
            origin_prog: 'acc-table-native-prog',
            origin_acc: 'acc-table-native-acc',
            coexist_acc: 'acc-table-coexist-acc'
        };
        defs.forEach(function(def) {
            var isProgram = def.key === 'origin_prog';
            accountTables[def.key] = new JFC.AccountTable({
                id: def.key,
                title: def.title,
                container: document.getElementById(containers[def.key]),
                columns: def.columns,
                enableHotkey: def.enableHotkey,
                defaultSortField: def.defaultSortField,
                getSwId: function() { return currentSwId; },
                // 重置账号后整表重载（备注/快捷键/隐藏/关联账号一起变，靠字段推送会留下半套真相）
                reloadAccounts: function() { if (currentSwId) loadAccountData(currentSwId); },
                // 原生程序表 = 平台自身：快捷键存 LocalSwConfig
                // （它不是账号，往 SwAccData 写会留下一条"路径键"节点、被当成失效账号）
                saveHotkey: isProgram ? savePlatformHotkey : null,
                // 账号表的头像文字兜底取"名称末尾 4 个字符宽"；程序表仍是首字符
                avatarFallbackTail: !isProgram,
                // 名称列的悬浮操作按钮（隐藏/重置/删除）是账号语义 → 程序表不显示
                // （名称列本身仍与账号表统一：可编辑 / 1 级色 / 字号+1 / 加粗 / 中英分段）
                // 行种类：'prog' = 原生程序行（管理态没有账号语义的行操作；登录态同样有"登录"）
                rowKind: isProgram ? 'prog' : 'acc'
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
        // 登录态下设置区域整体隐藏（CSS），这里不再做高度/动画计算：
        // 隐藏元素的 scrollHeight 恒为 0（LESSONS 第 30 条踩过），算了也不对；记录一律不动。
        if (pageMode === 'login') return;
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

    /**
     * 用**真实 DOM** 同步"上一帧"缓存 `_lastRender`.
     *
     * <p>为什么需要：`applyCurtainRender()` 靠 `_lastRender` 判断"状态是否变化"来决定要不要渲染。
     * 如果这里**伪造**一个状态（比如写死"已收起"），而界面其实还是展开的，两者就脱节了 ——
     * 之后点把手 / 滚轮收起时会被判成"状态没变化"→ 直接 return → **毫无反应**
     * （实测症状：从未完备平台切到正常平台后，把手与滚轮收起在其它平台全部失灵，回到未完备平台才恢复）。
     */
    function syncLastRenderFromDom() {
        var panel = getEl('manage-settings-panel');
        if (!panel) {
            _lastRender = { shown: false, expanded: false, byRecord: false, height: 0 };
            return;
        }
        var collapsed = panel.classList.contains('collapsed');
        var h = parseFloat(panel.style.maxHeight);
        _lastRender = { shown: true, expanded: !collapsed, byRecord: true, height: isNaN(h) ? 0 : h };
    }

    /**
     * 应用平台页形态（管理态 / 登录态）—— **唯一 DOM 写入点**（用户 2026-10-06 定）.
     *
     * <p>登录态：① 设置区域整体隐藏（CSS 隐藏容器，**不动 `settings_height`/`settings_expanded` 记录**）
     * ② 账号表只显示可登录的账号（失效/隐藏账号不显示）③ 行内/批量按钮只剩"登录 / 批量登录"
     * ④ 原生程序表隐藏（它不是账号，登录态没它的事）.
     *
     * <p>切回管理态：清掉登录态类 + 重置窗帘的"上一帧"缓存后重新按**记录**渲染设置区（记录从未被改过）。
     */
    function applyPageMode(mode) {
        pageMode = (mode === 'login') ? 'login' : 'manage';
        var login = pageMode === 'login';

        var mainEl = document.getElementById('page-main');
        if (mainEl) mainEl.classList.toggle('login-mode', login);

        // 滑块按钮：只切类名（滑块位置/颜色由 CSS 按类驱动）；
        // 文字在滑块上（默认显示**当前态**），鼠标移到整个按钮范围时换成"{箭头}{目标态}"
        var btn = getEl('manage-mode-toggle');
        if (btn) {
            btn.classList.toggle('is-manage', !login);
            btn.title = login ? '点击切换到管理态' : '点击切换到登录态';
            var cur = btn.querySelector('.mmt-cur');
            var next = btn.querySelector('.mmt-next');
            if (cur) cur.textContent = login ? '登录' : '管理';
            if (next) next.textContent = login ? '> 管理' : '< 登录';
        }

        // 设置区域：进入登录态 → **播放收起动画**后隐藏（不写记录）；切回管理态 → 从 0 播放展开动画到记录高度
        // （_lastRender 的 byRecord 必须为 true：这样退出登录态时 applyCurtainRender 会判定"需要动画"并给出来源高度 0）
        if (login) {
            // 无条件收起（不受 currentSwId 影响 —— 启动时还没有选中平台也要收，
            // 否则面板保持内容高度、隐藏后仍占位，就是用户看到的那块空白；
            // CSS 里还有 `#page-main.login-mode .manage-settings-panel { max-height: 0 !important }` 兜底）
            applyCollapsedCurtain();
            // 上面刚把它收起了 → 这里写"已收起"是**与真实 DOM 一致**的
            _lastRender = { shown: true, expanded: false, byRecord: true, height: 0 };
        } else if (currentSwId) {
            // 以真实 DOM 为准同步缓存，再按记录渲染（需要时从 0 播放展开动画）
            syncLastRenderFromDom();
            applyCurtainRender();
        }

        // 表格：三张表都跟随形态（原生程序也能登录，所以不特殊处理）
        ['origin_prog', 'origin_acc', 'coexist_acc'].forEach(function(k) {
            if (accountTables[k]) accountTables[k].setMode(pageMode);
        });
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
        // 未设置完备的平台：设置区会被**强制展开** → 模式也必须**强制为管理态**（用户 2026-10-06 定）。
        // 为什么放在这里而不是"进入平台时"：进入平台的那一刻三个路径还没检查（swPathGreen 里没有该平台记录），
        // `isSwSettingsComplete()` 会把未完备平台误判为完备 → 强制逻辑不会触发；
        // 而本函数是在路径检查结果回来后调用的（setPathGreen / 首次同步检查），此时判定才可信。
        if (currentSwId && !isSwSettingsComplete(currentSwId) && pageMode !== 'manage') {
            applyPageMode('manage');    // 内部会按记录渲染设置区（未完备 → 强制展开）
            return;
        }
        applyCurtainRender();
    }

    // ---- 加载平台列表 ----
    function loadPlatformList() {
        if (JFC.progress) JFC.progress.show();
        // 兜底检查：远程配置缺失则异步下载，失败则跳转设置页
        var ready = JFC.bridge.checkRemoteConfigReady();
        if (!ready || !ready.ready) {
            JFC.ensureRemoteConfigs(function() {
                loadPlatformListInternal();
                if (JFC.progress) JFC.progress.hide();
            });
            return;
        }
        loadPlatformListInternal();
        if (JFC.progress) JFC.progress.hide();
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
                item.addEventListener('click', function(e) {
                    var swId = this.getAttribute('data-swid');
                    if (swId) onPlatformItemClick(swId, e);
                });
            });
        }
        if (navContainer) {
            navContainer.querySelectorAll('.nav-item[data-swid]').forEach(function(item) {
                item.addEventListener('click', function(e) {
                    var swId = this.getAttribute('data-swid');
                    if (!swId) return;
                    // 只在"真的不在平台页"时才导航：否则每点一下都会重跑一次平台列表加载，
                    // 双击/多击时就会莫名闪出顶部进度条（用户实测反馈）
                    if (JFC.router.current() !== 'main') JFC.router.navigate('main');
                    onPlatformItemClick(swId, e);
                });
            });
        }
    }

    /** 获取平台显示名称: remark（本地） > alias（远程） > swId（标识） */    function getPlatformDisplayName(swId, remoteAlias) {
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

    // ---- 平台项点击策略 ----
    // 用户裁定（2026-10-05）：点别的平台 = 立即切换；点当前平台 = 单击刷新。
    // 用户补充（2026-10-07）：**双击（无论哪个平台）＝ 启动该平台程序**（= 程序表主程序点"登录"）。

    /** 统一的点击判定窗口（单击刷新 / 单击切平台 / 双击识别 / 双击启动，全部用它；用户 2026-10-07 定：250ms） */
    var CLICK_WINDOW_MS = 250;
    /** 挂起的"再点当前平台 → 刷新"定时器 */
    var pendingRefreshTimer = null;
    /**
     * 上一次点击的平台与时刻.
     *
     * <p>为什么要自己记而不用 {@code e.detail}：第一次点击"别的平台"会**立即切换平台**，
     * 而切换会重建侧栏 DOM → 第二次点击落在**新元素**上，浏览器给它的 {@code detail} 又从 1 开始
     * → 于是"在 A 平台双击 B 平台"根本不会被识别成双击（实测就表现为"只切了平台"）。
     * 记在自己模块里就与 DOM 是否重建无关了。
     */
    var lastPlatformClick = { swId: null, time: 0 };
    /** 挂起的"切到别的平台"定时器（双击时会被撤销 → 双击不切平台） */
    var pendingSwitchTimer = null;
    /** 挂起的"双击 → 启动该平台程序"定时器（三击要能撤销它） */
    var pendingLaunchTimer = null;
    /** 本轮连击计数：1=单击、2=双击、≥3=三击及以上（取消双击效果） */
    var clickStreak = 0;

    /**
     * 平台项点击入口（最左栏与平台页侧栏共用）.
     *
     * <p>· **双击** → **启动该平台程序**，且**不切换平台**（撤销挂起的切换）；动作**再延迟一个窗口**执行，
     * 这样紧接着的第三击能把它撤销<br>
     * · **三击及以上** → 取消双击效果（什么都不做）<br>
     * · 单击别的平台 → 等窗口过去再切换；单击当前平台 → 等窗口过去再刷新
     */
    function onPlatformItemClick(swId, e) {
        var now = Date.now();
        var sameStreak = (lastPlatformClick.swId === swId) && (now - lastPlatformClick.time < CLICK_WINDOW_MS);
        var isBrowserDouble = !!(e && e.detail > 1);
        lastPlatformClick = { swId: swId, time: now };
        clickStreak = sameStreak ? clickStreak + 1 : 1;

        if (clickStreak >= 3 || (isBrowserDouble && clickStreak >= 3)) {
            // 三击及以上：取消双击效果（连挂着的启动也撤销）
            cancelPendingRefresh();
            cancelPendingSwitch();
            cancelPendingLaunch();
            resetClickStreak();
            return;
        }

        if (clickStreak === 2 || isBrowserDouble) {
            // 双击：撤销单击效果（切平台 / 刷新），改为"启动该平台程序"，且再延迟一个窗口以便被三击撤销
            cancelPendingRefresh();
            cancelPendingSwitch();
            cancelPendingLaunch();
            pendingLaunchTimer = setTimeout(function() {
                pendingLaunchTimer = null;
                resetClickStreak();
                onPlatformMultiClick(swId);
            }, CLICK_WINDOW_MS);
            return;
        }

        if (currentSwId !== swId) {
            cancelPendingRefresh();          // 切平台：撤销可能挂着的"当前平台刷新"，避免切完又白刷一次
            cancelPendingSwitch();
            pendingSwitchTimer = setTimeout(function() {
                pendingSwitchTimer = null;
                resetClickStreak();
                selectPlatform(swId);
            }, CLICK_WINDOW_MS);
            return;
        }
        cancelPendingRefresh();
        pendingRefreshTimer = setTimeout(function() {
            pendingRefreshTimer = null;
            resetClickStreak();
            JFC.router.refresh();            // 统一刷新入口（2 秒不应期也在那里）
        }, CLICK_WINDOW_MS);
    }

    function resetClickStreak() {
        clickStreak = 0;
        lastPlatformClick = { swId: null, time: 0 };
    }

    /** 撤销挂起的"切到别的平台"（双击该平台时用） */
    function cancelPendingSwitch() {
        if (pendingSwitchTimer) {
            clearTimeout(pendingSwitchTimer);
            pendingSwitchTimer = null;
        }
    }

    /** 撤销挂起的"双击启动"（三击及以上时用） */
    function cancelPendingLaunch() {
        if (pendingLaunchTimer) {
            clearTimeout(pendingLaunchTimer);
            pendingLaunchTimer = null;
        }
    }

    function cancelPendingRefresh() {
        if (pendingRefreshTimer) {
            clearTimeout(pendingRefreshTimer);
            pendingRefreshTimer = null;
        }
    }

    /**
     * 双击/多击当前平台的入口 —— **启动平台程序**（= 程序表"登录"按钮同一件事）.
     *
     * <p>用户 2026-10-07 定：最左栏程序图标双击 = 平台页程序表的主程序点"登录"
     * （查杀该平台全部互斥体 + 降权启动 → 每次都能新开一个登录窗口）。
     */
    function onPlatformMultiClick(swId) {
        launchPlatformProgram(swId);
    }

    /**
     * 启动平台程序 —— **程序表"登录"按钮**与**最左栏程序图标双击**共用同一实现（单一来源）.
     *
     * <p>成功走右下角 toast（自动淡出，不打扰用户）；失败才弹窗（需要用户注意）。
     */
    function launchPlatformProgram(swId, count) {
        var id = swId || currentSwId;
        if (!id) return;
        var n = parseInt(count, 10);
        if (!n || n < 1) n = 1;
        var res = null;
        try {
            res = JFC.bridge.launchPlatformProgram(id, n);
        } catch (e) {
            res = null;
        }
        var mutexMsg = (res && res.mutexMessage) ? escapeHtml(res.mutexMessage) : '';
        if (res && res.success) {
            var pids = (res.pids && res.pids.length) ? res.pids.join(', ') : '';
            var detail = res.viaExplorer
                ? '（经资源管理器代启，未取到 PID）'
                : (pids ? '（PID ' + escapeHtml(pids) + '）' : '');
            JFC.toastSuccess('已以<b>普通用户权限</b>启动 <b>' + (res.count || n) + '</b> 个实例' + detail +
                (mutexMsg ? '<br><span style="opacity:.85">' + mutexMsg + '</span>' : ''), 4000);
            return;
        }
        JFC.modal.custom({
            title: '启动失败',
            bodyHtml: '<div style="line-height:1.9;">' +
                escapeHtml(res && res.error ? res.error : '启动失败') +
                (res && res.launched ? '<br>已成功启动 ' + res.launched + ' 个。' : '') + '<br>' +
                (mutexMsg ? '<span style="color:var(--text-muted);">' + mutexMsg + '</span>' : '') +
                '</div>',
            actions: [{ text: '知道了', cls: 'modal-ok' }]
        });
    }

    // ---- 选择平台 ----
    function selectPlatform(swId) {
        if (currentSwId === swId) {   // 兜底：已是当前平台 → 走统一刷新入口（2 秒不应期也在那里）
            JFC.router.refresh();
            return;
        }
        loadPlatform(swId);
    }

    /** 进入平台（含远程配置就绪兜底检查） */
    function loadPlatform(swId) {
        if (JFC.progress) JFC.progress.show();
        // 兜底检查远程配置
        var ready = JFC.bridge.checkRemoteConfigReady();
        if (!ready || !ready.ready) {
            JFC.ensureRemoteConfigs(function() {
                selectPlatformInternal(swId);
                if (JFC.progress) JFC.progress.hide();
            });
            return;
        }
        selectPlatformInternal(swId);
        if (JFC.progress) JFC.progress.hide();
    }

    /**
     * 重新加载当前页（平台页）.
     * **统一入口是 {@code JFC.router.refresh()}**（2 秒防连点不应期在那里，按钮与"再点当前平台"共用）；
     * 本函数只负责"重新走一遍加载链"：已进入平台 → 配置 + 账号数据 + 图标 + 滚动条，
     * 并重新触发 Java 侧后台数据维护；还停在"全部平台"占位页 → 只重载平台列表.
     */
    function refresh() {
        if (!isInitialized) { init(); return; }
        if (currentSwId) {
            loadPlatform(currentSwId);
        } else {
            loadPlatformList();
        }
    }

    /** 切换前记录上一个平台的高度，供切换动画使用 */

    function selectPlatformInternal(swId) {
        // 通知 Java：进入平台页 → 自动触发数据维护（登录态/PID/互斥体等，后台执行）
        JFC.bridge.notifyPlatformEntered(swId);
        currentSwId = swId;
        // 运行时数据（PID/HWND）**每次进平台重新取**（内存 Map，不落文件）
        fetchAccRuntime(swId);
        // 未设置完备的平台：设置区会被强制展开 → 因此也**强制进入管理态**（用户 2026-10-06 定）。
        // 注意：这个强制会写进"会话内的模式"，所以之后切到正常平台仍保持管理模式；
        // 而**正常的平台切换本身不改变模式**（模式是会话级单一变量，不按平台记忆、也不写配置）。
        if (!isSwSettingsComplete(swId)) applyPageMode('manage');
        else applyPageMode(pageMode);   // 只是把当前模式重新套到新平台的三张表上
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
        // fallbackName = "备注留空时会显示什么"（alias 或 swId）→ 标题输入框的灰字提示
        var fallbackName = (remoteInfo && remoteInfo.alias) || swId;
        var displayName = config.remark || fallbackName;
        // 清理历史遗留：早期把"远程别称"缓存成 config._alias 并**一起写进了本地配置**（本该只在内存里）。
        // 远程别称随时能从远程配置取（getRemotePlatformInfo），不需要持久化 → 这里删掉，
        // 之后的 saveSwConfig 就会把本地文件里那条 _alias 一并清掉。
        if (Object.prototype.hasOwnProperty.call(config, '_alias')) delete config._alias;
        delete swConfigData[swId]._alias;

        // 更新标题（灰字提示 = 不填备注时会显示的名称）
        setTitleDisplay(displayName, fallbackName);

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

    /**
     * 设置标题展示（h2），并绑定点击编辑.
     *
     * @param {string} name         当前显示名（remark > alias > swId）
     * @param {string} fallbackName 备注留空时会显示的名称（alias > swId）→ 输入框的灰色 placeholder，
     *                              让用户"清空回车前"就能看到会变成什么（用户 2026-10-05 要求）
     */
    function setTitleDisplay(name, fallbackName) {
        var titleEl = getEl('manage-detail-title');
        var inputEl = getEl('manage-detail-title-input');
        if (!titleEl) return;

        titleEl.textContent = name;
        titleEl.style.display = '';
        if (inputEl) {
            inputEl.style.display = 'none';
            if (fallbackName) inputEl.placeholder = fallbackName;
        }

        // 点击 h2 → 进入编辑模式
        titleEl.onclick = function() {
            if (!currentSwId) return;
            titleEl.style.display = 'none';
            if (inputEl) {
                inputEl.value = swConfigData[currentSwId] && swConfigData[currentSwId].remark
                    ? swConfigData[currentSwId].remark : '';
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
        // 备注留空时的显示名 = 远程别称 > 平台 id（远程别称按需取，不再依赖持久化的 _alias）
        var remoteAlias = (getRemotePlatformInfo(currentSwId) || {}).alias;
        var displayName = trimmed || remoteAlias || currentSwId;

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

    /**
     * 保存"平台主程序"的快捷键（原生程序表的快捷键列）.
     *
     * <p>存 `LocalSwConfig.<sw>.hotkey`，**不**进 SwAccData：原生程序不是账号（没有账号节点），
     * 往 SwAccData 里按 exe 路径建节点会让它在账号表里被判定成"失效账号"。
     */
    function savePlatformHotkey(accountId, value) {
        if (!currentSwId) return;
        if (!swConfigData[currentSwId]) swConfigData[currentSwId] = {};
        swConfigData[currentSwId].hotkey = value;
        try {
            JFC.bridge.saveSwConfig(currentSwId, JSON.stringify(swConfigData[currentSwId]));
        } catch (e) { /* 保存失败不影响本次显示 */ }
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

        // 原生程序表：软件路径对应的那个程序（图标/名称/版本/路径/快捷键）
        // 名称链（用户 2026-10-05 定）：**原生账号(origin_exe)的 remark > 平台名称**
        //   平台名称自身 = 本地 remark > 远程 alias > 平台 id（getPlatformDisplayName）
        //   origin_exe 不是磁盘上的账号，只是 SwAccData 里一条"程序自己的备注"记录 → 不会出现在账号表（Java 侧已过滤）
        var prog = JFC.bridge.getSwProgramData(swId);
        var progRows = [];
        if (prog && (prog.name || prog.path)) {
            var remoteInfo = getRemotePlatformInfo(swId) || {};
            var platformName = getPlatformDisplayName(swId, remoteInfo.alias);
            var progRemark = prog.remark || '';
            // 注意：程序行**不带 pid/hwnd**（用户 2026-10-07：程序只是启动器，不算具体账号 → 程序表没有这两列）
            progRows.push({
                id: 'origin_exe',                       // 固定 id：remark 存 SwAccData.<sw>.origin_exe.remark
                name: prog.name || '',                  // exe 文件名（保留字段）
                display_name: progRemark || platformName,
                display_name_auto: platformName,        // 备注留空时显示的名称 → 名称列编辑框的灰字提示
                remark: progRemark,
                avatar_data: programIcon(swId),
                version: prog.version || '',
                path: prog.path || '',
                // 平台自身的快捷键（存 LocalSwConfig，见 savePlatformHotkey）
                hotkey: (swConfigData[swId] && swConfigData[swId].hotkey) || ''
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
            // 名称回退链（**不含 remark**）：备注为空时该显示什么 —— 供名称列编辑框的灰字提示用。
            // 必须与下面的 name 用同一份输入，所以在这里一起算，避免"提示一套、提交后另一套"。
            var autoName = followLinkedAcc
                ? (src.nickname || src.alias || linkedAccId || id)
                : (acc.nickname || acc.alias || id);
            var name = followLinkedAcc
                ? (acc.remark || autoName)
                : (acc.display_name || autoName);
            // 运行时数据（PID/HWND）：来自内存 Map（不落任何配置文件）
            var rt = getAccRuntime(currentSwId, id);
            // 标准化字段类型；未记录的新账号显示为空白详情
            return {
                id: id,
                nickname: followLinkedAcc ? (src.nickname || '') : (acc.nickname || ''),
                alias: followLinkedAcc ? (src.alias || '') : (acc.alias || ''),
                hotkey: acc.hotkey || '',
                pid: rt.pid || '',
                hwnd: rt.hwnd || '',
                display_name: name,
                display_name_auto: autoName,   // 备注留空时将会显示的名称（名称列编辑框灰字 = 这个）
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
        // Java 侧推送里带 pid / main_hwnd 时，先收进**内存 Map**（PID/HWND 不进配置文件），
        // 再由 Map 统一渲染（注入行数据）→ 保持"一个数据来源"
        if (p && p.accountId && p.changed && currentSwId) {
            var rtPatch = {};
            if (p.changed.pid !== undefined) rtPatch.pid = p.changed.pid;
            if (p.changed.main_hwnd !== undefined) rtPatch.hwnd = p.changed.main_hwnd;
            if (Object.keys(rtPatch).length) setAccRuntime(currentSwId, p.accountId, rtPatch);
        }
        Object.keys(accountTables).forEach(function(k) {
            accountTables[k].onAccountChanged(p);
        });
    }

    /** 重新拉取某账号的头像（移除本地头像文件后用：清缓存 → 异步取 → 就地刷新那一格） */
    function refreshAvatar(swId, acc, table) {
        if (!acc) return;
        acc.avatar_data = '';
        acc._avatarFetching = false;
        requestAccountAvatar(swId, acc, table || accountTables.origin_acc);
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
        // 左上角二元按钮：管理态 ⇄ 登录态
        bind('manage-mode-toggle', 'click', function() {
            applyPageMode(pageMode === 'login' ? 'manage' : 'login');
        });

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
        // 注意：JavaFX WebView 的 keydown 里 event.key 为空串（见 app.js JFC.keys 注释），
        // 所以一律按 keyCode 判断（27=Esc、13=Enter），否则这两个键在这个 WebView 里根本不生效
        bind('manage-detail-title-input', 'keydown', function(e) {
            var code = JFC.keys.keyCodeOf(e);
            if (code === 13) {
                saveRemark(this.value);
            } else if (code === 27) {
                // 取消编辑
                var cfg = swConfigData[currentSwId] || {};
                var fallbackName = (getRemotePlatformInfo(currentSwId) || {}).alias || currentSwId;
                setTitleDisplay(cfg.remark || fallbackName, fallbackName);
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

        // Esc 关闭右键菜单 / 取消正在进行的单元格编辑（keyCode 判断，同上）
        document.addEventListener('keydown', function(e) {
            if (JFC.keys.keyCodeOf(e) === 27) {
                JFC.AccountTable.closeMenus();
                Object.keys(accountTables).forEach(function(k) { accountTables[k].cancelHotkeyEdit(); });
            }
        });
    }

    return { init: init, refresh: refresh, refreshAvatar: refreshAvatar,
             onAccountChanged: onAccountChanged, onHotkeyCapture: onHotkeyCapture,
             // 启动平台程序（程序表"登录"按钮 / 最左栏图标双击共用）
             launchPlatformProgram: launchPlatformProgram,
             // 运行时数据（PID/HWND）唯一写入点 + 读取器：登录流程接入后由它写入，界面自动定向刷新
             setAccRuntime: setAccRuntime, getAccRuntime: getAccRuntime, clearAccRuntime: clearAccRuntime };
})();

