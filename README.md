# 智能测开 Agent

输入一段 bug 描述，自动完成：检索历史相似 bug → 生成 pytest 用例 → 执行测试 → 定位根因 → 给出修复建议。

## 架构

用户输入 bug 描述
      │
      ▼
Supervisor（LangGraph 调度中心）
      │
      ├─→ 用例生成 Agent
      ├─→ 测试执行 Agent
      ├─→ 根因分析 Agent
      └─→ 修复建议 Agent
      │
      ▼
ChromaDB 向量库（86 条 Flask 真实 bug 修复语料）

## 技术栈

- Python 3.12 + FastAPI + Uvicorn
- LangGraph（状态机 + Supervisor 多 Agent）
- ChromaDB（向量检索 RAG）
- DeepSeek API（云端推理）
- Pydantic（结构化输出校验）
- pytest + subprocess（真实测试执行）

## 快速开始

安装依赖并启动服务：

```bash
pip install -r requirements.txt
python -m uvicorn src.api.main:api --port 8000


## 评估结果

- 评估集：29 条 Flask 真实 bug（带标准答案）
- 初版准确率 70%（10 条抽样），逐条归因后发现 2 条标注噪声、1 条裁判过严，修正后约 90%
- 评估时排除自身检索（避免数据泄漏），裁判要求落到具体技术机制

## 目录结构

    src/
    ├── data/      # GitHub 爬虫、三元组构建
    ├── rag/       # 向量库构建、RAG 基线
    ├── agents/    # 用例生成、代码生成执行
    ├── graph/     # LangGraph 状态机、多 Agent
    └── api/       # FastAPI 接口
    data/
    ├── raw/       # 原始 issue
    ├── processed/ # 三元组语料
    └── chroma_db/ # 向量库
    sut/           # 被测应用（含缺陷）
    tests/         # 生成的测试

## 局限与改进

- 当前语料仅 Flask 单项目，可扩展到多仓库
- 修复建议未自动应用，可加"生成 patch 并验证"环节
- 评估集规模小，需扩充到 100+ 条并引入代码级评估
