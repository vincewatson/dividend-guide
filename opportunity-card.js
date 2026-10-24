/* 红利机会卡（样式 A：白底 · 蓝框）—— 生成 / 下载 / 分享（2026-10-12）
   ---------------------------------------------------------------------------
   入口：在「A股红利机会值」页（#subOpportunity）蓝框 .reminder 的**右上角**自动注入
        「分享机会卡」按钮 → 点击居中弹出卡面。
   卡面：整张用 SVG 现场生成（750 宽、高度自适应），折行用 <canvas>.measureText 精确度量
        （与渲染同字体）并做中文「禁则」处理（行首不出现 ，。、；：）》等），因此换行/断句可控。
   控件布局（2026-10-12 用户要求）：卡面右上角**只放关闭 ✕**；「下载图片 / 分享」放在卡面
        **右下方、图外**，避免与 ✕ 挤在一起。
        （2026-10-17）移动端（≤767px）改为：✕ 左边只放「下载」，底部那排分享按钮整行隐藏。
   分享：点「分享」在按钮**下方浮出选项**（微信 / 朋友圈 / 复制链接 / 保存图片）——
        微信、朋友圈在桌面端弹二维码（用微信扫一扫打开后转发），在微信内置浏览器给出
        「点右上角 ⋯ 分享」引导。二维码为固定矢量路径，指向机会值页。
   对外：window.OpportunityCard = { open(d?), close(), build(d) }
   --------------------------------------------------------------------------- */
