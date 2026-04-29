# 指导性案例字段说明

> 数据源：人民法院案例库 / 多元解纷案例库  
> 格式：CSV（建议 TSV 或带引号的逗号分隔）  
> 编码：UTF-8

---

## 字段列表（21 列）

| 序号 | 字段名 | 类型 | 可空 | 说明 |
|:---:|---|---|---|---|
| 1 | `id` | INT | × | 案例唯一 ID |
| 2 | `web_name` | VARCHAR | × | 来源网站名称，如「人民法院案例库」 |
| 3 | `web_url` | VARCHAR | × | 案例详情链接 |
| 4 | `case_type` | VARCHAR | × | 案由，如「行政-不履行XX职责」 |
| 5 | `storage_no` | VARCHAR | × | 归档号，如「2024-12-3-021-005」 |
| 6 | `court_name` | VARCHAR | × | 审理法院 |
| 7 | `key_words` | VARCHAR | √ | 关键词，逗号分隔 |
| 8 | `trial_procedure` | VARCHAR | √ | 审理程序：一审 / 二审 / 再审 / 审监 |
| 9 | `trial_year` | VARCHAR | √ | 审判日期，格式「YYYY.MM.DD」或「YYYY/M/D」 |
| 10 | `case_level` | TINYINT | √ | 案件级别：1 / 2 / 3 |
| 11 | `basic_facts` | TEXT | √ | 基本事实（含 HTML `<p>` `<br/>`） |
| 12 | `judgment_reason` | TEXT | √ | 裁判理由（含 HTML） |
| 13 | `judgment_essence` | TEXT | √ | 裁判要旨（含 HTML） |
| 14 | `related_info` | TEXT | √ | 相关信息（含 HTML） |
| 15 | `related_law` | TEXT | √ | 适用法条，如《立法法》第96条 |
| 16 | `related_judgment_body` | TEXT | √ | 相关判决主体内容 |
| 17 | `create_time` | DATETIME | × | 创建时间，格式「YYYY/M/D H:mm」 |
| 18 | `update_time` | DATETIME | × | 更新时间 |
| 19 | `md5_value` | CHAR(32) | × | 全文 MD5 |
| 20 | `judgment_mean` | VARCHAR | √ | 判决意义摘要 |
| 21 | `dt` | CHAR(8) | × | 数据分区日期，格式「YYYYMMDD」 |

---

## 数据清洗规范

1. **NULL 表示**：CSV 中使用 `\N` 表示 NULL，入库前转换为 Python `None`。
2. **HTML 保留**：长文本字段保留原始 HTML 标签，后续 NLP 处理时可选择脱标签或保留结构。
3. **时间格式**：`trial_year` 为「YYYY.MM.DD」，`create_time` / `update_time` 为「YYYY/M/D H:mm」，入库前统一转换为 ISO 8601。
4. **案号格式**：`storage_no` 不做强校验，保留原始字符串。
5. **重复检测**：以 `md5_value` 为唯一约束，重复数据覆盖或跳过。

---

## 示例行

```csv
id,web_name,web_url,case_type,storage_no,court_name,key_words,trial_procedure,trial_year,case_level,basic_facts,judgment_reason,judgment_essence,related_info,related_law,related_judgment_body,create_time,update_time,md5_value,judgment_mean,dt
2292,人民法院案例库,https://rmfyalk.court.gov.cn,行政-不履行XX职责,2024-12-3-021-005,江苏省高级人民法院,行政,再审,2022.07.01,2,"<p> 原告孟某诉称... </p>","<p> 法院生效判决认为... </p>","<p>1.规范性文件不得... </p>","<p> 《立法法》第96条... </p>",\N,\N,2026/1/21 10:27,2026/1/21 10:27,000062e730a424b1df3b500e33cafc9b,\N,20260421
```
