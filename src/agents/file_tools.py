"""文件读写工具：给 Agent 装上一双"手"，让它能自己看代码、改代码"""
from pathlib import Path
import shutil

# 项目根目录（本文件在 src/agents/ 下，往上两级就是 D:\projects\test-agent）
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _to_abs(path: str) -> Path:
    """相对路径 → 项目根下的绝对路径"""
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()


def read_file(path: str) -> str:
    """读取文件全部内容"""
    p = _to_abs(path)
    if not p.exists():
        return f"[错误] 文件不存在: {path}"
    return p.read_text(encoding="utf-8")


def write_file(path: str, content: str, backup: bool = True) -> str:
    """写入文件；backup=True 时先把原文件备份成 xxx.bak"""
    p = _to_abs(path)
    if backup and p.exists():
        shutil.copy2(p, str(p) + ".bak")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {p}"


def list_py_files(dir_path: str) -> list[str]:
    """列出某个目录下所有 .py 文件（返回相对项目根的路径）"""
    d = _to_abs(dir_path)
    if not d.exists():
        return [f"[错误] 目录不存在: {dir_path}"]
    files = []
    for f in d.rglob("*.py"):
        if ".venv" in str(f):
            continue
        files.append(str(f.relative_to(PROJECT_ROOT)))
    return files
