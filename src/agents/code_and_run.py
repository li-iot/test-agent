import os
import subprocess
import sys
import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from test_case_generator import generate_cases

load_dotenv()

client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection("flask_bugs")
llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=os.getenv("DEEPSEEK_BASE_URL"))


def retrieve(query, k=3):
    return collection.query(query_texts=[query], n_results=k)["documents"][0]


def generate_pytest_code(bug_desc, retries=3):
    """把用例设计翻译成可直接运行的 pytest 代码"""
    cases = generate_cases(bug_desc)                        # 复用上一步的用例设计
    context = "\n\n".join(d[:500] for d in retrieve(bug_desc))

    prompt = f"""你是资深测试开发工程师。根据 bug 描述、测试用例设计和历史修复参考，生成一个可直接运行的 pytest 测试文件。

bug 描述：
{bug_desc}

测试用例设计：
{[c.model_dump() for c in cases]}

历史修复参考：
{context}

要求：
1. 只输出 Python 代码，不要 ``` 标记，不要任何解释文字
2. 顶部写 import pytest 和 from flask import Flask, url_for
3. 每个用例对应一个 def test_xxx() 函数，函数内写中文 docstring
4. 每个测试自己创建 Flask app 并注册路由，用 app.test_client() 发真实请求
"""
    for attempt in range(retries):
        resp = llm.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        code = resp.choices[0].message.content.strip()
        if code.startswith("```"):
            code = code.strip("`").removeprefix("python").strip()
        if "def test_" in code:          # 简单质检：至少要有测试函数
            return code
        print(f"第 {attempt+1} 次生成的代码不合格，重试...")
    return ""


def run_pytest():
    """真的把测试跑起来，拿回结果"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_generated.py", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},   # 防止 Windows 下中文乱码
    )
    return result.returncode, result.stdout


if __name__ == "__main__":
    bug = "When I use url_for() with a route that has a variable, it returns 404 instead of the correct URL"
    print("① 生成测试代码中...")
    code = generate_pytest_code(bug)
    os.makedirs("tests", exist_ok=True)
    with open("tests/test_generated.py", "w", encoding="utf-8") as f:
        f.write(code)
    print(f"② 已写入 tests/test_generated.py（{len(code)} 字符）")
    print("③ 正在执行 pytest...")
    returncode, output = run_pytest()
    print(f"④ 退出码: {returncode}（0=全通过，非0=有失败或错误）")
    print(output)
