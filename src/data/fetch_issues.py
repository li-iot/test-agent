import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()  # 读取 .env 里的配置
TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

BASE_URL = "https://api.github.com/repos/pallets/flask/issues"

def fetch_issues(pages=5):
    all_issues = []
    for page in range(1, pages + 1):
        params = {
            "state": "closed",   # 只要已关闭的 issue（关了才说明有结论）
            "per_page": 100,     # 每页拉 100 条
            "page": page,        # 翻页
        }
        resp = requests.get(BASE_URL, headers=HEADERS, params=params)
        if resp.status_code != 200:
            print(f"第 {page} 页请求失败: {resp.status_code}")
            time.sleep(60)
            continue
        page_data = resp.json()
        for item in page_data:
            if "pull_request" in item:          # 跳过 PR（GitHub 会把 PR 混进 issue 列表）
                continue
            text = (item.get("title", "") + " " + item.get("body", "")).lower()
            if any(kw in text for kw in ["error", "bug", "crash", "fail", "exception", "traceback"]):
                all_issues.append({
                    "id": item["number"],
                    "title": item["title"],
                    "body": item.get("body", ""),
                    "labels": [l["name"] for l in item.get("labels", [])],
                    "created_at": item["created_at"],
                    "closed_at": item["closed_at"],
                })
        print(f"第 {page} 页完成，累计 {len(all_issues)} 条")
        time.sleep(1)   # 礼貌限速，别把 GitHub 打爆
    return all_issues

if __name__ == "__main__":
    issues = fetch_issues(pages=5)
    os.makedirs("data/raw", exist_ok=True)
    with open("data/raw/flask_issues.json", "w", encoding="utf-8") as f:
        json.dump(issues, f, ensure_ascii=False, indent=2)
    print(f"完成！保存了 {len(issues)} 条 issue 到 data/raw/flask_issues.json")
