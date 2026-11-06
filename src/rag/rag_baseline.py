import os
import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection("flask_bugs")

llm = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),
)

def retrieve(query, k=3):
    """从向量库检索最相似的 k 条历史 bug"""
    results = collection.query(query_texts=[query], n_results=k)
    return results["documents"][0]

def analyze(new_bug):
    similar = retrieve(new_bug)                                    # 1. 检索
    context = "\n\n".join(f"[历史案例{i+1}]\n{d[:800]}" for i, d in enumerate(similar))  # 2. 拼上下文

    prompt = f"""你是 Flask 项目的资深测试开发工程师。
用户报告了一个新 bug：
{new_bug}

以下是历史上相似的 bug 及修复记录，供你参考：
{context}

请分析：
1. 最可能的原因
2. 排查步骤
3. 可参考的历史修复方案
"""
    resp = llm.chat.completions.create(                              # 3. 调 DeepSeek
        model=os.getenv("DEEPSEEK_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content

if __name__ == "__main__":
    test_bug = "When I use url_for() with a route that has a variable, it returns 404 instead of the correct URL"
    print(analyze(test_bug))
