// studio list — 获取博客文章列表
// Cloudflare Pages Functions 版（2026-10-03 由 Vercel Serverless 迁移）
// 原实现读服务器文件系统 blog/posts.json；Pages 无文件系统，改为经 env.ASSETS 读取同一静态资源。
// 环境变量：STUDIO_PASSWORD
export async function onRequest(context) {
  const { request, env } = context;
  const token = request.headers.get('x-studio-token');
  const password = env.STUDIO_PASSWORD;

  if (!password || !token) return json({ error: '未授权', posts: [] });
  if (!validToken(token, password)) return json({ error: 'Token 无效', posts: [] });

  try {
    const res = await env.ASSETS.fetch(new URL('/blog/posts.json', request.url));
    if (!res.ok) return json({ posts: [] });
    const data = await res.json();
    return json({ posts: data.posts || data });
  } catch (e) {
    return json({ posts: [] });
  }
}

function validToken(token, password) {
  try {
    const decoded = atob(token);
    return decoded.indexOf('studio:') === 0 && decoded.indexOf(password.slice(0, 4)) !== -1;
  } catch (e) { return false; }
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }
  });
}
