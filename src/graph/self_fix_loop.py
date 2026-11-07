"""自动修复闭环：跑测试 → 失败则读代码 → LLM 修复 → 重跑，最多 3 轮 → 输出报告"""
import os
import sys
import difflib
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 让项目根可 import

from dotenv import load_dotenv
from openai import OpenAI

from src.agents.file_tools import read_file, write_file

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

TARGET = "sut/buggy_app.py"
TEST_FILE = "tests/test_fix_demo.py"
BUG_DESC = "GET /add?a=2&b=3 应该返回 5，实际返回了 -1"
MAX_ROUNDS = 3

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
    """去掉模型可能加的 ```python 包裹"""
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def run_pytest():
    r = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE, "-q"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def fix_code(code: str) -> str:
    prompt = f"""你是一名修复工程师。下面是文件 {TARGET} 的内容：

{code}

已知 bug 现象：{BUG_DESC}

请修复代码中的错误逻辑。只输出修复后的完整文件内容，不要任何解释，不要 markdown 代码块标记。"""
    return strip_fence(llm(prompt))


def main():
    Path(TEST_FILE).parent.mkdir(exist_ok=True)
    Path(TEST_FILE).write_text(TEST_CODE, encoding="utf-8")

    original = read_file(TARGET)
    print(f"===== 自动修复闭环开始（最多 {MAX_ROUNDS} 轮）=====")
    print(f"被测文件: {TARGET}\n测试文件: {TEST_FILE}\n")

    result = "未完成"
    for rnd in range(1, MAX_ROUNDS + 1):
        rc, out = run_pytest()
        print(f"--- 第 {rnd} 轮：执行测试 ---")
        if rc == 0:
            print("[通过] 测试全部通过，闭环结束\n")
            result = f"第 {rnd} 轮修复成功"
            break
        print("[失败] 开始定位并修复\n")

        code = read_file(TARGET)
        fixed = fix_code(code)
        if "def add" not in fixed:
            print("[警告] 模型返回内容异常，跳过本轮\n")
            continue
        write_file(TARGET, fixed)
        print(f"[已修复] 写入 {TARGET}（原文件备份为 {TARGET}.bak）\n")
    else:
        result = f"{MAX_ROUNDS} 轮后仍未通过，需人工介入"

    final_code = read_file(TARGET)
    print("===== 最终报告 =====")
    print(f"结果: {result}")
    print(f"备份: {TARGET}.bak")
    print("\n改动 diff:")
    for line in difflib.unified_diff(
        original.splitlines(), final_code.splitlines(),
        fromfile="修复前", tofile="修复后", lineterm="",
    ):
        print(line)


if __name__ == "__main__":
    main()
