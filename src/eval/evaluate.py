import os
import json
import random
import chromadb
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection("flask_bugs")
llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url=os.getenv("DEEPSEEK_BASE_URL"))


def call_llm(prompt, temperature=0.2):
    resp = llm.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def analyze(bug_desc, exclude_title=""):
    """根因分析（排除自身检索 + 要求落到具体机制）"""
    raw = collection.query(query_texts=[bug_desc], n_results=5)["documents"][0]
    key = exclude_title[:25]
    docs = [d for d in raw if key not in d][:3]
    context = "\n\n".join(d[:400] for d in docs) if docs else "（无历史案例）"
    prompt = f"""你是缺陷根因分析专家。根据 bug 描述和历史相似案例，推断根因。

bug 描述：{bug_desc}
历史相似 bug：{context}

要求：根因必须指出具体技术原因（具体函数、配置项、机制或版本），不能只复述症状。"""
    return call_llm(prompt, 0.2)


def judge(bug_desc, prediction, ground_truth):
    """严格裁判：必须落到具体机制才算对"""
    prompt = f"""你是严格的评测裁判。

bug：{bug_desc[:500]}
预测根因：{prediction}
标准答案：{ground_truth}

判定规则：预测必须与标准答案指向同一个技术问题，并指出具体机制（函数/配置/版本/行为）。
只是复述症状、说"可能是某问题"但没落到具体机制的，一律 FAIL。
只输出 PASS 或 FAIL。"""
    return call_llm(prompt, 0.0)


def main():
    with open("data/processed/flask_triples.json", encoding="utf-8") as f:
        triples = json.load(f)
    # 评估集：只用 body 描述足够长的，且不给标题
    candidates = [t for t in triples if t.get("fix_title") and len((t.get("bug_body") or "")) >= 150]
    print(f"可用评估集: {len(candidates)} 条")
    random.seed(42)
    eval_set = random.sample(candidates, min(10, len(candidates)))

    hits = 0
    for i, t in enumerate(eval_set, 1):
        bug = (t["bug_body"] or "")[:600]        # 只用原始描述，标题不喂
        pred = analyze(bug, t["bug_title"])
        verdict = judge(bug, pred, t["fix_title"])
        ok = "PASS" in verdict.upper()
        hits += ok
        print(f"[{i}/{len(eval_set)}] {'✅' if ok else '❌'} issue #{t['issue_id']}: {t['bug_title'][:50]}")
        if not ok:
            print(f"    预测: {pred[:120]}")
            print(f"    标准: {t['fix_title'][:120]}")
    print(f"\n根因分析准确率: {hits}/{len(eval_set)} = {hits/len(eval_set):.0%}")

if __name__ == "__main__":
    main()
