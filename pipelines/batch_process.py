#!/usr/bin/env python3
"""
Batch processor: parse 50 guiding case records from the main CSV and append to Gold layer.
Compatible with pipelines/parse_guiding_cases.py logic.

|v3.0 — Post-audit fixes:
|  Fix 1: TRIAL_LEVEL_MAP dictionary for trial_procedure→trial_level mapping
|  Fix 2: All enum mappings use dictionary pattern with audit logging
|  Fix 3: tags (key_words) cleaned: leading/trailing Chinese colons, spaces
|  Fix 4: district_id set to "" when unresolvable (no strong filling)
"""
import csv
import re
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from extract_legal_provisions_regex import extract_legal_provisions as regex_extract_legal_provisions

# Paths
SOURCE_CSV = Path("/root/.hermes/hermes-agent/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv")
GOLD_DIR = Path("/root/.hermes/hermes-agent/remote-test/data_lake/gold")
BATCH_STATE = Path("/root/.hermes/hermes-agent/remote-test/data/processed/batch_state.json")
BATCH_SIZE = 50

# The first 21 columns are the actual data
HEADER = [
    "id", "web_name", "web_url", "case_type", "storage_no", "court_name",
    "key_words", "trial_procedure", "trial_year", "case_level",
    "basic_facts", "judgment_reason", "judgment_essence",
    "related_info", "related_law", "related_judgment_body",
    "create_time", "update_time", "md5_value", "judgment_mean", "dt"
]
EXPECTED_COLS = len(HEADER)

# ============ Fix 1 & 2: Dictionary-based enum mappings with audit logging ============
# Each map follows the same pattern:
#   - Key: Chinese/raw input value
#   - Value: English enum value (empty string = "unknown" rather than missing)
# After each batch run, check the audit log for unmapped values and add them.

AUDIT_LOG_UNMAPPED = {
    "category": set(),
    "trial_level": set(),
}

CATEGORY_MAP = {
    "民事": "civil",
    "刑事": "criminal",
    "行政": "administrative",
    "知识产权": "ip",
    "执行": "execution",
    "执行实施": "execution",
    "国家赔偿": "state_compensation",
}

# Fix 1: TRIAL_LEVEL_MAP — maintanable dictionary for trial_procedure → trial_level
TRIAL_LEVEL_MAP = {
    "一审": "first_instance",
    "二审": "second_instance",
    "再审": "retrial",
    "执行": "",
    "国家赔偿": "",
    "其他": "",
    "一审程序": "first_instance",
    "二审程序": "second_instance",
    "再审程序": "retrial",
    "重审": "retrial",
    "死刑复核": "",  # 独立于审级的特殊核准程序，不属于first_instance/second_instance/retrial
    # P1 fix: explicitly add values that substring fallback covers but
    # should be in the dictionary for clarity and audit accuracy
    "\\\\N": "",
    "执行监督": "",
    "委赔": "",
    "执行异议": "",
    "执行复议": "",
}

# Backward compat alias
TRIAL_PROCEDURE_MAP = TRIAL_LEVEL_MAP

# ============ P0-3: Province/city keywords for district extraction ============
PROVINCE_KEYWORDS = [
    "省", "自治区", "市",
]

# Common district code mapping for major courts
KNOWN_DISTRICTS = {
    "北京市": "CN-11",
    "天津市": "CN-12",
    "上海市": "CN-31",
    "重庆市": "CN-50",
    "河北省": "CN-13",
    "山西省": "CN-14",
    "辽宁省": "CN-21",
    "吉林省": "CN-22",
    "黑龙江省": "CN-23",
    "江苏省": "CN-32",
    "浙江省": "CN-33",
    "安徽省": "CN-34",
    "福建省": "CN-35",
    "江西省": "CN-36",
    "山东省": "CN-37",
    "河南省": "CN-41",
    "湖北省": "CN-42",
    "湖南省": "CN-43",
    "广东省": "CN-44",
    "广西壮族自治区": "CN-45",
    "海南省": "CN-46",
    "四川省": "CN-51",
    "贵州省": "CN-52",
    "云南省": "CN-53",
    "西藏自治区": "CN-54",
    "陕西省": "CN-61",
    "甘肃省": "CN-62",
    "青海省": "CN-63",
    "宁夏回族自治区": "CN-64",
    "新疆维吾尔自治区": "CN-65",
    "台湾省": "CN-71",
    "香港特别行政区": "CN-81",
    "澳门特别行政区": "CN-82",
}

