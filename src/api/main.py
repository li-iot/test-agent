import os
import sys
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.graph.multi_agent import graph

api = FastAPI(title="智能测开 Agent", description="输入 bug 描述，自动生成用例、执行、定位根因")


class AnalyzeRequest(BaseModel):
    bug_desc: str


class AnalyzeResponse(BaseModel):
    test_code: str
    returncode: int
    analysis: str
    fix_suggestion: str


@api.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """核心接口：跑完整多 Agent 流程"""
    result = graph.invoke({"bug_desc": req.bug_desc, "stage": "start"})
    return AnalyzeResponse(
        test_code=result["test_code"],
        returncode=result["returncode"],
        analysis=result["analysis"],
        fix_suggestion=result["fix_suggestion"],
    )


@api.get("/health")
def health():
    return {"status": "ok"}
# ===== 自动修复闭环接口 =====
from pydantic import BaseModel
from src.graph.self_fix_loop import run_fix_loop


class FixRequest(BaseModel):
    bug_desc: str = "GET /add?a=2&b=3 应该返回 5，实际返回了 -1"
    max_rounds: int = 3


@api.post("/fix")
def fix_endpoint(req: FixRequest):
    """跑完整自动修复闭环：测试 → 失败 → 改代码 → 重跑 → 报告"""
    return run_fix_loop(bug_desc=req.bug_desc, max_rounds=req.max_rounds)
