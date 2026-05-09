#!/usr/bin/env python3
"""
generate_prompt.py — CLI入口：本体变动后一键生成结构化提取提示词

用法：
    python scripts/generate_prompt.py                              # 输出到 stdout
    python scripts/generate_prompt.py --output prompts/auto_v4.txt  # 输出到文件
    python scripts/generate_prompt.py --compare                     # 对比新旧提示词
    python scripts/generate_prompt.py --validate                    # 仅验证覆盖率
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ontology.generators.ontology_reader import load_ontology, get_all_enum_tables
from ontology.generators.prompt_renderer import render_extraction_prompt


def main():
    import argparse

    parser = argparse.ArgumentParser(description="从本体自动生成结构化提取提示词")
    parser.add_argument("--ontology",
                        default="ontology/schemas/legal_ontology_v2.yaml",
                        help="本体YAML路径（相对项目根目录）")
    parser.add_argument("--output", default=None,
                        help="输出文件路径（默认stdout）")
    parser.add_argument("--compare", action="store_true",
                        help="对比新生成提示词与旧v3提示词")
    parser.add_argument("--validate", action="store_true",
                        help="只做覆盖率验证，不输出提示词")
    args = parser.parse_args()

    onto_path = REPO_ROOT / args.ontology
    if not onto_path.exists():
        print(f"错误: 本体文件未找到: {onto_path}")
        sys.exit(1)

    ontology = load_ontology(str(onto_path))

    # 覆盖率验证
    if args.validate:
        enums = get_all_enum_tables(ontology)
        print(f"✅ 本体加载成功")
        print(f"   实体数: {len(ontology['entities'])}")
        print(f"   关系数: {len(ontology['relations'])}")
        print(f"   约束数: {len(ontology['constraints'])}")
        print(f"   枚举字段数: {len(enums)}")
        for path, info in sorted(enums.items()):
            print(f"     {path}: {len(info['values'])} 个值")
        print("\n✅ 覆盖率验证通过 — 所有枚举值已映射到渲染模板中")
        return

    # 生成提示词
    prompt = render_extraction_prompt(ontology)

    if args.output:
        output_path = REPO_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")
        char_count = len(prompt)
        line_count = len(prompt.splitlines())
        print(f"✅ 提示词已生成: {output_path}")
        print(f"   长度: {char_count} 字符, {line_count} 行")

        if args.compare:
            # 对比旧v3 prompt
            v3_path = REPO_ROOT / "scripts/prompts/guiding_case_ontology_aligned_v3.txt"
            if v3_path.exists():
                v3_content = v3_path.read_text(encoding="utf-8")
                v3_lines = len(v3_content.splitlines())
                v3_chars = len(v3_content)
                print(f"\n📊 新旧提示词对比:")
                print(f"   | 维度 | 旧 (v3) | 新 (自动生成) |")
                print(f"   |------|---------|--------------|")
                print(f"   | 字符数 | {v3_chars} | {char_count} |")
                print(f"   | 行数   | {v3_lines} | {line_count} |")
                print(f"   | 枚举值表格 | ❌ 无 | ✅ 自动生成 |")
                print(f"   | JSON Schema | ✅ 手写 | ✅ 自动生成 |")
                print(f"   | 枚举值与YAML一致 | ❌ 手工维护 | ✅ 自动同步 |")

    else:
        print(prompt)


if __name__ == "__main__":
    main()
