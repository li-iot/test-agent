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
    """全流程共享的状态（白板）"""
    bug_desc: str
    test_code: str
    returncode: int
    stdout: str
    analysis: str


def retrieve(query, k=3):
    return collection.query(query_texts=[query], n_results=k)["documents"][0]


def generate_node(state: AgentState):
    """节点1：根据 bug 描述生成 pytest 测试代码"""
    bug = state["bug_desc"]
    context = "\n\n".join(d[:400] for d in retrieve(bug))
    prompt = f"""你是资深测试开发工程师。被测 Flask 应用位于 sut/buggy_app.py，用 `from sut.buggy_app import app` 导入。

bug 描述：
{bug}

历史参考：
{context}

请生成一个可直接运行的 pytest 测试文件，要求：
1. 只输出 Python 代码，不要 ``` 标记，不要解释文字
2. 顶部写 import pytest 和 from sut.buggy_app import app
3. 每个测试函数用 def test_xxx()，用 app.test_client() 发真实请求
4. 断言要覆盖这个 bug 场景"""
    resp = llm.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    code = resp.choices[0].message.content.strip()
    if code.startswith("```"):
        code = code.strip("`").removeprefix("python").strip()
    return {"test_code": code}


def execute_node(state: AgentState):
    """节点2：真正执行 pytest，拿回结果"""
    os.makedirs("tests", exist_ok=True)
    with open("tests/test_generated.py", "w", encoding="utf-8") as f:
        f.write(state["test_code"])
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_generated.py", "-v", "--tb=short"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return {"returncode": result.returncode, "stdout": result.stdout}


def route_after_execute(state: AgentState):
    """条件边：通过→结束，失败→分析"""
    return "pass" if state["returncode"] == 0 else "fail"


def analyze_node(state: AgentState):
    """节点3：失败根因分析（结合 RAG 检索的历史 bug）"""
    context = "\n\n".join(d[:400] for d in retrieve(state["bug_desc"]))
    prompt = f"""你是资深测试开发工程师。测试执行失败了，请定位根因。

bug 描述：
{state['bug_desc']}

pytest 失败输出：
{state['stdout'][-2000:]}

历史相似 bug 及修复：
{context}

被测应用 sut/buggy_app.py 的 add 接口代码：
@app.route("/add")
def add():
    a = int(request.args.get("a", 0))
    b = int(request.args.get("b", 0))
    return jsonify({{"result": a - b}})

请给出：
1. 这是测试代码的问题还是被测代码的问题
2. 根因定位到具体文件和具体行
3. 修复建议（哪一行改成什么）"""
    resp = llm.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return {"analysis": resp.choices[0].message.content}


# ===== 组装状态机 =====
builder = StateGraph(AgentState)
builder.add_node("generate", generate_node)
builder.add_node("execute", execute_node)
builder.add_node("analyze", analyze_node)

builder.add_edge(START, "generate")
builder.add_edge("generate", "execute")
builder.add_conditional_edges(
    "execute",
    route_after_execute,
    {"pass": END, "fail": "analyze"},   # 决策：通过结束，失败分析
)
builder.add_edge("analyze", END)

graph = builder.compile()


if __name__ == "__main__":
    bug = "GET /add?a=2&b=3 应该返回 5，实际返回了 -1"
    result = graph.invoke({"bug_desc": bug})
    print("=== ① 生成的测试代码 ===")
    print(result["test_code"])
    print(f"\n=== ② pytest 退出码: {result['returncode']}（1=有失败） ===")
    print(result["stdout"][-800:])
    print("\n=== ③ 根因分析 ===")
    print(result.get("analysis", "（测试全部通过，无需分析）"))
