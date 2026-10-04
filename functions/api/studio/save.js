// studio save — 保存/更新博客文章到 GitHub
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
  const { slug, title, tags, excerpt } = body || {};
  const content = body && body.body;
  if (!slug || !title || !content) return json({ success: false, error: '缺少必填字段' });
  const date = String(slug).slice(0, 10);

  try {
    // === 1. 主分支最新 commit SHA → 2. tree SHA ===
    const refData = await gh(pat, `/repos/${OWNER}/${REPO}/git/ref/heads/${BRANCH}`);
    const latestCommitSha = refData.object.sha;
    const commitData = await gh(pat, `/repos/${OWNER}/${REPO}/git/commits/${latestCommitSha}`);
    const baseTreeSha = commitData.tree.sha;

    // === 3. 准备文章 Markdown ===
    const mdContent = `---\ntitle: ${title}\ndate: ${date}\ntags:\n  - ${(tags || []).join('\n  - ')}\nexcerpt: ${excerpt || ''}\n---\n\n${content}`;

    // === 4. 新 tree ===
    const newTreeData = await gh(pat, `/repos/${OWNER}/${REPO}/git/trees`, 'POST', {
      base_tree: baseTreeSha,
      tree: [{ path: `blog/${slug}.md`, mode: '100644', type: 'blob', content: mdContent }]
    });

    // === 5. 新 commit ===
    const newCommitData = await gh(pat, `/repos/${OWNER}/${REPO}/git/commits`, 'POST', {
      message: `feat(blog): ${title}`,
      tree: newTreeData.sha,
      parents: [latestCommitSha]
    });

    // === 6. 更新 ref ===
    await gh(pat, `/repos/${OWNER}/${REPO}/git/refs/heads/${BRANCH}`, 'PATCH', {
      sha: newCommitData.sha, force: false
    });

    // === 7. 更新 posts.json（读 → 合并 → 写回）===
    let posts = [], postsSha;
    try {
      const idxJson = await gh(pat, `/repos/${OWNER}/${REPO}/contents/blog/posts.json`);
      const parsed = JSON.parse(b64ToUtf8(String(idxJson.content).replace(/\s/g, '')));
      posts = Array.isArray(parsed) ? parsed : (parsed.posts || []);
      postsSha = idxJson.sha;
    } catch (e) { posts = []; }

    const entry = { slug, title, date, tags: tags || [], excerpt: excerpt || '' };
    const i = posts.findIndex(p => p.slug === slug);
    if (i >= 0) posts[i] = entry; else posts.push(entry);

    const putBody = {
      message: `chore(blog): update posts.json - ${slug}`,
      content: utf8ToB64(JSON.stringify({ posts }, null, 2)),
      branch: BRANCH
    };
    if (postsSha) putBody.sha = postsSha;
    await gh(pat, `/repos/${OWNER}/${REPO}/contents/blog/posts.json`, 'PUT', putBody);

    return json({ success: true });
  } catch (e) {
    return json({ success: false, error: (e && e.message) || '保存失败' });
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
