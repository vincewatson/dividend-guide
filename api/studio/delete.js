// studio delete — 删除博客文章
const https = require('https');

module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  // === Auth Check ===
  const token = req.headers['x-studio-token'];
  const password = process.env.STUDIO_PASSWORD;
  if (!password || !token) {
    res.json({ success: false, error: '未授权' });
    return;
  }
  try {
    const decoded = Buffer.from(token, 'base64').toString();
    if (!decoded.startsWith('studio:') || !decoded.includes(password.slice(0, 4))) {
      res.json({ success: false, error: 'Token 无效' });
      return;
    }
  } catch (e) {
    res.json({ success: false, error: 'Token 无效' });
    return;
  }

  const pat = process.env.GITHUB_PAT;
  if (!pat) {
    res.json({ success: false, error: 'GITHUB_PAT 未配置' });
    return;
  }

  const { slug } = req.body || {};
  if (!slug) {
    res.json({ success: false, error: '缺少 slug' });
    return;
  }

  const owner = 'vincewatson';
  const repo = 'dividend-guide';
  const branch = 'main';

  try {
    // 1. Delete the .md file
    const mdFile = await githubGet(`/repos/${owner}/${repo}/contents/blog/${slug}.md`, pat);
    await githubPut(`/repos/${owner}/${repo}/contents/blog/${slug}.md`, pat, {
      message: `chore(blog): delete ${slug}`,
      content: '',
      sha: mdFile.sha,
      branch: branch
    }, 'DELETE');

    // 2. Update posts.json
    const postsRes = await githubGet(`/repos/${owner}/${repo}/contents/blog/posts.json`, pat);
    const postsContent = JSON.parse(Buffer.from(postsRes.content, 'base64').toString());
    const posts = Array.isArray(postsContent) ? postsContent : (postsContent.posts || []);
    const filtered = posts.filter(p => p.slug !== slug);

    await githubPut(`/repos/${owner}/${repo}/contents/blog/posts.json`, pat, {
      message: `chore(blog): remove ${slug} from index`,
      content: Buffer.from(JSON.stringify({ posts: filtered }, null, 2)).toString('base64'),
      sha: postsRes.sha,
      branch: branch
    }, 'PUT');

    res.json({ success: true });
  } catch (e) {
    console.error('Delete error:', e.message);
    res.json({ success: false, error: e.message || '删除失败' });
  }
};

function githubGet(path, pat) {
  return new Promise((resolve, reject) => {
    const opts = {
      hostname: 'api.github.com',
      path: path,
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${pat}`,
        'User-Agent': 'dividend-guide-studio',
        'Accept': 'application/vnd.github.v3+json'
      }
    };
    const req = https.request(opts, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch(e) { reject(new Error('解析失败: ' + data.slice(0,200))); }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function githubPut(path, pat, body, method) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    const opts = {
      hostname: 'api.github.com',
      path: path,
      method: method || 'PUT',
      headers: {
        'Authorization': `Bearer ${pat}`,
        'User-Agent': 'dividend-guide-studio',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const req = https.request(opts, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch(e) { reject(new Error('PUT 解析失败: ' + data.slice(0,200))); }
      });
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}
