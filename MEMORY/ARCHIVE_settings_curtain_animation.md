# 存档：设置区域"窗帘"高度动画（改造前，2026-10-05）

> 本文件保存**按平台记录**的旧实现与积累的经验，供回查。
> 改造后规则：展开/收起态与高度**全局统一**（`LocalGlobalConfig`），未启用平台强制展开且不影响全局记录。
> 改造后的说明见 `AGENTS.md` 第二十四节。

---

## 一、旧实现（按平台记录，逐字存档）

### 1. 状态与持久化（per-platform → `LocalSwConfig.json`）

```js
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
```

### 2. 切换平台时的应用（含"跨平台高度丝滑动画"）

```js
        var shouldExpand = settingsCollapsed[swId] !== true;
        var savedH = loadHeightPreference(swId);

        if (shouldExpand) {
            // 展开：先设箭头 + 解除 collapsed，再由 animatePanelHeight 接管高度（避免 applyCurtainState 清除 maxHeight 造成闪屏）
            getEl('manage-settings-panel').classList.remove('collapsed');
            var aUp = document.querySelector('#page-main #handle-arrow-up');
            var aDown = document.querySelector('#page-main #handle-arrow-down');
            if (aUp) aUp.style.display = '';
            if (aDown) aDown.style.display = 'none';
            animatePanelHeight(savedH, null, _prevHeight);
        } else {
            applyCurtainState(false);
            var aUp2 = document.querySelector('#page-main #handle-arrow-up');
            var aDown2 = document.querySelector('#page-main #handle-arrow-down');
            if (aUp2) aUp2.style.display = 'none';
            if (aDown2) aDown2.style.display = '';
        }
```

其中 `_prevHeight` 在 `selectPlatformInternal` 内、切换平台**之前**记录：

```js
    var _prevHeight = 180;
    // selectPlatformInternal 内：
    var panel = getEl('manage-settings-panel');
    if (panel && currentSwId) {
        _prevHeight = panel.getBoundingClientRect().height | 0;
    }
```

### 3. 统一的高度动画（核心）

```js
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
                var c = getEl('manage-settings-content');
                if (c) c.style.maxHeight = targetHeight + 'px';
                if (callback) callback();
            }, 400);
        });
    }
```

### 4. 手动展开/收起

```js
    function toggleSettingsPanel(expand) {
        if (!currentSwId) return;
        var panel = getEl('manage-settings-panel');
        if (!panel) return;

        var arrowUp = document.querySelector('#page-main #handle-arrow-up');
        var arrowDown = document.querySelector('#page-main #handle-arrow-down');

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
```

### 5. 底部分割线拖动

```js
        function onDown(e) {
            if (e.button !== 0) return;
            if (isSettingsCollapsed()) return;   // 收起状态不允许拖动
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
```

---

## 二、经验结晶（踩坑 → 结论，务必保留）

1. **内容区 `max-height` 是高度上限的隐形锁** → 动画前必须把 `#manage-settings-content` 的 `max-height` 设为 `none`，否则面板涨不上去；**动画结束后（400ms 兜底）必须恢复**为 `targetHeight`，否则内容高度=内容高、永不溢出，滚动条不再出现。
2. **JavaFX WebView 的 `transitionend` 不可靠** → 关键收尾一律用 `setTimeout(…, 400)` 兜底（旧 `toggleSettingsPanel` 只依赖 `transitionend`，是潜在隐患；新实现统一走 `animatePanelHeight`）。
3. **`transition:none` 快照与恢复 `transition` 必须在不同帧** → 单 `requestAnimationFrame` 分离"快照帧"与"过渡帧"；`offsetHeight` 强制重排后再改 `maxHeight`。
4. **`getBoundingClientRect().height` 比 `parseInt(style.maxHeight)` 可靠** → 前者是真实渲染高度（含 padding/border），后者可能是 `''`。
5. **收起时 `scrollHeight === 0`** → 要读真实内容高度必须**先 `remove('collapsed')`** 再读，然后快照回 0、再 rAF 过渡，否则动画目标为 0、看起来"没动画"。
6. **inline style 残留** → 收起时设的 `panel.style.maxHeight='0px'` 会盖住后续 `classList.remove('collapsed')`；展开务必显式清空/重设（新实现由 `animatePanelHeight` 统一接管）。
7. **跨平台切换的"丝滑"技巧** → 记录 A 平台当前高度 `_prevHeight`，切到 B 后直接调用同一个 `animatePanelHeight(targetH, null, _prevHeight)`，把"跨平台切换"退化成"同一页面的高度变化"，不引入新分支、不手写 transition。
8. **分割线拖动期间**：`transition:'none'` + 同步 `content.maxHeight = newH - 20`；松手恢复 `transition` 并 `initHandleSvg()`；拖动结束才落库（避免高频写盘）。
9. **拖动需要 min/max 夹取**：`minH = 100`、`maxH = content.scrollHeight + 40`。
10. **把手是"全宽 SVG + 中间曲线"**：`width:100%` + `preserveAspectRatio="none"`，所以 **viewBox 宽度必须随时与元素宽度一致**（窗口 resize 也要调 `initHandleSvg()`），否则把手被横向拉伸/压缩。
11. **收起状态禁止拖动底部分割线**（高度为 0 时拖动会瞬间跳到最小高度、与鼠标脱节），并把拖动区光标切成 `default`。
12. **滚动条刷新时序**：进入平台页后要在 120/350/800/1500ms 多个时间点刷新设置区滚动条（覆盖内容填充与展开动画的时序）。
13. **验证手段**：JavaFX WebView 离屏渲染（`stage.setX(-4000)`）+ `executeScript` 读几何/计算样式，可在不打扰用户的情况下确认真实布局（见 `AGENTS.md` 第二十一节）。
