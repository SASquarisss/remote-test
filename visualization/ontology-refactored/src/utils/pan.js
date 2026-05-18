export function bindCustomPan(network, container, onPan) {
  let dragState = null;
  
  function getPoint(ev) {
    const rect = container.getBoundingClientRect();
    return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
  }

  function stopDrag() {
    if (!dragState) return;
    dragState = null;
    container.classList.remove('panning');
    container.style.cursor = 'grab';
    document.removeEventListener('mousemove', onMouseMove, true);
    document.removeEventListener('mouseup', stopDrag, true);
  }

  function onMouseMove(ev) {
    if (!dragState || !network) return;
    ev.preventDefault();
    const dx = ev.clientX - dragState.startX;
    const dy = ev.clientY - dragState.startY;
    network.moveTo({
      position: {
        x: dragState.origin.x - dx / dragState.scale,
        y: dragState.origin.y - dy / dragState.scale
      },
      scale: dragState.scale,
      animation: false
    });
    if (onPan) onPan();
  }

  function onMouseDown(ev) {
    if (!network || ev.button !== 0) return;
    if (ev.target && ev.target.tagName !== 'CANVAS') return;
    const point = getPoint(ev);
    const hitNode = network.getNodeAt ? network.getNodeAt(point) : null;
    const hitEdge = network.getEdgeAt ? network.getEdgeAt(point) : null;
    if (hitNode || hitEdge) return; // Let vis.js handle node/edge dragging
    
    ev.preventDefault();
    ev.stopPropagation();
    dragState = {
      startX: ev.clientX,
      startY: ev.clientY,
      origin: network.getViewPosition(),
      scale: network.getScale() || 1
    };
    container.classList.add('panning');
    container.style.cursor = 'grabbing';
    document.addEventListener('mousemove', onMouseMove, true);
    document.addEventListener('mouseup', stopDrag, true);
  }

  container.addEventListener('mousedown', onMouseDown, true);
  
  return () => {
    stopDrag();
    container.removeEventListener('mousedown', onMouseDown, true);
  };
}