(function () {
  'use strict';
  var TARGET_URL = 'https://divlab.net/#/index/opportunity';
  var QR_PATH = "M0,0H1V1H0zM1,0H2V1H1zM2,0H3V1H2zM3,0H4V1H3zM4,0H5V1H4zM5,0H6V1H5zM6,0H7V1H6zM10,0H11V1H10zM12,0H13V1H12zM13,0H14V1H13zM18,0H19V1H18zM22,0H23V1H22zM23,0H24V1H23zM24,0H25V1H24zM25,0H26V1H25zM26,0H27V1H26zM27,0H28V1H27zM28,0H29V1H28zM0,1H1V2H0zM6,1H7V2H6zM8,1H9V2H8zM10,1H11V2H10zM14,1H15V2H14zM16,1H17V2H16zM17,1H18V2H17zM20,1H21V2H20zM22,1H23V2H22zM28,1H29V2H28zM0,2H1V3H0zM2,2H3V3H2zM3,2H4V3H3zM4,2H5V3H4zM6,2H7V3H6zM8,2H9V3H8zM9,2H10V3H9zM12,2H13V3H12zM15,2H16V3H15zM18,2H19V3H18zM22,2H23V3H22zM24,2H25V3H24zM25,2H26V3H25zM26,2H27V3H26zM28,2H29V3H28zM0,3H1V4H0zM2,3H3V4H2zM3,3H4V4H3zM4,3H5V4H4zM6,3H7V4H6zM8,3H9V4H8zM10,3H11V4H10zM11,3H12V4H11zM12,3H13V4H12zM13,3H14V4H13zM15,3H16V4H15zM16,3H17V4H16zM17,3H18V4H17zM19,3H20V4H19zM20,3H21V4H20zM22,3H23V4H22zM24,3H25V4H24zM25,3H26V4H25zM26,3H27V4H26zM28,3H29V4H28zM0,4H1V5H0zM2,4H3V5H2zM3,4H4V5H3zM4,4H5V5H4zM6,4H7V5H6zM9,4H10V5H9zM13,4H14V5H13zM14,4H15V5H14zM16,4H17V5H16zM18,4H19V5H18zM19,4H20V5H19zM20,4H21V5H20zM22,4H23V5H22zM24,4H25V5H24zM25,4H26V5H25zM26,4H27V5H26zM28,4H29V5H28zM0,5H1V6H0zM6,5H7V6H6zM11,5H12V6H11zM20,5H21V6H20zM22,5H23V6H22zM28,5H29V6H28zM0,6H1V7H0zM1,6H2V7H1zM2,6H3V7H2zM3,6H4V7H3zM4,6H5V7H4zM5,6H6V7H5zM6,6H7V7H6zM8,6H9V7H8zM10,6H11V7H10zM12,6H13V7H12zM14,6H15V7H14zM16,6H17V7H16zM18,6H19V7H18zM20,6H21V7H20zM22,6H23V7H22zM23,6H24V7H23zM24,6H25V7H24zM25,6H26V7H25zM26,6H27V7H26zM27,6H28V7H27zM28,6H29V7H28zM8,7H9V8H8zM10,7H11V8H10zM12,7H13V8H12zM14,7H15V8H14zM15,7H16V8H15zM16,7H17V8H16zM18,7H19V8H18zM19,7H20V8H19zM20,7H21V8H20zM0,8H1V9H0zM6,8H7V9H6zM8,8H9V9H8zM9,8H10V9H9zM17,8H18V9H17zM19,8H20V9H19zM21,8H22V9H21zM22,8H23V9H22zM25,8H26V9H25zM26,8H27V9H26zM27,8H28V9H27zM0,9H1V10H0zM1,9H2V10H1zM10,9H11V10H10zM12,9H13V10H12zM13,9H14V10H13zM14,9H15V10H14zM15,9H16V10H15zM18,9H19V10H18zM19,9H20V10H19zM20,9H21V10H20zM23,9H24V10H23zM24,9H25V10H24zM26,9H27V10H26zM27,9H28V10H27zM0,10H1V11H0zM1,10H2V11H1zM2,10H3V11H2zM3,10H4V11H3zM4,10H5V11H4zM6,10H7V11H6zM8,10H9V11H8zM9,10H10V11H9zM10,10H11V11H10zM12,10H13V11H12zM13,10H14V11H13zM14,10H15V11H14zM15,10H16V11H15zM16,10H17V11H16zM20,10H21V11H20zM21,10H22V11H21zM24,10H25V11H24zM2,11H3V12H2zM3,11H4V12H3zM4,11H5V12H4zM8,11H9V12H8zM9,11H10V12H9zM10,11H11V12H10zM12,11H13V12H12zM13,11H14V12H13zM16,11H17V12H16zM19,11H20V12H19zM21,11H22V12H21zM23,11H24V12H23zM25,11H26V12H25zM1,12H2V13H1zM2,12H3V13H2zM3,12H4V13H3zM5,12H6V13H5zM6,12H7V13H6zM7,12H8V13H7zM9,12H10V13H9zM11,12H12V13H11zM13,12H14V13H13zM15,12H16V13H15zM19,12H20V13H19zM20,12H21V13H20zM22,12H23V13H22zM23,12H24V13H23zM28,12H29V13H28zM0,13H1V14H0zM4,13H5V14H4zM5,13H6V14H5zM8,13H9V14H8zM9,13H10V14H9zM11,13H12V14H11zM15,13H16V14H15zM16,13H17V14H16zM17,13H18V14H17zM19,13H20V14H19zM22,13H23V14H22zM23,13H24V14H23zM24,13H25V14H24zM27,13H28V14H27zM28,13H29V14H28zM5,14H6V15H5zM6,14H7V15H6zM9,14H10V15H9zM11,14H12V15H11zM15,14H16V15H15zM18,14H19V15H18zM20,14H21V15H20zM21,14H22V15H21zM25,14H26V15H25zM26,14H27V15H26zM3,15H4V16H3zM5,15H6V16H5zM7,15H8V16H7zM8,15H9V16H8zM9,15H10V16H9zM11,15H12V16H11zM12,15H13V16H12zM18,15H19V16H18zM19,15H20V16H19zM23,15H24V16H23zM24,15H25V16H24zM26,15H27V16H26zM28,15H29V16H28zM1,16H2V17H1zM2,16H3V17H2zM4,16H5V17H4zM5,16H6V17H5zM6,16H7V17H6zM15,16H16V17H15zM16,16H17V17H16zM17,16H18V17H17zM18,16H19V17H18zM19,16H20V17H19zM21,16H22V17H21zM23,16H24V17H23zM25,16H26V17H25zM26,16H27V17H26zM0,17H1V18H0zM1,17H2V18H1zM2,17H3V18H2zM3,17H4V18H3zM5,17H6V18H5zM7,17H8V18H7zM9,17H10V18H9zM13,17H14V18H13zM14,17H15V18H14zM15,17H16V18H15zM16,17H17V18H16zM17,17H18V18H17zM18,17H19V18H18zM19,17H20V18H19zM22,17H23V18H22zM23,17H24V18H23zM24,17H25V18H24zM26,17H27V18H26zM27,17H28V18H27zM28,17H29V18H28zM0,18H1V19H0zM1,18H2V19H1zM3,18H4V19H3zM6,18H7V19H6zM10,18H11V19H10zM11,18H12V19H11zM15,18H16V19H15zM16,18H17V19H16zM19,18H20V19H19zM20,18H21V19H20zM24,18H25V19H24zM25,18H26V19H25zM28,18H29V19H28zM0,19H1V20H0zM2,19H3V20H2zM5,19H6V20H5zM8,19H9V20H8zM9,19H10V20H9zM10,19H11V20H10zM13,19H14V20H13zM15,19H16V20H15zM20,19H21V20H20zM22,19H23V20H22zM0,20H1V21H0zM2,20H3V21H2zM3,20H4V21H3zM4,20H5V21H4zM6,20H7V21H6zM8,20H9V21H8zM10,20H11V21H10zM14,20H15V21H14zM15,20H16V21H15zM16,20H17V21H16zM17,20H18V21H17zM20,20H21V21H20zM21,20H22V21H21zM22,20H23V21H22zM23,20H24V21H23zM24,20H25V21H24zM26,20H27V21H26zM27,20H28V21H27zM28,20H29V21H28zM8,21H9V22H8zM10,21H11V22H10zM14,21H15V22H14zM15,21H16V22H15zM17,21H18V22H17zM18,21H19V22H18zM19,21H20V22H19zM20,21H21V22H20zM24,21H25V22H24zM25,21H26V22H25zM0,22H1V23H0zM1,22H2V23H1zM2,22H3V23H2zM3,22H4V23H3zM4,22H5V23H4zM5,22H6V23H5zM6,22H7V23H6zM9,22H10V23H9zM15,22H16V23H15zM16,22H17V23H16zM17,22H18V23H17zM19,22H20V23H19zM20,22H21V23H20zM22,22H23V23H22zM24,22H25V23H24zM25,22H26V23H25zM26,22H27V23H26zM0,23H1V24H0zM6,23H7V24H6zM9,23H10V24H9zM11,23H12V24H11zM14,23H15V24H14zM15,23H16V24H15zM16,23H17V24H16zM19,23H20V24H19zM20,23H21V24H20zM24,23H25V24H24zM28,23H29V24H28zM0,24H1V25H0zM2,24H3V25H2zM3,24H4V25H3zM4,24H5V25H4zM6,24H7V25H6zM13,24H14V25H13zM14,24H15V25H14zM16,24H17V25H16zM19,24H20V25H19zM20,24H21V25H20zM21,24H22V25H21zM22,24H23V25H22zM23,24H24V25H23zM24,24H25V25H24zM25,24H26V25H25zM28,24H29V25H28zM0,25H1V26H0zM2,25H3V26H2zM3,25H4V26H3zM4,25H5V26H4zM6,25H7V26H6zM9,25H10V26H9zM11,25H12V26H11zM12,25H13V26H12zM14,25H15V26H14zM15,25H16V26H15zM16,25H17V26H16zM19,25H20V26H19zM21,25H22V26H21zM25,25H26V26H25zM26,25H27V26H26zM28,25H29V26H28zM0,26H1V27H0zM2,26H3V27H2zM3,26H4V27H3zM4,26H5V27H4zM6,26H7V27H6zM12,26H13V27H12zM13,26H14V27H13zM15,26H16V27H15zM18,26H19V27H18zM19,26H20V27H19zM21,26H22V27H21zM22,26H23V27H22zM23,26H24V27H23zM24,26H25V27H24zM25,26H26V27H25zM26,26H27V27H26zM27,26H28V27H27zM0,27H1V28H0zM6,27H7V28H6zM9,27H10V28H9zM10,27H11V28H10zM12,27H13V28H12zM16,27H17V28H16zM18,27H19V28H18zM21,27H22V28H21zM24,27H25V28H24zM25,27H26V28H25zM26,27H27V28H26zM28,27H29V28H28zM0,28H1V29H0zM1,28H2V29H1zM2,28H3V29H2zM3,28H4V29H3zM4,28H5V29H4zM5,28H6V29H5zM6,28H7V29H6zM8,28H9V29H8zM9,28H10V29H9zM10,28H11V29H10zM11,28H12V29H11zM13,28H14V29H13zM14,28H15V29H14zM15,28H16V29H15zM16,28H17V29H16zM17,28H18V29H17zM19,28H20V29H19zM21,28H22V29H21zM22,28H23V29H22zM23,28H24V29H23zM24,28H25V29H24zM26,28H27V29H26z";
  var FONT = "Arial,-apple-system,BlinkMacSystemFont,'PingFang SC','Helvetica Neue',sans-serif";
  var CW = 750;                                     /* 卡面逻辑宽度（导出 2x → 1500px） */
  var C = {
    brand: '#4680FD', ink: '#000000', body: '#404040', muted: '#767676', faint: '#a3a3a3',
    red: '#dc2626', green: '#059661', grid: '#e5e5e5', line: 'rgba(0,0,0,0.06)', boxBorder: '#E3EBFC'
  };
  var BANDS = [[80, 100, '机会很多', '积极加仓'], [60, 80, '机会较多', '加仓'], [40, 60, '中性区间', '持有'],
               [20, 40, '机会偏少', '暂停加仓'], [0, 20, '机会很少', '减仓']];
  var LEGEND = [['#4680FD', '红利机会值'], ['#e5e5e5', '中证红利指数点位（右轴）'], ['#000000', '50=中性值']];
  /* 中文禁则：这些字符不能出现在行首（否则连标点一起折到上一行） */
  var NO_START = '，。、；：！？）》」』”’·…～%!?),.;:';
  var IS_WX = /MicroMessenger/i.test(navigator.userAgent || '');

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function bandOf(v) {
    for (var i = 0; i < BANDS.length; i++) { if (v >= BANDS[i][0] && (v < BANDS[i][1] || BANDS[i][1] === 100)) return BANDS[i]; }
    return BANDS[2];
  }
  function colorOf(v) { return v >= 60 ? C.red : (v >= 40 ? C.ink : C.green); }

  /* ---------- 文本度量（canvas，与 SVG 同字体 → 折行准确） ---------- */
  var _ctx = null;
  function measure(s, fs) {
    if (!_ctx) { _ctx = document.createElement('canvas').getContext('2d'); }
    _ctx.font = fs + 'px ' + FONT;
    return _ctx.measureText(String(s)).width;
  }
  function wrap(s, maxW, fs) {
    s = String(s == null ? '' : s);
    var out = [], cur = '';
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (cur && measure(cur + ch, fs) > maxW) {
        if (NO_START.indexOf(ch) >= 0 && cur.length > 1) {
          out.push(cur.slice(0, -1));      /* 禁则：把上一行末字一起挪下来，避免标点顶行 */
          cur = cur.slice(-1) + ch;
        } else { out.push(cur); cur = ch; }
      } else { cur += ch; }
    }
    if (cur) out.push(cur);
    return out;
  }
  function T(x, y, s, fs, fill, o) {
    o = o || {};
    return '<text x="' + x + '" y="' + y + '" font-family="' + FONT + '" font-size="' + fs + '" fill="' + fill + '"'
      + (o.weight ? ' font-weight="' + o.weight + '"' : '')
      + (o.anchor ? ' text-anchor="' + o.anchor + '"' : '')
      + (o.tabular ? ' style="font-variant-numeric:tabular-nums"' : '')
      + '>' + esc(s) + '</text>';
  }
  function idxText(s) { return String(s || '').replace(/([\u4e00-\u9fa5])(\d)/, '$1 $2'); }

  /* ---------- 图表折线（近 3 年，抽样 ≤220 点） ---------- */
  function series3y(d) {
    var S = d && d.series;
    if (!S || !S.d || !S.d.length) return null;
    var n0 = S.d.length, last = new Date(S.d[n0 - 1]);
    var from = new Date(last.getFullYear() - 3, last.getMonth(), last.getDate()).getTime();
    var i0 = 0;
    for (var i = 0; i < n0; i++) { if (new Date(S.d[i]).getTime() >= from) { i0 = i; break; } }
    var D = [], V = [], P = [], step = Math.max(1, Math.floor((n0 - i0) / 220));
    for (var k = i0; k < n0; k += step) { D.push(S.d[k]); V.push(S.v[k]); P.push(S.p[k]); }
    if (V.length < 2) return null;
    return { d: D, v: V, p: P };
  }
  function chartContent(S, cw, ch) {
    var m = { l: 52, r: 62, t: 16, b: 44 };
    var iw = cw - m.l - m.r, ih = ch - m.t - m.b, n = S.v.length;
    var t0 = new Date(S.d[0]).getTime(), t1 = new Date(S.d[n - 1]).getTime();
    var X = function (i) { return m.l + (new Date(S.d[i]).getTime() - t0) / (t1 - t0) * iw; };
    var Y = function (v) { return m.t + (1 - v / 100) * ih; };
    var pmin = Math.min.apply(null, S.p), pmax = Math.max.apply(null, S.p);
    var st = (pmax - pmin) > 1500 ? 500 : 250;
    var lo = Math.floor(pmin / st) * st, hi = Math.ceil(pmax / st) * st;
    var YP = function (v) { return m.t + (1 - (v - lo) / (hi - lo)) * ih; };
    var s = '';
    [20, 50, 80].forEach(function (v) {
      s += '<line x1="' + m.l + '" x2="' + (m.l + iw) + '" y1="' + Y(v) + '" y2="' + Y(v) + '" stroke="' + C.grid
        + '" stroke-width="1"' + (v === 50 ? '' : ' stroke-dasharray="4 4"') + '/>';
    });
    [100, 50, 0].forEach(function (v) { s += T(m.l - 10, Y(v) + 7, v, 22, C.faint, { anchor: 'end' }); });
    s += T(m.l + iw + 10, YP(hi) + 7, hi, 22, C.faint);
    s += T(m.l + iw + 10, YP(lo) + 7, lo, 22, C.faint);
    var vp = S.v.map(function (v, i) { return X(i).toFixed(1) + ',' + Y(v).toFixed(1); }).join(' ');
    s += '<polygon points="' + (X(0).toFixed(1) + ',' + Y(50).toFixed(1) + ' ' + vp + ' ' + X(n - 1).toFixed(1) + ',' + Y(50).toFixed(1))
      + '" fill="' + C.brand + '" fill-opacity="0.14"/>';
    s += '<polyline points="' + S.p.map(function (v, i) { return X(i).toFixed(1) + ',' + YP(v).toFixed(1); }).join(' ')
      + '" fill="none" stroke="' + C.grid + '" stroke-width="1.4"/>';
    s += '<polyline points="' + vp + '" fill="none" stroke="' + C.brand + '" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>';
    s += '<circle cx="' + X(n - 1).toFixed(1) + '" cy="' + Y(S.v[n - 1]).toFixed(1) + '" r="5" fill="' + C.brand + '" stroke="#fff" stroke-width="2"/>';
    for (var k = 0; k < 3; k++) {
      var i2 = Math.round((n - 1) * k / 2);
      s += T(X(i2), ch - 12, S.d[i2].slice(0, 7), 22, C.faint,
        { anchor: k === 0 ? 'start' : (k === 2 ? 'end' : 'middle') });
    }
    return s;
  }

  /* ---------- 卡面（样式 A） ---------- */
  function build(d) {
    d = d || window.opportunityData || {};
    var score = Math.round(d.score), b = bandOf(score), bandText = b[0] + '~' + b[1] + ' · ' + b[2];
    var pad = 40, iw0 = CW - pad * 2, parts = [], y = 0;

    /* 头部（主标题缩小、上下留白拉开，避免与相邻文字挤在一起） */
    y = 64;
    parts.push(T(pad, y, '食息指南', 26, C.brand, { weight: 700 }));
    y += 58;
    parts.push(T(pad, y, 'A股红利机会值', 42, C.ink, { weight: 700 }));
    y += 60;
    parts.push(T(pad, y, '参照指数：' + idxText(d.index), 25, C.muted));
    y += 38;
    parts.push(T(pad, y, '数据截至 ' + (d.asof || '—'), 23, C.faint));
    y += 32;

    /* 蓝框：四个区块自上而下排列（2026-10-24 用户要求：机会值 / 当前建议 / 适用周期 / 历史对比） */
    var boxTop = y, ip = 32, cellX = pad + ip, cellW = iw0 - ip * 2;
    var cTop = boxTop + ip;

    /* ① 红利机会值（数字缩小，给其余区块留空间） */
    parts.push(T(cellX, cTop + 24, '红利机会值', 23, C.faint));
    parts.push(T(cellX, cTop + 88, score, 68, colorOf(score), { weight: 700, tabular: true }));
    var scoreW = measure(score, 68);
    parts.push(T(cellX + scoreW + 12, cTop + 88, '/100', 24, C.faint));
    parts.push(T(cellX + scoreW + 12 + measure('/100', 24) + 22, cTop + 88, bandText, 22, colorOf(score), { weight: 700 }));
    var div1 = cTop + 112;
    parts.push('<line x1="' + cellX + '" x2="' + (cellX + cellW) + '" y1="' + div1 + '" y2="' + div1 + '" stroke="rgba(70,128,253,0.16)" stroke-width="1"/>');

    /* ② 当前建议：标签 + 结论同行，说明整幅宽度折行 */
    var rowY = div1 + 38;
    parts.push(T(cellX, rowY, '当前建议', 23, C.faint));
    parts.push(T(cellX + measure('当前建议', 23) + 16, rowY, b[3], 32, C.ink, { weight: 700 }));
    var sumL = wrap(d.summary, cellW, 23);
    sumL.forEach(function (L, k) { parts.push(T(cellX, div1 + 80 + k * 38, L, 23, C.body)); });
    var div2 = div1 + 80 + (sumL.length - 1) * 38 + 27;
    parts.push('<line x1="' + cellX + '" x2="' + (cellX + cellW) + '" y1="' + div2 + '" y2="' + div2 + '" stroke="rgba(70,128,253,0.16)" stroke-width="1"/>');

    /* ③ 适用周期：标签 + 结论同行，说明整幅宽度折行 */
    var hzY = div2 + 38;
    parts.push(T(cellX, hzY, '适用周期', 23, C.faint));
    parts.push(T(cellX + measure('适用周期', 23) + 16, hzY, d.horizon || '—', 30, C.ink, { weight: 700 }));
    var hnL = wrap(d.horizonNote, cellW, 21);
    hnL.forEach(function (L, k) { parts.push(T(cellX, div2 + 80 + k * 34, L, 21, C.muted)); });
    var div3 = div2 + 80 + (hnL.length - 1) * 34 + 27;
    parts.push('<line x1="' + cellX + '" x2="' + (cellX + cellW) + '" y1="' + div3 + '" y2="' + div3 + '" stroke="rgba(70,128,253,0.16)" stroke-width="1"/>');

    /* ④ 历史对比（4 列，与页面蓝框同口径：取整、无小数点） */
    parts.push(T(cellX, div3 + 38, '历史对比', 23, C.faint));
    var labY = div3 + 78, valY = div3 + 124;
    var cmp = d.compare || {}, keys = Object.keys(cmp), colW = cellW / (keys.length || 1);
    keys.forEach(function (k, i) {
      var cx = cellX + colW * i, cv = Math.round(cmp[k]);
      parts.push(T(cx, labY, k, 23, C.faint));
      parts.push(T(cx, valY, cv, 34, colorOf(cv), { weight: 700, tabular: true }));
    });
    var boxBottom = valY + 30;
    parts.unshift('<rect x="' + pad + '" y="' + boxTop + '" width="' + iw0 + '" height="' + (boxBottom - boxTop)
      + '" rx="16" fill="url(#oppBlueGrad)" stroke="' + C.boxBorder + '" stroke-width="1.5"/>');

    /* 图表块（内容先算、外框后画） */
    var chartTop = boxBottom + 28, chX = pad + ip, chW = iw0 - ip * 2, chParts = [];
    chParts.push(T(pad + ip, chartTop + 52, '历史机会值', 30, C.ink, { weight: 700 }));
    chParts.push(T(pad + iw0 - ip, chartTop + 52, '近3年', 24, C.faint, { anchor: 'end' }));
    var S = series3y(d), chH = 210, chTop = chartTop + 74;
    if (S) chParts.push('<g transform="translate(' + chX + ',' + chTop + ')">' + chartContent(S, chW, chH) + '</g>');
    var legY = chTop + chH + 40, lx = pad + ip;
    /* 图例按可用宽度自适应间距，右侧留 20px，避免最后一项贴边/被裁掉（2026-10-24） */
    var legW = LEGEND.map(function (it) { return 30 + measure(it[1], 21); });
    var legFixed = legW.reduce(function (a, b) { return a + b; }, 0);
    var legGap = LEGEND.length > 1 ? Math.min(34, (chW - 20 - legFixed) / (LEGEND.length - 1)) : 0;
    legGap = Math.max(14, legGap);
    LEGEND.forEach(function (it, i) {
      chParts.push('<rect x="' + lx + '" y="' + (legY - 4) + '" width="22" height="' + (it[1] === '50=中性值' ? 1.5 : 3) + '" fill="' + it[0] + '"/>');
      chParts.push(T(lx + 30, legY, it[1], 21, C.faint));
      lx += legW[i] + legGap;
    });
    var chartBottom = legY + 30;
    parts.push('<rect x="' + pad + '" y="' + chartTop + '" width="' + iw0 + '" height="' + (chartBottom - chartTop)
      + '" rx="16" fill="#fff" stroke="' + C.line + '" stroke-width="1.5"/>');
    parts.push(chParts.join(''));

    /* 页脚：说明 + 固定二维码 */
    var footTop = chartBottom + 34, qrS = 158, qrX = CW - pad - qrS, qrY = footTop + 2;
    parts.push(T(pad, footTop + 52, '扫码查看完整页面', 28, C.ink, { weight: 700 }));
    parts.push(T(pad, footTop + 92, '含核心指标、打分参考与观察指标', 23, C.muted));
    parts.push(T(pad, footTop + 128, 'divlab.net', 23, C.faint));
    parts.push('<rect x="' + qrX + '" y="' + qrY + '" width="' + qrS + '" height="' + qrS + '" rx="14" fill="#fff" stroke="rgba(0,0,0,0.08)" stroke-width="1.5"/>');
    var qp = 9;
    parts.push('<g transform="translate(' + (qrX + qp) + ',' + (qrY + qp) + ') scale(' + ((qrS - qp * 2) / 29) + ')"><path d="' + QR_PATH + '" fill="#000000"/></g>');
    var H = Math.max(qrY + qrS, footTop + 144) + 46;

    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + CW + '" height="' + H.toFixed(0) + '" viewBox="0 0 ' + CW + ' ' + H.toFixed(0) + '">'
      + '<defs><linearGradient id="oppBlueGrad" x1="0" y1="0" x2="1" y2="1">'
      + '<stop offset="0" stop-color="#FBFCFE"/><stop offset="1" stop-color="#F0F5FF"/></linearGradient></defs>'
      + '<rect x="0" y="0" width="' + CW + '" height="' + H.toFixed(0) + '" fill="#ffffff"/>'
      /* 整图四周浅灰细线（与主站 Header 下边线同色 rgba(0,0,0,0.06)）；下载到纯白背景也能看出边界 */
      + '<rect x="0.75" y="0.75" width="' + (CW - 1.5) + '" height="' + (H - 1.5) + '" fill="none" stroke="' + C.line + '" stroke-width="1.5"/>'
      + parts.join('') + '</svg>';
  }

  /* ---------- 图标（内联 SVG） ---------- */
  /* 图标取自 IconPark（https://iconpark.oceanengine.com/official），
     原始文件：source/Brand/wechat.svg · source/Brand/friends-circle.svg · source/Edit/copy-link.svg ·
     source/Arrows/download.svg · source/Base/share.svg；已改为 currentColor 以适配任意底色。 */
  var ICO = {
    wx: '<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg"> <path fill-rule="evenodd" clip-rule="evenodd" d="M36.9974 21.7112C36.8434 13.0079 29.7401 6 21 6C12.1634 6 5 13.1634 5 22C5 26.1701 6.59531 29.9676 9.20892 32.8154L8.01043 40.0257L15.125 36.9699C18.2597 38.0122 21.218 38.2728 24 37.7516" fill="currentColor" fill-opacity=".22"/> <path d="M36.9974 21.7112C36.8434 13.0079 29.7401 6 21 6C12.1634 6 5 13.1634 5 22C5 26.1701 6.59531 29.9676 9.20892 32.8154L8.01043 40.0257L15.125 36.9699C18.2597 38.0122 21.218 38.2728 24 37.7516" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M15.125 20.4667C16.3676 20.4667 17.375 19.4519 17.375 18.2C17.375 16.9482 16.3676 15.9333 15.125 15.9333C13.8824 15.9333 12.875 16.9482 12.875 18.2C12.875 19.4519 13.8824 20.4667 15.125 20.4667Z" fill="currentColor"/> <path d="M24.125 20.4667C25.3676 20.4667 26.375 19.4519 26.375 18.2C26.375 16.9482 25.3676 15.9333 24.125 15.9333C22.8824 15.9333 21.875 16.9482 21.875 18.2C21.875 19.4519 22.8824 20.4667 24.125 20.4667Z" fill="currentColor"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M38.7618 39.9293C37.0135 41.2302 34.8467 42 32.5 42C26.701 42 22 37.299 22 31.5C22 25.701 26.701 21 32.5 21C38.299 21 43 25.701 43 31.5C43 33.0997 42.6423 34.6159 42.0024 35.9728" fill="currentColor" fill-opacity=".22"/> <path d="M38.7618 39.9293C37.0135 41.2302 34.8467 42 32.5 42C26.701 42 22 37.299 22 31.5C22 25.701 26.701 21 32.5 21C38.299 21 43 25.701 43 31.5C43 33.0997 42.6423 34.6159 42.0024 35.9728" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M42.0024 35.9728L43 42L38.7618 39.9293" fill="currentColor" fill-opacity=".22"/> <path d="M42.0024 35.9728L43 42L38.7618 39.9293" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M35.6875 30.7999C34.7555 30.7999 34 30.0388 34 29.0999C34 28.161 34.7555 27.3999 35.6875 27.3999C36.6195 27.3999 37.375 28.161 37.375 29.0999C37.375 30.0388 36.6195 30.7999 35.6875 30.7999Z" fill="currentColor"/> <path d="M28.9375 30.7999C28.0055 30.7999 27.25 30.0388 27.25 29.0999C27.25 28.161 28.0055 27.3999 28.9375 27.3999C29.8695 27.3999 30.625 28.161 30.625 29.0999C30.625 30.0388 29.8695 30.7999 28.9375 30.7999Z" fill="currentColor"/> </svg>',
    moments: '<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg"> <path d="M24 44C35.0457 44 44 35.0457 44 24C44 12.9543 35.0457 4 24 4C12.9543 4 4 12.9543 4 24C4 35.0457 12.9543 44 24 44Z" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M31 7V24V7Z" fill="currentColor" fill-opacity=".22"/> <path d="M31 7V24" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M16.6357 6.63599L30.7779 20.7781L16.6357 6.63599Z" fill="currentColor" fill-opacity=".22"/> <path d="M16.6357 6.63599L30.7779 20.7781" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M7 17H24H7Z" fill="currentColor" fill-opacity=".22"/> <path d="M7 17H24" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M20.3643 17.636L6.22212 31.7781L20.3643 17.636Z" fill="currentColor" fill-opacity=".22"/> <path d="M20.3643 17.636L6.22212 31.7781" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M17 25V42V25Z" fill="currentColor" fill-opacity=".22"/> <path d="M17 25V42" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M17.6357 27.636L31.7779 41.7781L17.6357 27.636Z" fill="currentColor" fill-opacity=".22"/> <path d="M17.6357 27.636L31.7779 41.7781" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M24 31L42 31L24 31Z" fill="currentColor" fill-opacity=".22"/> <path d="M24 31L42 31" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path fill-rule="evenodd" clip-rule="evenodd" d="M42.3643 16.636L28.2221 30.7781L42.3643 16.636Z" fill="currentColor" fill-opacity=".22"/> <path d="M42.3643 16.636L28.2221 30.7781" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M24 31C27.866 31 31 27.866 31 24C31 20.134 27.866 17 24 17C20.134 17 17 20.134 17 24C17 27.866 20.134 31 24 31Z" fill="currentColor" fill-opacity=".22" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> </svg>',
    link: '<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg"> <path d="M12 9.92704V7C12 5.34315 13.3431 4 15 4H41C42.6569 4 44 5.34315 44 7V33C44 34.6569 42.6569 36 41 36H38.0174" stroke="currentColor" stroke-width="4"/> <rect x="4" y="10" width="34" height="34" rx="3" fill="currentColor" fill-opacity=".22" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/> <path d="M18.4394 23.1101L23.7319 17.6006C25.1835 16.1489 27.5691 16.1809 29.0602 17.672C30.5513 19.1631 30.5833 21.5487 29.1316 23.0003L27.2215 25.0231" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M13.4661 28.7472C12.9558 29.2575 11.9006 30.2765 11.9006 30.2765C10.4489 31.7281 10.4095 34.3155 11.9006 35.8066C13.3917 37.2977 15.7772 37.3296 17.2289 35.878L22.3931 31.1896" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M18.6626 28.3284C17.97 27.6358 17.5922 26.7502 17.5317 25.8548C17.4619 24.8226 17.8138 23.7774 18.5912 23.0001" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M22.3213 25.8613C23.8124 27.3524 23.8444 29.738 22.3927 31.1896" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> </svg>',
    save: '<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg"> <path d="M6 24.0083V42H42V24" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M33 23L24 32L15 23" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M23.9917 6V32" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> </svg>',
    share: '<svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg"> <path d="M28 6H42V20" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M42 29.4737V39C42 40.6569 40.6569 42 39 42H9C7.34315 42 6 40.6569 6 39V9C6 7.34315 7.34315 6 9 6L18 6" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> <path d="M25.7998 22.1999L41.0998 6.8999" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/> </svg>',
  };

  /* ---------- 样式 ---------- */
  var CSS = [
    /* 页面入口：2026-10-17 起改为蓝框第 4 格（静态按钮 #oppShareBtn），不再绝对定位注入 */
    /* 弹层：卡面居中；✕ 在卡面右上角；下载/分享在卡面**右下方、图外** */
    '.oppCardMask{position:fixed;inset:0;background:rgba(15,23,42,.56);display:flex;align-items:center;justify-content:center;z-index:1000;padding:18px}',
    '.oppCardMask[hidden]{display:none}',
    /* 外层宽度 = 卡面宽度（width:min-content 由卡图决定），按钮行因此在卡宽内自动折行、右对齐 */
    '.oppCardWrap{position:relative;display:flex;flex-direction:column;align-items:center;max-height:100%;width:min-content;max-width:100%}',
    '.oppCardStage{position:relative;display:flex;justify-content:center;min-height:0}',
    '.oppCardBox img{display:block;max-width:min(94vw,470px);max-height:calc(100vh - 172px);width:auto;height:auto;box-shadow:0 18px 44px rgba(8,20,48,.34)}',
    '.oppCardClose{position:absolute;top:10px;right:10px;z-index:3;width:30px;height:30px;border-radius:50%;cursor:pointer;',
    'border:1px solid rgba(0,0,0,.12);background:rgba(255,255,255,.94);color:#525252;font-size:14px;line-height:1;display:flex;align-items:center;justify-content:center}',
    '.oppCardClose:hover{background:#fff;color:#111}',
    '.oppCardClose svg{width:15px;height:15px;display:block}',
    '.oppCardDl{display:none}',
    '.oppCardActions{position:relative;width:100%;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:10px;padding:14px 0 0}',
    /* 圆形图标按钮（无文字；顺序：微信 / 朋友圈 / 复制链接 / 下载到本地） */
    '.oppCardBtn{display:inline-flex;align-items:center;justify-content:center;width:42px;height:42px;padding:0;border-radius:50%;',
    'cursor:pointer;border:1px solid rgba(255,255,255,.34);background:rgba(255,255,255,.14);color:#fff}',
    '.oppCardBtn:hover{background:rgba(255,255,255,.26)}',
    '.oppCardBtn svg{width:20px;height:20px;display:block;flex:none}',
    /* 微信 / 朋友圈：在按钮行上方浮出二维码面板 */
    '.oppWxPanel{position:absolute;right:0;bottom:calc(100% + 10px);background:#fff;border:1px solid rgba(0,0,0,.08);border-radius:14px;',
    'box-shadow:0 12px 34px rgba(8,20,48,.28);padding:14px;text-align:center;width:214px;z-index:4}',
    '.oppWxPanel[hidden]{display:none}',
    '.oppWxPanel img{width:166px;height:166px;display:block;margin:0 auto 10px}',
    '.oppWxPanel b{display:block;font-size:13px;color:#111;margin-bottom:8px}',
    '.oppWxPanel p{font-size:12px;color:#767676;line-height:1.7;margin:0}',
    '.oppToast{position:fixed;left:50%;bottom:36px;transform:translateX(-50%);background:rgba(17,24,39,.92);color:#fff;',
    'font-size:13px;padding:9px 16px;border-radius:999px;z-index:1001;opacity:0;transition:opacity .2s}',
    '.oppToast.on{opacity:1}',
    /* 微信内置浏览器：右上角引导 */
    '.oppWxGuide{position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:1002;color:#fff;padding:24px}',
    '.oppWxGuide[hidden]{display:none}',
    '.oppWxGuide .arrow{position:absolute;top:10px;right:22px;font-size:30px;line-height:1}',
    '.oppWxGuide .tip{position:absolute;top:64px;right:22px;text-align:right;font-size:15px;line-height:1.9}',
    '.oppWxGuide .tip b{color:#7FB2FF}',
    /* 移动端（2026-10-17 用户要求）：只在 ✕ 左边保留「下载」，其余分享按钮整行隐藏。
       必须放在 .oppCardActions 定义之后，否则同权重会被上面的 display:flex 覆盖。 */
    '@media (max-width:767px){.oppCardActions{display:none}.oppCardDl{display:flex;right:48px}}'
  ].join('');

  /* ---------- DOM ---------- */
  function injectStyle() {
    if (document.getElementById('oppCardStyle')) return;
    var st = document.createElement('style'); st.id = 'oppCardStyle'; st.textContent = CSS;
    document.head.appendChild(st);
  }
  function qrDataURL() {
    /* 必须带 width/height：只有 viewBox 的 SVG 放进 <img> 时无固有尺寸（naturalWidth=0） */
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="174" height="174" viewBox="0 0 29 29" shape-rendering="crispEdges">'
      + '<rect width="29" height="29" fill="#fff"/><path d="' + QR_PATH + '" fill="#000"/></svg>';
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }
  var lastSVG = '';
  function svgURL(svg) { return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg); }

  function injectModal() {
    if (document.getElementById('oppCardMask')) return;
    var mask = document.createElement('div');
    mask.className = 'oppCardMask'; mask.id = 'oppCardMask'; mask.hidden = true;
    mask.innerHTML = '<div class="oppCardWrap">'
      + '<div class="oppCardStage">'
      + '<div class="oppCardBox" id="oppCardBox"></div>'
      + '<button type="button" class="oppCardClose oppCardDl" id="oppCardDl" aria-label="下载图片" title="下载图片">' + ICO.save + '</button>'
      + '<button type="button" class="oppCardClose" id="oppCardClose" aria-label="关闭">✕</button>'
      + '</div>'
      + '<div class="oppCardActions" id="oppCardActions">'
      + '<button type="button" class="oppCardBtn" data-act="wx" title="分享到微信" aria-label="分享到微信">' + ICO.wx + '</button>'
      + '<button type="button" class="oppCardBtn" data-act="moments" title="分享到朋友圈" aria-label="分享到朋友圈">' + ICO.moments + '</button>'
      + '<button type="button" class="oppCardBtn" data-act="copy" title="复制链接" aria-label="复制链接">' + ICO.link + '</button>'
      + '<button type="button" class="oppCardBtn" data-act="save" title="下载到本地" aria-label="下载到本地">' + ICO.save + '</button>'
      + '<div class="oppWxPanel" id="oppWxPanel" hidden></div>'
      + '</div></div>';
    document.body.appendChild(mask);

    var guide = document.createElement('div');
    guide.className = 'oppWxGuide'; guide.id = 'oppWxGuide'; guide.hidden = true;
    guide.innerHTML = '<div class="arrow">↗</div><div class="tip">点击右上角 <b>⋯</b><br>选择「发送给朋友」<br>或「分享到朋友圈」</div>';
    guide.addEventListener('click', function () { guide.hidden = true; });
    document.body.appendChild(guide);

    mask.addEventListener('click', function (e) { if (e.target === mask) close(); });
    document.getElementById('oppCardClose').addEventListener('click', close);
    document.getElementById('oppCardDl').addEventListener('click', function () { hideWxPanel(); doDownload(); });
    document.getElementById('oppCardActions').addEventListener('click', function (e) {
      var btn = e.target.closest ? e.target.closest('.oppCardBtn') : null;
      if (!btn) return;
      /* 面板内容会被重写、原点击目标随即脱离 DOM；拦截以免被文档级「点外部关闭」误关 */
      e.stopPropagation();
      shareAct(btn.getAttribute('data-act'));
    });
    document.addEventListener('click', function (e) {
      var p = document.getElementById('oppWxPanel');
      if (!p || p.hidden) return;
      var a = document.getElementById('oppCardActions');
      if (a && a.contains(e.target)) return;
      p.hidden = true;
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !mask.hidden) close(); });
  }

  function hideWxPanel() {
    var p = document.getElementById('oppWxPanel'); if (p) p.hidden = true;
  }

  function showWxPanel(which) {
    var p = document.getElementById('oppWxPanel');
    if (!p) return;
    var title = which === 'moments' ? '分享到朋友圈' : '分享到微信';
    p.innerHTML = '<b>' + title + '</b><img alt="微信扫码" src="' + qrDataURL() + '">'
      + '<p>用微信「扫一扫」打开本页<br>即可转发给好友或朋友圈</p>';
    p.hidden = false;
  }
  function shareAct(act) {
    if (act === 'wx' || act === 'moments') {
      if (IS_WX) { hideWxPanel(); document.getElementById('oppWxGuide').hidden = false; }
      else { showWxPanel(act); }
      return;
    }
    hideWxPanel();
    if (act === 'copy') {
      var done = function () { toast('已复制页面链接，可粘贴到微信/朋友圈'); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(TARGET_URL).then(done, function () { fallbackCopy(done); });
      else fallbackCopy(done);
      return;
    }
    if (act === 'save') { doDownload(); }
  }
  function fallbackCopy(cb) {
    var ta = document.createElement('textarea');
    ta.value = TARGET_URL; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); cb(); } catch (e) { toast('复制失败，请手动复制：' + TARGET_URL); }
    ta.remove();
  }

  /* 页面入口改为蓝框第 4 格的静态按钮（index.html #oppShareBtn），这里只负责绑定点击 */
  function bindPageButton() {
    var btn = document.getElementById('oppShareBtn');
    if (!btn || btn._oppBound) return;
    btn._oppBound = true;
    btn.addEventListener('click', function () { open(); });
  }
  function inject() { injectStyle(); injectModal(); bindPageButton(); }

  function open(d) {
    inject();
    lastSVG = build(d);
    document.getElementById('oppCardBox').innerHTML = '<img alt="A股红利机会卡" src="' + svgURL(lastSVG) + '">';
    hideWxPanel();
    document.getElementById('oppWxGuide').hidden = true;
    document.getElementById('oppCardMask').hidden = false;
  }
  function close() {
    var m = document.getElementById('oppCardMask'); if (m) m.hidden = true;
    var g = document.getElementById('oppWxGuide'); if (g) g.hidden = true;
    hideWxPanel();
  }

  function fileName() {
    var d = (window.opportunityData && window.opportunityData.asof) || '';
    return '食息指南-A股红利机会值' + (d ? '-' + d : '') + '.png';
  }
  function toPNG(scale) {
    return new Promise(function (resolve, reject) {
      var img = new Image();
      img.onload = function () {
        var cv = document.createElement('canvas');
        cv.width = img.width * scale; cv.height = img.height * scale;
        var ctx = cv.getContext('2d');
        ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, cv.width, cv.height);
        ctx.drawImage(img, 0, 0, cv.width, cv.height);
        cv.toBlob(function (bl) { bl ? resolve(bl) : reject(new Error('导出失败')); }, 'image/png');
      };
      img.onerror = function () { reject(new Error('图片渲染失败')); };
      img.src = svgURL(lastSVG || build());
    });
  }
  function save(blob) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = fileName();
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }
  function toast(msg) {
    var t = document.getElementById('oppToast');
    if (!t) { t = document.createElement('div'); t.className = 'oppToast'; t.id = 'oppToast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('on');
    clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove('on'); }, 2400);
  }
  function doDownload() {
    /* 2026-10-17 修复：此处原残留旧版菜单代码 `setExpanded(false)`，该函数已随圆形按钮改版删除 →
       点击下载会先抛 ReferenceError，导出逻辑完全没执行（表现为「点了没作用」）。改为只收面板。 */
    hideWxPanel();
    toPNG(2).then(save).then(function () { toast('已保存图片'); })
      .catch(function (e) { toast('下载失败：' + e.message); });
  }

  function init() { inject(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
  setTimeout(inject, 800);

  window.OpportunityCard = { open: open, close: close, build: build };
})();
