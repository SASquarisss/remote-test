import sys, os, json
sys.path.append(os.path.abspath('backend'))
from app import _load_test_data
data = _load_test_data()
print(list(data.get("json_result", {}).keys()))
