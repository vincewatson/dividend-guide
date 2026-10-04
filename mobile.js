/* ============================================================
   食息指南 · 移动端排序下拉框（2026-08-17）
   ------------------------------------------------------------
   仅视口 ≤767px 时生效：在表格隐藏表头后，向各列表注入
   <select> 排序控件（升/降序），复用原有全局排序函数与状态，
   不修改原 HTML / JS 逻辑。桌面端不注入。
   ============================================================ */
(function () {
  // 注意：不在加载时按宽度直接 return（2026-10-04）——此前若在 >767px 加载，整段移动层永不初始化，
  //   导致「桌面加载 → 缩窄窗口」时汉堡菜单/抽屉根本不会被构建（不丝滑）。改由文件末尾的断点监听按需启用。

  var CFG = [
    {
      host: 'assetTable', label: '资产排序',
      keyVar: 'assetSortKey', descVar: 'assetSortDesc',
      render: 'renderAssetTable',
      def: null,   // 默认保持现有状态（2026-08-18 简化）
      opts: [['yield','按食息率（从高到低）','desc']]
    },
    {
      host: 'indexListContainer', label: '指数排序',
      keyVar: 'sortKey', descVar: 'sortDesc',
      render: 'renderIndices',
      def: { key: 'listedDate', desc: true },   // 默认按指数发布日期（新→旧）（2026-10-04 用户要求）
      opts: [['listedDate','按发布日期（新→旧）','desc'],['name','按指数简称（A-Z）','asc'],['yieldNum','按指数股息率（从高到低）','desc']]
    },
    {
      host: 'cnEtfListContainer', label: 'ETF排序',
      keyVar: 'cnSortKey', descVar: 'cnSortDesc',
      render: 'renderCnEtf',
      def: { key: 'listedDate', desc: true },   // 默认按基金成立日期（新→旧）（2026-10-04 用户要求）
      opts: [['listedDate','按成立日期（新→旧）','desc'],['name','按ETF简称（A-Z）','asc'],['yieldNum','按挂钩指数股息率（从高到低）','desc'],['feeNum','按管理费（从低到高）','asc']]
    },
    {
      host: 'hketfListContainer', label: 'ETF排序',
      keyVar: 'hkSortKey', descVar: 'hkSortDesc',
      render: 'renderHkEtf',
      def: { key: 'listedDate', desc: true },   // 默认按基金成立日期（新→旧）（2026-10-04 用户要求）
      opts: [['listedDate','按成立日期（新→旧）','desc'],['name','按ETF简称（A-Z）','asc'],['feeNum','按管理费（从低到高）','asc']]
    },
    {
      host: 'monthlyEtfContainer', label: 'ETF排序',
      keyVar: 'monthlyEtfSortKey', descVar: 'monthlyEtfSortDesc',
      render: 'renderMonthlyEtf',
      def: { key: 'divDate', desc: true },   // 默认按最近分红日期（新→旧）（2026-10-04 用户要求）
      opts: [['divDate','按最近分红日期（新→旧）','desc'],['name','按ETF简称（A-Z）','asc'],['yieldNum','按挂钩指数股息率（从高到低）','desc'],['feeNum','按管理费（从低到高）','asc']]
    },
    {
      host: 'monthlyFundContainer', label: '基金排序',
      keyVar: 'monthlyFundSortKey', descVar: 'monthlyFundSortDesc',
      render: 'renderMonthlyFund',
      def: { key: 'divDate', desc: true },   // 默认按最近分红日期（新→旧）（2026-10-04 用户要求）
      opts: [['divDate','按最近分红日期（新→旧）','desc'],['name','按基金简称（A-Z）','asc'],['yieldNum','按挂钩指数股息率（从高到低）','desc'],['feeNum','按管理费（从低到高）','asc']]
    }
  ];

  function buildSelect(cfg) {
    var host = document.getElementById(cfg.host);
    if (!host) return;
    // 去重：容器内（tagbar 后）或容器前已有排序框则不重复注入（resize 重入保护）
    var has = host.querySelector('.mobile-sort-select') ||
              (host.previousElementSibling && host.previousElementSibling.classList.contains('mobile-sort-select'));
    if (has) return;
    var sel = document.createElement('select');
    sel.className = 'mobile-sort-select';
    sel.setAttribute('aria-label', cfg.label);

    if (!cfg.def) {   // 默认排序项：仅在无具体默认方式时显示（2026-08-18 语言规范）
      var def = document.createElement('option');
      def.value = '';
      def.textContent = '\u9ed8\u8ba4\u6392\u5e8f';
      sel.appendChild(def);
    }

    cfg.opts.forEach(function (o) {   // 固定方向单选项（2026-08-18 简化）
      var k = o[0], label = o[1], dir = o[2] || 'asc';
      var opt = document.createElement('option');
      opt.value = k + ':' + dir;
      opt.textContent = label;
      sel.appendChild(opt);
    });

    // 重建时恢复当前排序状态（render 会清空容器，observer 重建后保持）
    var curKey = window[cfg.keyVar];
    if (curKey) sel.value = curKey + ':' + (window[cfg.descVar] ? 'desc' : 'asc');

    sel.addEventListener('change', function () {
      if (!sel.value) {
        // 重置为默认顺序
        window[cfg.keyVar] = null;
        window[cfg.descVar] = false;
        if (typeof window[cfg.render] === 'function') window[cfg.render]();
        return;
      }
      var parts = sel.value.split(':');
      window[cfg.keyVar] = parts[0];
      window[cfg.descVar] = parts[1] === 'desc';
      if (typeof window[cfg.render] === 'function') window[cfg.render]();
    });

    placeSelect(sel, host);
    return sel;
  }

  // 排序工具定位：有筛选器的板块（红利指数浏览器/境内红利ETF）→ 插到筛选器与列表之间（2026-08-17 用户要求）
  // 2026-10-04：筛选器在手机端收进 .mf-bar 工具条，故优先插到 .mf-bar 之后
  function placeSelect(sel, host) {
    var bar = host.querySelector('.mf-bar');               // 手机端筛选工具条（漏斗 + 筛选器）首选
    var cnt = host.querySelector('.cn-etf-count');          // 境内红利ETF：筛选计数
    var tb  = host.querySelector('.index-tagbar');         // 两个板块的筛选器（手机端已隐藏）
    if (bar) { host.insertBefore(sel, bar.nextSibling); return; }
    if (cnt) { host.insertBefore(sel, cnt.nextSibling); return; }
    if (tb)  { host.insertBefore(sel, tb.nextSibling);  return; }
    host.parentNode.insertBefore(sel, host);               // 无筛选器：保持容器前（原逻辑）
  }

  // 页面加载后注入（等原脚本定义好排序函数/状态）
  function run() {
    if (window.innerWidth > 767) return;
    _ensureCnYield();
    var sels = {};
    CFG.forEach(function (cfg) {
      var s = buildSelect(cfg);
      if (s) sels[cfg.host] = s;
    });
    // 应用各列表默认排序（2026-10-04 用户要求：指数/ETF 默认按日期降序，月月分红默认按最近分红日期降序；食息保持现有）
    // 注意：初次加载时数据 fetch 可能未完成，render 抛异常不能中断其余列表（2026-08-18 修复）
    CFG.forEach(function (cfg) {
      if (!cfg.def || window[cfg.keyVar] != null) return;
      window[cfg.keyVar] = cfg.def.key;
      window[cfg.descVar] = !!cfg.def.desc;
      var s = sels[cfg.host];
      if (s) s.value = cfg.def.key + ':' + (cfg.def.desc ? 'desc' : 'asc');
      try { if (typeof window[cfg.render] === 'function') window[cfg.render](); } catch (e) {}
    });
    initHamburger();
  }

  // ===== 汉堡菜单（2026-08-17 用户要求：默认折叠）=====
  function initHamburger() {
    if (window.innerWidth > 767) return;
    document.querySelectorAll('.top-bar').forEach(function (bar) {
      try {
      if (bar.querySelector('.mobile-hamburger')) return;
      var btn = document.createElement('button');
      btn.className = 'mobile-hamburger';
      btn.setAttribute('aria-label', '菜单');
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = '<span class="hb-bar"></span><span class="hb-bar"></span><span class="hb-bar"></span>';
      var nr = bar.querySelector('.nav-right');
      var prof = document.getElementById('profileBtn');
      if (prof && bar.contains(prof)) prof.parentNode.insertBefore(btn, prof);
      else if (nr) nr.insertBefore(btn, nr.firstChild);   /* 详情页无 profileBtn：汉堡放 nav-right 内（五角星旁边），2026-08-17 修复跑到中间 */
      else bar.appendChild(btn);
      // 全屏菜单移到 body 顶层（参考 elevenreader，2026-08-17）
      var nav = bar.querySelector('.main-nav');
      if (nav) {
        // 顶部：logo + 右上角 ✕ 关闭按钮
        if (!nav.querySelector('.m-nav-drawer-header')) {
          var hdr = document.createElement('div');
          hdr.className = 'm-nav-drawer-header';
          hdr.innerHTML = '<span class="m-drawer-logo">食息指南</span>';
          var closeBtn = document.createElement('button');
          closeBtn.className = 'm-nav-close';
          closeBtn.setAttribute('aria-label', '关闭菜单');
          closeBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path stroke="currentColor" stroke-width="1.5" d="M4.929 19.071 19.07 4.93M4.929 4.929 19.07 19.07"/></svg>';
          closeBtn.addEventListener('click', function () { closeMenu(nav, btn); });
          hdr.appendChild(closeBtn);
          nav.insertBefore(hdr, nav.firstChild);
        }
        // 菜单项包进列表容器（等距竖排）
        if (!nav.querySelector('.m-nav-list')) {
          var list = document.createElement('div');
          list.className = 'm-nav-list';
          while (nav.children.length > 1) list.appendChild(nav.children[1]);   // 保留 header，其余移入列表
          nav.appendChild(list);
        }
        // 移除 ▼ 箭头（mobile 菜单纯文本，2026-08-17）
        nav.querySelectorAll('.arrow').forEach(function (a) { a.remove(); });
        // 二级菜单去 emoji（用户要求：mobile 菜单简化，2026-08-17；桌面保留原样）
        nav.querySelectorAll('.dropdown-item').forEach(function (d) {
          var t = d.textContent.replace(/^[\s\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]+/u, '');
          if (t !== d.textContent) d.textContent = t;
        });
        // 一级菜单去掉所有 emoji（用户要求：mobile 菜单简化，2026-08-17）
        nav.querySelectorAll('.main-nav-item').forEach(function (it) {
          var tc = it.firstChild;
          if (tc && tc.nodeType === 3) {
            var m = tc.textContent.match(/^(\s*)([\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}])\s*/u);
            if (m) tc.textContent = tc.textContent.slice(m[0].length);
          }
        });
        // 一级带子层级的项 → 标记 has-sub + 注入 svg 右箭头（与二级返回按钮同款线条，2026-08-17）
        nav.querySelectorAll('.main-nav-item').forEach(function (it) {
          var dd = it.querySelector('.dropdown');
          if (dd && dd.querySelector('.dropdown-item')) {
            it.classList.add('has-sub');
            if (!it.querySelector('.m-nav-arrow')) {
              var arrow = document.createElement('span');
              arrow.className = 'm-nav-arrow';
              arrow.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path stroke="currentColor" stroke-width="1.5" d="m10 6 6 6-6 6"/></svg>';
              it.appendChild(arrow);
            }
          }
        });
        // 二级菜单：抽屉内第二层（点击一级带子项的项 → 第二层滑入，返回按钮 + 分组标题）
        nav.querySelectorAll('.main-nav-item').forEach(function (it) {
          var dd = it.querySelector('.dropdown');
          if (!dd || !dd.querySelector('.dropdown-item')) return;
          var sub = document.createElement('div');
          sub.className = 'm-nav-sub';
          // 返回 header
          var sh = document.createElement('div');
          sh.className = 'm-nav-sub-header';
          var back = document.createElement('button');
          back.className = 'm-nav-sub-back';
          back.setAttribute('aria-label', '返回');
          back.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path stroke="currentColor" stroke-width="1.5" d="M14 6l-6 6 6 6"/></svg>';
          back.addEventListener('click', function () { sub.classList.remove('open'); });
          // 分组标题 + 子项（先移走子项，否则标题会带上子项文本）
          var sl = document.createElement('div');
          sl.className = 'm-nav-sub-list';
          while (dd.firstChild) sl.appendChild(dd.firstChild);
          var title = document.createElement('span');
          title.className = 'm-nav-sub-title';
          title.textContent = it.textContent.trim();   // 此时 dropdown 已空 → 纯标题
          sh.appendChild(back);
          sh.appendChild(title);
          sub.appendChild(sh);
          sub.appendChild(sl);
          nav.appendChild(sub);
          it._sub = sub;
        });
      }
      if (nav) {
        nav.classList.add('m-nav-drawer');
        if (nav.parentNode !== document.body) document.body.appendChild(nav);
        nav._btn = btn;   // 反向引用（关闭时找到对应汉堡按钮）
      }
      btn._nav = nav;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var nav = btn._nav;
        if (!nav) return;
        var open = nav.classList.toggle('menu-open');
        btn.classList.toggle('open', open);
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (window.__closeAllDropdown) window.__closeAllDropdown();
        document.body.style.overflow = open ? 'hidden' : '';
        toggleMask(open);
        if (open) syncMenuActive(nav);
      });
      } catch (err) { /* 单个 top-bar 异常不影响其他 */ }
    });
  }



  // 菜单项点击/点击外部 → 收起（捕获阶段：主脚本的 stopPropagation 不影响）
  document.addEventListener('click', function (e) {
    if (window.innerWidth > 767) return;
    document.querySelectorAll('.m-nav-drawer').forEach(function (nav) {
      if (!nav.classList.contains('menu-open')) return;
      var btn = nav._btn;
      var inNav = e.target.closest && e.target.closest('.m-nav-drawer') === nav;
      if (!inNav) { closeMenu(nav, btn); return; }
      // 一级带子项 → 打开第二层；无子项/子项 → 切页后收起（2026-08-17 二级层交互）
      var item = e.target.closest('.main-nav-item');
      var subItem = e.target.closest('.dropdown-item');
      if (subItem) {
        // 同步移动端二级菜单选中态（粗体只落在当前选中项，2026-08-17）
        var subParent = subItem.closest('.m-nav-sub');
        if (subParent) {
          subParent.querySelectorAll('.dropdown-item').forEach(function (d) { d.classList.remove('active'); });
          subItem.classList.add('active');
        }
        closeMenu(nav, btn);
      } else if (item) {
        var sub = item._sub;
        if (sub) {
          if (window.__closeAllDropdown) window.__closeAllDropdown();
          nav.querySelectorAll('.m-nav-sub.open').forEach(function (s) { if (s !== sub) s.classList.remove('open'); });
          sub.classList.add('open');
          e.stopPropagation();   // 仅展开二级，阻止主脚本切页：点一级不跳转，选中二级子项才跳（2026-08-17 用户要求）
        } else {
          closeMenu(nav, btn);   // 无子项：放行主脚本切页
        }
      }
    });
  }, true);

  // 打开菜单时：把二级菜单选中态同步到当前所在页面（粗体规则，2026-08-17）
  // 修复：必须基于当前激活的 .page 查 sub-page（pageIndex 隐藏后其 sub-page 会残留 active，2026-08-17）
  function syncMenuActive(nav) {
    if (!nav) return;
    nav.querySelectorAll('.m-nav-sub .dropdown-item').forEach(function (d) { d.classList.remove('active'); });
    var activePage = document.querySelector('.page.active');
    var cur = activePage ? activePage.querySelector('.sub-page.active') : null;
    if (!cur) return;
    var key = cur.id.replace(/^sub/, '');
    key = key.charAt(0).toLowerCase() + key.slice(1);
    nav.querySelectorAll('.m-nav-sub .dropdown-item').forEach(function (d) {
      if (d.getAttribute('data-sub') === key) d.classList.add('active');
    });
  }
  function closeMenu(nav, btn) {
    nav.classList.remove('menu-open');
    if (btn) btn.classList.remove('open');
    if (nav) nav.querySelectorAll('.m-nav-sub.open').forEach(function (s) { s.classList.remove('open'); });
    document.body.style.overflow = '';
    hideMask();
  }
  // 背景遮罩（抽屉打开时压暗页面，点击关闭）
  function ensureMask() {
    var m = document.querySelector('.m-nav-mask');
    if (!m) {
      m = document.createElement('div');
      m.className = 'm-nav-mask';
      m.addEventListener('click', function () {
        document.querySelectorAll('.m-nav-drawer.menu-open').forEach(function (nv) {
          closeMenu(nv, nv._btn);
        });
      });
      document.body.appendChild(m);
    }
    return m;
  }
  function toggleMask(open) {
    ensureMask().classList.toggle('show', !!open);
  }
  function hideMask() {
    var m = document.querySelector('.m-nav-mask');
    if (m) m.classList.remove('show');
  }
  // render 会清空容器内子元素（innerHTML），用 MutationObserver 在重建后恢复排序工具
  CFG.forEach(function (cfg) {
    var host = document.getElementById(cfg.host);
    if (!host) return;
    var obs = new MutationObserver(function () {
      if (window.innerWidth > 767) return;
      requestAnimationFrame(function () {
        // select 可能位于容器内（tagbar 后）或容器前（无筛选器板块），两种位置都检查
        var inside = host.querySelector('.mobile-sort-select');
        var before = host.previousElementSibling &&
                     host.previousElementSibling.classList.contains('mobile-sort-select');
        if (!inside && !before) buildSelect(cfg);
        // 兜底：主脚本词法绑定直接调用原渲染函数（表格 HTML）时，替换为移动版卡片
        // （window.renderXxx 覆写只拦截 window 路径，函数声明绑定无法覆写，2026-08-17）
        if (_mIsMobile()) {
          if (host.id === 'assetTable' && host.querySelector('.asset-row')) { renderAssetTableMobile(); return; }
          if (host.id === 'indexListContainer' && host.querySelector('.index-table')) { renderIndicesMobile(); return; }
          if (host.id === 'cnEtfListContainer' && host.querySelector('.index-table')) { renderCnEtfMobile(); return; }
        }
      });
    });
    obs.observe(host, { childList: true, subtree: false });
  });

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(run, 0);
  } else {
    window.addEventListener('DOMContentLoaded', run);
  }
  // ===== 断点监听：宽屏↔窄屏 自动启用/还原移动层（2026-10-04）=====
  // 目标：桌面加载后缩窄窗口时，汉堡菜单/抽屉能即时构建（丝滑）；手机↔横竖屏切换时补注入排序框。
  var _lastIsMobile = window.innerWidth <= 767;
  var _resizeRaf = false;
  function _rerenderListsForMode() {
    ['renderAssetTable', 'renderIndices', 'renderCnEtf', 'renderHkEtf', 'renderMonthlyEtf', 'renderMonthlyFund', 'renderBlogList']
      .forEach(function (fn) { try { if (typeof window[fn] === 'function') window[fn](); } catch (e) {} });
  }
  window.addEventListener('resize', function () {
    if (_resizeRaf) return;                       // rAF 节流：一帧内只处理一次
    _resizeRaf = true;
    requestAnimationFrame(function () {
      _resizeRaf = false;
      var nowMobile = window.innerWidth <= 767;
      if (nowMobile) {
        // 进入手机端（或手机端内排序框丢失）：注入排序框 + 构建汉堡菜单/抽屉；跨断点进入时把表格重渲染为移动卡片
        if (nowMobile !== _lastIsMobile ||
            !document.querySelector('.mobile-sort-select') ||
            !document.querySelector('.mobile-hamburger')) {
          run();
          if (nowMobile !== _lastIsMobile) _rerenderListsForMode();
        }
      } else if (_lastIsMobile) {
        // 回到桌面：抽屉已把导航搬到 body 并原地改造（丢失 ▼ 箭头/emoji），无法无损还原 → 重载
        // 页面为 hash 路由，重载后停留在同一子页
        if (document.querySelector('.m-nav-drawer')) window.location.reload();
      }
      _lastIsMobile = nowMobile;
    });
  });
})();

