# 给 TRAE 的指令：确认机会值脚本能写回中央库（第二次，2026-10-08）

请在 `dividend-guide-website` 仓库根目录运行下面两条命令（0 次万得调用，不改任何文件），把输出原样发给我：

```bash
python3 -c "import fetch_opportunity_inputs as f; print('选用:', f._submit_python('', verbose=True))"
env -u PYTHONHOME -u PYTHONPATH /Users/vincentwatson/.local/share/data_center/venv/bin/python -c "import sys, duckdb; print(sys.version); print(duckdb.__version__)"
```

不要安装任何东西，也不要改代码。
