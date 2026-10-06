#!/usr/bin/env node
// ============================================================
// 食息指南 · Wind 调用额度守卫（2026-10-06 新增）
// ────────────────────────────────────────────────────────────
// 背景：Wind 每日额度约 2000 次；同日多轮整跑极易把额度耗尽（2026-10-06 事故复盘）。
// 机制：各脚本的 CLI 指向本包装器；每次真实调用前，向 `.wind_calls_<YYYY-MM-DD>` 追加一行计数；
//       当日计数 ≥ SX_WIND_DAILY_CAP（默认 2000）时 **直接拒绝**（退出码 3），不发起真实调用。
//       脚本视非零退出码为失败 → 走既有「重试 / 保留旧值」逻辑安全降级，**绝不误改数据**。
// 覆盖：SX_WIND_DAILY_CAP 调整上限；SX_WIND_CLI_REAL 指定真实 cli.mjs（默认 wind-mcp-skill 那份）。
// 说明：argv / stdio / 退出码原样透传给真实 cli.mjs，对调用方完全透明。
// ============================================================
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REAL = process.env.SX_WIND_CLI_REAL
  || path.join(os.homedir(), '.agents', 'skills', 'wind-mcp-skill', 'scripts', 'cli.mjs');
const CAP = parseInt(process.env.SX_WIND_DAILY_CAP || '2000', 10);

const d = new Date();
const DAY = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const LOG = path.join(HERE, `.wind_calls_${DAY}`);

let used = 0;
try { used = fs.readFileSync(LOG, 'utf8').split('\n').filter(Boolean).length; } catch { used = 0; }

if (used >= CAP) {
  process.stderr.write(
    `[Wind 额度闸] 今日调用已达上限 ${CAP}（已用 ${used}）→ 拒绝本次调用（可设 SX_WIND_DAILY_CAP 调整）。\n`);
  process.exit(3);
}
try { fs.appendFileSync(LOG, '.\n'); } catch { /* 计数失败不阻断真实调用 */ }

const r = spawnSync('node', [REAL, ...process.argv.slice(2)], { stdio: 'inherit' });
process.exit(typeof r.status === 'number' ? r.status : 1);
