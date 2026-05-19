import re

with open('/root/remote-test/visualization/ontology-refactored/src/components/TerminalPanel.js', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace ensureTerminalUI function
new_ensure = """  ensureTerminalUI() {
    if (this.panel) {
      this.panel.style.display = 'flex';
      this.panel.style.flexDirection = 'column';
    }
    const body = document.getElementById('termBody');
    if (body) {
      body.style.display = 'flex';
      body.style.flex = '1';
      body.style.overflow = 'hidden';
      body.style.position = 'relative';
      
      if (!document.getElementById('termControls')) {
        body.insertAdjacentHTML('afterbegin', `
          <div id="termControls" style="display: flex; flex-direction: column; width: 350px; padding: 10px; border-right: 1px solid #334155; flex-shrink: 0; background: #0f172a;">
            <textarea id="termInputArea" placeholder="输入案件文本..." style="flex: 1; resize: none; margin-bottom: 10px; background: #1e293b; color: #fff; border: 1px solid #475569; padding: 8px; font-family: monospace; border-radius: 4px;"></textarea>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
              <button id="btnTermParse" style="padding: 6px 12px; background: #3b82f6; color: #fff; border: none; border-radius: 4px; cursor: pointer;">1. 开始解析</button>
              <button id="btnTermEvaluate" disabled style="padding: 6px 12px; background: #8e44ad; color: #fff; border: none; border-radius: 4px; cursor: pointer; opacity: 0.5;">2. 本体论评估</button>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span id="termStatusArea" style="color: #94a3b8; font-size: 12px;">就绪</span>
              <button id="btnTermSave" disabled style="padding: 4px 10px; background: #27ae60; color: #fff; border: none; border-radius: 4px; cursor: pointer; opacity: 0.5;">💾 保存</button>
            </div>
          </div>
          <div id="termWorkspace" style="flex: 1; display: flex; flex-direction: column; background: #0f172a; overflow: hidden;">
            <div style="display: flex; background: #1e293b; border-bottom: 1px solid #334155;">
              <div class="term-tab active" data-target="termVisContainer" style="padding: 8px 16px; color: #fff; cursor: pointer; border-bottom: 2px solid #3b82f6;">📊 解析图谱</div>
              <div class="term-tab" data-target="termIssuesTabContent" style="padding: 8px 16px; color: #94a3b8; cursor: pointer; border-bottom: 2px solid transparent;">⚠ 质量分析</div>
              <div class="term-tab" data-target="termEvalTabContent" style="padding: 8px 16px; color: #94a3b8; cursor: pointer; border-bottom: 2px solid transparent;">📋 本体评估</div>
            </div>
            <div id="termWorkspaceContent" style="flex: 1; position: relative;">
              <!-- The original #termVisContainer will be moved into here by JS -->
              <div id="termIssuesTabContent" class="term-content-pane" style="display: none; position: absolute; inset: 0; overflow-y: auto; background: #fff; color: #333;">
                <div style="padding: 16px; color: #94a3b8;">等待解析...</div>
              </div>
              <div id="termEvalTabContent" class="term-content-pane" style="display: none; position: absolute; inset: 0; overflow-y: auto; background: #fff; color: #333;">
                <div style="padding: 16px; color: #94a3b8;">等待评估...</div>
              </div>
            </div>
          </div>
        `);
        
        const visContainer = document.getElementById('termVisContainer');
        const workspaceContent = document.getElementById('termWorkspaceContent');
        if (visContainer && workspaceContent) {
          workspaceContent.appendChild(visContainer);
          visContainer.classList.add('term-content-pane');
          visContainer.style.position = 'absolute';
          visContainer.style.inset = '0';
          visContainer.style.display = 'block';
        }
      }
    }
  }"""

content = re.sub(r'  ensureTerminalUI\(\) \{.*?\n  \}', new_ensure, content, flags=re.DOTALL)

with open('/root/remote-test/visualization/ontology-refactored/src/components/TerminalPanel.js', 'w', encoding='utf-8') as f:
    f.write(content)