# Cities to province mapping (for courts named "XX市YY法院")
CITY_TO_PROVINCE = {
    # Jiangsu
    "南京市": "江苏省", "无锡市": "江苏省", "徐州市": "江苏省", "常州市": "江苏省",
    "苏州市": "江苏省", "南通市": "江苏省", "连云港市": "江苏省", "淮安市": "江苏省",
    "盐城市": "江苏省", "扬州市": "江苏省", "镇江市": "江苏省", "泰州市": "江苏省",
    "宿迁市": "江苏省", "东台市": "江苏省", "溧阳市": "江苏省",
    # Zhejiang
    "杭州市": "浙江省", "宁波市": "浙江省", "温州市": "浙江省", "嘉兴市": "浙江省",
    "湖州市": "浙江省", "绍兴市": "浙江省", "金华市": "浙江省", "衢州市": "浙江省",
    "舟山市": "浙江省", "台州市": "浙江省", "丽水市": "浙江省",
    # Anhui
    "合肥市": "安徽省", "芜湖市": "安徽省", "蚌埠市": "安徽省", "淮南市": "安徽省",
    "马鞍山市": "安徽省", "淮北市": "安徽省", "铜陵市": "安徽省", "安庆市": "安徽省",
    "黄山市": "安徽省", "滁州市": "安徽省", "阜阳市": "安徽省", "宿州市": "安徽省",
    "六安市": "安徽省", "亳州市": "安徽省", "池州市": "安徽省", "宣城市": "安徽省",
    # Fujian
    "福州市": "福建省", "厦门市": "福建省", "莆田市": "福建省", "三明市": "福建省",
    "泉州市": "福建省", "漳州市": "福建省", "南平市": "福建省", "龙岩市": "福建省",
    "宁德市": "福建省",
    # Jiangxi
    "南昌市": "江西省", "景德镇市": "江西省", "萍乡市": "江西省", "九江市": "江西省",
    "新余市": "江西省", "鹰潭市": "江西省", "赣州市": "江西省", "吉安市": "江西省",
    "宜春市": "江西省", "抚州市": "江西省", "上饶市": "江西省",
    # Shandong
    "济南市": "山东省", "青岛市": "山东省", "淄博市": "山东省", "枣庄市": "山东省",
    "东营市": "山东省", "烟台市": "山东省", "潍坊市": "山东省", "济宁市": "山东省",
    "泰安市": "山东省", "威海市": "山东省", "日照市": "山东省", "临沂市": "山东省",
    "德州市": "山东省", "聊城市": "山东省", "滨州市": "山东省", "菏泽市": "山东省",
    # Guangdong
    "广州市": "广东省", "韶关市": "广东省", "深圳市": "广东省", "珠海市": "广东省",
    "汕头市": "广东省", "佛山市": "广东省", "江门市": "广东省", "湛江市": "广东省",
    "茂名市": "广东省", "肇庆市": "广东省", "惠州市": "广东省", "梅州市": "广东省",
    "汕尾市": "广东省", "河源市": "广东省", "阳江市": "广东省", "清远市": "广东省",
    "东莞市": "广东省", "中山市": "广东省", "潮州市": "广东省", "揭阳市": "广东省",
    "云浮市": "广东省", "封开县": "广东省",
    # Hunan
    "长沙市": "湖南省", "株洲市": "湖南省", "湘潭市": "湖南省", "衡阳市": "湖南省",
    "邵阳市": "湖南省", "岳阳市": "湖南省", "常德市": "湖南省", "张家界市": "湖南省",
    "益阳市": "湖南省", "郴州市": "湖南省", "永州市": "湖南省", "怀化市": "湖南省",
    "娄底市": "湖南省", "湘西土家族苗族自治州": "湖南省",
    # Hubei
    "武汉市": "湖北省", "黄石市": "湖北省", "十堰市": "湖北省", "宜昌市": "湖北省",
    "襄阳市": "湖北省", "鄂州市": "湖北省", "荆门市": "湖北省", "孝感市": "湖北省",
    "荆州市": "湖北省", "黄冈市": "湖北省", "咸宁市": "湖北省", "随州市": "湖北省",
    "恩施土家族苗族自治州": "湖北省",
    # Sichuan
    "成都市": "四川省", "自贡市": "四川省", "攀枝花市": "四川省", "泸州市": "四川省",
    "德阳市": "四川省", "绵阳市": "四川省", "广元市": "四川省", "遂宁市": "四川省",
    "内江市": "四川省", "乐山市": "四川省", "南充市": "四川省", "眉山市": "四川省",
    "宜宾市": "四川省", "广安市": "四川省", "达州市": "四川省", "雅安市": "四川省",
    "巴中市": "四川省", "资阳市": "四川省", "阿坝藏族羌族自治州": "四川省",
    "甘孜藏族自治州": "四川省", "凉山彝族自治州": "四川省", "苍溪县": "四川省",
    # Hebei
    "石家庄市": "河北省", "唐山市": "河北省", "秦皇岛市": "河北省", "邯郸市": "河北省",
    "邢台市": "河北省", "保定市": "河北省", "张家口市": "河北省", "承德市": "河北省",
    "沧州市": "河北省", "廊坊市": "河北省", "衡水市": "河北省",
    # Henan
    "郑州市": "河南省", "开封市": "河南省", "洛阳市": "河南省", "平顶山市": "河南省",
    "安阳市": "河南省", "鹤壁市": "河南省", "新乡市": "河南省", "焦作市": "河南省",
    "濮阳市": "河南省", "许昌市": "河南省", "漯河市": "河南省", "三门峡市": "河南省",
    "南阳市": "河南省", "商丘市": "河南省", "信阳市": "河南省", "周口市": "河南省",
    "驻马店市": "河南省", "滑县": "河南省", "济源市": "河南省",
    # Liaoning
    "沈阳市": "辽宁省", "大连市": "辽宁省", "鞍山市": "辽宁省", "抚顺市": "辽宁省",
    "本溪市": "辽宁省", "丹东市": "辽宁省", "锦州市": "辽宁省", "营口市": "辽宁省",
    "阜新市": "辽宁省", "辽阳市": "辽宁省", "盘锦市": "辽宁省", "铁岭市": "辽宁省",
    "朝阳市": "辽宁省", "葫芦岛市": "辽宁省",
    # Shaanxi
    "西安市": "陕西省", "铜川市": "陕西省", "宝鸡市": "陕西省", "咸阳市": "陕西省",
    "渭南市": "陕西省", "延安市": "陕西省", "汉中市": "陕西省", "榆林市": "陕西省",
    "安康市": "陕西省", "商洛市": "陕西省",
    # Shanxi
    "太原市": "山西省", "大同市": "山西省", "阳泉市": "山西省", "长治市": "山西省",
    "晋城市": "山西省", "朔州市": "山西省", "晋中市": "山西省", "运城市": "山西省",
    "忻州市": "山西省", "临汾市": "山西省", "吕梁市": "山西省", "孝义市": "山西省",
    # Guangxi
    "南宁市": "广西壮族自治区", "柳州市": "广西壮族自治区", "桂林市": "广西壮族自治区",
    "梧州市": "广西壮族自治区", "北海市": "广西壮族自治区", "防城港市": "广西壮族自治区",
    "钦州市": "广西壮族自治区", "贵港市": "广西壮族自治区", "玉林市": "广西壮族自治区",
    "百色市": "广西壮族自治区", "贺州市": "广西壮族自治区", "河池市": "广西壮族自治区",
    "来宾市": "广西壮族自治区", "崇左市": "广西壮族自治区",
    # Yunnan
    "昆明市": "云南省", "曲靖市": "云南省", "玉溪市": "云南省", "保山市": "云南省",
    "昭通市": "云南省", "丽江市": "云南省", "普洱市": "云南省", "临沧市": "云南省",
    "楚雄彝族自治州": "云南省", "红河哈尼族彝族自治州": "云南省",
    "文山壮族苗族自治州": "云南省", "西双版纳傣族自治州": "云南省",
    "大理白族自治州": "云南省", "德宏傣族景颇族自治州": "云南省",
    "怒江傈僳族自治州": "云南省", "迪庆藏族自治州": "云南省",
    # Guizhou
    "贵阳市": "贵州省", "六盘水市": "贵州省", "遵义市": "贵州省", "安顺市": "贵州省",
    "毕节市": "贵州省", "铜仁市": "贵州省", "黔西南布依族苗族自治州": "贵州省",
    "黔东南苗族侗族自治州": "贵州省", "黔南布依族苗族自治州": "贵州省",
    # Gansu
    "兰州市": "甘肃省", "嘉峪关市": "甘肃省", "金昌市": "甘肃省", "白银市": "甘肃省",
    "天水市": "甘肃省", "武威市": "甘肃省", "张掖市": "甘肃省", "平凉市": "甘肃省",
    "酒泉市": "甘肃省", "庆阳市": "甘肃省", "定西市": "甘肃省", "陇南市": "甘肃省",
    "临夏回族自治州": "甘肃省", "甘南藏族自治州": "甘肃省",
    # Jilin
    "长春市": "吉林省", "吉林市": "吉林省", "四平市": "吉林省", "辽源市": "吉林省",
    "通化市": "吉林省", "白山市": "吉林省", "松原市": "吉林省", "白城市": "吉林省",
    "延边朝鲜族自治州": "吉林省",
    # Heilongjiang
    "哈尔滨市": "黑龙江省", "齐齐哈尔市": "黑龙江省", "鸡西市": "黑龙江省",
    "鹤岗市": "黑龙江省", "双鸭山市": "黑龙江省", "大庆市": "黑龙江省",
    "伊春市": "黑龙江省", "佳木斯市": "黑龙江省", "七台河市": "黑龙江省",
    "牡丹江市": "黑龙江省", "黑河市": "黑龙江省", "绥化市": "黑龙江省",
    "大兴安岭地区": "黑龙江省",
    # Other municipalities
    "昌平区": "北京市", "朝阳区": "北京市", "海淀区": "北京市", "东城区": "北京市",
    "西城区": "北京市", "丰台区": "北京市", "石景山区": "北京市", "通州区": "北京市",
    "顺义区": "北京市", "房山区": "北京市", "大兴区": "北京市", "怀柔区": "北京市",
    "平谷区": "北京市", "门头沟区": "北京市", "密云区": "北京市", "延庆区": "北京市",
    "浦东新区": "上海市", "黄浦区": "上海市", "徐汇区": "上海市", "长宁区": "上海市",
    "静安区": "上海市", "普陀区": "上海市", "虹口区": "上海市", "杨浦区": "上海市",
    "闵行区": "上海市", "宝山区": "上海市", "嘉定区": "上海市", "金山区": "上海市",
    "松江区": "上海市", "青浦区": "上海市", "奉贤区": "上海市", "崇明区": "上海市",
    "万州区": "重庆市", "涪陵区": "重庆市", "渝中区": "重庆市", "大渡口区": "重庆市",
    "江北区": "重庆市", "沙坪坝区": "重庆市", "九龙坡区": "重庆市", "南岸区": "重庆市",
    "北碚区": "重庆市", "綦江区": "重庆市", "大足区": "重庆市", "渝北区": "重庆市",
    "巴南区": "重庆市", "黔江区": "重庆市", "长寿区": "重庆市", "江津区": "重庆市",
    "合川区": "重庆市", "永川区": "重庆市", "南川区": "重庆市", "璧山区": "重庆市",
    "铜梁区": "重庆市", "潼南区": "重庆市", "荣昌区": "重庆市", "开州区": "重庆市",
    "梁平区": "重庆市", "武隆区": "重庆市", "云阳县": "重庆市",
    # Ningxia
    "银川市": "宁夏回族自治区", "石嘴山市": "宁夏回族自治区", "吴忠市": "宁夏回族自治区",
    "固原市": "宁夏回族自治区", "中卫市": "宁夏回族自治区",
    # Qinghai
    "西宁市": "青海省", "海东市": "青海省",
    # Tibet
    "拉萨市": "西藏自治区", "日喀则市": "西藏自治区",
    # Xinjiang
    "乌鲁木齐市": "新疆维吾尔自治区", "克拉玛依市": "新疆维吾尔自治区",
    "吐鲁番市": "新疆维吾尔自治区", "哈密市": "新疆维吾尔自治区",
    # Inner Mongolia
    "呼和浩特市": "内蒙古自治区", "包头市": "内蒙古自治区", "乌海市": "内蒙古自治区",
    "赤峰市": "内蒙古自治区", "通辽市": "内蒙古自治区", "鄂尔多斯市": "内蒙古自治区",
    "呼伦贝尔市": "内蒙古自治区", "巴彦淖尔市": "内蒙古自治区", "乌兰察布市": "内蒙古自治区",
    "兴安盟": "内蒙古自治区", "锡林郭勒盟": "内蒙古自治区", "阿拉善盟": "内蒙古自治区",
    # Hainan
    "海口市": "海南省", "三亚市": "海南省", "三沙市": "海南省", "儋州市": "海南省",
}


