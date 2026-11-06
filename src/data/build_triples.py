import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}
REPO = "pallets/flask"
TIMELINE_HEADERS = {**HEADERS, "Accept": "application/vnd.github.mockingbird-preview"}

def get_with_retry(url, headers, retries=5):
    """带重试的请求：断了自动重连，越等越久"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                print("触发限流，等 60 秒再试...")
                time.sleep(60)
                continue
            return resp
        except requests.exceptions.ConnectionError as e:
            print(f"连接被断开（第 {attempt+1} 次），等 {3*(attempt+1)} 秒重试...")
            time.sleep(3 * (attempt + 1))   # 3秒、6秒、9秒...递增
    print(f"重试 {retries} 次仍失败，跳过: {url}")
    return None

def find_fix_pr(issue_id):
    url = f"https://api.github.com/repos/{REPO}/issues/{issue_id}/timeline"
    resp = get_with_retry(url, TIMELINE_HEADERS)
    if resp is None or resp.status_code != 200:
        return None
    for event in resp.json():
        if event.get("event") == "cross-referenced":
            src = event.get("source", {})
            issue = src.get("issue", {})
            if issue and "pull_request" in issue:
                return issue["number"]
    return None

def get_fix_diff(pr_number):
    url = f"https://api.github.com/repos/{REPO}/pulls/{pr_number}"
    resp = get_with_retry(url, HEADERS)
    if resp is None or resp.status_code != 200:
        return None, None
    pr = resp.json()
    sha = pr.get("merge_commit_sha")
    if not sha:
        return pr.get("title"), None
    url2 = f"https://api.github.com/repos/{REPO}/commits/{sha}"
    resp2 = get_with_retry(url2, HEADERS)
    if resp2 is None or resp2.status_code != 200:
        return pr.get("title"), None
    patches = []
    for f in resp2.json().get("files", []):
        patch = f.get("patch", "")
        if patch:
            patches.append(f"## 文件: {f['filename']}\n{patch}")
    return pr.get("title"), "\n".join(patches)

def main():
    with open("data/raw/flask_issues.json", encoding="utf-8") as f:
        issues = json.load(f)

    triples = []
    for i, issue in enumerate(issues, 1):
        pr_num = find_fix_pr(issue["id"])
        fix_title, fix_diff = None, None
        if pr_num:
            fix_title, fix_diff = get_fix_diff(pr_num)
        triples.append({
            "issue_id": issue["id"],
            "bug_title": issue["title"],
            "bug_body": issue["body"],
            "fix_pr": pr_num,
            "fix_title": fix_title,
            "fix_diff": fix_diff,
        })
        print(f"[{i}/{len(issues)}] issue #{issue['id']} -> PR {pr_num}")
        time.sleep(0.5)
    with open("data/processed/flask_triples.json", "w", encoding="utf-8") as f:
        json.dump(triples, f, ensure_ascii=False, indent=2)
    has_fix = sum(1 for t in triples if t["fix_diff"])
    print(f"完成！共 {len(triples)} 条，其中 {has_fix} 条有修复代码")

if __name__ == "__main__":
    main()
