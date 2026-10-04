// studio auth — 简单的密码验证，返回 session token
// Cloudflare Pages Functions 版（2026-10-03 由 Vercel Serverless 迁移）
// 环境变量：STUDIO_PASSWORD（在 Cloudflare Pages 项目 Settings → Environment variables 配置）
export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== 'POST') return json({ error: 'Method not allowed' }, 405);

  const password = env.STUDIO_PASSWORD;
  if (!password) return json({ error: 'STUDIO_PASSWORD 未配置' }, 500);

  let body = {};
  try { body = await request.json(); } catch (e) { /* 空 body */ }

  if (body && body.password === password) {
    // token = base64('studio:<时间戳>:<口令前4位>')，与前端约定一致
    const payload = btoa('studio:' + Date.now() + ':' + password.slice(0, 4));
    return json({ token: payload });
  }
  return json({ error: '密码错误' });
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }
  });
}