def clean_tags(raw: str) -> str:
    """Fix 3: Clean key_words field — strip leading/trailing Chinese colons,
    spaces, and other abnormal characters. Returns clean comma-separated tags."""
    raw = (raw or "").strip()
    # Remove leading/trailing Chinese colons and any non-alphanumeric prefix junk
    raw = re.sub(r'^[：:\s,，]+', '', raw)
    raw = re.sub(r'[：:\s,，]+$', '', raw)
    # Remove stray quotation marks that may surround the field
    raw = raw.strip('"').strip("'").strip()
    # Normalize multiple spaces/newlines to single space
    raw = re.sub(r'\s+', ' ', raw)
    return raw


# ============ Helper functions (compatible with parse_guiding_cases.py) ============

def map_category(category: str) -> str:
    """Fix 2: Map Chinese category to English enum value.
    Records unmapped values to AUDIT_LOG_UNMAPPED for later review."""
    result = CATEGORY_MAP.get(category, None)
    if result is not None:
        return result
    # Log unmapped value and return original as-is
    if category:
        AUDIT_LOG_UNMAPPED["category"].add(category)
    return category


def map_trial_level(trial_procedure: str) -> str:
    """Fix 1: Map trial_procedure to trial_level using maintainable TRIAL_LEVEL_MAP dict.
    Records unmapped values to AUDIT_LOG_UNMAPPED for later review."""
    trial_procedure = (trial_procedure or "").strip()
    if not trial_procedure:
        return ""
    # Try exact match first
    if trial_procedure in TRIAL_LEVEL_MAP:
        return TRIAL_LEVEL_MAP[trial_procedure]
    # Try substring match
    for key, value in TRIAL_LEVEL_MAP.items():
        if key in trial_procedure:
            return value
    # Log unmapped value
    AUDIT_LOG_UNMAPPED["trial_level"].add(trial_procedure)
    return ""


