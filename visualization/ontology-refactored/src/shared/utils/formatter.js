export function escapeHtml(str) {
  if (typeof str !== 'string') return String(str ?? '');
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}
