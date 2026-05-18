export function safeGetElement(id) {
  const el = document.getElementById(id);
  if (!el) console.warn(`Element #${id} not found`);
  return el;
}