def extract_district_from_court(court_name: str) -> str:
    """Fix 4: Extract district_id from court name. Returns empty string if
    no district can be resolved (no strong filling)."""
    if not court_name:
        return ""
    # Handle "最高人民法院" — it's national level
    if court_name == "最高人民法院":
        return "CN"  # national
    # Special courts: "北京知识产权法院", "上海金融法院" etc.
    for district_name in ["北京市", "上海市", "天津市", "重庆市"]:
        if court_name.startswith(district_name):
            return KNOWN_DISTRICTS.get(district_name, "")
    # Try to find province/region name directly in court name
    for dist_name, code in sorted(KNOWN_DISTRICTS.items(), key=lambda x: -len(x[0])):
        if dist_name in court_name:
            return code
    # Try city → province → district_code mapping
    for city, province in sorted(CITY_TO_PROVINCE.items(), key=lambda x: -len(x[0])):
        if city in court_name:
            province_code = KNOWN_DISTRICTS.get(province, "")
            if province_code:
                return province_code
    # Fallback regex
    match = re.match(r'^([\u4e00-\u9fa5]{2,}(?:省|自治区|市))', court_name)
    if match:
        region = match.group(1)
        return KNOWN_DISTRICTS.get(region, "")
    return ""


def parse_date(raw: str) -> str:
    raw = raw.strip()
    if not raw or raw in ("\\\\N", "\\N", ""):
        return ""
    raw = raw.replace("/", "-").replace(".", "-")
    parts = raw.split("-")
    if len(parts) == 3:
        y, m, d = parts
        try:
            return f"{int(y)}-{int(m):02d}-{int(d):02d}"
        except ValueError:
            return ""
    return ""


