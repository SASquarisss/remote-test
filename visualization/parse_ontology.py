#!/usr/bin/env python3
"""
Parse legal_ontology_v2.zh.yaml and generate JS data for the detail panel.
Output: JS object containing entity fields, enums, relations by entity, constraints.
"""

import yaml
import json
import re
import sys

YAML_PATH = '/root/remote-test/ontology/schemas/legal_ontology_v2.zh.yaml'
OUTPUT_PATH = '/root/remote-test/visualization/ontology_data.js'

with open(YAML_PATH, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

types = data.get('types', {})
relations = data.get('relations', {})

# Parse entity data
entity_data = {}

for type_name, type_info in types.items():
    if not isinstance(type_info, dict):
        continue
    
    entry = {}
    entry['description'] = type_info.get('description', '')
    entry['required'] = type_info.get('required', [])
    entry['optional'] = type_info.get('optional', [])
    
    # Extract enums: keys ending in _enum
    enums = {}
    for key, value in type_info.items():
        if key.endswith('_enum') and isinstance(value, list):
            # Derive field name by removing _enum suffix
            field_name = key[:-5]  # remove '_enum'
            enums[field_name] = value
    entry['enums'] = enums
    
    # Extract constraints
    constraints = type_info.get('constraints', [])
    if constraints and isinstance(constraints, list):
        entry['constraints'] = constraints
    else:
        entry['constraints'] = []
    
    # Inheritance
    entry['is_a'] = type_info.get('is_a', None)
    
    entity_data[type_name] = entry

# Process global constraints from root level
global_constraints = data.get('constraints', [])
global_constraints_by_type = {}
for c in global_constraints:
    if isinstance(c, dict):
        t = c.get('type', 'global')
        if t not in global_constraints_by_type:
            global_constraints_by_type[t] = []
        global_constraints_by_type[t].append(c)

# Merge global constraints into entity data
for type_name, gcs in global_constraints_by_type.items():
    if type_name in entity_data:
        for gc in gcs:
            desc = gc.get('description', gc.get('rule', ''))
            if desc not in entity_data[type_name]['constraints']:
                entity_data[type_name]['constraints'].append({
                    'rule': gc.get('rule', ''),
                    'enforcement': gc.get('enforcement', 'block'),
                    'description': desc
                })
    elif type_name == 'global':
        # Store global constraints separately
        for gc in gcs:
            pass  # We'll add these to a special section

# Parse relations - build outgoing and incoming per entity
relations_by_entity = {}
relation_details = {}

for rel_name, rel_info in relations.items():
    if not isinstance(rel_info, dict):
        continue
    
    from_type = rel_info.get('from')
    to_type = rel_info.get('to')
    
    # Handle to_type that can be a list
    if isinstance(to_type, list):
        to_types = to_type
    else:
        to_types = [to_type]
    
    for t in to_types:
        if t is None:
            continue
        
        details = {
            'name': rel_name,
            'cardinality': rel_info.get('cardinality', ''),
            'description': rel_info.get('description', ''),
            'attributes': rel_info.get('attributes', []),
            'optional_attributes': rel_info.get('optional_attributes', []),
            'acyclic': rel_info.get('acyclic', False)
        }
        
        # Index by relation name + target
        rel_key = f"{rel_name}___{t}" if len(to_types) > 1 else rel_name
        relation_details[rel_key] = details
        
        # Outgoing: from_type -> t
        if from_type and from_type in entity_data:
            if from_type not in relations_by_entity:
                relations_by_entity[from_type] = {'outgoing': [], 'incoming': []}
            label = rel_info.get('description', rel_name)
            # Convert attributes dict to list of keys if needed
            attr_names = rel_info.get('attributes', [])
            if isinstance(attr_names, dict):
                attr_names = list(attr_names.keys())
            relations_by_entity[from_type]['outgoing'].append({
                'relation': rel_name,
                'target': t,
                'cardinality': rel_info.get('cardinality', ''),
                'description': label,
                'attributes': attr_names
            })
        
        # Incoming: t gets incoming from from_type
        if t in entity_data:
            if t not in relations_by_entity:
                relations_by_entity[t] = {'outgoing': [], 'incoming': []}
            label = rel_info.get('description', rel_name)
            attr_names = rel_info.get('attributes', [])
            if isinstance(attr_names, dict):
                attr_names = list(attr_names.keys())
            relations_by_entity[t]['incoming'].append({
                'relation': rel_name,
                'source': from_type,
                'cardinality': rel_info.get('cardinality', ''),
                'description': label,
                'attributes': attr_names
            })

# Generate JS
js_lines = []
js_lines.append("// Auto-generated ontology data for detail panel")
js_lines.append("// Generated from legal_ontology_v2.zh.yaml")
js_lines.append("var ENTITY_DATA = " + json.dumps(entity_data, ensure_ascii=False, indent=2) + ";")
js_lines.append("")
js_lines.append("var RELATIONS_BY_ENTITY = " + json.dumps(relations_by_entity, ensure_ascii=False, indent=2) + ";")
js_lines.append("")
js_lines.append("var RELATION_DETAILS = " + json.dumps(relation_details, ensure_ascii=False, indent=2) + ";")

output = '\n'.join(js_lines)

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(output)

print(f"Generated {OUTPUT_PATH}")
print(f"Entities: {len(entity_data)}")
print(f"Entities with relations: {len(relations_by_entity)}")
print(f"Relation details: {len(relation_details)}")
print(f"Output size: {len(output)} bytes")
