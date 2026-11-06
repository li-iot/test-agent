import os
import subprocess
import sys
from typing import TypedDict
import chromadb
from dotenv import load_dotenv
from openai import OpenAI
from langgraph.graph import StateGraph, START, END

load_dotenv()

client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection("flask_bugs")
llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=os.getenv("DEEPSEEK_BASE_URL"))


class AgentState(TypedDict):
    bug_desc: str
    stage: str          # 进度标记：start/generated/executed/analyzed/fixed
    next: str           # supervisor 派活结果
    test_code: str
    returncode: int
    stdout: str
    analysis: str
    fix_suggestion: str


def retrieve(query, k=3):
    return collection.query(query_texts=[query], n_results=k)["documents"][0]


def call_llm(prompt, temperature=0.2):
    resp = llm.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


# ========== 四个专家 Agent ==========

def generator_agent(state):
    """① 用例生成 Agent：产出可执行 pytest 代码"""
    bug = state["bug_desc"]
    context = "\n\n".join(d[:400] for d in retrieve(bug))
    prompt = f"""你是测试用例设计专家。被测应用位于 sut/buggy_app.py，用 `from sut.buggy_app import app` 导入。

bug 描述：{bug}
历史参考：{context}

生成可直接运行的 pytest 测试文件，要求：
1. 只输出 Python 代码，不要 ``` 标记和解释
2. 顶部 import pytest 和 from sut.buggy_app import app
3. 每个用例一个 def test_xxx()，用 app.test_client() 发真实请求，断言解析 JSON"""
    return {"test_code": call_llm(prompt), "stage": "generated"}


def executor_agent(state):
    """② 测试执行 Agent：跑 pytest，拿回结果"""
    os.makedirs("tests", exist_ok=True)
    with open("tests/test_generated.py", "w", encoding="utf-8") as f:
        f.write(state["test_code"])
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_generated.py", "-v", "--tb=short"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return {"returncode": result.returncode, "stdout": result.stdout, "stage": "executed"}


def analyzer_agent(state):
    """③ 根因分析 Agent：结合 RAG 定位问题"""
    context = "\n\n".join(d[:400] for d in retrieve(state["bug_desc"]))
    prompt = f"""你是缺陷根因分析专家。

bug 描述：{state['bug_desc']}
pytest 失败输出：{state['stdout'][-1800:]}
历史相似 bug：{context}
被测代码：sut/buggy_app.py 的 add() 里 return jsonify({{"result": a - b}})

分析：1) 是被测代码还是测试代码的问题 2) 根因定位到文件和行 3) 一句话结论"""
    return {"analysis": call_llm(prompt, 0.3), "stage": "analyzed"}


def fixer_agent(state):
    """④ 修复建议 Agent：给出可落地的修改方案"""
    prompt = f"""你是资深开发工程师。根据根因分析，给出具体修复方案。

根因分析：{state['analysis']}

请输出：
1. 要改的文件和行号
2. 修改前 → 修改后（代码级）
3. 需要补充的回归测试点"""
    return {"fix_suggestion": call_llm(prompt, 0.2), "stage": "fixed"}


# ========== Supervisor（调度者） ==========

def supervisor(state):
    """看进度决定派谁：这是整个系统的决策中枢"""
    stage = state.get("stage", "start")
    if stage == "start":
        return {"next": "generator"}
    if stage == "generated":
        return {"next": "executor"}
    if stage == "executed":
        return {"next": "finish" if state["returncode"] == 0 else "analyzer"}
    if stage == "analyzed":
        return {"next": "fixer"}
    return {"next": "finish"}


builder = StateGraph(AgentState)
builder.add_node("supervisor", supervisor)
builder.add_node("generator", generator_agent)
builder.add_node("executor", executor_agent)
builder.add_node("analyzer", analyzer_agent)
builder.add_node("fixer", fixer_agent)

builder.add_edge(START, "supervisor")
builder.add_conditional_edges(
    "supervisor",
    lambda s: s["next"],
    {"generator": "generator", "executor": "executor",
     "analyzer": "analyzer", "fixer": "fixer", "finish": END},
)
for name in ["generator", "executor", "analyzer", "fixer"]:
    builder.add_edge(name, "supervisor")     # 每个专家干完都回调度中心报到

graph = builder.compile()


if __name__ == "__main__":
    bug = "GET /add?a=2&b=3 应该返回 5，实际返回了 -1"
    result = graph.invoke({"bug_desc": bug, "stage": "start"})
    print("=== ① 生成的测试代码 ===")
    print(result["test_code"][:500], "...")
    print(f"\n=== ② pytest 退出码: {result['returncode']} ===")
    print(result["stdout"][-300:])
    print("\n=== ③ 根因分析 ===")
    print(result["analysis"])
    print("\n=== ④ 修复建议 ===")
    print(result["fix_suggestion"])