def extract_case_category(case_type: str) -> Tuple[str, str]:
    case_type = (case_type or "").strip()
    if "-" in case_type:
        return case_type.split("-", 1)
    return case_type, ""


def normalize_court_name(name: str) -> str:
    name = (name or "").strip()
    return name or "未知法院"


def parse_related_law(raw: str) -> List[Dict]:
    raw = raw or ""
    if raw in ("\\\\N", "\\N", ""):
        return []
    laws = []
    # Try to match 《XX法》第...条第...款 patterns
    # Pattern 1: 《XX法》第X条、第X条、第X条第X款
    pattern1 = r"《([^》]+)》第([零一二三四五六七八九十百千万\d]+)条(?:第([零一二三四五六七八九十百千万\d]+)款)?"
    for m in re.finditer(pattern1, raw):
        laws.append({
            "law_name": m.group(1).strip(),
            "article": m.group(2).strip(),
            "paragraph": "",
            "item": m.group(3).strip() if m.group(3) else ""
        })
    # Pattern 2: 独立法条引用，如 (2022)苏行再30号 等 - 跳过案号
    # Pattern 3: XX法第X条第X款 (没有书名号)
    pattern3 = r"(?:^|[^《\w])([一-龥]{2,20}(?:法典|条例|规定|法))(?:第([零一二三四五六七八九十百千万\d]+)条)?(?:第([零一二三四五六七八九十百千万\d]+)款)?"
    for m in re.finditer(pattern3, raw):
        law_name = m.group(1).strip()
        article = m.group(2) if m.group(2) else ""
        paragraph = m.group(3) if m.group(3) else ""
        if law_name and article:
            # deduplicate
            if not any(l["law_name"] == law_name and l["article"] == article for l in laws):
                laws.append({
                    "law_name": law_name,
                    "article": article,
                    "paragraph": "",
                    "item": paragraph
                })
    return laws


def md5_id(prefix: str, *parts) -> str:
    content = "|".join(str(p) for p in parts)
    return f"{prefix}_{hashlib.md5(content.encode()).hexdigest()[:12]}"


def load_batch_state() -> dict:
    if BATCH_STATE.exists():
        with open(BATCH_STATE, "r") as f:
            return json.load(f)
    return {
        "last_processed_id_sequence": -1,
        "last_id": None,
        "processed_ids": [],
        "total_processed": 0
    }


