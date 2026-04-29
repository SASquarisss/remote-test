.PHONY: help install up down import api test lint

help:
	@echo "Legal KG Platform - 常用命令"
	@echo "  make install     - 安装依赖"
	@echo "  make up          - 启动 Neo4j + ES + MinIO (需要 docker)"
	@echo "  make down        - 停止服务"
	@echo "  make import      - 导入 Gold 层 CSV 到 Neo4j"
	@echo "  make api         - 启动 FastAPI 服务"
	@echo "  make test        - 运行测试"

install:
	pip install -r requirements.txt

up:
	docker-compose up -d
	@echo "Neo4j: http://localhost:7474 (neo4j/legalkg2026)"
	@echo "ES:    http://localhost:9200"
	@echo "MinIO: http://localhost:9001 (legalkg/legalkg2026)"

down:
	docker-compose down

import:
	python pipelines/bulk_import.py --data-dir ./data_lake/gold

api:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

lint:
	flake8 kg_core/ api/ pipelines/ extraction/ --max-line-length=120
