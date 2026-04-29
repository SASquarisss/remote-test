"""
类案查询与判决推理 API
FastAPI Router
"""
from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kg_core.graph_store.neo4j_hot_client import Neo4jHotClient
from kg_core.case_reasoning.sentencing_predictor import SentencingPredictor


router = APIRouter(prefix="/api/v1", tags=["case-reasoning"])


def get_neo4j_client() -> Neo4jHotClient:
    return Neo4jHotClient()


# ---------- 请求/响应模型 ----------
class SimilarCaseRequest(BaseModel):
    case_type_id: str = Field(..., example="case_type_civil_001")
    court_level: str = Field(..., example="basic")
    claim_amount: Optional[float] = Field(None, example=500000.0)
    provision_ids: Optional[List[str]] = Field(None, example=["provision_civil_code_1042"])
    disputed_issues: Optional[List[str]] = Field(None, example=["离婚财产分割"])
    filing_date_after: Optional[str] = Field("2021-01-01", example="2021-01-01")
    limit: int = Field(20, ge=1, le=100)


class JudgmentPredictionRequest(BaseModel):
    case_type_id: str
    court_level: str
    claim_amount: Optional[float] = None
    provision_ids: Optional[List[str]] = None
    disputed_issues: Optional[List[str]] = None
    filing_date_after: Optional[str] = "2021-01-01"


class OrganizationHistoryRequest(BaseModel):
    credit_code: str = Field(..., pattern=r"^[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}$")
    role: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)


# ---------- 接口 ----------
@router.post("/cases/similar")
def find_similar_cases(req: SimilarCaseRequest, client: Neo4jHotClient = Depends(get_neo4j_client)):
    """类案检索：基于案由、法院层级、标的额、引用法条查找相似案件"""
    try:
        cases = client.find_similar_cases(
            case_type_id=req.case_type_id,
            court_level=req.court_level,
            claim_amount=req.claim_amount,
            provision_ids=req.provision_ids,
            filing_date_after=req.filing_date_after,
            limit=req.limit
        )
        return {
            "status": "ok",
            "count": len(cases),
            "cases": cases
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cases/predict")
def predict_judgment(req: JudgmentPredictionRequest):
    """判决推理：返回概率区间 + 指导案例 + 建议"""
    try:
        predictor = SentencingPredictor()
        report = predictor.predict(req.model_dump(exclude_none=True))
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guiding-cases")
def list_guiding_cases(
    case_type_id: str,
    disputed_issues: Optional[str] = None,
    limit: int = 10,
    client: Neo4jHotClient = Depends(get_neo4j_client)
):
    """指导性案例检索，按 binding_force 优先级排序"""
    issues = [i.strip() for i in disputed_issues.split(",")] if disputed_issues else None
    try:
        cases = client.find_guiding_case_prioritized(
            case_type_id=case_type_id,
            disputed_issues=issues,
            limit=limit
        )
        return {
            "status": "ok",
            "count": len(cases),
            "guiding_cases": cases
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/organization/history")
def organization_litigation_history(
    req: OrganizationHistoryRequest,
    client: Neo4jHotClient = Depends(get_neo4j_client)
):
    """通过统一社会信用代码查询企业涉诉历史（跨案件关联）"""
    try:
        cases = client.find_cases_by_organization(
            credit_code=req.credit_code,
            role=req.role,
            limit=req.limit
        )
        return {
            "status": "ok",
            "credit_code": req.credit_code,
            "count": len(cases),
            "cases": cases
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
