/**
 * task-center.js — 任务中心（右上角入口的面板 + 三小栏）.
 *
 * 数据来源：Java 侧 `core/task/TaskRegistry`（所有长耗时流程都在那儿登记）；
 * Java 每次任务变化都会推 `JFC.taskCenter.onTasks(jsonStr)`（JSON **字符串**，按项目约定再编码一层）。
 *
 * 三小栏：进行中 / 已完成（含失败）/ 已取消；底部"查看更多"去统计与任务列表页。
 * 取消是**协作式**的：点"取消"只是请求，任务跑到下一个安全检查点才停（已开的窗口不回滚）。
 */
var JFC = window.JFC || {};

JFC.taskCenter = (function() {
    'use strict';

    var panel = null, listEl = null, emptyEl = null, cancelAllBtn = null;
    var tabEls = null, moreBtn = null;
    var openFlag = false;
    var lastState = [];
    var tab = 'running';       // running | done | cancelled
    var ticker = null;

    // ==================== 工具 ====================

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function fmtElapsed(ms) {
        var s = Math.max(0, Math.floor((ms || 0) / 1000));
        var m = Math.floor(s / 60);
        s = s % 60;
        return m + ':' + (s < 10 ? '0' : '') + s;
    }

    function stateClass(st) {
        if (st === 'RUNNING') return 'running';
        if (st === 'CANCELLING') return 'cancelling';
        if (st === 'DONE') return 'done';
        if (st === 'FAILED') return 'failed';
        return 'cancelled';
    }

    /** 任务归到哪一栏：已完成栏含"失败"（红标签区分），避免失败无处可去 */
    function bucketOf(t) {
        if (t.active) return 'running';
        if (t.state === 'CANCELLED') return 'cancelled';
        return 'done';
    }

    function counts() {
        var c = { running: 0, done: 0, cancelled: 0 };
        for (var i = 0; i < lastState.length; i++) c[bucketOf(lastState[i])]++;
        return c;
    }

    // ==================== DOM ====================

    function buildPanel() {
        if (panel) return;
        panel = document.createElement('div');
        panel.className = 'task-center';
        panel.setAttribute('data-open', '0');
        panel.innerHTML =
            '<div class="tc-head">' +
            '  <span class="tc-title">任务中心</span>' +
            '  <span class="tc-head-actions">' +
            '    <button class="tc-btn tc-cancel-all" type="button">全部取消</button>' +
            '    <button class="tc-btn tc-close" type="button" title="收起">✕</button>' +
            '  </span>' +
            '</div>' +
            '<div class="tc-tabs">' +
            '  <button class="tc-tab" type="button" data-tab="running">进行中<i>0</i></button>' +
            '  <button class="tc-tab" type="button" data-tab="done">已完成<i>0</i></button>' +
            '  <button class="tc-tab" type="button" data-tab="cancelled">已取消<i>0</i></button>' +
            '</div>' +
            '<div class="tc-list"></div>' +
            '<div class="tc-empty">暂无任务</div>' +
            '<div class="tc-foot">' +
            '  <button class="tc-btn tc-more" type="button">查看更多</button>' +
            '</div>';
        document.body.appendChild(panel);

        listEl = panel.querySelector('.tc-list');
        emptyEl = panel.querySelector('.tc-empty');
        cancelAllBtn = panel.querySelector('.tc-cancel-all');
        moreBtn = panel.querySelector('.tc-more');
        tabEls = panel.querySelectorAll('.tc-tab');

        cancelAllBtn.addEventListener('click', function() {
            if (this.disabled) return;
            JFC.bridge.cancelAllTasks();
        });
        panel.querySelector('.tc-close').addEventListener('click', function() { close(); });
        moreBtn.addEventListener('click', function() {
            close();
            if (JFC.router && JFC.router.navigate) JFC.router.navigate('statistics');
        });
        for (var i = 0; i < tabEls.length; i++) {
            tabEls[i].addEventListener('click', function() {
                tab = this.getAttribute('data-tab');
                paint();
            });
        }

        // 点面板外面 → 收起
        document.addEventListener('mousedown', function(e) {
            if (!openFlag || !panel) return;
            if (panel.contains(e.target)) return;
            close();
        }, true);
    }

    function rowHtml(t) {
        var active = !!t.active;
        var pct = (t.total > 0) ? (' · ' + t.done + '/' + t.total) : '';
        return '<div class="tc-row" data-id="' + esc(t.id) + '">' +
            '<div class="tc-row-body">' +
            '  <div class="tc-row-main">' +
            '    <span class="tc-name">' + esc(t.title) + '</span>' +
            (t.target ? '<span class="tc-target">' + esc(t.target) + '</span>' : '') +
            '  </div>' +
            '  <div class="tc-row-sub">' +
            '    <span class="tc-state ' + stateClass(t.state) + '">' + esc(t.stateText) + '</span>' +
            '    <span class="tc-phase">' + esc(t.phase) + pct + '</span>' +
            '  </div>' +
            (t.error ? '<div class="tc-error">' + esc(t.error) + '</div>' : '') +
            '</div>' +
            '<div class="tc-row-right">' +
            '  <span class="tc-elapsed" data-start="' + (t.startedAt || 0) + '" data-end="' + (t.finishedAt || 0) + '">'
            + fmtElapsed(t.elapsedMs) + '</span>' +
            (active ? '<button class="tc-btn tc-cancel" type="button">取消</button>' : '') +
            '</div>' +
            '</div>';
    }

    function paint() {
        var c = counts();
        for (var i = 0; i < tabEls.length; i++) {
            var key = tabEls[i].getAttribute('data-tab');
            tabEls[i].className = 'tc-tab' + (key === tab ? ' active' : '');
            tabEls[i].querySelector('i').textContent = c[key];
        }
        var rows = [];
        for (var j = 0; j < lastState.length; j++) {
            if (bucketOf(lastState[j]) === tab) rows.push(lastState[j]);
        }
        listEl.innerHTML = rows.map(rowHtml).join('');
        emptyEl.style.display = rows.length ? 'none' : 'block';
        emptyEl.textContent = tab === 'running' ? '没有进行中的任务'
                : (tab === 'done' ? '还没有已完成的任务' : '还没有被取消的任务');
        cancelAllBtn.disabled = c.running === 0;

        var btns = listEl.querySelectorAll('.tc-cancel');
        for (var k = 0; k < btns.length; k++) {
            btns[k].addEventListener('click', function(e) {
                e.stopPropagation();
                var id = this.closest('.tc-row').getAttribute('data-id');
                this.disabled = true;
                this.textContent = '正在停止…';
                JFC.bridge.cancelTask(id);
            });
        }
    }

    function render(state) {
        lastState = state || [];
        if (!panel) return;
        paint();
        // 标题栏角标不在这里更新：它由 Java 侧 MainWindow 直接订阅 TaskRegistry（单一写入点）
    }

    /**
     * 每秒：① 拉一次最新状态 —— **指纹变了才重画**（阶段/进度/状态变了立刻反映，且不会因为重画而点不到按钮）
     *        ② 否则只更新"耗时"文本（不重画 → 不闪）
     * 之所以要轮询：位置/阶段这类信息只在任务内部变化，Java 侧不会为每次变化都推送（推送只发生在提交/取消/结束）。
     */
    function tick() {
        if (!panel || !listEl) return;
        try {
            var raw = JFC.bridge.getTaskList();
            var fresh = raw ? JSON.parse(raw) : [];
            if (fingerprint(fresh) !== fingerprint(lastState)) {
                render(fresh);
                return;
            }
        } catch (e) { /* 忽略，下面的耗时仍会更新 */ }

        var els = listEl.querySelectorAll('.tc-elapsed');
        var now = Date.now();
        for (var i = 0; i < els.length; i++) {
            var start = parseInt(els[i].getAttribute('data-start') || '0', 10);
            var end = parseInt(els[i].getAttribute('data-end') || '0', 10);
            els[i].textContent = fmtElapsed((end > 0 ? end : now) - start);
        }
    }

    /** 状态指纹：只要它变了就值得重画（阶段/进度/状态/数量） */
    function fingerprint(list) {
        var s = [];
        for (var i = 0; i < list.length; i++) {
            var t = list[i];
            s.push(t.id + '|' + t.state + '|' + t.phase + '|' + t.done + '/' + t.total);
        }
        return s.join(';');
    }

    function refresh() {
        try {
            var raw = JFC.bridge.getTaskList();
            render(raw ? JSON.parse(raw) : []);
        } catch (e) {
            console.log('[taskCenter] 刷新失败: ' + e);
        }
    }

    // ==================== 对外 ====================

    function open() {
        buildPanel();
        openFlag = true;
        panel.setAttribute('data-open', '1');
        refresh();
        // 有任务在进行中 → **优先定位到"进行中"栏**（用户 2026-10-13）：
        // 打开面板的动机通常就是"看看在跑什么"，此时停在别的栏等于白开
        if (counts().running > 0) {
            tab = 'running';
            paint();
        }
        if (!ticker) ticker = setInterval(tick, 1000);
    }

    function close() {
        if (!panel) return;
        openFlag = false;
        panel.setAttribute('data-open', '0');
        if (ticker) { clearInterval(ticker); ticker = null; }
    }

    function toggle() { if (openFlag) close(); else open(); }

    /** Java 推送入口：参数是 JSON 字符串 */
    function onTasks(jsonStr) {
        var state;
        try { state = JSON.parse(jsonStr); } catch (e) { return; }
        render(state);
    }

    /** 页面初始化时拉一次（同时让 Java 侧装上推送监听） */
    function init() {
        buildPanel();
        refresh();
    }

    return { init: init, toggle: toggle, open: open, close: close, onTasks: onTasks, refresh: refresh };
})();
