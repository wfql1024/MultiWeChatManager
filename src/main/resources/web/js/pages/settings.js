/**
 * settings.js — 设置页.
 */
JFC.pages = JFC.pages || {};

JFC.pages.settings = (function() {
    'use strict';

    var currentSection = 'appearance';
    var currentTheme = 'auto';
    var configInited = false;
    var updateInited = false;
    var thanksInited = false;
    var aboutInited = false;

    var defaultUserDir = '';
    var currentVersion = '4.0.0.7000';
    var correctSuffix = 'user_files';

    var urlListData = {
        sw:    { defaults: [], userUrls: [], lastValidSet: new Set() },
        global: { defaults: [], userUrls: [], lastValidSet: new Set() }
    };

    // ==================== 初始化 ====================

    function init() {
        document.querySelectorAll('#settings-nav li').forEach(function(item) {
            item.addEventListener('click', function() {
                showSection(this.getAttribute('data-setting'));
            });
        });
        if (JM()) {
            var t = JFC.bridge.call('getTheme');
            if (t === 'dark' || t === 'light' || t === 'auto') {
                currentTheme = t;
                document.documentElement.setAttribute('data-theme', currentTheme);
            }
        }
        if (!currentTheme || currentTheme === 'auto')
            currentTheme = document.documentElement.getAttribute('data-theme') || 'auto';
        initThemeButtons();
        showSection('appearance');
    }

    function JM() { return JFC.bridge && JFC.bridge.isAvailable(); }

    // ==================== 主题 ====================

    function initThemeButtons() {
        updateThemeButtons(currentTheme);
        document.querySelectorAll('#theme-segmented .theme-seg-btn').forEach(function(btn) {
            btn.addEventListener('click', function() { setTheme(this.getAttribute('data-theme')); });
        });
    }

    function setTheme(theme) {
        currentTheme = theme;
        updateThemeButtons(theme);
        if (JM()) { JFC.bridge.setTheme(theme); JFC.bridge.saveTheme(theme); }
        document.documentElement.setAttribute('data-theme', theme);
    }

    function updateThemeButtons(theme) {
        document.querySelectorAll('#theme-segmented .theme-seg-btn').forEach(function(btn) {
            btn.classList.toggle('active', btn.getAttribute('data-theme') === theme);
        });
    }

    // ==================== 配置 — 初始化 ====================

    function initConfigSection() {
        if (configInited) return;
        configInited = true;

        bind('cfg-use-proxy', 'change', function() {
            var d = document.getElementById('cfg-proxy-detail');
            if (d) d.style.display = this.checked ? '' : 'none';
        });

        bind('cfg-user-dir-browse', 'click', function() {
            if (!JM()) return;
            var cur = getActualDirVal();
            var sel = JFC.bridge.browseFolder(cur || defaultUserDir || '');
            if (sel) { setVal('cfg-user-dir', sel); el('cfg-user-dir').classList.remove('cfg-placeholder'); validateUserDir(); }
        });

        bind('cfg-user-dir', 'blur', validateUserDir);
        bind('cfg-user-dir', 'focus', onUserDirFocus);

        bind('cfg-sw-add', 'click', function() { addUrl('sw'); });
        bind('cfg-sw-test-all', 'click', function() { testAllUrls('sw'); });
        bind('cfg-global-add', 'click', function() { addUrl('global'); });
        bind('cfg-global-test-all', 'click', function() { testAllUrls('global'); });

        bind('cfg-btn-save', 'click', saveConfigData);
    }

    function bind(id, evt, fn) { var e = document.getElementById(id); if (e) e.addEventListener(evt, fn); }
    function el(id) { return document.getElementById(id); }

    // ==================== 用户目录 ====================

    function onUserDirFocus() {
        var input = el('cfg-user-dir');
        if (!input || !input.classList.contains('cfg-placeholder')) return;
        input.value = defaultUserDir || '';
        input.classList.remove('cfg-placeholder');
    }

    function validateUserDir() {
        var input = el('cfg-user-dir');
        if (!input || !JM()) { updateSaveButton(); return; }
        var val = getActualDirVal();

        if (!val || val === defaultUserDir) {
            input.value = defaultUserDir ? '（默认）' + defaultUserDir : '';
            input.classList.add('cfg-placeholder');
            input.classList.remove('input-error', 'input-warn');
            input.classList.add('input-ok');
            hideEl('cfg-user-dir-hint');
            updateSaveButton();
            return;
        }

        input.classList.remove('cfg-placeholder');

        var r = JFC.bridge.validatePath(val);
        if (!r || !r.valid) {
            input.classList.add('input-error'); input.classList.remove('input-ok', 'input-warn');
            showEl('cfg-user-dir-hint', (r && r.error) || '路径格式不合法', 'config-hint error');
            updateSaveButton(); return;
        }

        var corrected = ensureCorrectTail(val);
        if (corrected !== val) { input.value = corrected; val = corrected; }

        r = JFC.bridge.validatePath(val);
        if (!r || !r.valid) {
            input.classList.add('input-error'); input.classList.remove('input-ok', 'input-warn');
            showEl('cfg-user-dir-hint', (r && r.error) || '修正后路径不合法', 'config-hint error');
            updateSaveButton(); return;
        }

        var matches = val.match(/\d+\.\d+\.\d+\.\d+/g);
        var vCount = matches ? matches.length : 0;
        if (vCount > 1) {
            input.classList.remove('input-error', 'input-ok'); input.classList.add('input-warn');
            showEl('cfg-user-dir-hint', '路径中存在多个版本号 (' + matches.join(', ') + ')，可能存在版本嵌套，建议修改', 'config-hint warn');
        } else {
            input.classList.remove('input-error', 'input-warn'); input.classList.add('input-ok');
            hideEl('cfg-user-dir-hint');
        }
        updateSaveButton();
    }

    function getActualDirVal() {
        var input = el('cfg-user-dir');
        if (!input || input.classList.contains('cfg-placeholder')) return '';
        return getVal('cfg-user-dir');
    }

    function ensureCorrectTail(val) {
        var sep = val.indexOf('\\') >= 0 ? '\\' : '/';
        var parts = val.replace(/\\/g, '/').split('/').filter(function(p) { return p.length > 0; });
        if (parts.length === 0) return currentVersion + sep + correctSuffix;
        var len = parts.length;
        if (len >= 2 && parts[len-2] === currentVersion && parts[len-1] === correctSuffix) return val;
        if (parts[len-1] === currentVersion) { parts.push(correctSuffix); return parts.join(sep); }
        if (parts[len-1] === 'user_files' || parts[len-1] === 'dev_user_files') {
            parts[parts.length-1] = correctSuffix;
            if (parts.length >= 2 && parts[parts.length-2] === currentVersion) return parts.join(sep);
            parts.splice(parts.length-1, 0, currentVersion);
            return parts.join(sep);
        }
        parts.push(currentVersion); parts.push(correctSuffix);
        return parts.join(sep);
    }

    // ==================== 远程URL列表 ====================

    function renderUrlList(ns) {
        var listId = ns === 'global' ? 'cfg-global-list' : 'cfg-sw-list';
        var container = el(listId); if (!container) return;
        container.innerHTML = '';
        var data = urlListData[ns];
        data.defaults.forEach(function(item) { addUrlRow(container, ns, item.url, true); });
        data.userUrls.forEach(function(url) { addUrlRow(container, ns, url, false); });
    }

    function addUrlRow(container, ns, url, isDefault) {
        var data = urlListData[ns];

        var row = document.createElement('div');
        row.className = 'url-list-row';
        row.dataset.ns = ns;
        row.dataset.isDefault = isDefault ? '1' : '0';

        // 输入行
        var inputLine = document.createElement('div');
        inputLine.className = 'url-input-line';

        var input = document.createElement('input');
        input.type = 'text'; input.spellcheck = false;
        input.value = isDefault ? '(默认) ' + url : url;
        input.readOnly = isDefault;
        if (data.lastValidSet.has(url)) input.classList.add('input-ok');
        input.addEventListener('input', function() {
            input.classList.remove('input-ok', 'input-error');
            hideRowHint(row);
            updateSaveButton();
        });
        inputLine.appendChild(input);

        var testBtn = document.createElement('button');
        testBtn.className = 'btn-sm'; testBtn.textContent = '测试';
        testBtn.addEventListener('click', function() { testRowUrl(ns, row); });
        inputLine.appendChild(testBtn);

        var delBtn = document.createElement('button');
        delBtn.className = 'btn-sm btn-del'; delBtn.textContent = '删除';
        delBtn.disabled = isDefault;
        delBtn.addEventListener('click', function() { deleteUrlRow(ns, row); });
        inputLine.appendChild(delBtn);

        row.appendChild(inputLine);

        // 提示行（预留高度，不挤占布局）
        var hint = document.createElement('div');
        hint.className = 'url-row-hint-line';
        hint.style.visibility = 'hidden';
        row.appendChild(hint);

        container.appendChild(row);
    }

    function getRowInput(row) { return row.querySelector('input'); }
    function getRowUrl(row) {
        var inp = getRowInput(row);
        if (!inp) return '';
        var v = inp.value.trim();
        // 去掉默认前缀
        if (inp.readOnly && v.startsWith('(默认) ')) return v.substring(5);
        return v;
    }
    function getRowHint(row) { return row.querySelector('.url-row-hint-line'); }
    function showRowHint(row, msg, cls) {
        var h = getRowHint(row); if (!h) return;
        h.textContent = msg; h.className = 'url-row-hint-line ' + (cls || ''); h.style.visibility = 'visible';
    }
    function hideRowHint(row) {
        var h = getRowHint(row); if (h) h.style.visibility = 'hidden';
    }

    function testRowUrl(ns, row, onDone) {
        if (!JM()) { if (onDone) onDone(); return; }
        var input = getRowInput(row);
        var url = getRowUrl(row);
        if (!url) { showRowHint(row, 'URL 为空', 'error'); if (onDone) onDone(); return; }

        var testBtn = row.querySelector('.btn-sm');
        if (testBtn) testBtn.disabled = true;

        JFC.bridge.testUrlAsync(url, function(type, result) {
            if (testBtn) testBtn.disabled = false;
            var data = urlListData[ns];
            if (result && result.success) {
                input.classList.remove('input-error'); input.classList.add('input-ok');
                data.lastValidSet.add(url);
                showRowHint(row, '地址有效', 'ok');
            } else {
                input.classList.add('input-error'); input.classList.remove('input-ok');
                data.lastValidSet.delete(url);
                showRowHint(row, '测试失败: ' + ((result && result.error) || '连接失败'), 'error');
            }
            updateSaveButton();
            if (onDone) onDone();
        });
    }

    function testAllUrls(ns) {
        var listId = ns === 'global' ? 'cfg-global-list' : 'cfg-sw-list';
        var container = el(listId); if (!container) return;
        var allBtn = el(ns === 'global' ? 'cfg-global-test-all' : 'cfg-sw-test-all');
        if (allBtn) allBtn.disabled = true;
        var rows = container.querySelectorAll('.url-list-row');
        var remaining = rows.length;
        function onOneDone() { remaining--; if (remaining <= 0 && allBtn) allBtn.disabled = false; }
        for (var i = 0; i < rows.length; i++) {
            testRowUrl(ns, rows[i], onOneDone);
        }
    }

    function addUrl(ns) {
        var listId = ns === 'global' ? 'cfg-global-list' : 'cfg-sw-list';
        var container = el(listId); if (!container) return;
        var rows = container.querySelectorAll('.url-list-row');
        // 直接拷贝最后一条 URL（不管是不是默认）
        var lastUrl = rows.length > 0 ? getRowUrl(rows[rows.length-1]) : '';
        addUrlRow(container, ns, lastUrl, false);
        updateSaveButton();
    }

    function deleteUrlRow(ns, row) {
        if (row.dataset.isDefault === '1') return;
        urlListData[ns].lastValidSet.delete(getRowUrl(row));
        row.remove();
        updateSaveButton();
    }

    function collectUserUrls(ns) {
        var listId = ns === 'global' ? 'cfg-global-list' : 'cfg-sw-list';
        var container = el(listId); if (!container) return [];
        var urls = [];
        container.querySelectorAll('.url-list-row').forEach(function(row) {
            if (row.dataset.isDefault === '0') { var u = getRowUrl(row); if (u) urls.push(u); }
        });
        return urls;
    }

    function hasGreen(ns) {
        var listId = ns === 'global' ? 'cfg-global-list' : 'cfg-sw-list';
        var container = el(listId); if (!container) return false;
        var found = false;
        container.querySelectorAll('.url-list-row input').forEach(function(inp) {
            if (inp.classList.contains('input-ok')) found = true;
        });
        return found;
    }

    // ==================== 加载配置数据 ====================

    function loadConfigData() {
        if (!JM()) return;

        var dev = JFC.bridge.isDevMode();
        correctSuffix = dev ? 'dev_user_files' : 'user_files';

        var defUrls = JFC.bridge.getDefaultUrls();
        if (defUrls) {
            urlListData.global.defaults = defUrls.remoteGlobalDefaults || [];
            urlListData.sw.defaults     = defUrls.remoteSwDefaults || [];
        }

        defaultUserDir = JFC.bridge.getDefaultUserDir() || '';

        var data = JFC.bridge.getConfigData();
        if (!data) return;

        var cb = el('cfg-use-proxy');
        if (cb) cb.checked = !!data.useProxy;
        var detail = el('cfg-proxy-detail');
        if (detail) detail.style.display = data.useProxy ? '' : 'none';
        setVal('cfg-proxy-ip', data.proxyIp || '');
        setVal('cfg-proxy-port', data.proxyPort || '');

        var dirVal = data.userDataPath || '';
        var dirEl = el('cfg-user-dir');
        if (dirEl) {
            if (dirVal && dirVal !== defaultUserDir) {
                setVal('cfg-user-dir', dirVal); dirEl.classList.remove('cfg-placeholder');
            } else {
                dirEl.value = defaultUserDir ? '（默认）' + defaultUserDir : '';
                dirEl.classList.add('cfg-placeholder');
            }
        }

        urlListData.global.userUrls = [];
        urlListData.sw.userUrls = [];
        if (data.remoteGlobalUrls && Array.isArray(data.remoteGlobalUrls))
            data.remoteGlobalUrls.forEach(function(u) { if (u && urlListData.global.userUrls.indexOf(u) < 0) urlListData.global.userUrls.push(u); });
        if (data.remoteSwUrls && Array.isArray(data.remoteSwUrls))
            data.remoteSwUrls.forEach(function(u) { if (u && urlListData.sw.userUrls.indexOf(u) < 0) urlListData.sw.userUrls.push(u); });

        urlListData.global.userUrls.forEach(function(u) { if (u) urlListData.global.lastValidSet.add(u); });
        urlListData.sw.userUrls.forEach(function(u) { if (u) urlListData.sw.lastValidSet.add(u); });

        renderUrlList('sw');
        renderUrlList('global');

        var presets = JFC.bridge.getProxyPresets();
        if (presets) {
            renderPresets('cfg-proxy-ip-presets', presets.ipPresets || [], 'cfg-proxy-ip');
            renderPresets('cfg-proxy-port-presets', presets.portPresets || [], 'cfg-proxy-port');
        }

        validateUserDir();
    }

    // ==================== 保存 ====================

    function saveConfigData() {
        if (!JM()) { showMsg('保存失败: 桥接不可用', true); return; }
        validateUserDir();

        var hasDirErr = (el('cfg-user-dir') && el('cfg-user-dir').classList.contains('input-error'));
        var noGreen = false;
        ['sw','global'].forEach(function(ns) { if (!hasGreen(ns)) noGreen = true; });

        if (hasDirErr) { showMsg('请先修正用户目录路径错误', true); return; }
        if (noGreen) { showMsg('远程平台和远程全局都至少需要一个地址测试通过（绿框）', true); return; }

        var data = {
            useProxy: el('cfg-use-proxy').checked,
            proxyIp: getVal('cfg-proxy-ip'),
            proxyPort: getVal('cfg-proxy-port'),
            userDataPath: getActualDirVal(),
            remoteGlobalUrls: collectUserUrls('global'),
            remoteSwUrls: collectUserUrls('sw')
        };

        var result = JFC.bridge.saveConfigData(JSON.stringify(data));
        if (result && result.success) {
            showMsg('保存成功');
            if (result.pathChanged) setVal('cfg-user-dir', result.newPath || data.userDataPath);
            collectUserUrls('global').forEach(function(u) { urlListData.global.lastValidSet.add(u); });
            collectUserUrls('sw').forEach(function(u) { urlListData.sw.lastValidSet.add(u); });
            el('cfg-user-dir').classList.remove('input-error', 'input-warn');
        } else {
            showMsg((result && result.error) || '保存失败', true);
        }
    }

    function updateSaveButton() {
        var btn = el('cfg-btn-save'); if (!btn) return;
        var err = (el('cfg-user-dir') && el('cfg-user-dir').classList.contains('input-error'));
        btn.disabled = err;
    }

    // ==================== 更新（异步） ====================

    function loadUpdateData() {
        if (updateInited) return;
        updateInited = true;
        bind('upd-btn-check', 'click', function() { updateInited = false; loadUpdateData(); });

        setText('upd-current-ver', '—');
        setText('upd-code-ver', '—');
        setText('upd-commit-date', '—');
        setText('upd-latest-ver', '—');
        setText('upd-status', '正在检查更新…');

        if (!JM()) { setText('upd-status', '桥接不可用'); return; }

        JFC.bridge.fetchUpdateAsync(function(type, data) {
            if (!data || !data.currentVersion) { setText('upd-status', '检查失败，请检查网络连接'); return; }
            setText('upd-current-ver', data.currentVersion || '—');

            // commit info 同步（本地操作，不阻塞）
            var ci = JFC.bridge.getCommitInfo();
            setText('upd-code-ver', (ci && ci.commitId) || '—');
            setText('upd-commit-date', (ci && ci.commitDate) || '—');
            setText('upd-latest-ver', data.latestVersion || '—');

            var st = el('upd-status');
            if (data.latestVersion && data.hasUpdate) {
                st.textContent = '发现新版本 ' + data.latestVersion + '，建议更新！';
                st.className = 'update-status has-update';
            } else if (data.latestVersion) {
                st.textContent = '软件已是最新，尽情地体验吧~';
                st.className = 'update-status';
            } else {
                st.textContent = '无法获取最新版本信息';
                st.className = 'update-status';
            }

            if (data.updateLogs) {
                var ld = el('upd-changelog'), lc = el('upd-changelog-content');
                if (ld && lc) {
                    ld.style.display = '';
                    lc.innerHTML = '';
                    Object.keys(data.updateLogs).forEach(function(cat) {
                        var items = data.updateLogs[cat];
                        if (!items || !items.length) return;
                        var d = document.createElement('div'); d.className = 'update-log-cat';
                        var n = document.createElement('div'); n.className = 'update-log-cat-name'; n.textContent = cat;
                        d.appendChild(n);
                        var ul = document.createElement('ul');
                        items.forEach(function(it) { var li = document.createElement('li'); li.textContent = it; ul.appendChild(li); });
                        d.appendChild(ul);
                        lc.appendChild(d);
                    });
                }
            }
        });
    }

    // ==================== 鸣谢（异步） ====================

    var scrollAnims = {};  // sponsor / ref 滚动动画句柄

    function loadThanksData() {
        if (thanksInited) return;
        thanksInited = true;
        if (!JM()) return;

        var grid = el('thanks-grid');
        if (grid) grid.innerHTML = '<span style="color:var(--text-muted)">加载中…</span>';
        var tbody = el('sponsor-tbody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="3" style="color:var(--text-muted)">加载中…</td></tr>';
        var refList = document.getElementById('about-ref-list');
        if (refList) refList.innerHTML = '<span style="color:var(--text-muted);padding:8px;">加载中…</span>';

        JFC.bridge.fetchThanksAsync(function(type, data) {
            if (!data) return;

            // 鸣谢（多人多链接）
            if (grid && data.thanks) {
                grid.innerHTML = '';
                var entries = Object.entries(data.thanks);
                entries.forEach(function(kv, i) {
                    var info = kv[1];
                    if (!info || !info.text) return;
                    var a = document.createElement('a');
                    a.className = 'thanks-link';
                    a.textContent = info.text;
                    a.href = '#';
                    if (info.links) {
                        var allUrls = Object.values(info.links);
                        a.addEventListener('click', function(e) {
                            e.preventDefault();
                            allUrls.forEach(function(u) {
                                if (u && JM()) JFC.bridge.callWithArgs('openExternal', u);
                            });
                        });
                    }
                    grid.appendChild(a);
                    if (i < entries.length-1) {
                        var s = document.createElement('span');
                        s.className = 'thanks-link-sep'; s.textContent = ' · ';
                        grid.appendChild(s);
                    }
                });
            }

            // 赞助列表
            if (tbody && data.sponsors && Array.isArray(data.sponsors)) {
                tbody.innerHTML = '';
                data.sponsors.forEach(function(s) {
                    var tr = document.createElement('tr');
                    tr.innerHTML = '<td>'+(s.date||'')+'</td><td class="sponsor-amount">'+(s.currency||'')+(s.amount||'')+'</td><td>'+(s.user||'')+'</td>';
                    tbody.appendChild(tr);
                });
                startAutoScroll('sponsor-scroll', 'sponsor');
            }

            // 技术参考
            if (refList && data.reference && Array.isArray(data.reference)) {
                refList.innerHTML = '';
                data.reference.forEach(function(ref) {
                    var d = document.createElement('div'); d.className = 'about-ref-item';
                    if (ref.link) {
                        var a = document.createElement('a'); a.textContent = ref.title || ref.link; a.href = '#';
                        a.addEventListener('click', function(e) { e.preventDefault(); if (JM()) JFC.bridge.callWithArgs('openExternal', ref.link); });
                        d.appendChild(a);
                    } else if (ref.title) { d.textContent = ref.title; }
                    refList.appendChild(d);
                });
                startAutoScroll('ref-scroll', 'ref');
            }
        });
    }

    function startAutoScroll(containerId, key) {
        var el = document.getElementById(containerId);
        if (!el) return;
        if (scrollAnims[key]) clearInterval(scrollAnims[key]);

        var dir = 1;        // 1=向下, -1=向上
        var paused = false;

        el.onmouseenter = function() { paused = true; };
        el.onmouseleave = function() { paused = false; };

        function tick() {
            if (paused) { scrollAnims[key] = setTimeout(tick, 50); return; }
            var max = el.scrollHeight - el.clientHeight;
            if (max <= 0) { scrollAnims[key] = setTimeout(tick, 200); return; }

            var frac = el.scrollTop / max;

            if (frac >= 0.99) { dir = -1; el.scrollTop = max; }
            else if (frac <= 0.01) { dir = 1; el.scrollTop = 0; }

            el.scrollTop += dir * 0.4;
            scrollAnims[key] = setTimeout(tick, 16);
        }

        // 等两次渲染帧再开始，确保 DOM 已布局
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                tick();
            });
        });
    }


    // ==================== 关于（异步） ====================

    function loadAboutData() {
        if (aboutInited) return;
        aboutInited = true;
        if (!JM()) return;

        JFC.bridge.fetchAboutAsync(function(type, data) {
            if (!data) return;
            setText('about-app-name', data.appName || '极峰多聊');
            setText('about-app-author', 'by ' + (data.appAuthor || '吾峰起浪'));
            renderLinkGrid('about-home-grid', data.home);
            renderLinkGrid('about-project-grid', data.project);
        });
    }

    function renderLinkGrid(cId, m) {
        var c = el(cId); if (!c || !m) return; c.innerHTML = '';
        Object.entries(m).forEach(function(kv) {
            var v = kv[1]; if (v && v.text) {
                var a = document.createElement('a'); a.textContent = v.text; a.href = '#';
                if (v.links) {
                    var allUrls = Object.values(v.links);
                    a.addEventListener('click', function(e) {
                        e.preventDefault();
                        allUrls.forEach(function(u) { if (u && JM()) JFC.bridge.callWithArgs('openExternal', u); });
                    });
                }
                c.appendChild(a);
            }
        });
    }

    // ==================== 导航 ====================

    function showSection(name) {
        currentSection = name;
        document.querySelectorAll('#settings-nav li').forEach(function(item) {
            item.classList.toggle('active', item.getAttribute('data-setting') === name);
        });
        document.querySelectorAll('#settings-content > div').forEach(function(div) { div.style.display = 'none'; });
        var target = el('settings-section-' + name);
        if (target) target.style.display = '';
        if (name === 'config')  { initConfigSection(); loadConfigData(); }
        if (name === 'update')  { loadUpdateData(); }
        if (name === 'thanks')  { loadThanksData(); }
        if (name === 'about')   { loadAboutData(); }
    }

    // ==================== 辅助 ====================

    function renderPresets(containerId, presets, targetId) {
        var c = el(containerId); if (!c) return; c.innerHTML = '';
        presets.forEach(function(p) {
            var b = document.createElement('button'); b.className = 'config-preset-btn'; b.textContent = p.name;
            b.addEventListener('click', function() { setVal(targetId, p.value); });
            c.appendChild(b);
        });
    }

    function showMsg(msg, isErr) {
        var e = el('cfg-save-msg'); if (!e) return;
        e.textContent = msg; e.className = 'config-msg' + (isErr ? ' error' : ''); e.style.display = '';
        setTimeout(function() { e.style.display = 'none'; }, 3000);
    }

    function showEl(id, text, cls) {
        var e = el(id); if (!e) return;
        e.textContent = text; e.className = cls; e.style.display = '';
    }
    function hideEl(id) { var e = el(id); if (e) e.style.display = 'none'; }
    function getVal(id) { var e = el(id); return e ? e.value.trim() : ''; }
    function setVal(id, val) { var e = el(id); if (e) e.value = val; }
    function setText(id, text) { var e = el(id); if (e) e.textContent = text; }

    return { init: init, showSection: showSection, setTheme: setTheme };
})();
