"""
复用现有 LLM 解析逻辑，提供给 WebUI 调用。
直接读取 iterative_parse_eval.py 中的 prompt 和解析逻辑。
"""
import os
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到路径，以便导入 scripts 下的模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from openai import OpenAI


PROMPT_PATH = PROJECT_ROOT / "scripts" / "prompts" / "guiding_case_ontology_aligned.txt"


def load_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"未找到 prompt 文件: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def parse_text_to_kg(raw_text: str, model: str = "deepseek-v4-pro") -> Dict[str, Any]:
    """调用 LLM 解析案例文本，返回结构化 JSON。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")

    if not api_key:
        raise RuntimeError("缺少 OPENAI_API_KEY 环境变量")

    client = OpenAI(api_key=api_key, base_url=base_url)
    system_prompt = load_prompt()

    user_prompt = f"""请对以下案例文本进行知识图谱解析，严格按照本体论结构输出 JSON。

### 案例原文
{raw_text}

### 输出要求
请只输出纯 JSON，不要任何解释或 markdown 代码块标记。"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=4096,
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    parsed = json.loads(content)
    return parsed
