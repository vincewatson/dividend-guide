// studio delete — 删除博客文章
// Cloudflare Pages Functions 版（2026-10-03 由 Vercel Serverless 迁移）
// 原实现用 node:https + Buffer；Workers 运行时改为 fetch + UTF-8 安全的 base64 工具。
// 环境变量：STUDIO_PASSWORD、GITHUB_PAT
const OWNER = 'vincewatson';
const REPO = 'dividend-guide';
const BRANCH = 'main';

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== 'POST') return json({ error: 'Method not allowed' }, 405);

  // === Auth Check ===
  const token = request.headers.get('x-studio-token');
  const password = env.STUDIO_PASSWORD;
  if (!password || !token) return json({ success: false, error: '未授权' });
  if (!validToken(token, password)) return json({ success: false, error: 'Token 无效' });

  const pat = env.GITHUB_PAT;
  if (!pat) return json({ success: false, error: 'GITHUB_PAT 未配置' });

  let body = {};
  try { body = await request.json(); } catch (e) { /* 空 body */ }
  const slug = body && body.slug;
  if (!slug) return json({ success: false, error: '缺少 slug' });

  try {
    // 1. 删除 .md
    const mdFile = await gh(pat, `/repos/${OWNER}/${REPO}/contents/blog/${slug}.md`);
    await gh(pat, `/repos/${OWNER}/${REPO}/contents/blog/${slug}.md`, 'DELETE', {
      message: `chore(blog): delete ${slug}`, content: '', sha: mdFile.sha, branch: BRANCH
    });

    // 2. 更新 posts.json
    const postsRes = await gh(pat, `/repos/${OWNER}/${REPO}/contents/blog/posts.json`);
    const postsContent = JSON.parse(b64ToUtf8(String(postsRes.content).replace(/\s/g, '')));
    const posts = Array.isArray(postsContent) ? postsContent : (postsContent.posts || []);
    const filtered = posts.filter(p => p.slug !== slug);

    await gh(pat, `/repos/${OWNER}/${REPO}/contents/blog/posts.json`, 'PUT', {
      message: `chore(blog): remove ${slug} from index`,
      content: utf8ToB64(JSON.stringify({ posts: filtered }, null, 2)),
      sha: postsRes.sha,
      branch: BRANCH
    });

    return json({ success: true });
  } catch (e) {
    return json({ success: false, error: (e && e.message) || '删除失败' });
  }
}

// === GitHub API helper ===
async function gh(pat, path, method, body) {
  const res = await fetch('https://api.github.com' + path, {
    method: method || 'GET',
    headers: {
      'Authorization': 'Bearer ' + pat,
      'User-Agent': 'dividend-guide-studio',
      'Accept': 'application/vnd.github.v3+json',
      ...(body ? { 'Content-Type': 'application/json' } : {})
    },
    body: body ? JSON.stringify(body) : undefined
  });
  const text = await res.text();
  if (!res.ok) throw new Error('GitHub ' + res.status + ': ' + text.slice(0, 200));
  try { return JSON.parse(text); } catch (e) { throw new Error('解析响应失败: ' + text.slice(0, 200)); }
}

function validToken(token, password) {
  try {
    const decoded = atob(token);
    return decoded.indexOf('studio:') === 0 && decoded.indexOf(password.slice(0, 4)) !== -1;
  } catch (e) { return false; }
}

function utf8ToB64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = '';
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

function b64ToUtf8(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }
  });
}