def save_batch_state(state: dict):
    BATCH_STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(BATCH_STATE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_existing_ids() -> set:
    """Load already-processed guiding_case IDs from gold CSVs."""
    existing = set()
    gc_path = GOLD_DIR / "GuidingCase.csv"
    if gc_path.exists():
        with open(gc_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                gid = row.get("id", "").replace("guiding_case_", "")
                if gid.isdigit():
                    existing.add(int(gid))
    return existing


def read_source_csv() -> List[Dict]:
    """Read the source CSV with proper CSV parsing."""
    rows = []
    with open(SOURCE_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for line_parts in reader:
            if not line_parts or not line_parts[0].strip().isdigit():
                continue
            row = {}
            for i, col_name in enumerate(HEADER):
                val = line_parts[i] if i < len(line_parts) else ""
                row[col_name] = val
            rows.append(row)
    return rows


def overwrite_batch_csv(name: str, data: List[Dict], batch_ids: set):
    """Overwrite rows belonging to the current batch in an existing CSV.
    Reads existing CSV, removes rows matching batch_ids (where id contains a batch
    ID), then writes back the kept rows + new data. Creates file if not exists."""
    if not data:
        print(f"  No new {name} rows to write")
        return
    path = GOLD_DIR / name
    existing_rows = []
    if path.exists() and path.stat().st_size > 0:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_id = row.get("id", "")
                keep = True
                if name == "GuidingCase.csv":
                    # Remove old batch 2 GuidingCase rows by ID
                    for bid in batch_ids:
                        if f"guiding_case_{bid}" == row_id:
                            keep = False
                            break
                if keep:
                    existing_rows.append(row)

    # Build set of new row IDs for dedup
    new_ids = {d.get("id") for d in data if d.get("id")}

    # Merge: keep existing rows not in new data, then add all new data
    merged = [r for r in existing_rows if r.get("id") not in new_ids]
    merged.extend(data)

    # P0 fix: global dedup by id to clean up legacy duplicates from earlier runs
    # (e.g., 1089/1109 issue where append-mode writes left duplicate rows)
    seen = set()
    merged_deduped = []
    for row in reversed(merged):
        rid = row.get("id", "")
        if rid and rid not in seen:
            seen.add(rid)
            merged_deduped.append(row)
    merged = list(reversed(merged_deduped))

    keys = list(data[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(merged)
    print(f"  Wrote {len(merged)} rows to {path.name} (kept {len(merged) - len(data)} existing, added {len(data)} new)")


def process_batch():
    state = load_batch_state()
    existing_ids = load_existing_ids()

    # Read all source rows
    all_rows = read_source_csv()
    all_rows.sort(key=lambda r: int(r["id"]))

    print(f"Source CSV: {len(all_rows)} total rows")
    print(f"Already processed: {len(existing_ids)} IDs")

    # Find rows not yet processed, ordered by source ID
    unprocessed = [r for r in all_rows if int(r["id"]) not in existing_ids]

    if not unprocessed:
        print("No unprocessed rows remaining. All done!")
        return

    # Take the next BATCH_SIZE
    batch = unprocessed[:BATCH_SIZE]
    batch_ids = [int(r["id"]) for r in batch]

    print(f"Batch IDs: {batch_ids[0]} .. {batch_ids[-1]} ({len(batch)} records)")

    # ============ Parse ============
    guiding_cases: List[Dict] = []
    courts: Dict[str, Dict] = {}
    case_types: Dict[str, Dict] = {}
    provisions: Dict[str, Dict] = {}
    edges_cites: List[Dict] = []
    edges_guides: List[Dict] = []

    success_count = 0
    skip_count = 0
    field_stats = {"with_court": 0, "with_type": 0, "with_law": 0, "with_essence": 0}

    for row in batch:
        row_id = (row.get("id") or "").strip()
        if not row_id or not row_id.isdigit():
            skip_count += 1
            continue

        row_id_int = int(row_id)
        gc_id = f"guiding_case_{row_id_int}"

        # Skip if already in gold (belt-and-suspenders check)
        if row_id_int in existing_ids:
            skip_count += 1
            continue

        case_type_raw = row.get("case_type") or "unknown"
        category, sub_type = extract_case_category(case_type_raw)

        # === P0-1: Map category to English ===
        category_en = map_category(category)

        # CaseType
        ct_id = md5_id("case_type", category_en, sub_type)
        if ct_id not in case_types:
            case_types[ct_id] = {
                "id": ct_id,
                "code": ct_id.replace("case_type_", ""),
                "name": sub_type or category,
                "category": category_en,  # P0-1: Now English enum
                "level1": category,
                "level2": sub_type,
                "source": "指导案例库分类",
                "desensitize": "false",
                "create_time": "2026-04-21T00:00:00Z",
                "update_time": "2026-04-21T00:00:00Z",
            }

        # Court
        court_name = normalize_court_name(row.get("court_name"))
        court_id = md5_id("court", court_name)
        if court_id not in courts:
            level = "supreme" if "最高" in court_name else "high" if "高级" in court_name else "intermediate" if "中级" in court_name else "basic"
            # P0-3: Extract district_id from court name
            district_id = extract_district_from_court(court_name)
            courts[court_id] = {
                "id": court_id,
                "name": court_name,
                "org_type": "court",
                "credit_code": md5_id("cc", court_name)[-18:],
                "court_level": level,
                "district_id": district_id,  # P0-3: Now populated
                "source": "指导案例库",
                "desensitize": "false",
                "create_time": "2026-04-21T00:00:00Z",
                "update_time": "2026-04-21T00:00:00Z",
            }

        # GuidingCase
        pub_date = parse_date(row.get("trial_year") or "")
        case_level = (row.get("case_level") or "").strip()
        # Fix 1: Use dictionary-based mapping for case_level too
        CASE_LEVEL_MAP = {"1": "first_instance", "2": "second_instance", "": ""}
        trial_level = CASE_LEVEL_MAP.get(case_level, "")

        # Try to map from trial_procedure if trial_level is still empty
        if not trial_level:
            trial_procedure = (row.get("trial_procedure") or "").strip()
            trial_level = map_trial_level(trial_procedure)

        web_name = (row.get("web_name") or "").strip()
        binding = "mandatory" if "人民法院案例库" in web_name else "persuasive"

        # Extract guiding points from judgment_essence
        essence = (row.get("judgment_essence") or "").strip()
        # Clean HTML tags
        essence = re.sub(r'<[^>]+>', '', essence)
        # Fix specific Unicode escape issues noted in audit
        essence = essence.replace("\\\\u3000", " ").replace("u3000", " ")
        # P1 fix: also handle actual Unicode U+3000 ideographic space
        essence = essence.replace("\u3000", " ")
        essence = essence.replace("\\n", " ").replace("\\r", " ")
        essence = re.sub(r'\s+', ' ', essence).strip()
        essence = essence[:2000]

        guiding_cases.append({
            "id": gc_id,
            "guiding_case_number": (row.get("storage_no") or "").strip(),
            "name": f"{case_type_raw}-{(row.get('storage_no') or '').strip()}",
            "issuing_court_id": court_id,
            "publication_date": pub_date,
            "guiding_points": essence,
            "binding_force": binding,
            "source_url": (row.get("web_url") or "").strip(),
            "tags": clean_tags(row.get("key_words") or ""),
            "trial_procedure": (row.get("trial_procedure") or "").strip(),
            "trial_level": trial_level,  # P1-1: Now populated
            "source": web_name,
            "desensitize": "false",
            "create_time": "2026-04-21T00:00:00Z",
            "update_time": "2026-04-21T00:00:00Z",
        })

        edges_guides.append({
            "guiding_case_id": gc_id,
            "case_type_id": ct_id,
        })

        # ============ P0-2: Enhanced LegalProvision extraction ============
        # Strategy: extract from multiple fields and merge
        related_law = row.get("related_law") or ""

        # 1. Parse from related_law field (original)
        related_law_provisions = parse_related_law(related_law)

        # 2. Parse from judgment_reason and judgment_essence using regex library
        judgment_reason = row.get("judgment_reason") or ""
        judgment_essence = row.get("judgment_essence") or ""

        # Combine all text sources for regex extraction
        combined_text = f"{judgment_reason}\n{judgment_essence}\n{related_law}"
        regex_provisions = regex_extract_legal_provisions(combined_text)

        # 3. Merge: convert both to a common format
        seen_provision_keys = set()

        for law in related_law_provisions:
            prov_id = md5_id("provision", law["law_name"], law["article"], law["item"])
            key = (law["law_name"], law["article"], law["item"])
            if key not in seen_provision_keys:
                seen_provision_keys.add(key)
                if prov_id not in provisions:
                    provisions[prov_id] = {
                        "id": prov_id,
                        "law_id": md5_id("law", law["law_name"]),
                        "article": law["article"],
                        "paragraph": law["paragraph"],
                        "item": law["item"],
                        "content": "",
                        "status": "effective",
                        "source": law["law_name"],
                        "desensitize": "false",
                        "create_time": "2026-04-21T00:00:00Z",
                        "update_time": "2026-04-21T00:00:00Z",
                    }
                edges_cites.append({
                    "case_id": gc_id,
                    "provision_id": prov_id,
                    "citation_position": "裁判要旨",
                    "citation_purpose": "法律依据"
                })

        for prov in regex_provisions:
            statute = prov.get("statute", "")
            article = prov.get("article", "")
            paragraph = prov.get("paragraph", "")
            item = ""
            key = (statute, article, item)
            if key not in seen_provision_keys and article:
                seen_provision_keys.add(key)
                prov_id = md5_id("provision", statute, article, item)
                if prov_id not in provisions:
                    provisions[prov_id] = {
                        "id": prov_id,
                        "law_id": md5_id("law", statute),
                        "article": article,
                        "paragraph": paragraph,
                        "item": item,
                        "content": "",
                        "status": "effective",
                        "source": statute,
                        "desensitize": "false",
                        "create_time": "2026-04-21T00:00:00Z",
                        "update_time": "2026-04-21T00:00:00Z",
                    }
                edges_cites.append({
                    "case_id": gc_id,
                    "provision_id": prov_id,
                    "citation_position": "裁判要旨",
                    "citation_purpose": "法律依据"
                })

        success_count += 1
        existing_ids.add(row_id_int)

        # Stats
        if court_name != "未知法院":
            field_stats["with_court"] += 1
        if case_type_raw not in ("unknown", ""):
            field_stats["with_type"] += 1
        if related_law not in ("\\\\N", "\\N", ""):
            field_stats["with_law"] += 1
        if essence:
            field_stats["with_essence"] += 1

    # ============ P1-3: Deduplicate courts by court_id (same key in dict already dedupes, but ensure no duplicates from different sources) ============
    courts_deduped = list(courts.values())
    print(f"  Courts before dedup: {len(courts_deduped)}")

    # P2 fix: deduplicate CITES edges by (case_id, provision_id) to prevent
    # duplicates from parse_related_law + regex extract both matching same provision
    seen_edges = set()
    edges_cites_deduped = []
    for edge in edges_cites:
        key = (edge["case_id"], edge["provision_id"])
        if key not in seen_edges:
            seen_edges.add(key)
            edges_cites_deduped.append(edge)
    if len(edges_cites_deduped) < len(edges_cites):
        print(f"  Deduplicated {len(edges_cites) - len(edges_cites_deduped)} duplicate CITES edges")
        edges_cites = edges_cites_deduped

    # ============ P1-2: Filter CITES edges — only keep those where case_id exists in GuidingCase.csv ============
    gc_ids_in_batch = {gc["id"] for gc in guiding_cases}
    edges_cites_clean = [
        edge for edge in edges_cites
        if edge["case_id"] in gc_ids_in_batch
    ]
    if len(edges_cites_clean) < len(edges_cites):
        print(f"  Filtered out {len(edges_cites) - len(edges_cites_clean)} orphan CITES edges")
        edges_cites = edges_cites_clean

    # ============ Overwrite second batch in gold CSVs ============
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    batch_id_set = set(batch_ids)

    overwrite_batch_csv("GuidingCase.csv", guiding_cases, batch_id_set)
    overwrite_batch_csv("Court.csv", courts_deduped, batch_id_set)
    overwrite_batch_csv("CaseType.csv", list(case_types.values()), batch_id_set)
    overwrite_batch_csv("LegalProvision.csv", list(provisions.values()), batch_id_set)
    overwrite_batch_csv("edges_GUIDES_CASE_TYPE.csv", edges_guides, batch_id_set)
    overwrite_batch_csv("edges_CITES.csv", edges_cites, batch_id_set)

    # ============ Update state ============
    state["last_processed_id_sequence"] += len(batch)
    state["last_id"] = batch_ids[-1]
    state["processed_ids"] = sorted(set(state["processed_ids"] + batch_ids))
    state["total_processed"] = len(state["processed_ids"])
    save_batch_state(state)

    # ============ Report ============
    print(f"\n{'='*60}")
    print(f"BATCH PROCESSING REPORT")
    print(f"{'='*60}")
    print(f"ID Range:          {batch_ids[0]} - {batch_ids[-1]} ({len(batch_ids)} records)")
    print(f"Successfully parsed: {success_count}")
    print(f"Skipped (already processed): {skip_count}")
    print(f"Total processed (cumulative): {state['total_processed']}")
    print(f"")
    print(f"Entities created:")
    print(f"  GuidingCase:     {len(guiding_cases)}")
    print(f"  Court:           {len(courts_deduped)} (unique)")
    print(f"  CaseType:        {len(case_types)} (unique)")
    print(f"  LegalProvision:  {len(provisions)} (unique)")
    print(f"  Edges GUIDES:    {len(edges_guides)}")
    print(f"  Edges CITES:     {len(edges_cites)}")
    print(f"")
    print(f"Field coverage (among parsed):")
    print(f"  With court name:     {field_stats['with_court']}/{success_count}")
    print(f"  With case type:      {field_stats['with_type']}/{success_count}")
    print(f"  With related law:    {field_stats['with_law']}/{success_count}")
    print(f"  With guiding points: {field_stats['with_essence']}/{success_count}")
    # Fix 2: Audit log for unmapped enum values
    if AUDIT_LOG_UNMAPPED["category"]:
        print(f"")
        print(f"⚠️  AUDIT: Unmapped category values:")
        for v in sorted(AUDIT_LOG_UNMAPPED["category"]):
            print(f"    - '{v}'")
    if AUDIT_LOG_UNMAPPED["trial_level"]:
        print(f"")
        print(f"⚠️  AUDIT: Unmapped trial_level values:")
        for v in sorted(AUDIT_LOG_UNMAPPED["trial_level"]):
            print(f"    - '{v}'")
    print(f"{'='*60}")


if __name__ == "__main__":
    process_batch()
