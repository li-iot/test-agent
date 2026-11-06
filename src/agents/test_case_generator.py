import os
import json
import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()

client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection("flask_bugs")
llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=os.getenv("DEEPSEEK_BASE_URL"))

# 定义"用例长什么样"——这是契约，模型必须按这个交作业
class TestCase(BaseModel):
    name: str
    precondition: str
    steps: list[str]
    expected: str

class TestCaseList(BaseModel):
    cases: list[TestCase]

def retrieve(query, k=3):
    results = collection.query(query_texts=[query], n_results=k)
    return results["documents"][0]

def generate_cases(bug_desc, retries=3):
    context = "\n\n".join(d[:600] for d in retrieve(bug_desc))

    prompt = f"""你是资深测试开发工程师。基于下面的 bug 描述和历史修复案例，生成 3 条针对性测试用例。

bug 描述：
{bug_desc}

历史修复参考：
{context}

严格按这个 JSON 格式输出，不要任何解释、不要 markdown 代码块标记：
{{"cases": [{{"name": "用例名", "precondition": "前置条件", "steps": ["步骤1", "步骤2"], "expected": "预期结果"}}]}}
"""
    for attempt in range(retries):
        resp = llm.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,       # 低温度 = 输出更稳定、少发散
        )
        raw = resp.choices[0].message.content.strip()

        # 模型有时会裹上 ```json ... ```，先清掉再解析
        if raw.startswith("```"):
            raw = raw.strip("`").removeprefix("json").strip()

        try:
            data = json.loads(raw)          # ① 语法校验：能不能解析
            return TestCaseList(**data).cases  # ② 结构校验：字段齐不齐、类型对不对
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"第 {attempt+1} 次输出不合法：{e}，重试...")
    return []

if __name__ == "__main__":
    bug = "When I use url_for() with a route that has a variable, it returns 404 instead of the correct URL"
    cases = generate_cases(bug)
    for i, c in enumerate(cases, 1):
        print(f"\n=== 用例 {i}: {c.name} ===")
        print(f"前置: {c.precondition}")
        print(f"步骤: {c.steps}")
        print(f"预期: {c.expected}")
