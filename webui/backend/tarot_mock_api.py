"""
塔罗占卜 Mock API

运行方式:
uvicorn tarot_mock_api:app --reload --port 8011
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


SESSION_TTL_MINUTES = 30
QUESTION_MIN_LENGTH = 6
QUESTION_MAX_LENGTH = 120
UNSAFE_KEYWORDS = [
    "自杀",
    "轻生",
    "不想活",
    "结束生命",
    "伤害自己",
    "杀人",
]


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class CreateDivinationRequest(BaseModel):
    question: str = Field(..., description="用户输入的占卜问题")
    spread_id: str = Field(..., description="牌阵 ID")


class DrawCardRequest(BaseModel):
    client_draw_index: int | None = Field(default=None, description="前端当前认为的抽牌序号")


router = APIRouter(tags=["tarot-mock"])


def register_exception_handlers(target_app: FastAPI) -> None:
    @target_app.exception_handler(ApiError)
    async def handle_api_error(_request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @target_app.exception_handler(Exception)
    async def handle_unexpected_error(_request, _exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "服务内部异常"}},
        )


app = FastAPI(title="Tarot Mock API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(router)


@router.get("/api/v1/health")
def get_health():
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "service": "tarot-api", "mode": "mock"},
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_deck() -> list[dict[str, Any]]:
    major_arcana = [
        ("major-00", "愚者", ["新开始", "勇气", "探索"], ["迷失", "冲动", "迟疑"]),
        ("major-01", "魔术师", ["主动", "创造", "掌控"], ["虚张声势", "分散", "失衡"]),
        ("major-02", "女祭司", ["直觉", "沉静", "洞察"], ["封闭", "迟疑", "疏离"]),
        ("major-03", "皇后", ["丰盛", "滋养", "感受"], ["放纵", "依赖", "停滞"]),
        ("major-04", "皇帝", ["秩序", "边界", "主导"], ["控制", "僵化", "压抑"]),
        ("major-05", "教皇", ["传统", "学习", "信念"], ["教条", "束缚", "抗拒"]),
        ("major-06", "恋人", ["联结", "选择", "真诚"], ["摇摆", "失衡", "诱惑"]),
        ("major-07", "战车", ["推进", "意志", "胜利"], ["失控", "分裂", "阻滞"]),
        ("major-08", "力量", ["耐心", "韧性", "温柔"], ["压抑", "脆弱", "透支"]),
        ("major-09", "隐者", ["独处", "沉思", "寻找"], ["封闭", "迟缓", "疏离"]),
        ("major-10", "命运之轮", ["转折", "机会", "循环"], ["反复", "波动", "迟滞"]),
        ("major-11", "正义", ["平衡", "判断", "责任"], ["偏差", "逃避", "失衡"]),
        ("major-12", "倒吊人", ["等待", "换位", "领悟"], ["拖延", "受困", "停摆"]),
        ("major-13", "死神", ["结束", "蜕变", "更新"], ["抗拒", "执着", "消耗"]),
        ("major-14", "节制", ["协调", "流动", "修复"], ["失调", "过度", "分裂"]),
        ("major-15", "恶魔", ["欲望", "绑定", "诱因"], ["依赖", "失控", "内耗"]),
        ("major-16", "高塔", ["打破", "觉醒", "重建"], ["动荡", "突发", "崩裂"]),
        ("major-17", "星星", ["希望", "疗愈", "指引"], ["失望", "迷茫", "飘忽"]),
        ("major-18", "月亮", ["潜意识", "敏感", "想象"], ["疑虑", "误读", "不安"]),
        ("major-19", "太阳", ["清晰", "喜悦", "成长"], ["迟缓", "内耗", "遮蔽"]),
        ("major-20", "审判", ["召唤", "复盘", "觉察"], ["停留", "迟疑", "未决"]),
        ("major-21", "世界", ["完成", "整合", "圆满"], ["未竟", "拖延", "循环"]),
    ]

    suit_meta = {
        "cups": {"cn": "圣杯", "element": "water"},
        "wands": {"cn": "权杖", "element": "fire"},
        "swords": {"cn": "宝剑", "element": "air"},
        "pentacles": {"cn": "星币", "element": "earth"},
    }
    minor_ranks = [
        ("01", "一"),
        ("02", "二"),
        ("03", "三"),
        ("04", "四"),
        ("05", "五"),
        ("06", "六"),
        ("07", "七"),
        ("08", "八"),
        ("09", "九"),
        ("10", "十"),
        ("page", "侍从"),
        ("knight", "骑士"),
        ("queen", "王后"),
        ("king", "国王"),
    ]

    deck: list[dict[str, Any]] = []
    for card_id, name_cn, upright_keywords, reversed_keywords in major_arcana:
        deck.append(
            {
                "id": card_id,
                "name_cn": name_cn,
                "arcana_type": "major",
                "suit": None,
                "element": None,
                "upright_keywords": upright_keywords,
                "reversed_keywords": reversed_keywords,
            }
        )

    for suit_key, meta in suit_meta.items():
        for rank_code, rank_cn in minor_ranks:
            deck.append(
                {
                    "id": f"{suit_key}-{rank_code}",
                    "name_cn": f"{meta['cn']}{rank_cn}",
                    "arcana_type": "minor",
                    "suit": suit_key,
                    "element": meta["element"],
                    "upright_keywords": [f"{meta['cn']}能量", "推进", "体验"],
                    "reversed_keywords": [f"{meta['cn']}受阻", "迟疑", "修整"],
                }
            )
    return deck


DECK = build_deck()
CARD_LOOKUP = {card["id"]: card for card in DECK}
SESSIONS: dict[str, dict[str, Any]] = {}

SPREADS = {
    "three-card": {
        "id": "three-card",
        "name": "三牌阵",
        "subtitle": "过去、现在、未来",
        "description": "最简单直接的牌阵，适合日常问题和快速指引",
        "card_count": 3,
        "premium_reserved": False,
        "positions": [
            {"index": 0, "key": "past", "name": "过去", "description": "影响现在的情况和经历"},
            {"index": 1, "key": "present", "name": "现在", "description": "当前的状态和挑战"},
            {"index": 2, "key": "future", "name": "未来", "description": "可能的发展和建议"},
        ],
    },
    "celtic-cross": {
        "id": "celtic-cross",
        "name": "凯尔特十字牌阵",
        "subtitle": "经典10张深度牌阵",
        "description": "适合复杂问题的深度分析",
        "card_count": 10,
        "premium_reserved": True,
        "positions": [
            {"index": 0, "key": "present", "name": "现状", "description": "问题的核心状态"},
            {"index": 1, "key": "challenge", "name": "阻碍", "description": "当前主要挑战"},
            {"index": 2, "key": "foundation", "name": "基础", "description": "深层根源与背景"},
            {"index": 3, "key": "past", "name": "过去", "description": "即将远去的影响"},
            {"index": 4, "key": "goal", "name": "目标", "description": "意识层的愿望与目标"},
            {"index": 5, "key": "near_future", "name": "近期", "description": "短期内的发展方向"},
            {"index": 6, "key": "self", "name": "自我", "description": "你当前的态度与状态"},
            {"index": 7, "key": "environment", "name": "环境", "description": "外部关系与环境影响"},
            {"index": 8, "key": "hope_fear", "name": "希望与恐惧", "description": "内在拉扯"},
            {"index": 9, "key": "outcome", "name": "结果", "description": "整体走向与结论"},
        ],
    },
    "seven-planets": {
        "id": "seven-planets",
        "name": "七行星牌阵",
        "subtitle": "一周运势指引",
        "description": "基于七行星的能量，适合时间周期性占卜",
        "card_count": 7,
        "premium_reserved": True,
        "positions": [
            {"index": 0, "key": "self", "name": "自我状态", "description": "你当前的基础能量"},
            {"index": 1, "key": "love", "name": "情感关系", "description": "情感与关系走向"},
            {"index": 2, "key": "career", "name": "事业发展", "description": "事业与行动趋势"},
            {"index": 3, "key": "wealth", "name": "财富能量", "description": "金钱与资源状态"},
            {"index": 4, "key": "action", "name": "行动力", "description": "推进事务的力量"},
            {"index": 5, "key": "outside", "name": "外部影响", "description": "周围环境的干扰与帮助"},
            {"index": 6, "key": "overall", "name": "总体走向", "description": "本周期总体趋势"},
        ],
    },
}


def cleanup_sessions() -> None:
    now = utc_now()
    expired_ids = [session_id for session_id, session in SESSIONS.items() if session["expires_at"] <= now]
    for session_id in expired_ids:
        SESSIONS.pop(session_id, None)


def get_spread_or_404(spread_id: str) -> dict[str, Any]:
    spread = SPREADS.get(spread_id)
    if not spread:
        raise ApiError(404, "SPREAD_NOT_FOUND", "未找到对应牌阵")
    return spread


def get_session_or_404(session_id: str) -> dict[str, Any]:
    cleanup_sessions()
    session = SESSIONS.get(session_id)
    if not session:
        raise ApiError(404, "SESSION_NOT_FOUND", "会话不存在或已过期")
    return session


def validate_question(question: str) -> str:
    normalized = " ".join(question.strip().split())
    if not normalized:
        raise ApiError(400, "QUESTION_EMPTY", "请先输入你想咨询的问题")
    if len(normalized) < QUESTION_MIN_LENGTH:
        raise ApiError(400, "QUESTION_TOO_SHORT", f"问题至少需要 {QUESTION_MIN_LENGTH} 个字符")
    if len(normalized) > QUESTION_MAX_LENGTH:
        raise ApiError(400, "QUESTION_TOO_LONG", f"问题最多 {QUESTION_MAX_LENGTH} 个字符")
    if any(keyword in normalized for keyword in UNSAFE_KEYWORDS):
        raise ApiError(400, "QUESTION_UNSAFE", "当前问题不适合使用占卜进行判断，请优先寻求专业帮助")
    return normalized


def build_spread_summary(spread: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": spread["id"],
        "name": spread["name"],
        "subtitle": spread["subtitle"],
        "description": spread["description"],
        "card_count": spread["card_count"],
        "premium_reserved": spread["premium_reserved"],
    }


def build_card_meta(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": card["id"],
        "name_cn": card["name_cn"],
        "arcana_type": card["arcana_type"],
        "suit": card["suit"],
        "element": card["element"],
    }


def build_drawn_card(position: dict[str, Any], card: dict[str, Any], orientation: Literal["upright", "reversed"]) -> dict[str, Any]:
    return {
        "position_index": position["index"],
        "position_name": position["name"],
        "card": build_card_meta(card),
        "orientation": orientation,
        "cover_image_url": "/cards/back/gold.png",
        "face_image_url": f"/cards/{card['id']}.png",
    }


def count_elements(drawn_cards: list[dict[str, Any]]) -> dict[str, int]:
    result = {"water": 0, "fire": 0, "air": 0, "earth": 0, "other": 0}
    for drawn in drawn_cards:
        element = drawn["card"].get("element")
        if element in result:
            result[element] += 1
        else:
            result["other"] += 1
    return result


def summarize_keywords(card: dict[str, Any], orientation: str) -> str:
    keywords = card["upright_keywords"] if orientation == "upright" else card["reversed_keywords"]
    return "、".join(keywords[:3])


def render_card_analysis(question: str, position_name: str, card: dict[str, Any], orientation: str) -> str:
    orientation_label = "正位" if orientation == "upright" else "逆位"
    tone = "较为顺畅地流动" if orientation == "upright" else "出现停滞与回拉"
    return (
        f"{position_name}位置出现{card['name_cn']}{orientation_label}，围绕“{question}”，"
        f"它提示这部分能量正在{tone}。你需要留意其中关于"
        f"{summarize_keywords(card, orientation)}的信号。"
    )


def render_reading(session: dict[str, Any]) -> dict[str, Any]:
    drawn_cards = session["drawn_cards"]
    spread = SPREADS[session["spread_id"]]
    question = session["question"]
    elements = count_elements(drawn_cards)

    reading_cards = []
    orientation_labels = []
    card_names = []
    for drawn in drawn_cards:
        card = CARD_LOOKUP[drawn["card"]["id"]]
        orientation = drawn["orientation"]
        orientation_labels.append("正位" if orientation == "upright" else "逆位")
        card_names.append(card["name_cn"])
        reading_cards.append(
            {
                "position_name": drawn["position_name"],
                "card_name": card["name_cn"],
                "orientation": orientation,
                "core_meaning": summarize_keywords(card, orientation),
                "analysis": render_card_analysis(question, drawn["position_name"], card, orientation),
            }
        )

    dominant_element = max(elements.items(), key=lambda item: item[1])[0]
    dominant_text = {
        "water": "情绪与感受",
        "fire": "行动与欲望",
        "air": "理性与判断",
        "earth": "现实与落地",
        "other": "整体能量",
    }[dominant_element]

    return {
        "title": f"{spread['name']}深度解读",
        "opening_message": f"命运的帷幕已经轻轻掀开，围绕“{question}”的问题，你正处在一个值得凝视的节点。",
        "question": question,
        "cards": reading_cards,
        "overall_analysis": f"这组牌显示你当前正在经历一段需要觉察与选择的周期。{ '、'.join(card_names[:3]) }共同指向同一个主题：先看清自己，再决定下一步。",
        "energy_flow": f"本次牌面以{dominant_text}为主轴，说明你需要重点观察该维度的流动。{'、'.join(orientation_labels)}交织，意味着局势并非单线推进，而是在变化中寻找平衡。",
        "conflict_and_harmony": "部分牌面在提醒你推进，部分牌面则要求你放慢。真正的突破不在于强行前进，而在于识别哪些关系、情绪或期待正在互相拉扯。",
        "timing_hint": "短期内适合先观察、再行动。若你愿意先完成内在整理，后续一到两周会更容易看见清晰回应。",
        "action_advice": "先把问题聚焦到一个最核心的决定点上，再采取一步具体行动，例如主动沟通、明确边界、或暂停消耗性的反复猜测。",
        "long_term_advice": "你的答案并不只藏在结果里，更藏在你如何面对不确定性。保持觉察、稳定节奏、减少过度投射，未来会逐步显现更清楚的方向。",
    }


def session_snapshot(session: dict[str, Any]) -> dict[str, Any]:
    spread = SPREADS[session["spread_id"]]
    remaining_count = spread["card_count"] - len(session["drawn_cards"])
    return {
        "session_id": session["id"],
        "status": session["status"],
        "question": session["question"],
        "spread_id": session["spread_id"],
        "spread": build_spread_summary(spread),
        "positions": spread["positions"],
        "drawn_cards": session["drawn_cards"],
        "remaining_count": remaining_count,
        "reading": session["reading"],
        "expires_at": isoformat(session["expires_at"]),
    }


@router.get("/api/v1/spreads")
def get_spreads():
    items = [build_spread_summary(spread) for spread in SPREADS.values()]
    return {"items": items}


@router.get("/api/v1/spreads/{spread_id}")
def get_spread_detail(spread_id: str):
    spread = get_spread_or_404(spread_id)
    return {**build_spread_summary(spread), "positions": spread["positions"]}


@router.post("/api/v1/divinations")
def create_divination(payload: CreateDivinationRequest):
    question = validate_question(payload.question)
    spread = get_spread_or_404(payload.spread_id)
    expires_at = utc_now() + timedelta(minutes=SESSION_TTL_MINUTES)
    session_id = f"div_{uuid.uuid4().hex[:8]}"
    deck_ids = [card["id"] for card in DECK]
    random.shuffle(deck_ids)

    session = {
        "id": session_id,
        "question": question,
        "spread_id": spread["id"],
        "status": "drawing",
        "deck_ids": deck_ids,
        "drawn_cards": [],
        "reading": None,
        "expires_at": expires_at,
    }
    SESSIONS[session_id] = session

    return {
        "session_id": session_id,
        "status": "drawing",
        "question": question,
        "spread": build_spread_summary(spread),
        "positions": spread["positions"],
        "remaining_count": spread["card_count"],
        "expires_at": isoformat(expires_at),
    }


@router.post("/api/v1/divinations/{session_id}/draw")
def draw_card(session_id: str, payload: DrawCardRequest):
    session = get_session_or_404(session_id)
    spread = SPREADS[session["spread_id"]]
    current_draw_index = len(session["drawn_cards"])

    if current_draw_index >= spread["card_count"]:
        raise ApiError(400, "DRAW_ALREADY_COMPLETE", "当前会话已经完成全部抽牌")

    position = spread["positions"][current_draw_index]
    card_id = session["deck_ids"].pop()
    card = CARD_LOOKUP[card_id]
    orientation: Literal["upright", "reversed"] = random.choice(["upright", "reversed"])
    drawn_card = build_drawn_card(position, card, orientation)
    session["drawn_cards"].append(drawn_card)

    remaining_count = spread["card_count"] - len(session["drawn_cards"])
    all_cards_drawn = remaining_count == 0
    session["status"] = "draw_complete" if all_cards_drawn else "drawing"

    return {
        "session_id": session_id,
        "status": session["status"],
        "current_position_index": position["index"],
        "next_position_index": None if all_cards_drawn else current_draw_index + 1,
        "remaining_count": remaining_count,
        "drawn_card": drawn_card,
        "all_cards_drawn": all_cards_drawn,
    }


@router.post("/api/v1/divinations/{session_id}/reading")
def generate_reading(session_id: str):
    session = get_session_or_404(session_id)
    spread = SPREADS[session["spread_id"]]

    if len(session["drawn_cards"]) < spread["card_count"]:
        raise ApiError(400, "DRAW_NOT_COMPLETE", "请先完成全部抽牌，再生成解读")

    if session["reading"] is None:
        session["reading"] = render_reading(session)
    session["status"] = "reading_ready"

    return {
        "session_id": session_id,
        "status": "reading_ready",
        "reading": session["reading"],
    }


@router.get("/api/v1/divinations/{session_id}")
def get_divination_session(session_id: str):
    session = get_session_or_404(session_id)
    return session_snapshot(session)
