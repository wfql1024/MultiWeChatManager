/**
 * tasks.js — 「任务与统计」页（任务中心面板底部"查看更多"落到这里）.
 *
 * 数据全部来自任务中心内核（core/task）：
 *   · `JFC.bridge.getTaskList()`   → 任务列表（含各阶段耗时 phases）
 *   · `JFC.bridge.getTaskStats()`  → 按 kind 的聚合（次数/成功/失败/取消/平均/最长）
 *
 * 因为**统计与任务中心同源**（任务结束自动记一条），这里不需要任何额外埋点：
 * 以后新写一个流程，只要走 TaskRegistry.submit + TaskContext.phase/step，就会自动出现在本页。
 */
var JFC = window.JFC || {};
JFC.pages = JFC.pages || {};

JFC.pages.tasks = (function() {
    'use strict';

    var tab = 'running';
    var bound = false;
    var poller = null;
    var lastList = [];

    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function fmtMs(ms) {
        ms = Math.max(0, Math.floor(ms || 0));
        if (ms < 1000) return ms + 'ms';
        var s = Math.floor(ms / 1000);
        if (s < 60) return s + 's';
        var m = Math.floor(s / 60);
        s = s % 60;
        return m + 'm' + (s < 10 ? '0' : '') + s + 's';
    }

    function bucketOf(t) {
        if (t.active) return 'running';
        if (t.state === 'CANCELLED') return 'cancelled';
        return 'done';
    }

    function stateClass(st) {
        return { RUNNING: 'running', CANCELLING: 'cancelling', DONE: 'done', FAILED: 'failed', CANCELLED: 'cancelled' }[st] || '';
    }

    function phasesText(t) {
        var p = t.phases;
        if (!p) return '—';
        var keys = Object.keys(p);
        if (!keys.length) return '—';
        var out = [];
        for (var i = 0; i < keys.length; i++) out.push(keys[i] + ' ' + fmtMs(p[keys[i]]));
        return out.join(' · ');
    }

    // ==================== 渲染 ====================

    function renderSummary() {
        var box = document.getElementById('tasks-summary');
        if (!box) return;
        var stats;
        try {
            stats = JSON.parse(JFC.bridge.getTaskStats() || '{}');
        } catch (e) {
            stats = {};
        }
        var rows = stats.summary || [];
        if (!rows.length) {
            box.innerHTML = '<div class="tasks-summary-empty">还没有统计数据（跑一次登录或多开会话就有）</div>';
            return;
        }
        var html = '';
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i];
            // 阶段耗时（按流程聚合）：哪一步最费时间，一眼看出来
            var phases = r.phases || {};
            var pk = Object.keys(phases).sort(function(a, b) { return phases[b] - phases[a]; });
            var phasesHtml = '';
            if (pk.length) {
                var parts = [];
                for (var q = 0; q < pk.length && q < 4; q++) parts.push(pk[q] + ' ' + fmtMs(phases[pk[q]]));
                phasesHtml = '<div class="tasks-card-phases">阶段：' + esc(parts.join(' · ')) + '</div>';
            }
            // 派生统计（用户口径）：单次统计 = 末次/最短/最长；总平均 = Σ时长 ÷ Σ轮次
            var d = r.derived;
            var derivedHtml = '';
            if (d) {
                var unit = (d.countKey === '开窗轮次' ? '窗' : '个');
                derivedHtml = '<div class="tasks-card-derived">' +
                    '<span class="tasks-card-label">总平均</span> ' +
                    '<b class="tasks-card-big">' + fmtMs(d.avgPerUnitMs) + '</b>/' + unit +
                    '<span class="tasks-card-dim">（' + d.totalCount + ' 轮 · ' + fmtMs(d.totalDurationMs) + '）</span>' +
                    '<br><span class="tasks-card-label">单次</span> ' +
                    '末次 <b>' + fmtMs(d.lastPerUnitMs) + '</b>' +
                    '　最短 <b>' + fmtMs(d.minPerUnitMs) + '</b>' +
                    '　最长 <b>' + fmtMs(d.maxPerUnitMs) + '</b>' +
                    '<span class="tasks-card-dim">（共 ' + d.runs + ' 次运行）</span>' +
                    '</div>';
            }
            // 业务指标（现在是 {sum,count,avg,min,max} 聚合结构）
            var metrics = r.metrics || {};
            var mk = Object.keys(metrics);
            var metricsHtml = '';
            if (mk.length) {
                var mp = [];
                for (var w = 0; w < mk.length; w++) {
                    var mv = metrics[mk[w]];
                    var val = (mv && typeof mv === 'object') ? mv.sum : mv;
                    mp.push(mk[w] + ' ' + val);
                }
                metricsHtml = '<div class="tasks-card-metrics">' + esc(mp.join(' · ')) + '</div>';
            }
            html += '<div class="tasks-card">' +
                '<div class="tasks-card-kind">' + esc(r.kind) + '</div>' +
                '<div class="tasks-card-main">' +
                '  <span class="tasks-card-num">' + r.count + '</span><span class="tasks-card-unit">次</span>' +
                '  <span class="tasks-card-sub">成功 ' + r.success + ' / 失败 ' + r.failed + ' / 取消 ' + r.cancelled + '</span>' +
                '</div>' +
                // 有派生统计时不再显示"任务总耗时"（登录/多开看的不是它）
                (d ? '' : '<div class="tasks-card-time">任务耗时：平均 ' + fmtMs(r.avgMs) + '　最长 ' + fmtMs(r.maxMs) + '</div>') +
                derivedHtml + phasesHtml + metricsHtml +
                '</div>';
        }
        box.innerHTML = html;
    }

    function renderList() {
        var tbody = document.getElementById('tasks-tbody');
        var empty = document.getElementById('tasks-empty');
        if (!tbody) return;

        var counts = { running: 0, done: 0, cancelled: 0 };
        for (var i = 0; i < lastList.length; i++) counts[bucketOf(lastList[i])]++;

        var tabs = document.querySelectorAll('.tasks-tab');
        for (var j = 0; j < tabs.length; j++) {
            var k = tabs[j].getAttribute('data-tab');
            tabs[j].className = 'tasks-tab' + (k === tab ? ' active' : '');
            tabs[j].querySelector('i').textContent = counts[k];
        }

        var rows = [];
        for (var m = 0; m < lastList.length; m++) if (bucketOf(lastList[m]) === tab) rows.push(lastList[m]);

        tbody.innerHTML = rows.map(function(t) {
            return '<tr>' +
                '<td class="tasks-td-name">' + esc(t.title) + '</td>' +
                '<td>' + esc(t.target || '—') + '</td>' +
                '<td><span class="tc-state ' + stateClass(t.state) + '">' + esc(t.stateText) + '</span></td>' +
                '<td class="tasks-td-phase">' + esc(t.phase) + (t.total > 0 ? '（' + t.done + '/' + t.total + '）' : '') + '</td>' +
                '<td class="tasks-td-phases">' + esc(phasesText(t)) + '</td>' +
                '<td class="tasks-td-ms">' + fmtMs(t.elapsedMs) + '</td>' +
                '<td>' + (t.active ? '<button class="tc-btn tasks-cancel" data-id="' + esc(t.id) + '" type="button">取消</button>' : '') + '</td>' +
                '</tr>';
        }).join('');

        if (empty) {
            empty.style.display = rows.length ? 'none' : 'block';
            empty.textContent = tab === 'running' ? '没有进行中的任务'
                    : (tab === 'done' ? '还没有已完成的任务' : '还没有被取消的任务');
        }

        var btns = tbody.querySelectorAll('.tasks-cancel');
        for (var n = 0; n < btns.length; n++) {
            btns[n].addEventListener('click', function() {
                this.disabled = true;
                this.textContent = '正在停止…';
                JFC.bridge.cancelTask(this.getAttribute('data-id'));
            });
        }
    }

    function refresh() {
        try {
            lastList = JSON.parse(JFC.bridge.getTaskList() || '[]');
        } catch (e) {
            lastList = [];
        }
        renderSummary();
        renderList();
    }

    // ==================== 绑定 / 对外 ====================

    function init() {
        if (!bound) {
            bound = true;
            var tabs = document.querySelectorAll('.tasks-tab');
            for (var i = 0; i < tabs.length; i++) {
                tabs[i].addEventListener('click', function() {
                    tab = this.getAttribute('data-tab');
                    renderList();
                });
            }
            var btn = document.getElementById('tasks-refresh');
            if (btn) btn.addEventListener('click', refresh);
        }
        refresh();
        // 页面在前台时每秒刷新一次（阶段/进度是活的；指纹没变就只更新耗时，避免闪）
        if (!poller) {
            poller = setInterval(function() {
                var page = document.getElementById('page-statistics');
                if (!page || !page.classList.contains('active')) return;
                refresh();
            }, 1000);
        }
    }

    return { init: init, refresh: refresh };
})();
