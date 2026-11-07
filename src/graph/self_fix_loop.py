"""自动修复闭环：跑测试 → 失败则读代码 → LLM 修复 → 重跑，最多 N 轮"""
import os
import sys
import difflib
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from openai import OpenAI

from src.agents.file_tools import read_file, write_file

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
PROJECT_ROOT = Path(__file__).resolve().parents[2]

TARGET = "sut/buggy_app.py"
TEST_FILE = "tests/test_fix_demo.py"

TEST_CODE = '''import json
from sut.buggy_app import app


def test_add_two_numbers():
    client = app.test_client()
    resp = client.get("/add?a=2&b=3")
    assert resp.status_code == 200
    data = json.loads(resp.get_data(as_text=True))
    assert data["result"] == 5, f"期望 5，实际 {data['result']}"
'''


def llm(prompt: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


def strip_fence(text: str) -> str:
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def run_pytest():
    r = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE, "-q"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def fix_code(code: str, bug_desc: str) -> str:
    prompt = f"""你是一名修复工程师。下面是文件 {TARGET} 的内容：

{code}

已知 bug 现象：{bug_desc}

请修复代码中的错误逻辑。只输出修复后的完整文件内容，不要任何解释，不要 markdown 代码块标记。"""
    return strip_fence(llm(prompt))


def run_fix_loop(bug_desc: str = "GET /add?a=2&b=3 应该返回 5，实际返回了 -1",
                 max_rounds: int = 3) -> dict:
    """执行完整闭环，返回结构化结果（接口和脚本共用）"""
    (PROJECT_ROOT / TEST_FILE).parent.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / TEST_FILE).write_text(TEST_CODE, encoding="utf-8")

    original = read_file(TARGET)
    logs, ok, rounds_used = [], False, 0

    for rnd in range(1, max_rounds + 1):
        rounds_used = rnd
        rc, _ = run_pytest()
        logs.append(f"第 {rnd} 轮测试: {'通过' if rc == 0 else '失败'}")
        if rc == 0:
            ok = True
            break
        fixed = fix_code(read_file(TARGET), bug_desc)
        if "def add" not in fixed:
            logs.append(f"第 {rnd} 轮模型输出异常，跳过")
            continue
        write_file(TARGET, fixed)
        logs.append(f"第 {rnd} 轮已修复并写入 {TARGET}")

    final = read_file(TARGET)
    diff = "\n".join(difflib.unified_diff(
        original.splitlines(), final.splitlines(),
        fromfile="修复前", tofile="修复后", lineterm="",
    ))
    return {"ok": ok, "rounds": rounds_used, "backup": f"{TARGET}.bak",
            "diff": diff, "logs": logs}


def main():
    r = run_fix_loop()
    print("===== 最终报告 =====")
    print(f"结果: {'修复成功' if r['ok'] else '未修复'}")
    for line in r["logs"]:
        print(line)
    print(r["diff"])


if __name__ == "__main__":
    main()
