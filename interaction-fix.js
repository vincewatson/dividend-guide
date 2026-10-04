/* ============================================================
   食息指南 · 交互兜底与触屏适配（2026-08-17）
   ------------------------------------------------------------
   背景：Safari 隐私模式 localStorage 抛 SecurityError 会中断主脚本，
   导致其后所有 addEventListener（下拉菜单/图表时间选项）失效。
   本文件在 <body> 开头加载（早于主脚本），用 document 级事件委托
   保证交互可用；主脚本正常时（__mainReady=true）委托仅做触屏
   dropdown 切换，不重复执行主逻辑。
   ============================================================ */
(function () {
  'use strict';

  // ---- 1. 触屏下拉：点击导航项切换显示（不依赖 :hover）----
  document.addEventListener('click', function (e) {
    var item = e.target.closest ? e.target.closest('.main-nav-item') : null;
    if (item && !(e.target.closest && e.target.closest('.dropdown-item'))) {
      var d = item.querySelector('.dropdown');
      if (d) {
        var wasOpen = item.classList.contains('dropdown-open');
        closeAllDropdown();
        if (!wasOpen) item.classList.add('dropdown-open');
        return;
      }
    }
    // 点击其他区域关闭所有下拉
    closeAllDropdown();
  });

  function closeAllDropdown() {
    var list = document.querySelectorAll('.main-nav-item.dropdown-open');
    for (var i = 0; i < list.length; i++) list[i].classList.remove('dropdown-open');
  }
  window.__closeAllDropdown = closeAllDropdown;

  // ---- 2. 下拉菜单项兜底（主脚本绑定失效时仍可用）----
  document.addEventListener('click', function (e) {
    var it = e.target.closest ? e.target.closest('.dropdown-item') : null;
    if (!it || !it.dataset || !it.dataset.sub) return;
    var nav = it.closest('.main-nav-item');
    var sub = it.dataset.sub;
    var pageId = (nav && nav.dataset && nav.dataset.tab) || 'pageIndex';
    if (pageId === 'pageMonthly') pageId = 'pageMonthly';

    if (window.__mainReady && typeof switchPage === 'function') {
      return; // 主脚本正常：原 handler 已处理（幂等，委托不再重复）
    }
    // 兜底：主脚本中断时手动切换
    e.stopPropagation();
    document.querySelectorAll('.main-nav-item').forEach(function (t) { t.classList.remove('active'); });
    document.querySelectorAll('.page').forEach(function (p) { p.classList.remove('active'); });
    var tab = document.querySelector('.main-nav-item[data-tab="' + pageId + '"]');
    if (tab) tab.classList.add('active');
    var pg = document.getElementById(pageId);
    if (pg) pg.classList.add('active');
    document.querySelectorAll('#' + pageId + ' .sub-page').forEach(function (p) { p.classList.remove('active'); });
    var subEl = document.getElementById('sub' + sub.charAt(0).toUpperCase() + sub.slice(1));
    if (subEl) subEl.classList.add('active');
    var sc = nav ? nav.querySelectorAll('.dropdown-item') : [];
    for (var i = 0; i < sc.length; i++) sc[i].classList.remove('active');
    it.classList.add('active');
    closeAllDropdown();
    closeAllDropdown();
  });

  // ---- 3. 图表时间选项 change 兜底（主脚本绑定失效时）----
  var RANGE_MAP = {
    detailChartRange:          { st: 'detailSliderState',          detail: null, special: true },
    assetDetailChartRange:     { st: 'assetSliderState',           detail: 'assetDetail' },
    monthlyEtfDetailChartRange:{ st: 'monthlyEtfSliderState',      detail: 'monthlyEtfDetail' },
    cnEtfDetailChartRange:     { st: 'cnEtfSliderState',           detail: 'cnEtfDetail' },
    hkEtfDetailChartRange:     { st: 'hkEtfSliderState',           detail: 'hkEtfDetail' },
    monthlyFundDetailChartRange:{ st: 'monthlyFundSliderState',    detail: 'monthlyFundDetail' }
  };
  document.addEventListener('change', function (e) {
    var t = e.target;
    if (!t || t.tagName !== 'SELECT' || !t.id || !RANGE_MAP[t.id]) return;
    if (window.__mainReady) return; // 主脚本正常：原 handler 已处理
    var cfg = RANGE_MAP[t.id];
    var st = window[cfg.st];
    if (!st || !st.hist || !st.hist.length) return;
    var r = t.value;
    var months = r === 'max' ? 9999 : (r === '3y' ? 36 : (r === '1y' ? 12 : (r === '6m' ? 6 : 1)));
    var p0 = monthsToRangePct(st.hist, months);
    if (cfg.special) {
      sliderSetRange(p0, 100, false);
      sliderRenderChart();
    } else {
      sliderSetRange(p0, 100, false, st, cfg.detail);
      sliderRenderChart(st, cfg.detail);
    }
  });
})();