// ============ 移动端独立渲染层（2026-08-17 中间态）============
// 思路：移动端不再"表格 + CSS 改卡片"，而是独立渲染函数直接生成卡片 HTML。
// 数据（assetData/indexData/cnEtfData）、筛选/排序函数（idxTagFilter/sortData 等）、
// 详情函数（showAssetDetail 等）仍复用主脚本；渲染与交互代码物理隔离在本文件。
var _mIsMobile = function () { return window.innerWidth <= 767; };
/* 默认排序兜底：数据加载完成后的 render 调用必然经过这里（2026-08-18 修复 run() 时序脆弱） */
function _ensureDef(kv, dv, dflt) {
  if (dflt && window[kv] == null) {
    window[kv] = dflt.key;
    window[dv] = !!dflt.desc;
  }
}
/* 境内ETF 挂钩指数股息率字段注入（渲染时兜底，数据加载完成后必然执行；2026-08-18 修复 run() 过早） */
function _ensureCnYield() {
  if (!window.cnEtfData || typeof _trackIdx !== 'function') return;
  cnEtfData.forEach(function (e) {
    if (e.yieldNum != null) return;
    var tx = _trackIdx(e.trackCode);
    var v = tx ? tx.yieldNum : null;
    if (v == null && tx && tx.yield) v = parseFloat(tx.yield);
    if (v == null && e.yield) v = parseFloat(e.yield);
    e.yieldNum = (v != null) ? v : -1;
  });
}
var _origRenderAssetTable = window.renderAssetTable;
var _origRenderIndices = window.renderIndices;
var _origRenderCnEtf = window.renderCnEtf;
var _origRenderHkEtf = window.renderHkEtf;
var _origRenderMonthlyEtf = window.renderMonthlyEtf;
var _origRenderMonthlyFund = window.renderMonthlyFund;

