(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart: 架构图 ---
  var archChart = echarts.init(document.getElementById('chart-arch'), null, { renderer: 'svg' });
  archChart.setOption({
    animation: false,
    tooltip: { show: false },
    series: [{
      type: 'sankey',
      layout: 'none',
      emphasis: { focus: 'adjacency' },
      nodeAlign: 'left',
      nodeWidth: 20,
      nodeGap: 12,
      data: [
        { name: '用户访问', itemStyle: { color: accent } },
        { name: '网页版 (H5)', itemStyle: { color: accent2 } },
        { name: '微信小程序', itemStyle: { color: accent } },
        { name: 'uni-app 框架', itemStyle: { color: '#8b5cf6' } },
        { name: 'uView Plus 组件库', itemStyle: { color: '#6366f1' } },
        { name: 'Vue 3 核心', itemStyle: { color: '#4f46e5' } },
        { name: '微信云开发', itemStyle: { color: accent2 } },
        { name: '云数据库', itemStyle: { color: '#059669' } },
        { name: '云函数', itemStyle: { color: '#047857' } },
        { name: '云存储', itemStyle: { color: '#065f46' } },
        { name: '外部数据源', itemStyle: { color: '#d97706' } },
        { name: 'Tushare API', itemStyle: { color: '#f59e0b' } },
        { name: '手动录入数据', itemStyle: { color: '#eab308' } },
        { name: 'Vercel 部署', itemStyle: { color: '#111827' } }
      ],
      links: [
        { source: '用户访问', target: '网页版 (H5)', value: 1 },
        { source: '用户访问', target: '微信小程序', value: 1 },
        { source: '网页版 (H5)', target: 'uni-app 框架', value: 1 },
        { source: '微信小程序', target: 'uni-app 框架', value: 1 },
        { source: 'uni-app 框架', target: 'uView Plus 组件库', value: 1 },
        { source: 'uni-app 框架', target: 'Vue 3 核心', value: 1 },
        { source: 'uni-app 框架', target: '微信云开发', value: 1 },
        { source: '微信云开发', target: '云数据库', value: 1 },
        { source: '微信云开发', target: '云函数', value: 1 },
        { source: '微信云开发', target: '云存储', value: 1 },
        { source: '云函数', target: '外部数据源', value: 1 },
        { source: '外部数据源', target: 'Tushare API', value: 1 },
        { source: '外部数据源', target: '手动录入数据', value: 1 },
        { source: '网页版 (H5)', target: 'Vercel 部署', value: 1 }
      ],
      label: {
        color: ink,
        fontSize: 11
      },
      lineStyle: { color: 'gradient', curveness: 0.5 }
    }]
  });
  window.addEventListener('resize', function() { archChart.resize(); });

  // --- Chart: 页面结构 ---
  var pagesChart = echarts.init(document.getElementById('chart-pages'), null, { renderer: 'svg' });
  pagesChart.setOption({
    animation: false,
    tooltip: { show: false },
    series: [{
      type: 'tree',
      data: [{
        name: '食息指南',
        itemStyle: { color: accent },
        children: [{
          name: '首页',
          itemStyle: { color: accent2 },
          children: [
            { name: '股息排行榜', itemStyle: { color: '#059669' } },
            { name: '精选文章', itemStyle: { color: '#059669' } },
            { name: '热点日历', itemStyle: { color: '#059669' } }
          ]
        }, {
          name: '工具',
          itemStyle: { color: accent2 },
          children: [
            { name: '股息率计算器', itemStyle: { color: '#059669' } },
            { name: '红利指数浏览器', itemStyle: { color: '#059669' } },
            { name: '资产生息率对比', itemStyle: { color: '#059669' } },
            { name: '月月分红基金', itemStyle: { color: '#059669' } }
          ]
        }, {
          name: '自选',
          itemStyle: { color: accent2 },
          children: [
            { name: '我的自选池', itemStyle: { color: '#059669' } },
            { name: '分组管理', itemStyle: { color: '#059669' } },
            { name: '股息日历', itemStyle: { color: '#059669' } }
          ]
        }, {
          name: '内容',
          itemStyle: { color: accent2 },
          children: [
            { name: '文章列表', itemStyle: { color: '#059669' } },
            { name: '文章详情', itemStyle: { color: '#059669' } },
            { name: '博主专栏', itemStyle: { color: '#059669' } }
          ]
        }, {
          name: '我的',
          itemStyle: { color: accent2 },
          children: [
            { name: '个人信息', itemStyle: { color: '#059669' } },
            { name: '我的收藏', itemStyle: { color: '#059669' } },
            { name: '提醒设置', itemStyle: { color: '#059669' } }
          ]
        }]
      }],
      layout: 'radial',
      symbolSize: function(v, params) {
        var depth = params.depth;
        return depth === 0 ? 24 : depth === 1 ? 18 : 14;
      },
      label: {
        color: ink,
        fontSize: 11,
        position: 'left',
        rotate: 0
      },
      leaves: {
        label: {
          color: muted,
          fontSize: 10,
          position: 'right',
          rotate: 0
        }
      },
      lineStyle: { color: rule, width: 1.5, curveness: 0.5 },
      expandAndCollapse: false,
      initialTreeDepth: 2,
      roam: false
    }]
  });
  window.addEventListener('resize', function() { pagesChart.resize(); });
})();
