// studio save — 保存/更新博客文章到 GitHub
// 需要 GITHUB_PAT 和 STUDIO_PASSWORD 环境变量

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

  const { slug, title, tags, excerpt, body } = req.body || {};
  if (!slug || !title || !body) {
    res.json({ success: false, error: '缺少必填字段' });
    return;
  }

  const owner = 'vincewatson';
  const repo = 'dividend-guide';
  const branch = 'main';
  const date = slug.slice(0, 10);

  try {
    // === 1. 获取当前主分支最新的 commit SHA ===
    const refData = await githubGet(`/repos/${owner}/${repo}/git/ref/heads/${branch}`, pat);
    const latestCommitSha = refData.object.sha;

    // === 2. 获取最新 commit 的 tree SHA ===
    const commitData = await githubGet(`/repos/${owner}/${repo}/git/commits/${latestCommitSha}`, pat);
    const baseTreeSha = commitData.tree.sha;

    // === 3. 准备要创建/更新的文件 ===
    const mdContent = `---\ntitle: ${title}\ndate: ${date}\ntags:\n  - ${(tags || []).join('\n  - ')}\nexcerpt: ${excerpt || ''}\n---\n\n${body}`;

    const files = [
      { path: `blog/${slug}.md`, content: mdContent },
    ];

    // === 4. 创建新的 tree 条目 ===
    const treeItems = files.map(f => ({
      path: f.path,
      mode: '100644',
      type: 'blob',
      content: f.content
    }));

    const newTreeData = await githubPost(`/repos/${owner}/${repo}/git/trees`, pat, {
      base_tree: baseTreeSha,
      tree: treeItems
    });
    const newTreeSha = newTreeData.sha;

    // === 5. 创建新的 commit ===
    const commitMsg = `feat(blog): ${title}`;
    const newCommitData = await githubPost(`/repos/${owner}/${repo}/git/commits`, pat, {
      message: commitMsg,
      tree: newTreeSha,
      parents: [latestCommitSha]
    });
    const newCommitSha = newCommitData.sha;

    // === 6. 更新 ref ===
    await githubPostWithMethod(`/repos/${owner}/${repo}/git/refs/heads/${branch}`, pat, {
      sha: newCommitSha,
      force: false
    }, 'PATCH');

    // === 7. 更新 posts.json ===
    const currentPostsRes = await fetch(`https://raw.githubusercontent.com/${owner}/${repo}/${branch}/blog/posts.json`);
    let postsData;
    try {
      postsData = await currentPostsRes.json();
    } catch (e) {
      postsData = { posts: [] };
    }

    const posts = Array.isArray(postsData) ? postsData : (postsData.posts || []);
    const existingIdx = posts.findIndex(p => p.slug === slug);

    const postEntry = {
      slug: slug,
      title: title,
      date: date,
      tags: tags || [],
      excerpt: excerpt || ''
    };

    if (existingIdx >= 0) {
      posts[existingIdx] = postEntry;
    } else {
      posts.push(postEntry);
    }

    // Write updated posts.json via raw GitHub API
    const getContentRes = await githubGet(`/repos/${owner}/${repo}/contents/blog/posts.json`, pat);
    const postsSha = getContentRes.sha;
    const postsContent = JSON.stringify({ posts: posts }, null, 2);

    await githubPostWithMethod(`/repos/${owner}/${repo}/contents/blog/posts.json`, pat, {
      message: `chore(blog): update posts.json - ${slug}`,
      content: Buffer.from(postsContent).toString('base64'),
      sha: postsSha,
      branch: branch
    }, 'PUT');

    res.json({ success: true });

  } catch (e) {
    console.error('Save error:', e.message);
    res.json({ success: false, error: e.message || '保存失败' });
  }
};

// === GitHub API helpers ===
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
        catch(e) { reject(new Error('解析响应失败: ' + data.slice(0,200))); }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function githubPost(path, pat, body) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    const opts = {
      hostname: 'api.github.com',
      path: path,
      method: 'POST',
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
        catch(e) { reject(new Error('POST 解析失败: ' + data.slice(0,200))); }
      });
    });
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

function githubPostWithMethod(path, pat, body, method) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify(body);
    const opts = {
      hostname: 'api.github.com',
      path: path,
      method: method,
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
