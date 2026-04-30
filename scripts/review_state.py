#!/usr/bin/env python3
"""
评审状态管理器
维护 opinion/status.json，记录每条建议的生命周期
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

REPO_PATH = Path(os.environ.get("REPO_PATH", Path(__file__).resolve().parent.parent))
STATE_FILE = REPO_PATH / "opinion" / "status.json"


class ReviewState:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return self._default()
        return self._default()

    def _default(self) -> dict:
        return {"version": 1, "opinions": {}, "meta": {}}

    def save(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_opinion(self, opinion_file: str) -> dict:
        return self.data["opinions"].get(opinion_file, {})

    def set_opinion(self, opinion_file: str, items: Dict[str, dict],
                    branch: Optional[str] = None, pr_url: Optional[str] = None):
        self.data["opinions"][opinion_file] = {
            "last_updated": datetime.now().isoformat(),
            "items": items,
            "branch": branch,
            "pr_url": pr_url,
        }
        self.save()

    def update_item(self, opinion_file: str, item_id: str, **kwargs):
        opinion = self.data["opinions"].setdefault(opinion_file, {
            "last_updated": datetime.now().isoformat(),
            "items": {},
            "branch": None,
            "pr_url": None,
        })
        item = opinion["items"].setdefault(str(item_id), {})
        item.update(kwargs)
        item["last_updated"] = datetime.now().isoformat()
        self.save()

    def get_pending_items(self, opinion_file: str) -> List[dict]:
        opinion = self.data["opinions"].get(opinion_file, {})
        items = opinion.get("items", {})
        return [
            {"id": k, **v}
            for k, v in items.items()
            if v.get("state") in ("pending_user", "failed_test")
        ]

    def get_branch_for_opinion(self, opinion_file: str) -> Optional[str]:
        return self.data["opinions"].get(opinion_file, {}).get("branch")

    def mark_item_state(self, opinion_file: str, item_id: str, state: str,
                        **extra):
        """标记单条状态：auto_fixed / pending_user / failed_test / merged / rejected"""
        self.update_item(opinion_file, item_id, state=state, **extra)


if __name__ == "__main__":
    # 简单测试
    rs = ReviewState()
    rs.set_opinion("2026-04-30.md", {
        "1": {"state": "auto_fixed", "classification": "同意"},
        "2": {"state": "pending_user", "classification": "有争议"},
    }, branch="auto-fix/20260430-1000")
    print(json.dumps(rs.data, ensure_ascii=False, indent=2))
    print("\n待确认:", rs.get_pending_items("2026-04-30.md"))
