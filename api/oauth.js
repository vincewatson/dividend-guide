// Vercel Serverless Function — Decap CMS GitHub OAuth 代理
// 使用前需在 GitHub Settings > Developer Settings > OAuth Apps 创建应用：
//   Homepage URL: https://dividend-guide.cn
//   Authorization callback URL: https://dividend-guide.cn/api/oauth
// 然后将 Client ID / Client Secret 设为 Vercel 环境变量：
//   GITHUB_OAUTH_CLIENT_ID
//   GITHUB_OAUTH_CLIENT_SECRET

const https = require('https');

module.exports = async (req, res) => {
  const clientId = process.env.GITHUB_OAUTH_CLIENT_ID;
  const clientSecret = process.env.GITHUB_OAUTH_CLIENT_SECRET;

  if (!clientId || !clientSecret) {
    res.status(500).send(
      `<h2>OAuth 未配置</h2>
       <p>请设置 GITHUB_OAUTH_CLIENT_ID 和 GITHUB_OAUTH_CLIENT_SECRET 环境变量。</p>`
    );
    return;
  }

  const siteUrl = process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : 'https://dividend-guide.cn';

  const url = new URL(req.url, siteUrl);

  // === 第一步：重定向到 GitHub 授权 ===
  if (!url.searchParams.has('code')) {
    const redirectUri = `${siteUrl}/api/oauth`;
    const githubAuthUrl =
      `https://github.com/login/oauth/authorize` +
      `?client_id=${clientId}` +
      `&redirect_uri=${encodeURIComponent(redirectUri)}` +
      `&scope=repo,user` +
      `&state=${encodeURIComponent(siteUrl)}`;
    res.writeHead(302, { Location: githubAuthUrl });
    res.end();
    return;
  }

  // === 第二步：用 code 换 access_token ===
  const code = url.searchParams.get('code');

  try {
    const token = await exchangeCode(code, clientId, clientSecret);
    // 返回 HTML 页面，通过 postMessage 把 token 传回 Decap CMS
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end(`
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>授权成功</title></head>
<body>
  <p style="font-family:sans-serif;text-align:center;margin-top:40px;color:#1c1c1e">授权成功，正在跳转至管理后台...</p>
  <script>
    (function() {
      var authResult = { token: '${token}', provider: 'github' };
      if (window.opener) {
        window.opener.postMessage(authResult, '${siteUrl}');
        window.opener.postMessage(authResult, 'https://dividend-guide.cn');
        window.close();
      } else {
        document.title = '授权完成';
        document.body.innerHTML = '<p style="font-family:sans-serif;text-align:center;margin-top:40px;color:#1c1c1e">授权完成，请关闭此窗口。</p>';
      }
    })();
  </script>
</body>
</html>
    `);
  } catch (err) {
    res.status(500).send(`<h2>OAuth 错误</h2><pre>${err.message}</pre>`);
  }
};

function exchangeCode(code, clientId, clientSecret) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      client_id: clientId,
      client_secret: clientSecret,
      code,
    });
    const options = {
      hostname: 'github.com',
      path: '/login/oauth/access_token',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'Content-Length': Buffer.byteLength(body),
      },
    };
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.error) return reject(new Error(json.error_description || json.error));
          resolve(json.access_token);
        } catch (e) {
          reject(new Error('解析响应失败: ' + data));
        }
      });
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}
