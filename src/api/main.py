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