function _esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

/* ---------- 主流资产食息率（移动卡片） ---------- */
function renderAssetTableMobile() {
  var asd = document.getElementById('assetSubInfo');
  if (asd) asd.textContent = '在低利率时代，专注生息资产，构建属于你自己的被动收入体系，为自己打造赚钱分身';
  var items = (assetData || []).slice();
  if (assetSortKey) {
    items.sort(function (a, b) {
      var r = smartCompare(a[assetSortKey], b[assetSortKey], assetSortKey);
      if (r === 0) { var ca = String(a.name || ''), cb = String(b.name || ''); r = ca.localeCompare(cb, 'zh-Hans-CN'); }
      return assetSortDesc ? -r : r;
    });
  }
  var h = '<div class="m-list">';
  items.forEach(function (item) {
    var tc = (typeColors && typeColors[item.type]) || { color: '#737373' };
    var fav = (favorites || []).indexOf(item.name) > -1;
    // listNote 是主脚本 renderAssetTable 的嵌套函数（非全局），移动层内联同款逻辑（2026-08-17）
    var note = item.name === '中证同业存单AAA指数' ? '同业存单指数年化收益率' : (item.note || '');
    var nm = _esc(item.name);
    /* 2026-09-27 Tier1-④：食息率移到右上角放大，指标名（note）作其下小标签；
       数字沿用类型色，保留原「颜色跟随类型标签」的意图。 */
    var hasY = !!(item.yield && String(item.yield).trim());
    var stat = hasY ? _mStat(item.yield, note, tc.color) : '';
    var metaBits = [];
    if (!hasY && note) metaBits.push(_esc(note));
    if (item.source) metaBits.push(_esc(item.source));
    metaBits.push(_esc(item.date || '—'));
    h += '<div class="m-card" onclick="showAssetDetail(\'' + nm + '\')">' +
      '<div class="m-card-top"><span class="m-type" style="color:' + tc.color + '">' + _esc(item.type) + '</span>' + stat + '</div>' +
      '<div class="m-card-name">' + nm + '</div>' +
      '<div class="m-card-meta">' + metaBits.join(' · ') + '</div>' +
      '<div class="m-card-fav"><span class="fav-btn' + (fav ? ' active' : '') + '" data-fav="' + nm.replace(/"/g, '&quot;') + '" onclick="event.stopPropagation();toggleFav(this.dataset.fav)">' + (fav ? '⭐' : '☆') + '</span></div>' +
    '</div>';
  });
  h += '</div>';
  document.getElementById('assetTable').innerHTML = h;
}

function _hexA(hex, a) {  /* 胶囊跟随类型色的辅助（2026-08-18） */
  var m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
  if (!m) return hex || '#737373';
  var n = parseInt(m[1], 16);
  return 'rgba(' + ((n >> 16) & 255) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + a + ')';
}

/* ---------- 红利指数浏览器（移动卡片） ---------- */
function renderIndicesMobile() {
  /* 仅展示「有挂钩产品发行」的指数；trackOnly 为详情页图表补充的跟踪指数（2026-10-04），不进列表 */
  var _allIdx = (indexData || []).filter(function (x) { return !x.trackOnly; });
  var items = _allIdx.slice();
  var f = idxTagFilter || {};
  if (f.theme || f.market || f.adjust || f.publisher) {
    items = items.filter(function (idx) {
      if (f.theme && !idxTagMatch(idx, 'theme', f.theme)) return false;
      if (f.market && !idxTagMatch(idx, 'market', f.market)) return false;
      if (f.adjust && !idxTagMatch(idx, 'adjust', f.adjust)) return false;
      if (f.publisher && !idxTagMatch(idx, 'publisher', f.publisher)) return false;
      return true;
    });
  }
  if (sortKey) items = sortData(items, sortKey, sortDesc);
  else items.sort(function (a, b) { return (b.fundCount || 0) - (a.fundCount || 0); });

  /* 移动卡片：名称 / 代码·市场·币种 / 股息率蓝胶囊 + 本年涨跌胶囊
     （2026-10-04 用户要求：股息率由「右上角大数字」改为浅蓝底蓝字胶囊，置于「本年」胶囊之前；右上角不再放大数字） */
  var h = '<div class="m-list">';
  items.forEach(function (idx) {
    var hasYr = (typeof idx.yrChange === 'number') && !!idx.dailyDate;
    var yc = hasYr ? _mPill('本年' + _pct(idx.yrChange), idx.yrChange >= 0 ? 'up' : 'down') : '';  /* 无数据不显示胶囊（2026-08-18） */
    var hasYd = !!(idx.yield && String(idx.yield).trim());
    var yd = hasYd ? _mPill('股息率' + _esc(idx.yield), 'blue') : '';   /* 浅蓝底 / 蓝字数据胶囊（2026-10-04） */
    var pills = yd + yc;
    h += '<div class="m-card" onclick="showIndexDetail(\'' + _esc(idx.code) + '\')">' +
      '<div class="m-card-top"><span class="m-name">' + _esc(idx.name) + '</span></div>' +
      '<div class="m-card-meta">' + _esc(idx.code) + ' · ' + _esc(idx.market || '') + ' · ' + _esc(idx.currency || '') + '</div>' +
      (pills ? '<div class="m-card-pcts">' + pills + '</div>' : '') +
    '</div>';
  });
  h += '</div>';
  var c = document.getElementById('indexListContainer');
  c.innerHTML = (typeof mfBarHtml === 'function' ? mfBarHtml('idx', '共<b>' + items.length + '</b>/' + _allIdx.length + '只') : '') +
                (idxTagBarHtml ? idxTagBarHtml() : '') + h;
  if (typeof mfSyncBadge === 'function') mfSyncBadge('idx');   /* 同步手机端筛选器徽标（2026-10-04） */
  var sub = document.getElementById('indexSubInfo');
  if (sub) {
    sub.textContent = '本表仅展示有挂钩产品发行的' + _allIdx.length + '个指数 · 数据更新至' + (dailyDateLabel || '');
  }
}

/* ---------- 境内红利 ETF（移动卡片） ---------- */
function renderCnEtfMobile() {
  _ensureCnYield();
  var items = (cnEtfData || []).slice();
  var f = cnEtfTagFilter || {};
  if (f.theme || f.market || f.fee || f.company) {
    items = items.filter(function (e) {
      if (f.theme && cnEtfThemeOf(e.trackName) !== f.theme) return false;
      if (f.market && cnEtfMarketOf(e.trackName) !== f.market) return false;
      if (f.fee && cnEtfFeeBand(e.feeNum) !== f.fee) return false;
      if (f.company && cnEtfCompanyShort(e.manager) !== f.company) return false;
      return true;
    });
  }
  if (cnSortKey) {
    items.sort(function (a, b) {
      var r = smartCompare(a[cnSortKey], b[cnSortKey], cnSortKey);
      if (r === 0) { var ca = String(a.code || ''), cb = String(b.code || ''); r = ca.localeCompare(cb, 'zh-Hans-CN'); }
      return cnSortDesc ? -r : r;
    });
  }
  /* 移动卡片：三行结构（简称/代码·挂钩指数/对应指数股息率蓝胶囊 + 本年涨跌胶囊），右上角无数字
     （2026-10-04 用户要求：对应指数股息率由「右上角大数字」改为浅蓝底/蓝字胶囊，与红利指数浏览器同一逻辑） */
  var h = '<div class="cn-etf-count" style="font-size:12px;color:#767676;margin:2px 0 8px">共' + items.length + '/' + (cnEtfData || []).length + '只</div>';
  h += '<div class="m-list">';
  items.forEach(function (e) {
    var tx = _trackIdx(e.trackCode);
    var _ey = e.yield || (tx && tx.yield ? tx.yield : '');
    var yd = _ey ? _mPill('对应指数股息率' + _esc(_ey), 'blue') : '';   /* 浅蓝底 / 蓝字胶囊（2026-10-04） */
    var yr = (typeof e.yrChange === 'number') ? _mPill('本年' + _pct(e.yrChange), e.yrChange >= 0 ? 'up' : 'down') : '';  /* 无数据不显示胶囊（2026-08-18） */
    var pills = yd + yr;
    h += '<div class="m-card" onclick="showCnEtfDetail(\'' + _esc(e.code) + '\')">' +
      '<div class="m-card-top"><span class="m-name">' + _esc(e.name) + '</span></div>' +
      '<div class="m-card-meta">' + _esc(e.code) + ' · ' + _esc(e.trackName || '') + _mFee(e) + '</div>' +
      (pills ? '<div class="m-card-pcts">' + pills + '</div>' : '') +
    '</div>';
  });
  h += '</div>';
  var c = document.getElementById('cnEtfListContainer');
  c.innerHTML = (typeof mfBarHtml === 'function' ? mfBarHtml('cnetf', '共<b>' + items.length + '</b>/' + (cnEtfData || []).length + '只') : '') +
                (cnEtfTagBarHtml ? cnEtfTagBarHtml() : '') + h;
  if (typeof mfSyncBadge === 'function') mfSyncBadge('cnetf');   /* 同步手机端筛选器徽标（2026-10-04） */
}


/* ---------- 移动卡片通用 helper（2026-08-17 用户要求：五列表三行结构统一） ---------- */
function _mPill(text, cls) { return '<span class="m-pct ' + cls + '">' + text + '</span>'; }
/* 右上角「大数字」块（Tier1-④，2026-09-27）：关键数字放大 + 指标名小字在下。
   替代原先「指标名+数值」同挤一颗 11px 胶囊的写法（数字被埋没）。 */
function _mStat(num, label, color) {
  if (!num) return '';
  return '<span class="m-stat"><b class="m-stat-num"' + (color ? ' style="color:' + color + '"' : '') + '>' + _esc(num) + '</b>' + (label ? '<i class="m-stat-lb">' + _esc(label) + '</i>' : '') + '</span>';
}
/* 管理费字段（2026-08-18 用户要求：四列表卡片第二行追加"管理费率x.xx%"） */
function _mFee(o) {
  var v = o && o.feeNum;
  if (typeof v !== 'number' || isNaN(v)) return '';
  return ' · 管理费率' + (v * 100).toFixed(2) + '%';
}
function _pct(v) { return (v * 100).toFixed(2) + '%'; }
var _trackIdxMap = null;
function _trackIdx(code) {
  if (!_trackIdxMap) { _trackIdxMap = {}; (indexData || []).forEach(function (x) { _trackIdxMap[x.code] = x; }); }
  return _trackIdxMap[code];
}

/* ---------- 港交所红利 ETF（移动卡片，三行；对应指数股息率=有数据才显示） ---------- */
function renderHkEtfMobile() {
  var items = (hkEtfData || []).slice();
  if (hkSortKey) {
    items.sort(function (a, b) {
      var r = smartCompare(a[hkSortKey], b[hkSortKey], hkSortKey);
      if (r === 0) { var ca = String(a.code || ''), cb = String(b.code || ''); r = ca.localeCompare(cb, 'zh-Hans-CN'); }
      return hkSortDesc ? -r : r;
    });
  }
  var h = '<div class="m-list">';
  items.forEach(function (etf) {
    /* 对应指数股息率：港交所源头数据无 yield 字段，按「跟踪指数代码」到指数库匹配
       （与境内红利ETF同逻辑）；匹配到才显示蓝胶囊，匹配不到则不显示（2026-10-04 用户要求：有数据的就加，没数据的就不加） */
    var tx = _trackIdx(etf.trackCode);
    var _ey = etf.yield || (tx && tx.yield ? tx.yield : '');
    var yd = _ey ? _mPill('对应指数股息率' + _esc(_ey), 'blue') : '';   /* 浅蓝底 / 蓝字胶囊（2026-10-04） */
    var yr = (typeof etf.yrChange === 'number') ? _mPill('本年' + _pct(etf.yrChange), etf.yrChange >= 0 ? 'up' : 'down') : '';  /* 无数据不显示胶囊（2026-08-18） */
    var pills = yd + yr;
    h += '<div class="m-card" onclick="showHkEtfDetail(\'' + _esc(etf.code) + '\')">' +
      '<div class="m-card-top"><span class="m-name">' + _esc(etf.name) + '</span>' + (etf.connect ? '<span class="m-tag-connect">互联互通</span>' : '') + '</div>' +  /* 互联互通蓝底白字标签（2026-08-18 用户要求） */
      '<div class="m-card-meta">' + _esc(etf.code) + ' · ' + _esc(etf.trackName || '') + _mFee(etf) + '</div>' +
      (pills ? '<div class="m-card-pcts">' + pills + '</div>' : '') +
    '</div>';
  });
  h += '</div>';
  var c = document.getElementById('hketfListContainer');
  if (c) c.innerHTML = h;
}

/* ---------- ETF 月月分红（移动卡片，三行） ---------- */
function renderMonthlyEtfMobile() {
  var items = (etfData || []).slice();
  if (monthlyEtfSortKey) {
    items.sort(function (a, b) {
      var r = smartCompare(a[monthlyEtfSortKey], b[monthlyEtfSortKey], monthlyEtfSortKey);
      if (r === 0) { var ca = String(a.code || ''), cb = String(b.code || ''); r = ca.localeCompare(cb, 'zh-Hans-CN'); }
      return monthlyEtfSortDesc ? -r : r;
    });
  }
  var h = '<div class="m-list">';
  items.forEach(function (etf) {
    var yd = etf.yield ? _mPill('对应指数股息率' + _esc(etf.yield), 'blue') : '';   /* 浅蓝底 / 蓝字胶囊（2026-10-04：替代右上角大数字） */
    var yr = (typeof etf.yrChange === 'number') ? _mPill('本年' + _pct(etf.yrChange), etf.yrChange >= 0 ? 'up' : 'down') : '';  /* 无数据不显示胶囊（2026-08-18） */
    var pills = yd + yr;
    h += '<div class="m-card" onclick="showMonthlyEtfDetail(\'' + _esc(etf.code) + '\')">' +
      '<div class="m-card-top"><span class="m-name">' + _esc(etf.name) + '</span></div>' +
      '<div class="m-card-meta">' + _esc(etf.code) + ' · ' + _esc(etf.trackName || '') + _mFee(etf) + '</div>' +
      (pills ? '<div class="m-card-pcts">' + pills + '</div>' : '') +
    '</div>';
  });
  h += '</div>';
  var c = document.getElementById('monthlyEtfContainer');
  if (c) c.innerHTML = h;
}

/* ---------- 指数基金月月分红（移动卡片，三行） ---------- */
function renderMonthlyFundMobile() {
  var items = (fundData || []).slice();
  if (monthlyFundSortKey) {
    items.sort(function (a, b) {
      var r = smartCompare(a[monthlyFundSortKey], b[monthlyFundSortKey], monthlyFundSortKey);
      if (r === 0) { var ca = String(a.code || ''), cb = String(b.code || ''); r = ca.localeCompare(cb, 'zh-Hans-CN'); }
      return monthlyFundSortDesc ? -r : r;
    });
  }
  var h = '<div class="m-list">';
  items.forEach(function (f) {
    var yd = f.yield ? _mPill('对应指数股息率' + _esc(f.yield), 'blue') : '';   /* 浅蓝底 / 蓝字胶囊（2026-10-04：替代右上角大数字） */
    var yr = (typeof f.yrChange === 'number') ? _mPill('本年' + _pct(f.yrChange), f.yrChange >= 0 ? 'up' : 'down') : '';  /* 无数据不显示胶囊（2026-08-18） */
    var pills = yd + yr;
    h += '<div class="m-card" onclick="showMonthlyFundDetail(\'' + _esc(f.code) + '\')">' +
      '<div class="m-card-top"><span class="m-name">' + _esc(f.name) + '</span></div>' +
      '<div class="m-card-meta">' + _esc(f.code) + ' · ' + _esc(f.trackName || '') + _mFee(f) + '</div>' +
      (pills ? '<div class="m-card-pcts">' + pills + '</div>' : '') +
    '</div>';
  });
  h += '</div>';
  var c = document.getElementById('monthlyFundContainer');
  if (c) c.innerHTML = h;
}

/* ---------- 覆写：移动端走独立渲染，桌面走原函数 ---------- */
window.renderAssetTable = function () { if (_mIsMobile()) { renderAssetTableMobile(); return; } _origRenderAssetTable(); };
window.renderIndices   = function () { if (_mIsMobile()) { _ensureDef('sortKey', 'sortDesc', { key: 'listedDate', desc: true }); renderIndicesMobile();   return; } _origRenderIndices(); };
window.renderCnEtf     = function () { if (_mIsMobile()) { _ensureDef('cnSortKey', 'cnSortDesc', { key: 'listedDate', desc: true }); renderCnEtfMobile();     return; } _origRenderCnEtf(); };
window.renderHkEtf     = function () { if (_mIsMobile()) { _ensureDef('hkSortKey', 'hkSortDesc', { key: 'listedDate', desc: true }); renderHkEtfMobile();     return; } _origRenderHkEtf(); };
window.renderMonthlyEtf = function () { if (_mIsMobile()) { _ensureDef('monthlyEtfSortKey', 'monthlyEtfSortDesc', { key: 'divDate', desc: true }); renderMonthlyEtfMobile(); return; } _origRenderMonthlyEtf(); };
window.renderMonthlyFund = function () { if (_mIsMobile()) { _ensureDef('monthlyFundSortKey', 'monthlyFundSortDesc', { key: 'divDate', desc: true }); renderMonthlyFundMobile(); return; } _origRenderMonthlyFund(); };

// 覆写后立即按移动端重渲染（覆写前的初始渲染是桌面表格）
if (_mIsMobile()) {
  setTimeout(function () {
    try { window.renderAssetTable(); } catch (e) {}
    try { window.renderIndices(); } catch (e) {}
    try { window.renderCnEtf(); } catch (e) {}
    try { window.renderHkEtf(); } catch (e) {}
    try { window.renderMonthlyEtf(); } catch (e) {}
    try { window.renderMonthlyFund(); } catch (e) {}
  }, 0);
}

