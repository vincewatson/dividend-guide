// studio list — 获取博客文章列表
const fs = require('fs');
const path = require('path');

module.exports = async (req, res) => {
  const token = req.headers['x-studio-token'];
  const password = process.env.STUDIO_PASSWORD;

  if (!password || !token) {
    res.json({ error: '未授权', posts: [] });
    return;
  }

  try {
    const decoded = Buffer.from(token, 'base64').toString();
    if (!decoded.startsWith('studio:') || !decoded.includes(password.slice(0, 4))) {
      res.json({ error: 'Token 无效', posts: [] });
      return;
    }
  } catch (e) {
    res.json({ error: 'Token 无效', posts: [] });
    return;
  }

  try {
    const indexFile = path.join(process.cwd(), 'blog', 'posts.json');
    const data = JSON.parse(fs.readFileSync(indexFile, 'utf-8'));
    res.json({ posts: data.posts || data });
  } catch (e) {
    res.json({ posts: [] });
  }
};
