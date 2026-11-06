import json
import chromadb

# 1. 读三元组
with open("data/processed/flask_triples.json", encoding="utf-8") as f:
    triples = json.load(f)

# 2. 把每条经验拼成一段文字（检索时的"档案"）
documents = []
ids = []
metadatas = []
for t in triples:
    doc = f"Bug: {t['bug_title']}\n描述: {t['bug_body']}\n修复: {t['fix_diff'] or '（无修复记录）'}"
    documents.append(doc)
    ids.append(str(t["issue_id"]))
    metadatas.append({"fix_pr": str(t["fix_pr"] or "")})

# 3. 建 ChromaDB，持久化到 data/chroma_db 文件夹
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_or_create_collection("flask_bugs")

# 4. 全部入库（embedding 自动算，不需要手动调模型）
collection.add(ids=ids, documents=documents, metadatas=metadatas)
print(f"入库完成！共 {collection.count()} 条经验")

# 5. 验证：随便搜一个"新的 bug"，看能不能找到相似的
results = collection.query(query_texts=["route not found 404"], n_results=3)
for i, (doc, dist) in enumerate(zip(results["documents"][0], results["distances"][0])):
    print(f"--- 第{i+1}条 (距离{dist:.4f}) ---")
    print(doc[:200])
