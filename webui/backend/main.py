"""
FastAPI 后端入口。
提供 /api/parse 和静态文件托管。
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# 确保能导入同级模块
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from parser_bridge import parse_text_to_kg
from kg_builder import convert_to_cytoscape


app = FastAPI(title="法律知识图谱 WebUI", version="0.1.0")

FRONTEND_DIR = BACKEND_DIR.parent / "frontend"


class ParseRequest(BaseModel):
    text: str
    model: str = "deepseek-v4-pro"


class ParseResponse(BaseModel):
    raw_json: Dict[str, Any]
    cytoscape_elements: Dict[str, Any]


@app.post("/api/parse", response_model=ParseResponse)
async def api_parse(req: ParseRequest):
    if not req.text or len(req.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="输入文本过短，请提供完整案例内容")
    try:
        raw = parse_text_to_kg(req.text, model=req.model)
        cy = convert_to_cytoscape(raw)
        return ParseResponse(raw_json=raw, cytoscape_elements=cy)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@app.get("/api/health")
async def health():
    return {"status": "ok", "env": "dev"}


# 静态文件托管（开发时用）
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
