"""把站点目录复制到部署目录，排除规则与 deploy_cloudflare.sh 里的 rsync 一致（Windows 没有 rsync 时用，2026-11-08）。

用法：python deploy_copy.py <源目录> <目标目录>
"""
import fnmatch, os, shutil, sys

# 任意层级按名称排除
NAMES = {".DS_Store", ".git", ".vercel", ".trae", "node_modules", "__pycache__", "archive", "backup", "docs",
         "prototype", "user_upload", "vercel.json", ".vercelignore", ".gitignore"}
GLOBS = ["*.xlsx", "*.py", "*.sh", "*.bak", "*.bak-*", "*.tmp"]
# 只在根目录排除（rsync 里以 / 开头的规则）
ROOT_NAMES = {"api", "inputs", "logs", "deploy"}
ROOT_GLOBS = ["*.md", ".*"]
# 相对路径排除（rsync 的 data/user）
PATHS = {"data/user"}


def skip(rel, name, at_root):
    if name in NAMES or any(fnmatch.fnmatch(name, g) for g in GLOBS):
        return True
    if at_root and (name in ROOT_NAMES or any(fnmatch.fnmatch(name, g) for g in ROOT_GLOBS)):
        return True
    return any(rel == p or rel.endswith("/" + p) for p in PATHS)


def main(src, dst):
    src, dst = os.path.abspath(src), os.path.abspath(dst)
    n = 0
    for root, dirs, files in os.walk(src):
        relroot = os.path.relpath(root, src).replace("\\", "/")
        relroot = "" if relroot == "." else relroot
        at_root = relroot == ""
        dirs[:] = [d for d in dirs if not skip((relroot + "/" + d).lstrip("/"), d, at_root)]
        for f in files:
            rel = (relroot + "/" + f).lstrip("/")
            if skip(rel, f, at_root):
                continue
            out = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copy2(os.path.join(root, f), out)
            n += 1
    print(f"已复制 {n} 个文件到 {dst}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
