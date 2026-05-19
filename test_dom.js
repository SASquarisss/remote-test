const { JSDOM } = require('jsdom');
const { window } = new JSDOM('<!DOCTYPE html><div id="termJsonTree"></div><div id="termJsonPlaceholder"></div>');
global.document = window.document;
global.window = window;

const fs = require('fs');
const data = JSON.parse(fs.readFileSync('visualization/data/test_data.json', 'utf8'));

// Minimal version of TerminalPanel's render logic
class TerminalPanel {
  renderJson(jsonResult) {
    const treeHost = document.getElementById('termJsonTree');
    const jsonObj = typeof jsonResult === 'string' ? JSON.parse(jsonResult) : jsonResult;
    treeHost.innerHTML = '';
    treeHost.appendChild(this.buildJsonTree(jsonObj, true));
  }
  buildJsonTree(obj, isRoot = false) {
    const container = document.createElement('div');
    if (typeof obj !== 'object' || obj === null) {
      const val = document.createElement('span');
      val.textContent = JSON.stringify(obj);
      container.appendChild(val);
      return container;
    }
    const isArray = Array.isArray(obj);
    const keys = Object.keys(obj);
    keys.forEach((key, idx) => {
      const line = document.createElement('div');
      if (!isArray) line.setAttribute('data-json-key', key);
      const isComplex = typeof obj[key] === 'object' && obj[key] !== null;
      if (isComplex) {
        const childContainer = this.buildJsonTree(obj[key]);
        container.appendChild(line);
        container.appendChild(childContainer);
      } else {
        container.appendChild(line);
      }
    });
    return container;
  }
}

try {
  const panel = new TerminalPanel();
  panel.renderJson(data.json_result);
  console.log("Success, tree nodes:", document.getElementById('termJsonTree').innerHTML.length);
} catch (e) {
  console.error("Error:", e);
}
