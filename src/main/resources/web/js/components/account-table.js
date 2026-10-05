/**
 * account-table.js — 可复用账号/程序列表组件.
 *
 * 支持任意列组合（列头右键菜单勾选显示/列宽拖拽/自适应）、
 * 标题行（标题 + "已选 N 项" + 批量操作）、行右键菜单、快捷键列编辑。
 * 供 main.js 创建多个表实例（原生程序/原生账号/共存账号/无效账号）复用。
 *
 * 用法:
 *   var table = new JFC.AccountTable({
 *       id: 'origin_acc',                 // 唯一 id，列配置持久化键
 *       title: '原生账号',                 // 标题行文字
 *       container: document.getElementById('acc-table-origin-acc'),
 *       columns: [ {key,label,mandatory,sortable,defVisible,defWidth,fixed} ],
 *       defaultSortField: 'display_name',  // 默认排序列（可空）
 *       getSwId: function() { return currentSwId; },
 *       enableHotkey: true                 // 是否启用快捷键列编辑（需 hotkey 列）
 *   });
 *   table.setData(rows);                  // 渲染数据
 *   table.onAccountChanged(payload);      // EventBus 流B 推送路由
 *   table.onHotkeyCapture(combo);         // Java Scene 捕获的组合键
 */
var JFC = window.JFC || {};
JFC.AccountTable = (function() {
    'use strict';

    // 全局右键菜单元素（index.html 中定义，多个表共用）
    function colMenuEl() { return document.getElementById('account-col-menu'); }
    function rowMenuEl() { return document.getElementById('account-row-menu'); }

    // 当前打开菜单所属的表实例
    var activeTable = null;

    // 末尾占位列（不在 columns 里、不参与排序/显隐/菜单）：
    // 宽度 = 容器剩余宽度 → 表格总宽恒 >= 容器宽，所有真实列都能拖拽调宽，
    // 且行悬浮/选中的感应区天然覆盖整行（占位单元格属于该行）。
    var FILLER_COL = '_filler';

    /** 状态标签（名称前缀）：失效 → 禁用 → 隐藏；只作视觉前缀，不参与排序 */
    function renderNameTags(acc) {
        var html = '';
        if (acc.invalid) html += '<span class="manage-name-tag manage-invalid-tag">失效</span>';
        if (acc.disabled) html += '<span class="manage-name-tag manage-disabled-tag">禁用</span>';
        if (acc.hidden) html += '<span class="manage-name-tag manage-hidden-tag">隐藏</span>';
        return html;
    }

    /**
     * 把名称按"中日韩字符 / 其它"拆成两段，分别套 `.cjk-run` / `.lat-run`.
     *
     * <p>为什么要拆（2026-10-05 实测）：本 WebKit **做不到**"一个元素里中文雅黑 + 英文等宽" ——
     * `font-family` 列表在缺字时会走系统 CJK 回退（雅黑排在等宽之后也不生效），
     * `@font-face + unicode-range` 在这个版本同样不生效（放最前会把英文也吃掉）。
     * 只有**显式分段、各自指定字体**才能真正做到"中文雅黑 + 英文等宽"。
     */
    function scriptSplitHtml(text) {
        var s = String(text == null ? '' : text);
        if (!s) return '';
        if (!JFC.text || !JFC.text.isWide) return escapeHtml(s);
        var html = '', buf = '', cur = null;
        for (var i = 0; i < s.length; i++) {
            var cjk = JFC.text.isWide(s.charCodeAt(i));
            if (cur === null) cur = cjk;
            if (cjk !== cur) {
                html += wrapRun(buf, cur);
                buf = '';
                cur = cjk;
            }
            buf += s.charAt(i);
        }
        return html + wrapRun(buf, cur === true);
    }

    function wrapRun(txt, cjk) {
        if (!txt) return '';
        return '<span class="' + (cjk ? 'cjk-run' : 'lat-run') + '">' + escapeHtml(txt) + '</span>';
    }

    /**
     * 名称单元格内部 HTML（状态标签 + 名称 + 悬浮操作按钮）.
     * 渲染时与"编辑结束后回填单元格"共用同一份，避免两处结构漂移。
     *
     * <p>按钮分档（用户 2026-10-05 裁定）：非失效账号只给"隐藏/显示"+"重置"；
     * 失效账号再加"删除"（记录节点移除 → 该行消失）。非失效账号删不掉（磁盘上还在，下次加载照样出现）。
     *
     * <p>{@code showActions=false} 时**不渲染悬浮按钮**：原生程序表复用同一套名称列（可编辑、1 级色、字号+1、加粗），
     * 但"隐藏/重置/删除"是**账号**语义，对程序行没有意义。
     */
    function nameCellInnerHtml(acc, displayName, invalid, showActions) {
        var id = acc.id;
        var hidden = !!acc.hidden;
        var actions = '';
        if (showActions !== false) {
            actions = '<span class="manage-row-quick-actions">' +
                '<button class="qa-btn' + (hidden ? ' on' : '') + '" data-action="toggle-hidden" data-id="' + escapeAttr(id) + '"' +
                ' title="' + (hidden ? '显示账号' : '隐藏账号') + '">' + (hidden ? '显示' : '隐藏') + '</button>' +
                '<button class="qa-btn" data-action="reset" data-id="' + escapeAttr(id) + '" title="重置账号记录（清空备注/快捷键/隐藏等）">重置</button>' +
                (invalid
                    ? '<button class="qa-btn danger" data-action="delete" data-id="' + escapeAttr(id) + '" title="删除失效账号记录">删除</button>'
                    : '') +
                '</span>';
        }
        return '<div class="manage-nickname-inner">' +
            renderNameTags(acc) +
            '<span class="dn-text" title="点击编辑备注">' + scriptSplitHtml(displayName) + '</span>' +
            actions +
            '</div>';
    }

    // ---- 工具函数 ----
    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function escapeAttr(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // ---- 构造函数 ----
    function AccountTable(opts) {
        this.id = opts.id;
        this.title = opts.title || '';
        this.columns = opts.columns || [];
        this.container = opts.container;
        this.getSwId = opts.getSwId || function() { return null; };
        // 重置账号后需要"整表重载数据"（备注/快捷键/隐藏/关联账号一起变，光靠字段推送会留下半套真相）
        // 由 main.js 注入（走既有的 loadAccountData 链路），组件不自己拼数据来源
        this.reloadAccounts = opts.reloadAccounts || null;
        // 快捷键保存方式（默认存账号数据 SwAccData；原生程序表是"平台自身"，由 main.js 换成存 LocalSwConfig）
        this.saveHotkey = opts.saveHotkey || null;
        // 头像文字兜底取"名称末尾 4 个字符宽"（账号表）；默认取首字符（程序图标等）
        this.avatarFallbackTail = !!opts.avatarFallbackTail;
        // 名称列的悬浮操作按钮（隐藏/重置/删除）—— 账号语义；原生程序表传 false（只保留"可编辑 + 同名样式"）
        this.showRowActions = opts.showRowActions !== false;
        this.enableHotkey = !!opts.enableHotkey;
        this.accountData = [];
        this.selectedIds = new Set();
        this.sortField = opts.defaultSortField || '';
        this.sortAsc = true;
        this.colVisible = {};
        this.colWidth = {};
        this.resizeState = null;
        this.hotkeyEditAccountId = null;
        this.nameEditAccountId = null;
        this._menuOpen = false;
        // "结束编辑的那一下点击不要再选中行"：一次性标记 + 400ms 自动失效（见 _suppressRowSelectOnce）
        this._suppressSelectOnce = false;
        this._suppressSelectTimer = null;

        this._buildDom();
        this._loadColumnPrefs();
        this._bindDelegatedEvents();
    }

    // 列辅助
    AccountTable.prototype.colByKey = function(key) {
        for (var i = 0; i < this.columns.length; i++) {
            if (this.columns[i].key === key) return this.columns[i];
        }
        return null;
    };
    AccountTable.prototype.visibleCols = function() {
        var self = this;
        return this.columns.filter(function(c) { return self.colVisible[c.key]; });
    };

    // ---- DOM 构建 ----
    AccountTable.prototype._buildDom = function() {
        var self = this;
        var el = document.createElement('div');
        el.className = 'acc-table';
        el.setAttribute('data-table', this.id);

        var colgroupHtml = '';
        var theadHtml = '';
        this.columns.forEach(function(col) {
            colgroupHtml += '<col data-col="' + col.key + '">';
            var sortable = col.sortable ? ' data-sort="' + col.key + '"' : '';
            var cls = 'manage-col-' + col.key;
            var inner = (col.key === 'check')
                ? '<label class="acc-check"><input type="checkbox" class="acc-select-all">' +
                  '<span class="acc-check-box"></span></label>'
                : (col.label || '');
            theadHtml += '<th class="' + cls + '" data-col="' + col.key + '"' + sortable + '>' +
                inner + '</th>';
        });
        // 末尾占位列（撑满容器剩余宽度；无表头文字、无 data-col → 不参与显隐/排序/列菜单）
        colgroupHtml += '<col data-col="' + FILLER_COL + '">';
        theadHtml += '<th class="manage-col-filler"></th>';

        el.innerHTML =
            '<div class="acc-table-titlebar">' +
                '<span class="acc-table-title"></span>' +
                '<span class="acc-table-meta">' +
                    '<span class="acc-table-count" style="display:none;">已选 0 项</span>' +
                    // 取消多选：夹在"已选 x 项"与批量按钮之间（用户要求）
                    '<button class="btn btn-sm acc-table-cancel" data-batch="cancel" style="display:none;">取消</button>' +
                    '<span class="acc-table-batch" style="display:none;">' +
                        // 隐藏/显示合并成一个按钮：文案按"选中项是否全为隐藏"变（全隐藏→"显示"，否则→"隐藏"）
                        '<button class="btn btn-sm" data-batch="toggle-hidden">隐藏</button>' +
                        '<button class="btn btn-sm" data-batch="reset">重置</button>' +
                        '<button class="btn btn-sm batch-danger" data-batch="delete">删除</button>' +
                    '</span>' +
                '</span>' +
            '</div>' +
            '<div class="acc-table-scroll">' +
                '<table class="manage-account-table">' +
                    '<colgroup>' + colgroupHtml + '</colgroup>' +
                    '<thead><tr>' + theadHtml + '</tr></thead>' +
                    '<tbody></tbody>' +
                '</table>' +
            '</div>';

        this.container.appendChild(el);
        this.el = el;
        this.titleEl = el.querySelector('.acc-table-title');
        this.countEl = el.querySelector('.acc-table-count');
        this.batchEl = el.querySelector('.acc-table-batch');
        this.cancelEl = el.querySelector('.acc-table-cancel');
        this.tbody = el.querySelector('tbody');
        this.tableEl = el.querySelector('table');
        this.titleEl.textContent = this.title;
        // 表内横向 overlay 滚动条（列宽总和 > 表宽时显示，不占位不撑高）
        this._hScrollbar = attachCustomScrollbar(el.querySelector('.acc-table-scroll'), 'x');
        // 整行背景层（悬浮 + 选中）：tr 背景只能覆盖列区域，覆盖不到表格右侧空白
        // 两层都放在表格内容之下（CSS z-index:-1）+ 不透明色，避免半透明叠加与遮挡文字
        this._rowHighlight = document.createElement('div');
        this._rowHighlight.className = 'acc-row-highlight';
        el.querySelector('.acc-table-scroll').appendChild(this._rowHighlight);
        this._selLayer = document.createElement('div');
        this._selLayer.className = 'acc-row-selection-layer';
        el.querySelector('.acc-table-scroll').appendChild(this._selLayer);
        this._hoverRow = null;
    };

    // ---- 列配置持久化（LocalGlobalConfig.json.account_columns.<表id>） ----
    AccountTable.prototype._loadColumnPrefs = function() {
        var prefs = null;
        try {
            var cfg = JFC.bridge.getGlobalConfig();
            if (cfg && cfg.account_columns && cfg.account_columns[this.id]) {
                prefs = cfg.account_columns[this.id];
            }
        } catch (e) { /* 配置缺失时使用默认值 */ }
        // 列定义结构性变化（如"原生程序"表删掉"状态"列、加"版本"列）→ 旧配置里的列名已不存在，
        // 直接作废回默认值，避免沿用已经不存在的列宽/显隐（例如旧的 path 显示、58px 列宽）
        if (prefs && prefs.visible) {
            var stale = false;
            for (var k in prefs.visible) {
                if (Object.prototype.hasOwnProperty.call(prefs.visible, k) && !this.colByKey(k)) { stale = true; break; }
            }
            if (stale) prefs = null;
        }
        var self = this;
        this.columns.forEach(function(col) {
            self.colVisible[col.key] = col.mandatory ? true :
                (prefs && prefs.visible && prefs.visible[col.key] !== undefined
                    ? !!prefs.visible[col.key] : col.defVisible);
            // 固定列（勾选框/头像）宽度绝对固定，不读取持久化配置
            self.colWidth[col.key] = col.fixed ? col.defWidth :
                ((prefs && prefs.width && prefs.width[col.key] && typeof prefs.width[col.key] === 'number')
                    ? prefs.width[col.key] : col.defWidth);
        });
        this._applyColumnLayout();
    };

    AccountTable.prototype._saveColumnPrefs = function() {
        try {
            var visible = {}, width = {};
            this.columns.forEach(function(col) {
                visible[col.key] = !!this.colVisible[col.key];
                width[col.key] = this.colWidth[col.key];
            }, this);

            // 写嵌套的 account_columns.<表id>（唯一读取结构）。
            // saveGlobalConfig 是顶层浅合并，故先读出现有 account_columns 再合并，避免清掉其它表的配置；
            // 同时剔除历史遗留的 visible/width 顶层项（更早版本把单表配置直接挂在 account_columns 下）。
            var all = {};
            try {
                var cfg = JFC.bridge.getGlobalConfig();
                var exist = cfg && cfg.account_columns;
                if (exist) {
                    Object.keys(exist).forEach(function(k) {
                        if (k !== 'visible' && k !== 'width') all[k] = exist[k];
                    });
                }
            } catch (e) { /* 读不到就从空对象开始 */ }
            all[this.id] = { visible: visible, width: width };

            JFC.bridge.saveGlobalConfig(JSON.stringify({ account_columns: all }));
        } catch (e) { /* 保存失败不影响使用 */ }
    };

    AccountTable.prototype._applyColumnLayout = function() {
        var table = this.tableEl;
        if (!table) return;
        table.querySelectorAll('colgroup col[data-col]').forEach(function(col) {
            var key = col.getAttribute('data-col');
            if (key === FILLER_COL) return;   // 占位列宽度由 _updateTableWidth 按容器剩余空间决定
            var def = this.colByKey(key);
            var visible = !!this.colVisible[key];
            // 隐藏列：col 宽度必须归零 + 整列隐藏。
            // 只把 th/td 设 display:none 是不够的——table-layout:fixed 下列宽仍取自 <col>，
            // 于是"声明的列宽总和"大于表格设定宽度，浏览器会重新分配列宽 →
            // 表现为"最右可见列拖不动 / 调至合适宽度不生效"，而所有列都显示时一切正常。
            col.classList.toggle('hidden-col', !visible);
            // 固定列（勾选框/头像）宽度绝对固定（defWidth），不随任何操作/配置改变
            col.style.width = !visible ? '0px'
                : ((def && def.fixed ? def.defWidth : (this.colWidth[key] || 0)) + 'px');
        }, this);
        table.querySelectorAll('th[data-col], td[data-col]').forEach(function(cell) {
            var key = cell.getAttribute('data-col');
            cell.classList.toggle('hidden-col', !this.colVisible[key]);
        }, this);
        this._initColResizers(table);
        this._updateTableWidth();
    };

    // 表格宽度恒 = 可见列宽总和 + 占位列（容器剩余宽度）：
    //   - 列宽由各 col 固定 px 决定，绝不按比例分配 → 调整某列不影响其它列
    //   - 总和 >= 容器 → 占位列宽 0，容器出现横向滚动条
    //   - 总和 < 容器 → 占位列补足 → 表格总宽 = 容器宽（行背景层/悬浮感应覆盖整行）
    AccountTable.prototype._updateTableWidth = function() {
        var sum = 0;
        for (var i = 0; i < this.columns.length; i++) {
            var col = this.columns[i];
            if (this.colVisible[col.key]) {
                sum += col.fixed ? col.defWidth : (this.colWidth[col.key] || 0);
            }
        }
        var scrollEl = this.el ? this.el.querySelector('.acc-table-scroll') : null;
        var avail = scrollEl ? scrollEl.clientWidth : 0;
        sum = Math.round(sum);
        // 占位列 = 容器可显示宽 - 可见列宽总和 → 占位列右端恰好落在列表区域右边缘
        var filler = Math.max(0, avail - sum);

        this.tableEl.style.width = (sum + filler) + 'px';
        var fillerCol = this.tableEl.querySelector('colgroup col[data-col="' + FILLER_COL + '"]');
        if (fillerCol) fillerCol.style.width = filler + 'px';
        // 占位列无剩余空间时（列宽总和已超出容器）隐藏其单元格，避免多余边框
        this.tableEl.querySelectorAll('.manage-col-filler')
            .forEach(function(cell) { cell.classList.toggle('hidden-col', filler <= 0); });

        if (this._hScrollbar) this._hScrollbar.update();
        // 表格宽度变了 → 整行背景层宽度同步（选中色/悬浮色要覆盖到容器右边缘）
        if (this._selLayer) this._updateSelectionLayer();
    };

    // ---- 数据 ----
    AccountTable.prototype.setData = function(rows) {
        this.cancelHotkeyEdit();   // 数据重载前结束编辑（DOM 即将重建）
        this.accountData = rows || [];
        // 清除不在数据中的选中项
        var valid = new Set(this.accountData.map(function(a) { return a.id; }));
        var self = this;
        this.selectedIds.forEach(function(id) { if (!valid.has(id)) self.selectedIds.delete(id); });
        this.render();
    };

    // ---- 渲染 ----
    AccountTable.prototype.render = function() {
        var tbody = this.tbody;
        var accounts = this._sortAccounts(this.accountData);

        if (accounts.length === 0) {
            tbody.innerHTML = '<tr class="manage-empty-row"><td colspan="' + (this.columns.length + 1) + '">' +
                '<div class="manage-empty-state">暂无数据</div></td></tr>';
            this._updateRowHighlight();
            this._updateSelectionLayer();
            return;
        }

        var html = '';
        var self = this;
        accounts.forEach(function(acc) {
            html += self._rowHtml(acc);
        });

        tbody.innerHTML = html;
        this._bindRowEvents();
        this._applyColumnLayout();
        if (this._hScrollbar) this._hScrollbar.update();
        // 行已重建，清除悬停高亮（旧行元素失效）；选中层按新行重画
        this._hoverRow = null;
        this._updateRowHighlight();
        this._updateSelectionLayer();
    };

    AccountTable.prototype._rowHtml = function(acc) {
        var id = acc.id;
        var displayName = acc.display_name || acc.nickname || id;
        var avatarUrl = acc.avatar_data || acc.avatar_url;
        var hidden = !!acc.hidden;
        var isSelected = this.selectedIds.has(id);
        var html = '';

        this.columns.forEach(function(col) {
            html += this._cellHtml(acc, col, {
                id: id, displayName: displayName, avatarUrl: avatarUrl,
                hidden: hidden, isSelected: isSelected, invalid: !!acc.invalid
            });
        }, this);
        // 占位列单元格：让本行铺满整行（悬浮/选中感应区覆盖到容器右边缘）
        html += '<td class="manage-col-filler"></td>';

        // 行级状态类（供 CSS 决定文字三级色）：
        //   hidden-row  → 整行 2 级（名称列也从 1 级降到 2 级）
        //   invalid-row → 整行 3 级（CSS 里排在 hidden-row 之后，同时满足时失效优先）
        return '<tr data-acc-id="' + escapeAttr(id) + '" class="' +
            (isSelected ? 'selected' : '') + (acc.hidden ? ' hidden-row' : '') +
            (acc.invalid ? ' invalid-row' : '') + '">' +
            html + '</tr>';
    };

    AccountTable.prototype._cellHtml = function(acc, col, ctx) {
        var key = col.key;
        var id = ctx.id;

        if (key === 'check') {
            // 自绘勾选框：原生 input 只当状态载体（透明），可见的圆角方块由 .acc-check-box 画。
            // 原因：原生控件在 JavaFX WebView 里会先画一帧"纯方形"、随后才应用圆角/主题色 → 用户看到闪烁。
            return '<td data-col="check" class="manage-col-check">' +
                '<label class="acc-check">' +
                '<input type="checkbox"' + (ctx.isSelected ? ' checked' : '') +
                ' data-acc-id="' + escapeAttr(id) + '">' +
                '<span class="acc-check-box"></span>' +
                '</label></td>';
        }
        if (key === 'avatar') {
            var label = this._avatarFallbackLabel(ctx.displayName);
            return '<td data-col="avatar" class="manage-col-avatar"><div class="manage-account-avatar">' +
                (ctx.avatarUrl
                    ? '<img src="' + escapeAttr(ctx.avatarUrl) + '" alt="" onerror="this.parentElement.innerHTML=\'' +
                        this._avatarPlaceholderHtml(label) + '\';">'
                    : this._avatarPlaceholderHtml(label)) +
                '</div></td>';
        }
        if (key === 'display_name') {
            // 名称前缀状态标签（失效/禁用/隐藏）：只是视觉前缀，排序仍按 display_name 数据，不受标签影响
            // 注意：td 本身不能用 display:flex —— 那会让 td 不再是 table-cell，
            // 浏览器插入匿名 cell，td 自己的 padding/border 就画在里面，名称列会多出一条"下划线"。
            // 所以 flex 放在内层 div（.manage-nickname-inner）上。
            // 点击名称文字 → 就地编辑备注（与快捷键列同款交互）
            return '<td data-col="display_name" class="manage-nickname-cell">' +
                nameCellInnerHtml(acc, ctx.displayName, ctx.invalid, this.showRowActions) +
                '</td>';
        }
        if (key === 'hotkey' && this.enableHotkey) {
            var hotkeyHtml = acc.hotkey
                ? '<span class="hotkey-text">' + escapeHtml(acc.hotkey) + '</span>'
                : '<span class="hotkey-text"><span class="hotkey-placeholder">—</span></span>';
            return '<td data-col="hotkey" class="manage-hotkey-cell" title="点击设置快捷键">' + hotkeyHtml + '</td>';
        }
        // 通用文本列
        var val = acc[key] !== undefined ? acc[key] : '';
        var textClass = 'manage-text-cell' + (col.cellClass ? ' ' + col.cellClass : '');
        // 程序表的名称列：与账号表名称列一致，按"中文段 / 非中文段"分段给字体
        //（WebKit 的 font-family 回退不可靠，只有显式分段才能做到"中文雅黑 + 英文等宽"）
        var cellInner = (key === 'name') ? scriptSplitHtml(val) : escapeHtml(val);
        return '<td data-col="' + key + '" class="' + textClass + '" title="' + escapeAttr(val) + '">' +
            cellInner + '</td>';
    };

    // ---- 排序 ----
    // 排序：先按排序字段，再做"置底分组"——隐藏账号次置底、失效账号永远置底
    // （Array#sort 在现代浏览器是稳定排序，同组内保持上面的排序结果）
    AccountTable.prototype._sortAccounts = function(accounts) {
        var field = this.sortField;
        var asc = this.sortAsc;
        var list = accounts.slice();
        if (field) {
            list.sort(function(a, b) {
                var va = a[field], vb = b[field];
                if (va == null) va = '';
                if (vb == null) vb = '';
                if (typeof va === 'boolean') va = va ? '1' : '0';
                if (typeof vb === 'boolean') vb = vb ? '1' : '0';
                if (typeof va === 'string' && typeof vb === 'string') {
                    var cmp = va.localeCompare(vb, 'zh-CN');
                    return asc ? cmp : -cmp;
                }
                return 0;
            });
        }
        var rank = function(a) { return a.invalid ? 2 : (a.hidden ? 1 : 0); };
        list.sort(function(a, b) { return rank(a) - rank(b); });
        return list;
    };

    // ---- 事件绑定（render 后：行级元素） ----
    AccountTable.prototype._bindRowEvents = function() {
        var tbody = this.tbody;
        var self = this;

        // 全选框状态同步
        var selectAll = this.el.querySelector('.acc-select-all');
        if (selectAll) {
            var allIds = this.accountData.map(function(a) { return a.id; });
            selectAll.checked = allIds.length > 0 && allIds.every(function(id) { return self.selectedIds.has(id); });
        }

        // 行点击选中（排除勾选框/按钮/快捷键单元格/名称单元格）
        // 名称单元格必须排除：它自己有点击进编辑的行为，且行选中会 render() 重建 DOM，
        // 让编辑拿到已脱离文档的 cell 引用（同一坑快捷键列早就踩过）
        tbody.querySelectorAll('tr[data-acc-id]').forEach(function(row) {
            row.addEventListener('click', function(e) {
                // 这一下点击如果是"用来结束单元格编辑"的，就不要再顺手选中行（用户要求）
                if (self._suppressSelectOnce) { self._suppressSelectOnce = false; return; }
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON' ||
                    e.target.closest('.qa-btn') || e.target.closest('.manage-hotkey-cell') ||
                    e.target.closest('.manage-col-avatar') || e.target.closest('.acc-check') ||
                    e.target.closest('.manage-nickname-cell')) return;
                var id = this.getAttribute('data-acc-id');
                if (self.selectedIds.has(id)) self.selectedIds.delete(id);
                else self.selectedIds.add(id);
                self.render();
                self._updateSelectionUI();
            });
        });

        // 行内勾选框
        tbody.querySelectorAll('input[type="checkbox"][data-acc-id]').forEach(function(cb) {
            cb.addEventListener('change', function(e) {
                e.stopPropagation();
                var id = this.getAttribute('data-acc-id');
                if (this.checked) self.selectedIds.add(id);
                else self.selectedIds.delete(id);
                var row = this.closest('tr');
                if (row) row.classList.toggle('selected', this.checked);
                self._updateSelectionUI();
            });
        });

        // 悬浮操作按钮：改为**容器委托**（见 _bindDelegatedEvents）——
        // 名称单元格编辑结束会就地重建按钮，逐行绑定的话重建后就点不动了

        // 表头排序（当前排序列高亮，无箭头字符）
        var table = this.tableEl;
        table.querySelectorAll('th[data-sort]').forEach(function(th) {
            var newTh = th.cloneNode(true);
            th.parentNode.replaceChild(newTh, th);
            newTh.addEventListener('click', function(e) {
                if (e.target.closest('.col-resizer')) return;
                var field = this.getAttribute('data-sort');
                if (self.sortField === field) self.sortAsc = !self.sortAsc;
                else { self.sortField = field; self.sortAsc = true; }
                self.render();
            });
        });
        table.querySelectorAll('th[data-sort]').forEach(function(th) {
            th.classList.toggle('sorted', th.getAttribute('data-sort') === self.sortField);
        });
    };

    // ---- 事件绑定（一次性：标题行/表格容器委托） ----
    AccountTable.prototype._bindDelegatedEvents = function() {
        var self = this;

        // 全选框
        var selectAll = this.el.querySelector('.acc-select-all');
        if (selectAll) {
            selectAll.addEventListener('change', function() {
                if (this.checked) {
                    self.accountData.forEach(function(a) { self.selectedIds.add(a.id); });
                } else {
                    self.selectedIds.clear();
                }
                self.render();
                self._updateSelectionUI();
            });
        }

        // 批量操作
        this.el.querySelector('.acc-table-titlebar').addEventListener('click', function(e) {
            var btn = e.target.closest('[data-batch]');
            if (!btn) return;
            self.batchAction(btn.getAttribute('data-batch'));
        });

        // 右键菜单（统一绑在滚动容器，覆盖列头/最右列右侧空白区域 → 列菜单；数据行 → 行菜单）
        this.el.querySelector('.acc-table-scroll').addEventListener('contextmenu', function(e) {
            var tr = e.target.closest('tr[data-acc-id]');
            if (tr) {
                e.preventDefault();
                closeColMenu();
                self._showRowMenu(e.clientX, e.clientY, tr.getAttribute('data-acc-id'));
                return;
            }
            // 列头或占位列/空白区域 → 列菜单（无具体列时省略"该列调至合适宽度"）
            e.preventDefault();
            var th = e.target.closest('th[data-col]');
            var colKey = th ? th.getAttribute('data-col') : null;
            closeRowMenu();
            self._showColMenu(e.clientX, e.clientY, colKey);
        });

        // 快捷键单元格点击编辑
        if (this.enableHotkey) {
            this.tbody.addEventListener('click', function(e) {
                var cell = e.target.closest('.manage-hotkey-cell');
                if (!cell) return;
                if (e.target.tagName === 'INPUT') return;
                e.stopPropagation();
                var tr = cell.closest('tr[data-acc-id]');
                if (!tr) return;
                self.activateHotkeyEdit(cell, tr.getAttribute('data-acc-id'));
            });
        }

        // 名称单元格点击编辑（点名称文字进入编辑；点悬浮按钮不进入）
        this.tbody.addEventListener('click', function(e) {
            var cell = e.target.closest('.manage-nickname-cell');
            if (!cell) return;
            if (e.target.tagName === 'INPUT') return;
            if (e.target.closest('.qa-btn') || e.target.closest('.manage-name-tag')) return;
            e.stopPropagation();
            var tr = cell.closest('tr[data-acc-id]');
            if (!tr) return;
            self.activateNameEdit(cell, tr.getAttribute('data-acc-id'));
        });

        // 头像单元格点击：弹出头像预览（高清 + 编辑/移除）
        this.tbody.addEventListener('click', function(e) {
            var cell = e.target.closest('.manage-col-avatar');
            if (!cell) return;
            e.stopPropagation();
            var tr = cell.closest('tr[data-acc-id]');
            if (!tr) return;
            self.showAvatarDialog(tr.getAttribute('data-acc-id'));
        });

        // 行内悬浮操作按钮（容器委托）：名称单元格编辑结束会就地重建按钮，
        // 逐行绑定的话重建后的按钮就没有监听了 —— 所以统一委托到 tbody
        this.tbody.addEventListener('click', function(e) {
            var btn = e.target.closest('.qa-btn');
            if (!btn) return;
            e.stopPropagation();
            self.handleAction(btn.getAttribute('data-action'), btn.getAttribute('data-id'));
        });

        // 行悬浮整行高亮（JS 层覆盖列区域+右侧空白；mousemove 委托，匹配数据行与空表的空行）
        var scrollEl2 = this.el.querySelector('.acc-table-scroll');
        this.tbody.addEventListener('mousemove', function(e) {
            var tr = e.target.closest('tr');
            if (tr && tr.parentNode === self.tbody) {
                if (tr !== self._hoverRow) self._setHoverRow(tr);
            } else if (self._hoverRow) {
                self._setHoverRow(null);
            }
        });
        this.tbody.addEventListener('mouseleave', function() { self._setHoverRow(null); });
        scrollEl2.addEventListener('scroll', function() { self._updateRowHighlight(); });

        // 窗口大小变化时刷新表格宽度（列宽总和与容器宽的 max，保证横向滚动正确）
        window.addEventListener('resize', function() { self._updateTableWidth(); });
    };

    // ---- 整行背景层（hover / 选中） ----
    /** 整行宽度 = max(表格宽, 容器可视宽)：表格窄于容器时也要覆盖右侧空白 */
    AccountTable.prototype._rowBandWidth = function() {
        var scrollEl = this.el.querySelector('.acc-table-scroll');
        if (!scrollEl) return 0;
        return Math.max(this.tableEl.offsetWidth || 0, scrollEl.clientWidth || 0);
    };

    AccountTable.prototype._setHoverRow = function(row) {
        this._hoverRow = row;
        this._updateRowHighlight();
    };
    /** 悬浮层：仅非选中行显示（选中行保持选中色，不叠加悬浮色） */
    AccountTable.prototype._updateRowHighlight = function() {
        var h = this._rowHighlight;
        var scrollEl = this.el.querySelector('.acc-table-scroll');
        if (!h || !scrollEl) return;
        var row = this._hoverRow;
        if (!row || !row.isConnected || row.classList.contains('selected')) {
            h.classList.remove('active');
            return;
        }
        h.style.top = (row.offsetTop - scrollEl.scrollTop) + 'px';
        h.style.height = row.offsetHeight + 'px';
        h.style.width = this._rowBandWidth() + 'px';
        h.classList.add('active');
    };

    /** 选中层：每个选中行一个整行色块（覆盖列区域 + 右侧空白） */
    AccountTable.prototype._updateSelectionLayer = function() {
        var layer = this._selLayer;
        if (!layer) return;
        var rows = this.tbody.querySelectorAll('tr[data-acc-id].selected');
        if (rows.length === 0) {
            layer.innerHTML = '';
            return;
        }
        var width = this._rowBandWidth();
        var html = '';
        for (var i = 0; i < rows.length; i++) {
            html += '<div class="acc-row-sel" style="top:' + rows[i].offsetTop + 'px;height:' +
                rows[i].offsetHeight + 'px;width:' + width + 'px;"></div>';
        }
        layer.innerHTML = html;
    };

    // ---- 标题行：选中计数与批量按钮 ----
    AccountTable.prototype._updateSelectionUI = function() {
        var count = this.selectedIds.size;
        if (count > 0) {
            this.countEl.style.display = '';
            this.batchEl.style.display = '';
            if (this.cancelEl) this.cancelEl.style.display = '';
            this.countEl.textContent = '已选 ' + count + ' 项';
            // 隐藏/显示合并按钮：默认"隐藏"，只有选中项**全是隐藏**时才变成"显示"
            var toggle = this.batchEl.querySelector('[data-batch="toggle-hidden"]');
            if (toggle) toggle.textContent = this._allSelectedHidden() ? '显示' : '隐藏';
        } else {
            this.countEl.style.display = 'none';
            this.batchEl.style.display = 'none';
            if (this.cancelEl) this.cancelEl.style.display = 'none';
        }
        this._updateSelectionLayer();
        this._updateRowHighlight();
    };

    /** 选中的账号是否**全部**处于隐藏状态（决定合并按钮显示"隐藏"还是"显示"） */
    AccountTable.prototype._allSelectedHidden = function() {
        if (this.selectedIds.size === 0) return false;
        var self = this;
        var all = true;
        this.selectedIds.forEach(function(id) {
            var acc = self.accountData.find(function(a) { return a.id === id; });
            if (!acc || !acc.hidden) all = false;
        });
        return all;
    };

    AccountTable.prototype.batchAction = function(action) {
        if (action === 'cancel') {            // 取消多选
            this._clearSelectionLight();
            return;
        }
        if (this.selectedIds.size === 0) return;
        var count = this.selectedIds.size;
        var swId = this.getSwId();
        if (!swId) return;
        var self = this;
        var ids = Array.from(this.selectedIds);

        if (action === 'toggle-hidden') {
            // 全是隐藏 → 显示；否则 → 隐藏（与按钮文案同一判据，不会各说各话）
            var target = !this._allSelectedHidden();
            ids.forEach(function(id) {
                var acc = self.accountData.find(function(a) { return a.id === id; });
                if (acc) acc.hidden = target;
                JFC.bridge.saveAccount(swId, id, JSON.stringify({ hidden: target }));
            });
            this.selectedIds.clear();
            this.render();
            this._updateSelectionUI();
        } else if (action === 'reset') {
            JFC.modal.confirm({
                title: '重置账号记录',
                message: '将清空选中的 ' + count + ' 个账号在记录中的备注、快捷键、隐藏状态等个性化数据；'
                    + '账号本身不受影响，重置后名称会回退到自动识别的结果。',
                okText: '重置'
            }, function(ok) {
                if (!ok) return;
                ids.forEach(function(id) { JFC.bridge.resetAccount(swId, id); });
                self.selectedIds.clear();
                // 重置会同时改掉名称/隐藏/关联账号等一批字段 → 整表重载（单一数据来源）
                if (self.reloadAccounts) self.reloadAccounts();
                else { self.render(); self._updateSelectionUI(); }
            });
        } else if (action === 'delete') {
            // 批量删除：**确认框照常弹**（弹窗里说明"正常账号不能删、会被跳过"），
            // 用户仍可确认；真正删除时只对**失效账号**动手，正常账号（磁盘上还在）一律不作为。
            // 为什么不直接静默不响应：那样用户会疑惑"为啥点不了"（用户 2026-10-05 指正）。
            var invalidIds = ids.filter(function(id) {
                var a = self.accountData.find(function(x) { return x.id === id; });
                return !!(a && a.invalid);
            });
            var skipped = ids.length - invalidIds.length;
            var message;
            if (invalidIds.length === 0) {
                message = '选中的 ' + ids.length + ' 个账号都是正常账号（磁盘上仍然存在），正常账号无法删除；'
                    + '点击删除不会有任何改动。';
            } else if (skipped > 0) {
                message = '选中的 ' + ids.length + ' 个账号里，有 ' + skipped + ' 个是正常账号（磁盘上仍然存在）——'
                    + '正常账号无法删除、将被跳过；实际只会删除其中 ' + invalidIds.length + ' 条失效账号记录，'
                    + '并清除它们在数据目录里的头像文件。此操作不可撤销。';
            } else {
                message = '将删除选中的 ' + invalidIds.length + ' 条失效账号记录（磁盘上已不存在的账号），'
                    + '同时清除它们在数据目录里的头像文件。此操作不可撤销。';
            }
            JFC.modal.confirm({
                title: '删除账号记录',
                message: message,
                okText: '删除',
                danger: true
            }, function(ok) {
                if (!ok) return;
                if (!invalidIds.length) return;      // 没有可删的 → 不作为（配置与文件都不动）
                invalidIds.forEach(function(id) { JFC.bridge.deleteAccount(swId, id); });
                self.accountData = self.accountData.filter(function(a) { return invalidIds.indexOf(a.id) === -1; });
                invalidIds.forEach(function(id) { self.selectedIds.delete(id); });
                self.render();
                self._updateSelectionUI();
            });
        }
    };

    // ---- 行操作（悬浮按钮/行右键菜单共用） ----
    AccountTable.prototype.handleAction = function(action, accountId) {
        var swId = this.getSwId();
        if (!swId) return;
        var self = this;
        var acc = this.accountData.find(function(a) { return a.id === accountId; });

        if (action === 'toggle-hidden') {
            if (acc) {
                acc.hidden = !acc.hidden;
                JFC.bridge.saveAccount(swId, accountId, JSON.stringify({ hidden: acc.hidden }));
                // 整表重渲染：隐藏状态变化会改变置底顺序 + 名称右侧的"隐藏"标签
                this.render();
                this._updateSelectionUI();
                // 不再往平台标题区打"已隐藏/已显示"通知：行上已有"隐藏"标签 + 按钮文案变化，足够可见
            }
        } else if (action === 'reset') {
            var label = acc ? (acc.display_name || accountId) : accountId;
            JFC.modal.confirm({
                title: '重置账号记录',
                message: '将清空账号「' + label + '」在记录中的备注、快捷键、隐藏状态等个性化数据；'
                    + '账号本身不受影响，重置后名称会回退到自动识别的结果。',
                okText: '重置'
            }, function(ok) {
                if (!ok) return;
                JFC.bridge.resetAccount(swId, accountId);
                self.selectedIds.delete(accountId);
                if (self.reloadAccounts) self.reloadAccounts();
                else { self.render(); self._updateSelectionUI(); }
            });
        } else if (action === 'delete') {
            var label2 = acc ? (acc.display_name || accountId) : accountId;
            JFC.modal.confirm({
                title: '删除失效账号记录',
                message: '将删除失效账号「' + label2 + '」的记录，此操作不可撤销。',
                okText: '删除',
                danger: true
            }, function(ok) {
                if (!ok) return;
                var result = JFC.bridge.deleteAccount(swId, accountId);
                if (result && result.success) {
                    self.accountData = self.accountData.filter(function(a) { return a.id !== accountId; });
                    self.selectedIds.delete(accountId);
                    self.render();
                    self._updateSelectionUI();
                }
            });
        }
    };

    // ---- 事件驱动：Java 推送账号数据变更，定向更新单行/格 ----
    AccountTable.prototype.onAccountChanged = function(p) {
        if (!p || !p.accountId) return;
        var row = this.tbody.querySelector('tr[data-acc-id="' + p.accountId + '"]');
        if (!row) return;
        var ch = p.changed || {};
        var acc = this.accountData.find(function(a) { return a.id === p.accountId; });
        if (!acc) return;

        if (ch.hidden !== undefined) acc.hidden = ch.hidden;
        if (ch.disabled !== undefined) acc.disabled = ch.disabled;
        if (ch.hidden !== undefined || ch.disabled !== undefined) {
            this._updateRowQuickActions(row, acc);
        }
        if (ch.display_name !== undefined) {
            acc.display_name = ch.display_name;
            var nc = row.querySelector('.manage-nickname-cell .dn-text');
            if (nc) nc.innerHTML = scriptSplitHtml(ch.display_name);   // 分段字体，不能用 textContent
        }
        if (ch.avatar_url !== undefined) {
            acc.avatar_url = ch.avatar_url;
            this._updateAvatarCell(p.accountId, ch.avatar_url);
        }
        if (ch.hotkey !== undefined) {
            acc.hotkey = ch.hotkey || '';
            var hc = row.querySelector('.manage-hotkey-cell');
            if (hc && hc.getAttribute('data-editing') !== '1') {
                hc.innerHTML = acc.hotkey
                    ? '<span class="hotkey-text">' + escapeHtml(acc.hotkey) + '</span>'
                    : '<span class="hotkey-text"><span class="hotkey-placeholder">—</span></span>';
            }
        }
        // 通用字段（alias/nickname/其它文本列）
        Object.keys(ch).forEach(function(key) {
            if (acc[key] !== undefined && ['hidden', 'disabled', 'display_name', 'avatar_url', 'hotkey'].indexOf(key) === -1) {
                acc[key] = ch[key] === null || ch[key] === undefined ? '' : ch[key];
                var cell = row.querySelector('td[data-col="' + key + '"]');
                if (cell) {
                    cell.textContent = acc[key];
                    cell.title = acc[key];
                }
            }
        });
    };

    AccountTable.prototype._updateRowQuickActions = function(row, acc) {
        if (!row || !acc) return;
        var btn = row.querySelector('.qa-btn[data-action="toggle-hidden"]');
        if (btn) {
            btn.classList.toggle('on', !!acc.hidden);
            btn.textContent = acc.hidden ? '显示' : '隐藏';
            btn.title = acc.hidden ? '显示账号' : '隐藏账号';
        }
        // 名称前缀标签整组重画（失效/禁用/隐藏，固定顺序）
        var inner = row.querySelector('.manage-nickname-inner');
        if (inner) {
            inner.querySelectorAll('.manage-name-tag').forEach(function(t) { t.remove(); });
            var tags = renderNameTags(acc);
            if (tags) inner.insertAdjacentHTML('afterbegin', tags);
        }
    };

    AccountTable.prototype._updateAvatarCell = function(accountId, dataUrl) {
        var self = this;
        var rows = this.tbody.rows;
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].getAttribute('data-acc-id') !== accountId) continue;
            var avatarBox = rows[i].querySelector('.manage-col-avatar .manage-account-avatar');
            if (!avatarBox) break;
            var acc = this.accountData.find(function(a) { return a.id === accountId; });
            var label = this._avatarFallbackLabel(acc ? (acc.display_name || acc.nickname || acc.id) : accountId);

            if (!dataUrl) {
                // 没有头像了（例如刚被移除）→ 直接画文字兜底，**不要**留一个空 <img>
                avatarBox.innerHTML = this._avatarPlaceholderHtml(label);
                break;
            }
            var isFallback = dataUrl.indexOf('image/svg') !== -1;
            var cur = avatarBox.querySelector('img');
            var curSrc = cur ? (cur.getAttribute('src') || '') : '';
            // 已经有"真实头像"（非空、非文字兜底）时，不要用文字兜底把它盖掉
            if (isFallback && curSrc && curSrc.indexOf('image/svg') === -1) break;
            avatarBox.innerHTML = '<img src="' + escapeAttr(dataUrl) + '" alt="" onerror="this.parentElement.innerHTML=\'' +
                this._avatarPlaceholderHtml(label) + '\';">';
            break;
        }
    };

    /**
     * 头像文字兜底取什么字.
     * 账号表（`avatarFallbackTail`）= **名称末尾 4 个字符宽**（中文算 2 宽，与 Java 侧 `AvatarUtils.textAvatarLabel` 同一规则）；
     * 其它表（程序图标等）保持首字符。
     */
    AccountTable.prototype._avatarFallbackLabel = function(displayName) {
        var name = displayName || '';
        if (!name) return '?';
        if (this.avatarFallbackTail && JFC.text) return JFC.text.tailUnits(name, 4);
        return name.charAt(0).toUpperCase();
    };

    /** 文字头像占位 HTML：class **不加引号**（这段 HTML 会被塞进 onerror="…" 属性里） */
    AccountTable.prototype._avatarPlaceholderHtml = function(label) {
        var units = JFC.text ? JFC.text.visualUnits(label) : String(label).length;
        var cls = units >= 3 ? 'manage-avatar-placeholder-wide' : 'manage-avatar-placeholder';
        return '<span class=' + cls + '>' + escapeHtml(label) + '</span>';
    };

    // ---- 列间竖线：拖拽调整列宽 ----
    AccountTable.prototype._initColResizers = function(table) {
        if (!table) return;
        table.querySelectorAll('.col-resizer').forEach(function(r) { r.remove(); });
        var ths = table.querySelectorAll('thead th[data-col]');
        // 所有可见的非固定列都注入竖线（含最右列，可调整其宽度）
        for (var i = 0; i < ths.length; i++) {
            var col = this.colByKey(ths[i].getAttribute('data-col'));
            if (!col || col.fixed || !this.colVisible[col.key]) continue;
            var th = ths[i];
            var rz = document.createElement('div');
            rz.className = 'col-resizer';
            rz.setAttribute('data-col', col.key);
            (function(self, rz) {
                rz.addEventListener('mousedown', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    activeTable = self;   // 拖拽期间 _onResizeMove/_onResizeEnd 需要知道所属表
                    self._startResize(e.clientX, rz.getAttribute('data-col'));
                });
            })(this, rz);
            th.appendChild(rz);
        }
    };

    AccountTable.prototype._startResize = function(startX, key) {
        this.resizeState = { key: key, startX: startX, startWidth: this.colWidth[key] || 0 };
        document.body.classList.add('resizing-cols');
        document.addEventListener('mousemove', this._onResizeMove);
        document.addEventListener('mouseup', this._onResizeEnd);
    };

    AccountTable.prototype._onResizeMove = function(e) {
        var t = activeTable;  // 拖拽中的表（打开菜单时设置，这里直接取当前）
        if (!t || !t.resizeState) return;
        // 取整：避免小数宽度让"列宽总和 + 占位列"恰好超出容器 1px 而冒出横向滚动条
        var w = Math.max(30, Math.round(t.resizeState.startWidth + (e.clientX - t.resizeState.startX)));
        t.colWidth[t.resizeState.key] = w;
        t._applyColumnWidth(t.resizeState.key, w);
    };

    AccountTable.prototype._onResizeEnd = function() {
        var t = activeTable;
        if (!t || !t.resizeState) return;
        t._saveColumnPrefs();
        t.resizeState = null;
        document.body.classList.remove('resizing-cols');
        document.removeEventListener('mousemove', t._onResizeMove);
        document.removeEventListener('mouseup', t._onResizeEnd);
    };

    AccountTable.prototype._applyColumnWidth = function(key, w) {
        var col = this.tableEl.querySelector('colgroup col[data-col="' + key + '"]');
        if (col) col.style.width = w + 'px';
        this._updateTableWidth();   // 列宽变化 → 表格总宽随之扩展/收缩
    };

    // ---- 列头右键菜单 ----
    AccountTable.prototype._showColMenu = function(x, y, colKey) {
        var menu = colMenuEl();
        if (!menu) return;
        activeTable = this;

        var html = '<div class="acm-title">显示列</div>';
        this.columns.forEach(function(col) {
            var checked = this.colVisible[col.key] ? ' checked' : '';
            var locked = col.mandatory ? ' disabled' : '';
            // 固定列（勾选框/头像）虽必显，但可让用户自行理解；仅 mandatory 锁定
            html += '<div class="acm-item' + locked + '" data-col-toggle="' + col.key + '">' +
                '<input type="checkbox" class="acm-checkbox"' + checked + locked + '>' +
                '<span class="acm-label">' + escapeHtml(col.label) + '</span>' +
                '</div>';
        }, this);
        html += '<div class="acm-sep"></div>';
        html += '<div class="acm-item" data-col-fit="all"><span class="acm-label">所有列调至合适宽度</span></div>';
        // 占位列 / 表格外空白：不提供"该列"项（占位列没有宽度概念，宽度由容器剩余空间决定）
        var clickedCol = colKey ? this.colByKey(colKey) : null;
        if (clickedCol) {
            if (!clickedCol.fixed && this.colVisible[clickedCol.key]) {
                html += '<div class="acm-item" data-col-fit="' + clickedCol.key + '"><span class="acm-label">该列调至合适宽度</span></div>';
            } else {
                html += '<div class="acm-item disabled" data-col-fit=""><span class="acm-label">该列调至合适宽度</span></div>';
            }
        }
        menu.innerHTML = html;
        menu.style.display = 'block';
        positionMenu(menu, x, y);

        menu.querySelectorAll('.acm-item[data-col-toggle]').forEach(function(item) {
            var key = item.getAttribute('data-col-toggle');
            if (item.classList.contains('disabled')) return;
            var cb = item.querySelector('input');
            cb.addEventListener('change', function() {
                this.colVisible[key] = cb.checked;
                this._saveColumnPrefs();
                this._applyColumnLayout();
            }.bind(this));
            item.addEventListener('click', function(e) {
                if (e.target !== cb) {
                    cb.checked = !cb.checked;
                    this.colVisible[key] = cb.checked;
                    this._saveColumnPrefs();
                    this._applyColumnLayout();
                }
            }.bind(this));
        }, this);
        menu.querySelectorAll('.acm-item[data-col-fit]').forEach(function(item) {
            item.addEventListener('click', function() {
                var target = item.getAttribute('data-col-fit');   // this 被 bind 为表实例，从 item 取属性
                closeColMenu();
                if (target === 'all') this.fitAllColumns();
                else if (target) this.fitColumn(target);
            }.bind(this));
        }, this);
    };

    // ---- 行右键菜单 ----
    AccountTable.prototype._showRowMenu = function(x, y, accountId) {
        var menu = rowMenuEl();
        if (!menu) return;
        activeTable = this;
        var acc = this.accountData.find(function(a) { return a.id === accountId; });
        var hidden = !!(acc && acc.hidden);
        // 三项齐全（隐藏 / 重置 / 删除）；**不能做的操作显示为禁用**而不是隐藏。
        // 规则：删除只对失效账号可用（正常账号磁盘上还在，删了也会重新出现）；隐藏/重置对所有账号都可用。
        var canDelete = !!(acc && acc.invalid);
        var html = '<div class="acm-title">' + escapeHtml(accountId) + '</div>' +
            '<div class="acm-item" data-row-action="toggle-hidden">' + (hidden ? '显示' : '隐藏') + '</div>' +
            '<div class="acm-item" data-row-action="reset">重置</div>' +
            (canDelete
                ? '<div class="acm-item danger" data-row-action="delete">删除</div>'
                : '<div class="acm-item danger disabled" data-row-action="delete" title="正常账号（磁盘上仍然存在）无法删除">删除</div>');
        menu.innerHTML = html;
        menu.style.display = 'block';
        positionMenu(menu, x, y);

        menu.querySelectorAll('.acm-item[data-row-action]').forEach(function(item) {
            item.addEventListener('click', function() {
                if (this.classList.contains('disabled')) return;   // 禁用项点不动
                var action = this.getAttribute('data-row-action');
                closeRowMenu();
                activeTable.handleAction(action, accountId);
            });
        });
    };

    // ---- 列宽调至合适宽度 ----

    // 展示名列右端悬浮按钮（隐藏/显示 + 重置 [+ 删除]）的占位总宽估算：
    // 3 个按钮（失效账号行：隐藏/显示 + 重置 + 删除）时的总宽，各按钮 2 字 + padding + border + gap
    var QUICK_ACTIONS_WIDTH = 144;

    AccountTable.prototype.fitColumn = function(key) {
        var col = this.colByKey(key);
        if (!col || col.fixed) return;   // 固定列不参与
        var table = this.tableEl;

        // 1. 内容最大宽度（列头文字 + 全部数据单元格），无上限
        var maxW = 0;
        table.querySelectorAll('thead th[data-col="' + key + '"], tbody td[data-col="' + key + '"]').forEach(function(cell) {
            if (cell.classList.contains('hidden-col')) return;
            var cs = window.getComputedStyle(cell);
            var pad = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
            // 名称列：只量名称（.dn-text）+"禁用/失效/隐藏"前缀标签，不量悬浮操作按钮的按钮文字
            var text = '';
            cell.querySelectorAll('.dn-text, .manage-name-tag').forEach(function(sp) { text += sp.textContent; });
            if (!text) text = cell.innerText || cell.textContent || '';
            text = text.replace(/\s+/g, ' ').trim();
            var w = measureTextWidth(text, cs.fontFamily, cs.fontSize, cs.fontWeight) + pad;
            if (w > maxW) maxW = w;
        });

        // 名称列：悬浮按钮常驻占位（仅 visibility 切换）→ 合适宽度 = 名称宽 + 按钮预留宽
        // （原生程序表没有悬浮按钮 → 不预留）
        if (key === 'display_name' && this.showRowActions) maxW += QUICK_ACTIONS_WIDTH;

        // 2. 下限：列名宽度 + 余量；展示名列特殊 = 4 字符宽 + 按钮占位总宽 + 余量
        var th = table.querySelector('thead th[data-col="' + key + '"]');
        var minW = 0;
        if (th) {
            var thCs = window.getComputedStyle(th);
            if (key === 'display_name') {
                var fourChars = measureTextWidth('四字姓名', thCs.fontFamily, thCs.fontSize, thCs.fontWeight);
                minW = fourChars + (this.showRowActions ? QUICK_ACTIONS_WIDTH : 0) + 8;
            } else {
                var thText = th.innerText.replace(/\s+/g, ' ').trim() || '';
                var thPad = (parseFloat(thCs.paddingLeft) || 0) + (parseFloat(thCs.paddingRight) || 0);
                minW = measureTextWidth(thText, thCs.fontFamily, thCs.fontSize, thCs.fontWeight) + thPad + 8;
            }
        }

        var w = Math.max(Math.round(maxW) + 4, Math.round(minW));
        this.colWidth[key] = w;
        this._applyColumnWidth(key, w);
        this._saveColumnPrefs();
    };

    AccountTable.prototype.fitAllColumns = function() {
        var self = this;
        this.columns.forEach(function(col) {
            if (self.colVisible[col.key] && !col.fixed) self.fitColumn(col.key);
        });
    };

    // ---- 快捷键列：点击激活输入框（按下预览，**松手即确认**） ----
    /**
     * 快捷键录入（用户 2026-10-05 定的规则）：
     * · 按下时实时预览，**所有键松开的那一刻即确认并退出输入框**
     * · 松手时若只有修饰键（如 Alt+Shift），或普通字符多于一个（如 Alt+A+B）→ 视为无效，
     *   **恢复原本的快捷键**（不保存、不丢值）
     * · 按了 Backspace → 清空快捷键并退出
     * · Esc → 放弃修改；点击格外 → 同样放弃
     *
     * <p>为什么改掉"点别处才提交"：那时点击别处若顺手选中了某些行，触发整表重渲染，
     * 还没提交的录入就跟着 DOM 一起没了 —— 录入丢失的根因。
     */
    AccountTable.prototype.activateHotkeyEdit = function(cell, accountId) {
        if (!this.enableHotkey) return;
        var acc = this.accountData.find(function(a) { return a.id === accountId; });
        var current = (acc && acc.hotkey) ? acc.hotkey : '';
        var self = this;

        // 进入编辑态 → 清空多选（"编辑某个格子"和"多选批量"是两种操作意图）；同时结束上一个编辑
        this._clearSelectionLight();
        if (this._editFinish) this._editFinish();

        this.hotkeyEditAccountId = accountId;
        cell.setAttribute('data-editing', '1');
        JFC.bridge.notifyHotkeyCapture(true);

        cell.innerHTML = '<input type="text" class="hotkey-input" value="' + escapeAttr(current) +
            '" placeholder="按下快捷键…" spellcheck="false">';
        var input = cell.querySelector('input');
        input.focus();
        input.select();

        var held = {};           // 当前按住的键（keyCode → true）
        var normalCodes = [];    // 本次录入按下的"普通键"（非修饰键，按按下顺序）
        var normalMods = null;   // 第一个普通键按下时的修饰键集合（决定组合写法，如 Alt+A）
        var backspace = false;   // 是否按过 Backspace（= 清空）
        var done = false;

        /** 幂等收尾：只清状态与监听，**不动单元格 DOM** */
        function endEdit() {
            if (done) return;
            done = true;
            document.removeEventListener('mousedown', docMousedown);
            document.removeEventListener('keyup', onKeyUp, true);
            if (self._editFinish === cancelEdit) self._editFinish = null;
            if (self.hotkeyEditAccountId === accountId) self.hotkeyEditAccountId = null;
            JFC.bridge.notifyHotkeyCapture(false);
            cell.removeAttribute('data-editing');
        }
        /**
         * 结束编辑并**还原单元格**——这是对外的统一入口（`_editFinish`）.
         * 必须还原 DOM：否则开新编辑时旧格子只是状态结束、输入框还留在页面上（用户实测：点过的格子全留在编辑态）。
         */
        function cancelEdit() {
            endEdit();
            if (acc) acc.hotkey = current;
            self._renderHotkeyCell(cell, accountId, current);
        }
        /** 保存并退出（val='' 表示清空快捷键） */
        function commit(val) {
            endEdit();
            if (acc) acc.hotkey = val;
            self._renderHotkeyCell(cell, accountId, val);
            if (val !== current) {
                // 保存延后一拍：本函数可能是在 mousedown 阶段被调用，同步做桥调用会挡住这一下点击
                setTimeout(function() {
                    if (!self.getSwId()) return;
                    if (self.saveHotkey) {
                        self.saveHotkey(accountId, val);          // 原生程序表：存平台配置
                    } else {
                        JFC.bridge.saveAccount(self.getSwId(), accountId, JSON.stringify({ hotkey: val }));
                    }
                }, 0);
            }
        }

        function refreshPreview(ev) {
            var mods = JFC.keys.modifiersOf(ev);
            input.value = mods.concat(normalCodes.map(function(c) {
                return JFC.keys.nameOfCode(c);
            })).join('+');
        }

        function onKeyDown(ev) {
            var code = JFC.keys.keyCodeOf(ev);
            if (code === 27) { ev.preventDefault(); ev.stopPropagation(); cancelEdit(); return; }   // Esc：放弃
            if (code === 13) { ev.preventDefault(); ev.stopPropagation(); return; }                 // Enter 不是热键，忽略
            ev.preventDefault();
            ev.stopPropagation();

            held[code] = true;
            if (code === 8) {                        // Backspace：清空（松手时提交）
                backspace = true;
                input.value = '';
                return;
            }
            if (JFC.keys.isModifierOnly(ev)) {       // 纯修饰键：只更新预览
                refreshPreview(ev);
                return;
            }
            // 普通键（A-Z / 0-9 / F 键 / 标点 / 空格 / Tab…）：只记录，等松手统一判定
            if (normalCodes.indexOf(code) === -1) {
                if (normalCodes.length === 0) normalMods = JFC.keys.modifiersOf(ev);
                normalCodes.push(code);
            }
            refreshPreview(ev);
        }

        function onKeyUp(ev) {
            delete held[JFC.keys.keyCodeOf(ev)];
            if (Object.keys(held).length > 0) { refreshPreview(ev); return; }   // 还有键按着：继续等

            // 所有键都松开了 —— 这一刻就是"确认时机"
            if (backspace) { commit(''); return; }
            if (normalCodes.length === 1) {
                commit((normalMods || []).concat([JFC.keys.nameOfCode(normalCodes[0])]).join('+'));
                return;
            }
            cancelEdit();   // 只有修饰键 / 普通键多于一个 → 无效，恢复原值
        }

        function docMousedown(ev) {
            // 用 contains 判断"点的是不是编辑格内部"。
            // **不能用 closest(cell)**：closest 只接受选择器字符串，传元素会抛 SyntaxError，
            // 整个"点框外结束编辑"的处理会从这一行静默失效（实测踩过）。
            if (ev.target && cell.contains(ev.target)) return;
            // 这一下点击只用于"结束编辑"：不要再顺手把行选中（用户要求）
            self._suppressRowSelectOnce();
            cancelEdit();
        }

        input.addEventListener('keydown', onKeyDown);
        // keyup 挂在 document 且用捕获：松键哪怕落在输入框外（或输入框已被重建）也一定收得到
        document.addEventListener('keyup', onKeyUp, true);
        document.addEventListener('mousedown', docMousedown);
        this._editFinish = cancelEdit;
        // 注意：这里**不要**再给 cell 挂 click-stopPropagation。
        // 单元格元素在"只重建本格"的情况下会一直存活，挂上去的监听会逐次累积，
        // 同一个单元格第二次点击就被自己 stopPropagation 掉（tbody 的委托收不到）→ 表现为"点了没反应"。
        // 点击输入框不会重新进入编辑，靠的是委托处理里的 `e.target.tagName === 'INPUT'` 判断。
    };

    // ---- 名称列：点击激活输入框（编辑备注 remark） ----
    /**
     * 名称单元格点击 → 就地编辑备注（交互与快捷键列同款）.
     *
     * <p>输入框预填当前 remark；**输入框为空时用灰色 placeholder 显示"不填会显示什么"**——
     * 取自行数据里的 {@code display_name_auto}（名称回退链去掉 remark 的结果），
     * 所以用户按空回车前看到的提示，与提交后真正显示的名称完全一致（同一份推导结果，不是另写一套规则）。
     *
     * <p>Enter / 点击格外交付，Esc 取消；空白提交 = 清空备注 → 名称回退到自动识别结果。
     */
    AccountTable.prototype.activateNameEdit = function(cell, accountId) {
        var acc = this.accountData.find(function(a) { return a.id === accountId; });
        if (!acc) return;
        var current = acc.remark || '';
        var auto = acc.display_name_auto || acc.display_name || accountId;
        var self = this;

        // 进入编辑态 → 清空多选（"编辑某个格子"和"多选批量"是两种操作意图，混在一起容易误批量）
        this._clearSelectionLight();
        if (this._editFinish) this._editFinish();   // 同时只允许一个编辑（会把上一个格子还原）

        this.nameEditAccountId = accountId;
        cell.setAttribute('data-editing', '1');
        // 回到 <input>：contenteditable 在 JavaFX WebView 里实测**没法正常输入/修改**（用户实测反馈），
        // 所以编辑态不追求"中英两种字体"，编辑框统一用等宽（见 CSS .name-input）。
        // 显示态仍然两种字体（.cjk-run/.lat-run）。
        cell.innerHTML = '<input type="text" class="name-input" value="' + escapeAttr(current) + '"' +
            ' placeholder="' + escapeAttr(auto) + '" title="留空则显示：' + escapeAttr(auto) + '" spellcheck="false">';
        var input = cell.querySelector('input');
        input.focus();
        input.select();

        var done = false;
        /** 幂等收尾：只清状态与监听，**不动单元格 DOM** */
        function endEdit() {
            if (done) return;
            done = true;
            document.removeEventListener('mousedown', docMousedown);
            if (self._editFinish === cancelEdit) self._editFinish = null;
            if (self.nameEditAccountId === accountId) self.nameEditAccountId = null;
            cell.removeAttribute('data-editing');
        }
        /** 结束并还原单元格（Esc / 开新编辑时走这里）—— 对外统一入口，绝不留输入框在页面上 */
        function cancelEdit() {
            endEdit();
            self._renderNameCell(cell, accountId, acc);
        }
        /** 提交备注（Enter / 点击格外） */
        function commit() {
            var val = input.value.trim();
            endEdit();
            if (val === current) {                 // 没改：只还原
                self._renderNameCell(cell, accountId, acc);
                return;
            }
            acc.remark = val;
            acc.display_name = val || auto;        // 与行渲染同一规则（remark 为空 → 自动名称）
            // 先就地还原这一格（同步、只动本格 DOM）
            self._renderNameCell(cell, accountId, acc);
            // **保存与整表重排延后一拍**：本函数可能是在 document 的 mousedown 阶段被调用的，
            // 若此刻重建 tbody，用户这一下点击所在的元素会被换掉 → 后续 click 落空
            //（实测症状：点到别处没反应、要点第二次）
            setTimeout(function() {
                if (self.getSwId()) {
                    JFC.bridge.saveAccount(self.getSwId(), accountId, JSON.stringify({ remark: val }));
                }
                self.render();                 // 名称是默认排序列 → 行位置可能变，需重排
                self._updateSelectionUI();
            }, 0);
        }
        // 点击单元格外部 → 提交（mousedown 阶段处理，避免 blur 与 click 的 DOM 竞态）
        function docMousedown(ev) {
            // 同快捷键列：必须用 contains，不能用 closest(cell)（传元素会抛 SyntaxError）
            if (ev.target && cell.contains(ev.target)) return;
            // 这一下点击只用于"结束编辑"：不要再顺手把行选中（用户要求）
            self._suppressRowSelectOnce();
            commit();
        }
        document.addEventListener('mousedown', docMousedown);
        this._editFinish = cancelEdit;

        input.addEventListener('keydown', function(ev) {
            var code = JFC.keys.keyCodeOf(ev);
            if (code === 27) { ev.preventDefault(); ev.stopPropagation(); cancelEdit(); return; }   // Esc：放弃修改
            if (code === 13) { ev.preventDefault(); ev.stopPropagation(); commit(); return; }       // Enter：提交
            ev.stopPropagation();   // 普通输入放行；只要别冒泡去触发行选中
        });
        // 同样不挂 cell 级 click-stopPropagation（原因见 activateHotkeyEdit 末尾注释）
    };

    AccountTable.prototype._renderNameCell = function(cell, accountId, acc) {
        if (!cell || !acc) return;
        cell.innerHTML = nameCellInnerHtml(acc, acc.display_name || acc.nickname || accountId, !!acc.invalid, this.showRowActions);
    };

    /**
     * 清空多选（**轻量**：不重建表格 DOM）.
     *
     * <p>进入单元格编辑态前必须清空多选，但不能整表重渲染 —— 调用方手里还拿着"要变成输入框的那个单元格"，
     * 一旦重建，那个格子就成了脱离文档的旧节点（输入框挂在一个已经不在页面上的 td 里）。
     */
    AccountTable.prototype._clearSelectionLight = function() {
        if (this.selectedIds.size === 0) return;
        this.selectedIds.clear();
        this.tbody.querySelectorAll('tr.selected').forEach(function(tr) { tr.classList.remove('selected'); });
        this.tbody.querySelectorAll('input[type="checkbox"][data-acc-id]').forEach(function(cb) { cb.checked = false; });
        var all = this.el.querySelector('.acc-select-all');
        if (all) all.checked = false;
        this._updateSelectionUI();
    };

    /** 结束当前单元格编辑（快捷键列 / 名称列通用；幂等，且会把单元格还原） */
    /**
     * 头像单元格 → 弹出头像预览弹窗（大图 + 编辑 / 移除）.
     *
     * <p>弹窗展示的是当前头像 data URL 的**原图**（本地头像文件或已下载的网络头像，未做缩放），
     * 所以比列表里 32px 的缩略图清晰得多。
     *  · 「编辑」→ Java 侧弹文件选择器，把选中的图片转 JPEG 写入本地头像文件，返回新 data URL 就地刷新
     *  · 「✕」→ 删除本地头像文件（并清掉 avatar_url，避免又被网络头像覆盖），随后重新拉一次（回退到文字头像）
     */
    AccountTable.prototype.showAvatarDialog = function(accountId) {
        var self = this;
        var acc = this.accountData.find(function(a) { return a.id === accountId; });
        if (!acc) return;
        var swId = this.getSwId();
        var url = acc.avatar_data || acc.avatar_url || '';
        var title = acc.display_name || acc.name || accountId;

        var imgHtml = url
            ? '<img class="avatar-preview-img" src="' + escapeAttr(url) + '" alt="">'
            : '<div class="avatar-preview-empty">该账号还没有头像</div>';

        var dialog = JFC.modal.custom({
            title: title,
            center: true,          // 标题与按钮都居中（用户要求）
            bodyHtml: '<div class="avatar-preview">' + imgHtml + '</div>',
            actions: [
                {
                    text: '✎ 编辑', title: '选择本地图片作为头像', cls: '',
                    onClick: function() {
                        if (!swId) return true;
                        var r = JFC.bridge.pickAccAvatar(swId, accountId);
                        if (r && r.success && r.dataUrl) {
                            acc.avatar_data = r.dataUrl;
                            self.updateAvatar(accountId, r.dataUrl);
                        }
                        return true;   // 关闭弹窗
                    }
                },
                {
                    text: '✕ 移除', title: '移除本地头像文件', cls: 'danger',
                    onClick: function() {
                        if (!swId) return true;
                        var r = JFC.bridge.removeAccAvatar(swId, accountId);
                        if (r && r.success) {
                            // 本地文件没了：清缓存并重新拉一次（会回退到链接账号/网络头像/文字头像）
                            acc.avatar_data = '';
                            acc._avatarFetching = false;
                            self.updateAvatar(accountId, '');
                            if (JFC.pages && JFC.pages.main && JFC.pages.main.refreshAvatar) {
                                JFC.pages.main.refreshAvatar(swId, acc, self);
                            }
                        }
                        return true;
                    }
                }
            ]
        });
        return dialog;
    };

    AccountTable.prototype.cancelHotkeyEdit = function() {
        if (this._editFinish) this._editFinish();
    };

    /**
     * 标记"接下来这一下点击只用于结束编辑，不要再选中行".
     * 用**一次性**标记而不是时间窗：时间窗会把用户紧接着的下一次正常点击也吞掉；
     * 同时用 400ms 兜底清除，避免点击落在别的表格上时标记残留到很久之后。
     */
    AccountTable.prototype._suppressRowSelectOnce = function() {
        var self = this;
        this._suppressSelectOnce = true;
        clearTimeout(this._suppressSelectTimer);
        this._suppressSelectTimer = setTimeout(function() {
            self._suppressSelectOnce = false;
            self._suppressSelectTimer = null;
        }, 400);
    };

    AccountTable.prototype._renderHotkeyCell = function(cell, accountId, hotkey) {
        var acc = this.accountData.find(function(a) { return a.id === accountId; });
        if (acc) acc.hotkey = hotkey || '';
        cell.innerHTML = hotkey
            ? '<span class="hotkey-text">' + escapeHtml(hotkey) + '</span>'
            : '<span class="hotkey-text"><span class="hotkey-placeholder">—</span></span>';
    };

    // ---- Java Scene 捕获的组合键（兜底 WebView 漏掉的按键） ----
    AccountTable.prototype.onHotkeyCapture = function(combo) {
        if (!this.enableHotkey || !this.hotkeyEditAccountId) return;
        var row = this.tbody.querySelector('tr[data-acc-id="' + this.hotkeyEditAccountId + '"]');
        if (!row) return;
        var input = row.querySelector('.manage-hotkey-cell input.hotkey-input');
        if (input) input.value = combo;
    };

    // ---- 菜单关闭（组件间共用，main.js 也调用） ----
    function closeColMenu() {
        var menu = colMenuEl();
        if (menu) menu.style.display = 'none';
    }
    function closeRowMenu() {
        var menu = rowMenuEl();
        if (menu) menu.style.display = 'none';
    }
    function positionMenu(menu, x, y) {
        var rect = menu.getBoundingClientRect();
        var vw = window.innerWidth, vh = window.innerHeight;
        if (x + rect.width > vw - 4) x = vw - rect.width - 4;
        if (y + rect.height > vh - 4) y = vh - rect.height - 4;
        menu.style.left = Math.max(4, x) + 'px';
        menu.style.top = Math.max(4, y) + 'px';
    }

    // 文本测量（跨表复用）
    var _measureEl = null;
    function measureTextWidth(text, fontFamily, fontSize, fontWeight) {
        if (!_measureEl) {
            _measureEl = document.createElement('span');
            _measureEl.style.position = 'absolute';
            _measureEl.style.visibility = 'hidden';
            _measureEl.style.whiteSpace = 'pre';
            document.body.appendChild(_measureEl);
        }
        _measureEl.style.fontFamily = fontFamily || '';
        _measureEl.style.fontSize = fontSize || '';
        _measureEl.style.fontWeight = fontWeight || '';
        _measureEl.textContent = text || '';
        return _measureEl.offsetWidth;
    }

    /**
     * 强制同步布局：JavaFX WebView 布局惰性，内容变化后读取 offsetHeight 强制 WebKit 重算。
     */
    function forceReflow(el) {
        if (!el) return;
        void el.offsetHeight;
        void el.offsetWidth;
        setTimeout(function() { if (el.isConnected) { void el.offsetHeight; void el.offsetWidth; } }, 50);
    }

    /**
     * 自定义 overlay 滚动条（DOM 元素，absolute 定位不占位 → 不撑大容器高度）。
     * JavaFX WebView 的原生滚动条不可靠（纵向需手动触发才出现），
     * 这里用绝对定位细条替代：内容溢出时显示、可拖拽、非交互一段时间后自动隐形。
     *
     * 关键：滚动条挂载在滚动容器的【父级】（absolute 子元素会随滚动内容一起滚动，
     * 导致滚动条被内容带着跑），父级需 position:relative 且尺寸与容器对齐。
     *
     * @param container 滚动容器（overflow:auto）
     * @param axis      'x'=横向, 'y'=纵向
     * @return { update: function } 内容/尺寸变化后调用 update 刷新
     */
    function attachCustomScrollbar(container, axis) {
        if (!container) return { update: function() {} };
        // 滚动条宿主 = 容器的父级（避免随内容滚动）；无父级则退化为容器内
        var host = container.parentElement || container;
        var bar = document.createElement('div');
        bar.className = 'ct-scrollbar ' + (axis === 'x' ? 'ct-scrollbar-x' : 'ct-scrollbar-y');
        var thumb = document.createElement('div');
        thumb.className = 'ct-scrollbar-thumb';
        bar.appendChild(thumb);
        host.appendChild(bar);

        var isX = axis === 'x';
        var hideTimer = null;
        var hasOverflow = false;    // 内容是否溢出（是否需要滚动条）——显示的第一条件
        var onBar = false;          // 鼠标是否在滚动条上（在滚动条上不隐藏）

        // 显示（持续，不设自动隐藏——用于鼠标在滚动条上）
        function show() {
            bar.classList.add('visible');
            if (hideTimer) clearTimeout(hideTimer);
        }
        // 显示并 1.5s 后自动隐形（用于鼠标在内容区/滚动时）；内容不溢出则不显示
        function showTemporarily() {
            if (!hasOverflow) return;
            show();
            hideTimer = setTimeout(function() {
                if (!onBar) bar.classList.remove('visible');
            }, 1500);
        }
        // 延时隐藏：给鼠标从内容区移到滚动条上的时间
        function scheduleHide() {
            if (hideTimer) clearTimeout(hideTimer);
            hideTimer = setTimeout(function() { bar.classList.remove('visible'); }, 600);
        }
        function hide() {
            if (hideTimer) clearTimeout(hideTimer);
            bar.classList.remove('visible');
        }

        function update() {
            if (!container.isConnected) return;
            // 强制同步布局：JavaFX WebView 布局惰性，内容变化后 scrollHeight/clientHeight 可能未重算，
            // 必须读取 offset 尺寸触发重排（否则 hasOverflow 判断基于旧值，滚动条不出现）
            void container.offsetHeight;
            void container.offsetWidth;
            var cw = container.clientWidth, sw = container.scrollWidth;
            var ch = container.clientHeight, sh = container.scrollHeight;
            // 内容实际高度/宽度（JavaFX 对 height:auto+max-height 容器的 scrollHeight 可能不更新，用子元素实测）
            var realH = 0, realW = 0;
            for (var i = 0; i < container.children.length; i++) {
                var r = container.children[i].getBoundingClientRect();
                realH += r.height;
                if (r.width > realW) realW = r.width;
            }
            if (isX) {
                var canScroll = Math.max(sw, realW) > cw;
                hasOverflow = canScroll;
                if (canScroll) {
                    var trackW = bar.clientWidth;
                    if (trackW <= 0) { hide(); return; }   // 折叠/隐藏时轨道无尺寸，不计算
                    var thumbW = Math.max(20, trackW * cw / Math.max(sw, realW));
                    thumb.style.width = thumbW + 'px';
                    thumb.style.height = '100%';
                    thumb.style.left = (trackW - thumbW) * container.scrollLeft / (Math.max(sw, realW) - cw) + 'px';
                    thumb.style.top = '';
                    if (onBar) show(); else showTemporarily();
                } else {
                    hide();
                }
            } else {
                var canScrollV = Math.max(sh, realH) > ch;
                hasOverflow = canScrollV;
                if (canScrollV) {
                    var trackH = bar.clientHeight;
                    if (trackH <= 0) { hide(); return; }   // 折叠/隐藏时轨道无尺寸，不计算
                    var thumbH = Math.max(20, trackH * ch / Math.max(sh, realH));
                    thumb.style.height = thumbH + 'px';
                    thumb.style.width = '100%';
                    thumb.style.top = (trackH - thumbH) * container.scrollTop / (Math.max(sh, realH) - ch) + 'px';
                    thumb.style.left = '';
                    if (onBar) show(); else showTemporarily();
                } else {
                    hide();
                }
            }
        }

        // 显示条件 = 需要滚动条(hasOverflow) + 鼠标在内容区或滚动条上
        container.addEventListener('mouseenter', showTemporarily);
        container.addEventListener('mousemove', showTemporarily);
        container.addEventListener('mouseleave', scheduleHide);
        bar.addEventListener('mouseenter', function() { onBar = true; show(); });
        bar.addEventListener('mouseleave', function() { onBar = false; scheduleHide(); });
        container.addEventListener('scroll', update);
        window.addEventListener('resize', update);

        // rAF 检测滚动位置与内容尺寸变化（事件驱动、丝滑；JavaFX WebView scroll 事件可能不触发，作兜底）
        var lastPos = isX ? container.scrollLeft : container.scrollTop;
        var lastCw = container.clientWidth, lastSw = container.scrollWidth;
        var lastCh = container.clientHeight, lastSh = container.scrollHeight;
        function rafLoop() {
            if (!container.isConnected) return;
            var pos = isX ? container.scrollLeft : container.scrollTop;
            var cw = container.clientWidth, sw = container.scrollWidth;
            var ch = container.clientHeight, sh = container.scrollHeight;
            if (pos !== lastPos || cw !== lastCw || sw !== lastSw || ch !== lastCh || sh !== lastSh) {
                lastPos = pos; lastCw = cw; lastSw = sw; lastCh = ch; lastSh = sh;
                update();
            }
            requestAnimationFrame(rafLoop);
        }
        requestAnimationFrame(rafLoop);

        // 拖拽滚动条 → 滚动容器（滚动位置变化由轮询/scroll 事件驱动 update）
        var dragging = false, startPos = 0, startScroll = 0;
        thumb.addEventListener('mousedown', function(e) {
            e.preventDefault();
            e.stopPropagation();
            dragging = true;
            startPos = isX ? e.clientX : e.clientY;
            startScroll = isX ? container.scrollLeft : container.scrollTop;
            showTemporarily();
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
        function onMove(e) {
            if (!dragging) return;
            var pos = isX ? e.clientX : e.clientY;
            var delta = pos - startPos;
            var maxScroll = isX ? (container.scrollWidth - container.clientWidth)
                                : (container.scrollHeight - container.clientHeight);
            var maxTravel = isX ? (bar.clientWidth - thumb.clientWidth)
                                : (bar.clientHeight - thumb.clientHeight);
            if (maxTravel > 0 && maxScroll > 0) {
                if (isX) container.scrollLeft = startScroll + delta * maxScroll / maxTravel;
                else container.scrollTop = startScroll + delta * maxScroll / maxTravel;
                update();   // 拖拽中即时刷新 thumb 位置（不依赖 scroll 事件）
            }
        }
        function onUp() {
            dragging = false;
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
        }

        setTimeout(update, 0);
        return { update: update, bar: bar };
    }


    // 对外暴露
    AccountTable.closeMenus = function() { closeColMenu(); closeRowMenu(); activeTable = null; };
    AccountTable.getActiveTable = function() { return activeTable; };
    AccountTable.measureTextWidth = measureTextWidth;
    // overlay 自定义滚动条（供外部容器如账号区域使用）：attachScrollbar(container, 'y')
    AccountTable.attachScrollbar = attachCustomScrollbar;

    // 公开方法：外部路由调用
    AccountTable.prototype.updateAvatar = function(accountId, dataUrl) {
        this._updateAvatarCell(accountId, dataUrl);
    };
    AccountTable.prototype.clearSelection = function() {
        this.selectedIds.clear();
        this._updateSelectionUI();
    };
    AccountTable.prototype.getSelectedIds = function() { return this.selectedIds; };

    return AccountTable;
})();
