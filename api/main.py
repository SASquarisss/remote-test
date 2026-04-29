"""
FastAPI 主应用
运行: uvicorn api.main:app --reload --port 8000
"""
from fastapi import FastAPI
from api.routers import query

app = FastAPI(
    title="Legal KG Platform API",
    description="生产级法律知识图谱平台 - 类案查询与判决推理",
    version="0.1.0"
)

app.include_router(query.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "legal-kg-api"}
