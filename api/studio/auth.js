// studio auth — 简单的密码验证，返回 session token
module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method not allowed' });
    return;
  }

  const password = process.env.STUDIO_PASSWORD;
  if (!password) {
    res.status(500).json({ error: 'STUDIO_PASSWORD 未配置' });
    return;
  }

  const { password: inputPwd } = req.body || {};

  if (inputPwd === password) {
    // 返回一个简单的 token（base64 编码时间戳 + 标记）
    const payload = Buffer.from(`studio:${Date.now()}:${password.slice(0, 4)}`).toString('base64');
    res.json({ token: payload });
  } else {
    res.json({ error: '密码错误' });
  }
};
