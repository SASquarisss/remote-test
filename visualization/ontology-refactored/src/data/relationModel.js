import { RELATION_EDGES } from './schema.js';

export const DERIVED_RELATION_POLICIES = [
  {
    relationType: 'element_of_provision',
    fromType: 'LegalProvisionElement',
    toType: 'LegalProvision',
    label: '要件对应法条',
    description: '通过 legal_provision_elements[].provision_index 自动补图，不要求模型在 relations 中显式输出。',
    source: 'derived',
    derivationKind: 'provision_index'
  }
];

export function getOntologyRelationEdges() {
  const explicitEdges = (RELATION_EDGES || []).map((edge, index) => ({
    id: `schema_edge_${index}`,
    relationType: edge[0],
    fromType: edge[1],
    toType: edge[2],
    label: edge[0],
    source: 'schema',
    description: ''
  }));

  const derivedEdges = DERIVED_RELATION_POLICIES.map((edge, index) => ({
    id: `derived_edge_${index}`,
    relationType: edge.relationType,
    fromType: edge.fromType,
    toType: edge.toType,
    label: edge.label || edge.relationType,
    source: 'derived',
    description: edge.description || '',
    derivationKind: edge.derivationKind || ''
  }));

  return [...explicitEdges, ...derivedEdges];
}

