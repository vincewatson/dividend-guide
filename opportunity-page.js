/* A股红利机会值 · 页面渲染 / 图表
   2026-10-08 由 红利机会值/index.html 并入主站（不再是独立页面 / iframe）。
   数据：优先 window.opportunityData —— 由 index.html 内嵌兜底，运行时 fetch /data/opportunity.json 覆盖。
   对外挂 window.OpportunityPage：{ setData(d), show(), render(), draw() }，供主站路由（applyRoute）与数据加载器调用。
   所有选择器限定在 #subOpportunity 子树内，避免与主站全局样式/元素冲突。 */
(function () {
  var root = document.getElementById('subOpportunity');
  if (!root) return;

  var BANDS = [[80, 100, "机会很多", "积极加仓"], [60, 80, "机会较多", "加仓"], [40, 60, "中性区间", "持有"], [20, 40, "机会偏少", "暂停加仓"], [0, 20, "机会很少", "减仓"]];
  var JUDGE = { up: ["up", "上行空间"], dn: ["dn", "下行风险"], rel: ["rel", "相对全A"] };
  var C = { brand: "#4680FD", red: "#dc2626", idx: "#949494", grid: "#e5e5e5", axis: "#737373", ink: "#000000" };
  var $ = function (id) { return document.getElementById(id); };
  var r0 = function (v) { return Math.round(v); };
  var bandOf = function (v) { return BANDS.find(function (b) { return v >= b[0] && (v < b[1] || b[1] === 100); }); };
  var colorOf = function (v) { return v >= 60 ? C.brand : (v >= 40 ? C.ink : C.red); };

  var years = 3;
  var DATA = (window.opportunityData && window.opportunityData.schema) ? window.opportunityData : null;
  var chartBound = false;

  function render() {
    if (!DATA) return;
    var s = r0(DATA.score), b = bandOf(s);
    $('oppSub').textContent = '参照指数：' + DATA.index.replace(/([\u4e00-\u9fa5])(\d)/, '$1 $2') + ' · 数据截至' + DATA.asof + ' · 本页信息仅供交流学习之用，不作为投资建议';
    $('oppUpd').textContent = '更新于' + DATA.asof;
    $('oppScore').innerHTML = s + '<small>/100</small>';
    $('oppScore').style.color = colorOf(s);
    var chip = $('oppBand');
    chip.textContent = b[0] + '–' + b[1] + ' · ' + b[2];
    chip.style.background = 'rgba(70,128,253,0.1)';
    chip.style.color = colorOf(s);
    $('oppAdvice').textContent = b[3];
    $('oppSummary').textContent = DATA.summary;
    $('oppHorizon').textContent = DATA.horizon;
    $('oppHorizonNote').textContent = DATA.horizonNote;
    $('oppCmp').innerHTML = Object.entries(DATA.compare).map(function (kv) {
      return '<div><small>' + kv[0] + '</small><b style="color:' + colorOf(r0(kv[1])) + '">' + r0(kv[1]) + '</b></div>';
    }).join('');
    $('oppCore').innerHTML = DATA.core.map(function (c) {
      return '<tr><td><b>' + c.name + '</b></td><td class="num">' + c.value + '</td>' +
        '<td><div class="scorebar"><div class="track"><i style="width:' + c.score + '%;background:' + (c.score >= 50 ? C.brand : C.red) + '"></i></div><b class="num">' + r0(c.score) + '</b></div></td>' +
        '<td class="col-num num">' + c.weight + '%</td>' +
        '<td>' + c.judge.map(function (j) { return '<span class="tag ' + JUDGE[j][0] + '">' + JUDGE[j][1] + '</span>'; }).join('') + '</td></tr>';
    }).join('');
    $('oppBands').innerHTML = BANDS.map(function (d, i) {
      var r = DATA.bands[4 - i], now = (d === b), col = d[0] >= 60 ? C.brand : (d[0] >= 40 ? '#949494' : C.red);
      return '<tr class="' + (now ? 'now' : '') + '"><td><span class="sw2" style="background:' + col + '"></span>' + d[0] + '–' + d[1] + (now ? '（当前）' : '') + '</td>' +
        '<td>' + d[2] + ' · ' + d[3] + '</td>' +
        '<td class="col-num num">' + r[0] + '</td>' +
        '<td class="col-num num" style="color:' + (r[1] >= 0 ? '#dc2626' : '#059661') + '">' + (r[1] >= 0 ? '+' : '−') + Math.abs(r[1]).toFixed(1) + '%</td>' +
        '<td class="col-num num">' + r[2] + '%</td>' +
        '<td class="col-num num">−' + Math.abs(r[3]).toFixed(1) + '%</td></tr>';
    }).join('');
    $('oppObs').innerHTML = DATA.observe.map(function (o) {
      return '<tr><td><b>' + o.name + '</b></td><td class="num">' + o.value + '</td><td class="muted">' + o.note + '</td></tr>';
    }).join('');
    $('oppNoteMethod').textContent = DATA.method;
    $('oppNoteCore').innerHTML = DATA.core.map(function (c) { return '<li><b>' + c.name + '</b>：' + (c.calc || '') + '</li>'; }).join('');
    $('oppNoteObs').innerHTML = DATA.observe.map(function (o) { return '<li><b>' + o.name + '</b>：' + (o.calc || '') + '</li>'; }).join('');
  }

  function isVisible() { return root.classList.contains('active'); }

  function slice() {
    var S = DATA.series;
    if (!years) return S;
    var last = new Date(S.d[S.d.length - 1]);
    var from = new Date(last); from.setFullYear(last.getFullYear() - years);
    var i = S.d.findIndex(function (d) { return new Date(d) >= from; });
    if (i < 0) i = 0;
    return { d: S.d.slice(i), v: S.v.slice(i), p: S.p.slice(i) };
  }

  function draw() {
    if (!DATA || !isVisible()) return;
    var svg = $('oppChart'), tip = $('oppTip'), S = slice(), n = S.v.length;
    if (!svg || !n) return;
    var W = svg.clientWidth || 900, H = svg.clientHeight || 320, m = { l: 34, r: 56, t: 14, b: 26 }, iw = W - m.l - m.r, ih = H - m.t - m.b;
    var t0 = +new Date(S.d[0]), t1 = +new Date(S.d[n - 1]);
    var x = function (i) { return m.l + (+new Date(S.d[i]) - t0) / (t1 - t0) * iw; };
    var y = function (v) { return m.t + (1 - v / 100) * ih; };
    var pmin = Math.min.apply(null, S.p), pmax = Math.max.apply(null, S.p);
    var st = pmax - pmin > 1500 ? 500 : 250, lo = Math.floor(pmin / st) * st, hi = Math.ceil(pmax / st) * st;
    var yp = function (v) { return m.t + (1 - (v - lo) / (hi - lo)) * ih; };
    var F = 'Arial,"Helvetica Neue",Helvetica,sans-serif';
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    var s = '<defs><clipPath id="oppAb"><rect x="' + m.l + '" y="' + m.t + '" width="' + iw + '" height="' + (y(50) - m.t) + '"/></clipPath><clipPath id="oppBe"><rect x="' + m.l + '" y="' + y(50) + '" width="' + iw + '" height="' + (m.t + ih - y(50)) + '"/></clipPath></defs>';
    [0, 20, 40, 60, 80, 100].forEach(function (v) {
      s += '<line x1="' + m.l + '" x2="' + (m.l + iw) + '" y1="' + y(v) + '" y2="' + y(v) + '" stroke="' + C.grid + '" stroke-dasharray="' + (v === 20 || v === 80 ? '4 4' : '') + '"/>' +
        '<text x="' + (m.l - 8) + '" y="' + (y(v) + 4) + '" text-anchor="end" font-size="14" font-family=\'' + F + '\' fill="' + C.axis + '">' + v + '</text>';
    });
    [lo, hi].forEach(function (v) {
      s += '<text x="' + (m.l + iw + 8) + '" y="' + (yp(v) + 4) + '" font-size="14" font-family=\'' + F + '\' fill="' + C.idx + '">' + v + '</text>';
    });
    var ticks = 5;
    for (var k = 0; k < ticks; k++) {
      var tt = t0 + (t1 - t0) * k / (ticks - 1), dtx = new Date(tt);
      var lab = dtx.getFullYear() + '-' + String(dtx.getMonth() + 1).padStart(2, '0');
      var xx = m.l + (tt - t0) / (t1 - t0) * iw;
      s += '<text x="' + xx + '" y="' + (H - 6) + '" text-anchor="' + (k === 0 ? 'start' : (k === ticks - 1 ? 'end' : 'middle')) + '" font-size="14" font-family=\'' + F + '\' fill="' + C.axis + '">' + lab + '</text>';
    }
    var pts = S.v.map(function (v, i) { return x(i).toFixed(1) + ',' + y(v).toFixed(1); }).join(' ');
    var area = m.l + ',' + y(50) + ' ' + pts + ' ' + x(n - 1) + ',' + y(50);
    s += '<polygon points="' + area + '" fill="' + C.brand + '" fill-opacity="0.14" clip-path="url(#oppAb)"/><polygon points="' + area + '" fill="' + C.brand + '" fill-opacity="0.06" clip-path="url(#oppBe)"/>';
    // 中证红利指数点位线：用图表网格横线的浅灰（C.grid），比原来的 C.idx 更浅（2026-10-08 用户要求，与标注数据的灰色横线一致）
    s += '<polyline points="' + S.p.map(function (v, i) { return x(i).toFixed(1) + ',' + yp(v).toFixed(1); }).join(' ') + '" fill="none" stroke="' + C.grid + '" stroke-width="1.2" stroke-linejoin="round"/>';
    s += '<line x1="' + m.l + '" x2="' + (m.l + iw) + '" y1="' + y(50) + '" y2="' + y(50) + '" stroke="' + C.ink + '" stroke-width="1"/>';
    s += '<polyline points="' + pts + '" fill="none" stroke="' + C.brand + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
    var lv = S.v[n - 1];
    s += '<circle cx="' + x(n - 1) + '" cy="' + y(lv) + '" r="4.5" fill="' + C.brand + '" stroke="#fff" stroke-width="2"/>';
    s += '<line id="oppHl" y1="' + m.t + '" y2="' + (m.t + ih) + '" stroke="' + C.axis + '" stroke-dasharray="3 3" visibility="hidden"/><circle id="oppHd" r="4" fill="' + C.brand + '" stroke="#fff" stroke-width="2" visibility="hidden"/>';
    svg.innerHTML = s;
    svg.onpointermove = function (e) {
      var r = svg.getBoundingClientRect(), px = (e.clientX - r.left) * (W / r.width);
      var i = 0, best = 1e9;
      for (var k2 = 0; k2 < n; k2++) { var dd = Math.abs(x(k2) - px); if (dd < best) { best = dd; i = k2; } }
      var hl = svg.querySelector('#oppHl'), hd = svg.querySelector('#oppHd');
      hl.setAttribute('x1', x(i)); hl.setAttribute('x2', x(i)); hl.setAttribute('visibility', 'visible');
      hd.setAttribute('cx', x(i)); hd.setAttribute('cy', y(S.v[i])); hd.setAttribute('visibility', 'visible');
      tip.hidden = false;
      tip.innerHTML = '<div class="d">' + S.d[i] + '</div><div class="r"><span class="sw" style="background:' + C.brand + '"></span>红利机会值<b>' + r0(S.v[i]) + '</b></div><div class="r"><span class="sw" style="background:' + C.idx + '"></span>中证红利指数点位<b>' + S.p[i] + '</b></div>';
      var tx = x(i) / W * r.width;
      tip.style.left = (tx > r.width / 2 ? tx - tip.offsetWidth - 12 : tx + 12) + 'px';
    };
    svg.onpointerleave = function () {
      tip.hidden = true;
      var hl = svg.querySelector('#oppHl'), hd = svg.querySelector('#oppHd');
      if (hl) hl.setAttribute('visibility', 'hidden');
      if (hd) hd.setAttribute('visibility', 'hidden');
    };
  }

  function bindChart() {
    if (chartBound) return;
    root.querySelectorAll('.range button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        years = +btn.dataset.y;
        root.querySelectorAll('.range button').forEach(function (o) { o.setAttribute('aria-pressed', String(o === btn)); });
        draw();
      });
    });
    root.querySelectorAll('.hint').forEach(function (h) {
      h.setAttribute('aria-expanded', 'false');
      h.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = h.getAttribute('aria-expanded') === 'true';
        root.querySelectorAll('.hint').forEach(function (x) { x.setAttribute('aria-expanded', 'false'); });
        h.setAttribute('aria-expanded', String(!open));
      });
    });
    chartBound = true;
  }

  // 点击空白处收起说明气泡（限定本子树）
  document.addEventListener('click', function () {
    root.querySelectorAll('.hint').forEach(function (x) { x.setAttribute('aria-expanded', 'false'); });
  });
  // 窗口尺寸变化：仅在本页可见时重绘（隐藏时 clientWidth=0，重绘会得到空图）
  window.addEventListener('resize', function () { if (isVisible()) draw(); });

  window.OpportunityPage = {
    setData: function (d) { if (d && d.schema) { DATA = d; render(); if (isVisible()) draw(); } },
    show: function () { bindChart(); render(); if (isVisible()) draw(); },
    render: render,
    draw: draw
  };

  // 初始：用内嵌兜底数据渲染（浅色文字即可），若本页此刻可见则同时画图
  bindChart();
  render();
  if (isVisible()) draw();
})();
