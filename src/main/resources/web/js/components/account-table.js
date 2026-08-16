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
        this.enableHotkey = !!opts.enableHotkey;
        this.accountData = [];
        this.selectedIds = new Set();
        this.sortField = opts.defaultSortField || '';
        this.sortAsc = true;
        this.colVisible = {};
        this.colWidth = {};
        this.resizeState = null;
        this.hotkeyEditAccountId = null;
        this._menuOpen = false;

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
                ? '<input type="checkbox" class="acc-select-all">'
                : (col.label || '');
            theadHtml += '<th class="' + cls + '" data-col="' + col.key + '"' + sortable + '>' +
                inner + '</th>';
        });

        el.innerHTML =
            '<div class="acc-table-titlebar">' +
                '<span class="acc-table-title"></span>' +
                '<span class="acc-table-meta">' +
                    '<span class="acc-table-count" style="display:none;">已选 0 项</span>' +
                    '<span class="acc-table-batch" style="display:none;">' +
                        '<button class="btn btn-sm" data-batch="hide">批量隐藏</button>' +
                        '<button class="btn btn-sm" data-batch="show">批量显示</button>' +
                        '<button class="btn btn-sm batch-danger" data-batch="delete">批量删除</button>' +
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
        this.tbody = el.querySelector('tbody');
        this.tableEl = el.querySelector('table');
        this.titleEl.textContent = this.title;
    };

    // ---- 列配置持久化（LocalGlobalConfig.json.account_columns.<id>） ----
    AccountTable.prototype._loadColumnPrefs = function() {
        var prefs = null;
        try {
            var cfg = JFC.bridge.getGlobalConfig();
            if (cfg && cfg.account_columns && cfg.account_columns[this.id]) {
                prefs = cfg.account_columns[this.id];
            }
        } catch (e) { /* 配置缺失时使用默认值 */ }
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
            var key = 'account_columns.' + this.id;
            var patch = {};
            patch[key] = { visible: visible, width: width };
            JFC.bridge.saveGlobalConfig(JSON.stringify(patch));
        } catch (e) { /* 保存失败不影响使用 */ }
    };

    AccountTable.prototype._applyColumnLayout = function() {
        var table = this.tableEl;
        if (!table) return;
        table.querySelectorAll('colgroup col[data-col]').forEach(function(col) {
            var key = col.getAttribute('data-col');
            col.style.width = (this.colWidth[key] || 0) + 'px';
        }, this);
        table.querySelectorAll('th[data-col], td[data-col]').forEach(function(cell) {
            var key = cell.getAttribute('data-col');
            cell.classList.toggle('hidden-col', !this.colVisible[key]);
        }, this);
        this._initColResizers(table);
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
            tbody.innerHTML = '<tr class="manage-empty-row"><td colspan="' + this.columns.length + '">' +
                '<div class="manage-empty-state">暂无数据</div></td></tr>';
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
                hidden: hidden, isSelected: isSelected
            });
        }, this);

        return '<tr data-acc-id="' + escapeAttr(id) + '" class="' + (isSelected ? 'selected' : '') + '">' +
            html + '</tr>';
    };

    AccountTable.prototype._cellHtml = function(acc, col, ctx) {
        var key = col.key;
        var id = ctx.id;

        if (key === 'check') {
            return '<td data-col="check" class="manage-col-check"><input type="checkbox"' +
                (ctx.isSelected ? ' checked' : '') + ' data-acc-id="' + escapeAttr(id) + '"></td>';
        }
        if (key === 'avatar') {
            var avatarHtml;
            if (ctx.avatarUrl) {
                avatarHtml = '<img src="' + escapeAttr(ctx.avatarUrl) + '" alt="" onerror="this.parentElement.innerHTML=\'<span class=manage-avatar-placeholder>' +
                    escapeHtml(ctx.displayName.charAt(0).toUpperCase()) + '</span>\';">';
            } else {
                avatarHtml = '<span class="manage-avatar-placeholder">' +
                    escapeHtml(ctx.displayName.charAt(0).toUpperCase()) + '</span>';
            }
            return '<td data-col="avatar" class="manage-col-avatar"><div class="manage-account-avatar">' +
                avatarHtml + '</div></td>';
        }
        if (key === 'display_name') {
            var quickActions = '<span class="manage-row-quick-actions">' +
                '<button class="qa-btn' + (ctx.hidden ? ' on' : '') + '" data-action="toggle-hidden" data-id="' + escapeAttr(id) + '"' +
                ' title="' + (ctx.hidden ? '取消隐藏' : '隐藏') + '">' + (ctx.hidden ? '已隐藏' : '隐藏') + '</button>' +
                '<button class="qa-btn danger" data-action="delete" data-id="' + escapeAttr(id) + '" title="删除账号">删除</button>' +
                '</span>';
            return '<td data-col="display_name" class="manage-nickname-cell">' +
                '<span class="dn-text">' + escapeHtml(ctx.displayName) + '</span>' +
                (acc.disabled ? '<span class="manage-disabled-tag">禁用</span>' : '') +
                quickActions + '</td>';
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
        return '<td data-col="' + key + '" class="' + textClass + '" title="' + escapeAttr(val) + '">' +
            escapeHtml(val) + '</td>';
    };

    // ---- 排序 ----
    AccountTable.prototype._sortAccounts = function(accounts) {
        var field = this.sortField;
        var asc = this.sortAsc;
        if (!field) return accounts.slice();
        return accounts.slice().sort(function(a, b) {
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

        // 行点击选中（排除勾选框/按钮/快捷键单元格）
        tbody.querySelectorAll('tr[data-acc-id]').forEach(function(row) {
            row.addEventListener('click', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON' ||
                    e.target.closest('.qa-btn') || e.target.closest('.manage-hotkey-cell')) return;
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

        // 悬浮操作按钮
        tbody.querySelectorAll('.qa-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                self.handleAction(this.getAttribute('data-action'), this.getAttribute('data-id'));
            });
        });

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

        // 列头右键菜单（显示列/自适应）
        this.tableEl.querySelector('thead').addEventListener('contextmenu', function(e) {
            e.preventDefault();
            var th = e.target.closest('th[data-col]');
            var colKey = th ? th.getAttribute('data-col') : null;
            closeRowMenu();
            self._showColMenu(e.clientX, e.clientY, colKey);
        });

        // 行右键菜单
        this.tbody.addEventListener('contextmenu', function(e) {
            var tr = e.target.closest('tr[data-acc-id]');
            if (!tr) return;
            e.preventDefault();
            closeColMenu();
            self._showRowMenu(e.clientX, e.clientY, tr.getAttribute('data-acc-id'));
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
    };

    // ---- 标题行：选中计数与批量按钮 ----
    AccountTable.prototype._updateSelectionUI = function() {
        var count = this.selectedIds.size;
        if (count > 0) {
            this.countEl.style.display = '';
            this.batchEl.style.display = '';
            this.countEl.textContent = '已选 ' + count + ' 项';
        } else {
            this.countEl.style.display = 'none';
            this.batchEl.style.display = 'none';
        }
    };

    AccountTable.prototype.batchAction = function(action) {
        if (this.selectedIds.size === 0) return;
        var count = this.selectedIds.size;
        var swId = this.getSwId();
        if (!swId) return;

        if (action === 'hide' || action === 'show') {
            var fields = { hidden: action === 'hide' };
            var self = this;
            this.selectedIds.forEach(function(id) {
                var acc = self.accountData.find(function(a) { return a.id === id; });
                if (acc) acc.hidden = fields.hidden;
                JFC.bridge.saveAccount(swId, id, JSON.stringify(fields));
            });
            this.selectedIds.clear();
            this.render();
            this._updateSelectionUI();
            flashTitle('已' + (action === 'hide' ? '隐藏' : '显示') + ' ' + count + ' 项');
        } else if (action === 'delete') {
            if (!confirm('确定要删除选中的 ' + count + ' 个账号吗？此操作不可撤销。')) return;
            var self2 = this;
            this.selectedIds.forEach(function(id) {
                JFC.bridge.deleteAccount(swId, id);
            });
            this.accountData = this.accountData.filter(function(a) { return !self2.selectedIds.has(a.id); });
            this.selectedIds.clear();
            this.render();
            this._updateSelectionUI();
            flashTitle('已删除 ' + count + ' 项');
        }
    };

    // ---- 行操作（悬浮按钮/行右键菜单共用） ----
    AccountTable.prototype.handleAction = function(action, accountId) {
        var swId = this.getSwId();
        if (!swId) return;

        if (action === 'toggle-hidden') {
            var acc = this.accountData.find(function(a) { return a.id === accountId; });
            if (acc) {
                acc.hidden = !acc.hidden;
                JFC.bridge.saveAccount(swId, accountId, JSON.stringify({ hidden: acc.hidden }));
                var row = this.tbody.querySelector('tr[data-acc-id="' + accountId + '"]');
                if (row) this._updateRowQuickActions(row, acc);
            }
        } else if (action === 'delete') {
            if (!confirm('确定要删除账号 "' + accountId + '" 吗？此操作不可撤销。')) return;
            var result = JFC.bridge.deleteAccount(swId, accountId);
            if (result && result.success) {
                this.accountData = this.accountData.filter(function(a) { return a.id !== accountId; });
                this.selectedIds.delete(accountId);
                this.render();
                this._updateSelectionUI();
                flashTitle('已删除');
            } else {
                flashTitle('删除失败', true);
            }
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
            if (nc) nc.textContent = ch.display_name;
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
            btn.textContent = acc.hidden ? '已隐藏' : '隐藏';
            btn.title = acc.hidden ? '取消隐藏' : '隐藏';
        }
        var dnCell = row.querySelector('.manage-nickname-cell');
        var tag = row.querySelector('.manage-disabled-tag');
        if (acc.disabled && !tag && dnCell) {
            var t = document.createElement('span');
            t.className = 'manage-disabled-tag';
            t.textContent = '禁用';
            dnCell.insertBefore(t, dnCell.querySelector('.manage-row-quick-actions'));
        } else if (!acc.disabled && tag) {
            tag.remove();
        }
    };

    AccountTable.prototype._updateAvatarCell = function(accountId, dataUrl) {
        var rows = this.tbody.rows;
        for (var i = 0; i < rows.length; i++) {
            if (rows[i].getAttribute('data-acc-id') === accountId) {
                var avatarBox = rows[i].querySelector('.manage-col-avatar .manage-account-avatar');
                if (avatarBox) {
                    var isFallback = dataUrl.indexOf('image/svg') !== -1;
                    var hasImg = avatarBox.querySelector('img');
                    if (isFallback && hasImg) return;
                    avatarBox.innerHTML = '<img src="' + escapeAttr(dataUrl) + '" alt="" onerror="this.style.display=\'none\';">';
                }
                break;
            }
        }
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
        var w = Math.max(30, t.resizeState.startWidth + (e.clientX - t.resizeState.startX));
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
        html += '<div class="acm-item" data-col-fit="all"><span class="acm-label">所有列自适应大小</span></div>';
        var fitCol = colKey && !this.colByKey(colKey).fixed ? colKey : null;
        if (colKey && (!fitCol || !this.colVisible[colKey])) {
            html += '<div class="acm-item disabled" data-col-fit=""><span class="acm-label">该列自适应大小</span></div>';
        } else if (fitCol) {
            html += '<div class="acm-item" data-col-fit="' + fitCol + '"><span class="acm-label">该列自适应大小</span></div>';
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
                var target = this.getAttribute('data-col-fit');
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
        var html = '<div class="acm-title">' + escapeHtml(accountId) + '</div>' +
            '<div class="acm-item" data-row-action="toggle-hidden">' + (hidden ? '显示' : '隐藏') + '</div>' +
            '<div class="acm-item danger" data-row-action="delete">删除</div>';
        menu.innerHTML = html;
        menu.style.display = 'block';
        positionMenu(menu, x, y);

        menu.querySelectorAll('.acm-item[data-row-action]').forEach(function(item) {
            item.addEventListener('click', function() {
                var action = this.getAttribute('data-row-action');
                closeRowMenu();
                activeTable.handleAction(action, accountId);
            });
        });
    };

    // ---- 列宽自适应 ----

    // 展示名列右端悬浮按钮（隐藏/已隐藏+删除）的占位总宽估算：
    // 覆盖最长按钮文字（"已隐藏"3字）+ padding + border + gap
    var QUICK_ACTIONS_WIDTH = 96;

    AccountTable.prototype.fitColumn = function(key) {
        var col = this.colByKey(key);
        if (!col || col.fixed) return;   // 固定列不参与自适应
        var table = this.tableEl;

        // 1. 内容最大宽度（列头文字 + 全部数据单元格），无上限
        var maxW = 0;
        table.querySelectorAll('thead th[data-col="' + key + '"], tbody td[data-col="' + key + '"]').forEach(function(cell) {
            if (cell.classList.contains('hidden-col')) return;
            var cs = window.getComputedStyle(cell);
            var pad = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
            var text = cell.innerText.replace(/\s+/g, ' ').trim() || '';
            var w = measureTextWidth(text, cs.fontFamily, cs.fontSize, cs.fontWeight) + pad;
            if (w > maxW) maxW = w;
        });

        // 2. 下限：列名宽度 + 余量；展示名列特殊 = 4 字符宽 + 按钮占位总宽 + 余量
        var th = table.querySelector('thead th[data-col="' + key + '"]');
        var minW = 0;
        if (th) {
            var thCs = window.getComputedStyle(th);
            if (key === 'display_name') {
                var fourChars = measureTextWidth('四字姓名', thCs.fontFamily, thCs.fontSize, thCs.fontWeight);
                minW = fourChars + QUICK_ACTIONS_WIDTH + 8;
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

    // ---- 快捷键列：点击激活输入框 ----
    AccountTable.prototype.activateHotkeyEdit = function(cell, accountId) {
        if (!this.enableHotkey) return;
        var acc = this.accountData.find(function(a) { return a.id === accountId; });
        var current = (acc && acc.hotkey) ? acc.hotkey : '';
        var self = this;

        // 结束上一个编辑（如有）：确保任何时刻只有一个编辑、捕获只开一次
        if (this._editFinish) this._editFinish();

        this.hotkeyEditAccountId = accountId;
        cell.setAttribute('data-editing', '1');
        JFC.bridge.notifyHotkeyCapture(true);

        cell.innerHTML = '<input type="text" class="hotkey-input" value="' + escapeAttr(current) + '" placeholder="按下快捷键…" spellcheck="false">';
        var input = cell.querySelector('input');
        input.focus();
        input.select();

        var done = false;
        function finish(commitValue) {
            if (done) return;
            done = true;
            document.removeEventListener('mousedown', docMousedown);
            if (self._editFinish === finish) self._editFinish = null;
            if (self.hotkeyEditAccountId === accountId) self.hotkeyEditAccountId = null;
            JFC.bridge.notifyHotkeyCapture(false);
            cell.removeAttribute('data-editing');
            var val = commitValue === undefined ? input.value.trim() : commitValue;
            if (val && val !== current && self.getSwId()) {
                if (acc) acc.hotkey = val;
                JFC.bridge.saveAccount(self.getSwId(), accountId, JSON.stringify({ hotkey: val }));
            }
            self._renderHotkeyCell(cell, accountId, val);
        }
        // 点击单元格外部 → 提交（mousedown 阶段处理，避免 blur 与 click 的 DOM 竞态）
        function docMousedown(ev) {
            if (ev.target.closest && ev.target.closest(cell)) return;   // 点击在编辑格内不提交
            finish();
        }
        document.addEventListener('mousedown', docMousedown);
        this._editFinish = finish;
        this._editDocMousedown = docMousedown;

        input.addEventListener('keydown', function(ev) {
            ev.preventDefault();
            ev.stopPropagation();
            if (ev.key === 'Escape') { finish(current); return; }
            if (ev.key === 'Enter') { finish(); return; }
            // 退格/方向键走原生编辑（不 preventDefault）
            if (ev.key === 'Backspace' || ev.key === 'Delete' ||
                ev.key.indexOf('Arrow') === 0 || ev.key === 'Home' || ev.key === 'End') {
                return;
            }
            var parts = [];
            if (ev.ctrlKey) parts.push('Ctrl');
            if (ev.altKey) parts.push('Alt');
            if (ev.shiftKey) parts.push('Shift');
            if (ev.metaKey) parts.push('Win');
            var k = ev.key;
            if (k === 'Control' || k === 'Alt' || k === 'Shift' || k === 'Meta') {
                input.value = parts.join('+');   // 单独修饰键：预览
                return;
            }
            if (k.length === 1 && /^[a-zA-Z0-9]$/.test(k)) {
                parts.push(k.toUpperCase());
                input.value = parts.join('+');
            } else if (/^F\d{1,2}$/.test(k)) {
                parts.push(k);
                input.value = parts.join('+');
            } else if (parts.length > 0) {
                var names = { ' ': 'Space', 'Tab': 'Tab', 'Delete': 'Delete', 'Insert': 'Insert',
                    'Home': 'Home', 'End': 'End', 'PageUp': 'PageUp', 'PageDown': 'PageDown' };
                parts.push(names[k] || (k.length === 1 ? k.toUpperCase() : k));
                input.value = parts.join('+');
            }
        });
        // 阻止点击输入框时触发 tbody click 再次进入编辑
        cell.addEventListener('click', function(ev) { ev.stopPropagation(); });
    };

    AccountTable.prototype.cancelHotkeyEdit = function() {
        if (!this.hotkeyEditAccountId) return;
        var row = this.tbody.querySelector('tr[data-acc-id="' + this.hotkeyEditAccountId + '"]');
        if (row) {
            var cell = row.querySelector('.manage-hotkey-cell');
            var acc = this.accountData.find(function(a) { return a.id === this.hotkeyEditAccountId; }, this);
            if (cell && acc) this._renderHotkeyCell(cell, acc.id, acc.hotkey || '');
        }
        // 结束编辑状态（还原 DOM，不提交）
        if (this._editFinish) {
            var finish = this._editFinish;
            this._editFinish = null;
            // 直接清理而不调用 finish（避免提交）
            document.removeEventListener('mousedown', this._editDocMousedown);
            JFC.bridge.notifyHotkeyCapture(false);
            var editingCell = this.tbody.querySelector('.manage-hotkey-cell[data-editing="1"]');
            if (editingCell) editingCell.removeAttribute('data-editing');
        }
        this.hotkeyEditAccountId = null;
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

    // ---- 标题闪烁反馈（与 main.js flashTitle 相同，独立实现避免循环依赖） ----
    function flashTitle(msg, isError) {
        var el = document.querySelector('#page-main #manage-detail-title');
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

    // 对外暴露
    AccountTable.closeMenus = function() { closeColMenu(); closeRowMenu(); activeTable = null; };
    AccountTable.getActiveTable = function() { return activeTable; };
    AccountTable.measureTextWidth = measureTextWidth;

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
