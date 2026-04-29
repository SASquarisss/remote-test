"""
判决推理引擎：类案统计 + 指导案例加权
输出：概率区间 + 强制/参照指导案例
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
from kg_core.graph_store.neo4j_hot_client import Neo4jHotClient


class SentencingPredictor:
    def __init__(self, client: Optional[Neo4jHotClient] = None):
        self.client = client or Neo4jHotClient()

    def predict(self, case_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据案件画像返回综合判决推理报告

        case_profile = {
            "case_type_id": "case_type_civil_001",
            "court_level": "basic",
            "claim_amount": 500000.0,
            "provision_ids": ["provision_civil_code_1042", ...],
            "disputed_issues": ["离婚财产分割"],
            "filing_date_after": "2021-01-01"
        }
        """
        case_type_id = case_profile["case_type_id"]
        court_level = case_profile["court_level"]
        claim_amount = case_profile.get("claim_amount")
        provision_ids = case_profile.get("provision_ids", [])
        disputed_issues = case_profile.get("disputed_issues", [])
        filing_date_after = case_profile.get("filing_date_after", "2021-01-01")

        # 1. 类案统计
        stats = self.client.predict_judgment_distribution(
            case_type_id=case_type_id,
            court_level=court_level,
            claim_amount=claim_amount,
            filing_date_after=filing_date_after,
            min_samples=30
        )

        # 2. 类案子图检索（Top 20）
        similar_cases = self.client.find_similar_cases(
            case_type_id=case_type_id,
            court_level=court_level,
            claim_amount=claim_amount,
            provision_ids=provision_ids,
            filing_date_after=filing_date_after,
            limit=20
        )

        # 3. 指导性案例加权
        guiding_cases = self.client.find_guiding_case_prioritized(
            case_type_id=case_type_id,
            disputed_issues=disputed_issues,
            limit=10
        )

        # 4. 拼装报告
        report = {
            "case_profile": case_profile,
            "statistical_prediction": self._format_stats(stats, claim_amount),
            "similar_cases": similar_cases[:5],  # 仅展示前5
            "guiding_cases": self._format_guiding(guiding_cases),
            "recommendations": self._generate_recommendations(stats, guiding_cases)
        }
        return report

    def _format_stats(self, stats: Dict[str, Any], claim_amount: Optional[float]) -> Dict[str, Any]:
        if stats.get("status") != "ok":
            return stats

        comp = stats.get("compensation_quartiles", {})
        sent = stats.get("sentence_quartiles", {})

        result = {
            "sample_size": stats["total"],
            "win_rate": f"{stats['win_rate']*100:.1f}%",
            "compensation_range": self._safe_range(comp, "赔偿金额"),
            "sentence_range": self._safe_range(sent, "量刑/处罚"),
            "result_distribution": stats.get("result_distribution", [])
        }

        if claim_amount and comp:
            # 计算诉请金额与历史判赔的偏离度
            median = comp.get("0.5", 0)
            if median > 0:
                deviation = (claim_amount - median) / median
                result["claim_deviation_from_median"] = f"{deviation*100:+.1f}%"
                if deviation > 0.5:
                    result["warning"] = "当前诉请金额显著高于历史中位数，建议补充特殊情节证据"

        return result

    def _safe_range(self, quartiles: Dict[str, float], label: str) -> str:
        if not quartiles:
            return "暂无数据"
        q25 = quartiles.get("0.25", 0)
        q75 = quartiles.get("0.75", 0)
        median = quartiles.get("0.5", 0)
        return f"{label}: {q25:,.0f} ~ {q75:,.0f}（中位数 {median:,.0f}）"

    def _format_guiding(self, guiding_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for gc in guiding_cases:
            formatted.append({
                "id": gc["id"],
                "number": gc["number"],
                "name": gc["name"],
                "binding_force": gc["binding_force"],
                "force_label": {
                    "mandatory": "强制适用（应当参照）",
                    "persuasive": "参照适用（可以参照）",
                    "reference": "参考意义"
                }.get(gc["binding_force"], "未知"),
                "key_points": gc["points"][:200] + "..." if len(gc["points"]) > 200 else gc["points"]
            })
        return formatted

    def _generate_recommendations(
        self,
        stats: Dict[str, Any],
        guiding_cases: List[Dict[str, Any]]
    ) -> List[str]:
        recs = []

        if stats.get("status") != "ok":
            recs.append("历史样本不足，建议扩大案件检索范围或降低筛选条件")
            return recs

        # 指导性案例强制引用
        mandatory = [g for g in guiding_cases if g.get("binding_force") == "mandatory"]
        if mandatory:
            recs.append(f"存在 {len(mandatory)} 个强制适用指导性案例，判决应当严格对齐案例要点")

        # 胜诉率提示
        win_rate = stats.get("win_rate", 0)
        if win_rate > 0.7:
            recs.append("历史类案原告胜诉率较高，建议重点准备证据链")
        elif win_rate < 0.3:
            recs.append("历史类案原告胜诉率较低，建议评估诉讼策略或考虑调解")

        return recs
