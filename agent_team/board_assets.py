BOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Team Read-Only Board</title>
  <style>
    :root {
      --ink: #14202b;
      --muted: #667788;
      --paper: #f7f1e6;
      --panel: #ffffff;
      --line: #ded5c4;
      --blue: #2f6f9f;
      --green: #3f8f5f;
      --yellow: #d8a026;
      --orange: #c56d2d;
      --red: #b74436;
      --deep-red: #7f1d1d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 0%, rgba(216,160,38,.18), transparent 32rem),
        linear-gradient(135deg, var(--paper), #e9eef2);
    }
    header {
      padding: 22px 28px;
      border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,.72);
      backdrop-filter: blur(10px);
    }
    h1 { margin: 0; font-size: 28px; }
    h2, h3 { margin-top: 0; }
    .subtitle { color: var(--muted); margin-top: 4px; }
    .stats {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
      padding: 16px 28px;
    }
    .stat {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
    }
    .stat b { display: block; font-size: 24px; }
    main {
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 18px;
      padding: 0 28px 28px;
    }
    aside, section {
      background: rgba(255,255,255,.82);
      border: 1px solid var(--line);
      border-radius: 18px;
      min-height: 560px;
      overflow: hidden;
    }
    .tree, .detail { padding: 18px; }
    .project, .worktree, .session {
      border-radius: 12px;
      padding: 10px;
      margin-bottom: 8px;
      word-break: break-word;
    }
    .project { background: var(--ink); color: var(--paper); }
    .worktree { margin-left: 14px; background: #eef3f6; }
    .session { margin-left: 28px; background: #fff; border: 1px solid var(--line); cursor: pointer; }
    .session.active { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(47,111,159,.16); }
    .timeline {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 8px;
      margin: 16px 0;
    }
    .stage {
      padding: 10px;
      border-radius: 12px;
      text-align: center;
      background: #ece7dc;
      font-size: 12px;
    }
    .stage.current { background: #dbeafe; border: 1px solid var(--blue); }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      margin-bottom: 12px;
    }
    .pill { display: inline-block; padding: 4px 8px; border-radius: 999px; color: white; font-size: 12px; }
    .RUNNING, .SUBMITTED { background: var(--blue); }
    .VERIFYING { background: var(--orange); }
    .PASSED, .Done { background: var(--green); }
    .FAILED { background: var(--red); }
    .BLOCKED, .Blocked { background: var(--deep-red); }
    .WaitForProductDefinitionApproval, .WaitForTechnicalDesignApproval, .WaitForHumanDecision { background: var(--yellow); color: #1b1308; }
    pre {
      white-space: pre-wrap;
      max-height: 300px;
      overflow: auto;
      background: #111827;
      color: #e5e7eb;
      padding: 12px;
      border-radius: 12px;
    }
    button.link {
      border: 0;
      background: transparent;
      color: var(--blue);
      cursor: pointer;
      padding: 0;
      font: inherit;
      text-decoration: underline;
    }
    .filters {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 16px 16px 0;
    }
    .filter {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      padding: 6px 10px;
    }
    .filter.active {
      background: var(--ink);
      border-color: var(--ink);
      color: var(--paper);
    }
    .session-meta {
      color: var(--muted);
      display: block;
      margin-top: 4px;
    }
    .artifact-section {
      margin-top: 14px;
    }
    .artifact-section-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: .08em;
      margin: 0 0 8px;
      text-transform: uppercase;
    }
    .artifact-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .artifact-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: #fffdf8;
    }
    .artifact-card h4 {
      margin: 0 0 6px;
      font-size: 17px;
    }
    .artifact-description {
      color: var(--muted);
      margin: 0 0 10px;
    }
    .artifact-file {
      color: var(--ink);
      font-size: 13px;
      margin: 8px 0 4px;
    }
    .artifact-path {
      color: var(--muted);
      display: block;
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .artifact-preview-title {
      color: var(--muted);
      margin: 16px 0 8px;
    }
    .workflow-bottleneck {
      background: linear-gradient(135deg, #fffdf7, #f4efe2);
    }
    .workflow-bottleneck.blocked {
      background: linear-gradient(135deg, #fff5f5, #fbeaea);
      border-color: #e4bcbc;
    }
    .workflow-bottleneck.active {
      background: linear-gradient(135deg, #eef6ff, #e5eef9);
      border-color: #bfd0e4;
    }
    .workflow-bottleneck.waiting {
      background: linear-gradient(135deg, #fff9ee, #f7f0e0);
    }
    .workflow-summary-title {
      font-size: 15px;
      margin: 0 0 8px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: .08em;
    }
    .workflow-summary-main {
      font-size: 26px;
      line-height: 1.3;
      margin: 0 0 10px;
    }
    .workflow-summary-reason {
      margin: 0 0 8px;
      color: var(--ink);
    }
    .workflow-summary-next {
      margin: 0;
      color: var(--ink);
    }
    .workflow-board {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .workflow-node {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
    }
    .workflow-node.current {
      background: #eef6ff;
      border-color: var(--blue);
      box-shadow: 0 0 0 2px rgba(47,111,159,.12);
    }
    .workflow-node.blocked {
      background: #fff6f6;
      border-color: #d9a9a0;
    }
    .workflow-node h4 {
      margin: 0 0 8px;
      font-size: 20px;
    }
    .workflow-node-owner {
      color: var(--muted);
      display: block;
      font-size: 13px;
      margin-bottom: 8px;
    }
    .workflow-node-status {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      background: #efe7d8;
      font-size: 12px;
      margin-bottom: 10px;
    }
    .workflow-node.current .workflow-node-status {
      background: #d7e8fb;
    }
    .workflow-node.blocked .workflow-node-status {
      background: #f6d7d2;
    }
    .workflow-node p {
      margin: 0 0 8px;
    }
    .workflow-node .next {
      color: var(--ink);
      font-weight: 700;
    }
    @media (max-width: 860px) {
      .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      main { grid-template-columns: 1fr; }
      .timeline { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .workflow-board { grid-template-columns: 1fr; }
      .artifact-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Agent Team Read-Only Board</h1>
    <div class="subtitle">Project -> Worktree -> Session. Read-only. Polling every 5 seconds.</div>
  </header>
  <div id="stats" class="stats"></div>
  <main>
    <aside><div id="filters" class="filters"></div><div id="tree" class="tree"></div></aside>
    <section><div id="detail" class="detail"></div></section>
  </main>
  <script>
    let board = null;
    let selectedSessionId = null;
    let currentFilter = 'all';
    const stages = [
      'Route',
      'ProductDefinition',
      'WaitForProductDefinitionApproval',
      'ProjectRuntime',
      'TechnicalDesign',
      'WaitForTechnicalDesignApproval',
      'Implementation',
      'Verification',
      'GovernanceReview',
      'Acceptance',
      'SessionHandoff',
      'WaitForHumanDecision',
      'Done'
    ];
    const workflowStageDefinitions = [
      { key: 'Route', title: 'Route', owner: 'Router' },
      { key: 'ProductDefinition', title: 'ProductDefinition / L1', owner: 'ProductDefinition' },
      { key: 'WaitForProductDefinitionApproval', title: 'L1 人工审批', owner: 'Human' },
      { key: 'ProjectRuntime', title: 'ProjectRuntime / L3', owner: 'ProjectRuntime' },
      { key: 'TechnicalDesign', title: 'TechnicalDesign / L2', owner: 'TechnicalDesign' },
      { key: 'WaitForTechnicalDesignApproval', title: '设计人工审批', owner: 'Human' },
      { key: 'Implementation', title: 'Implementation / L2', owner: 'Implementation' },
      { key: 'Verification', title: 'Verification / L2', owner: 'Verification' },
      { key: 'GovernanceReview', title: 'GovernanceReview / L4', owner: 'GovernanceReview' },
      { key: 'Acceptance', title: 'Acceptance', owner: 'Acceptance' },
      { key: 'SessionHandoff', title: 'SessionHandoff / L5', owner: 'SessionHandoff' },
      { key: 'WaitForHumanDecision', title: '最终人工决策', owner: 'Human' },
      { key: 'Done', title: 'Done', owner: 'System' }
    ];
    const filterDefinitions = [
      { key: 'all', label: 'All' },
      { key: 'active', label: 'Active' },
      { key: 'waiting_human', label: 'Waiting Human' },
      { key: 'has_run', label: 'Has Run' },
      { key: 'empty', label: 'Empty' }
    ];

    async function loadBoard() {
      const response = await fetch('/api/board');
      board = await response.json();
      render();
    }

    function allSessions() {
      const sessions = [];
      for (const project of board?.projects || []) {
        for (const worktree of project.worktrees || []) {
          for (const session of worktree.sessions || []) {
            sessions.push({ project, worktree, session });
          }
        }
      }
      return sessions;
    }

    function render() {
      renderStats();
      renderFilters();
      renderTree();
      renderDetail();
    }

    function renderStats() {
      const stats = board?.stats || {};
      const keys = ['projects', 'worktrees', 'sessions', 'blocked', 'waiting_human', 'submitted_runs'];
      document.getElementById('stats').innerHTML = keys
        .map(key => `<div class="stat"><b>${stats[key] || 0}</b><span>${key}</span></div>`).join('');
    }

    function renderFilters() {
      document.getElementById('filters').innerHTML = filterDefinitions.map(item => {
        const count = countSessionsForFilter(item.key);
        return `<button class="filter ${currentFilter === item.key ? 'active' : ''}" onclick="selectFilter('${item.key}')">${item.label} ${count}</button>`;
      }).join('');
    }

    function renderTree() {
      const visible = visibleSessions();
      if (!visible.some(item => item.session.session_id === selectedSessionId)) {
        selectedSessionId = visible.length ? visible[0].session.session_id : null;
      }
      const treeHtml = (board?.projects || []).map(project => {
        const worktreeHtml = (project.worktrees || []).map(worktree => {
          const sessions = (worktree.sessions || []).filter(sessionMatchesCurrentFilter);
          if (!sessions.length) return '';
          return `
          <div class="worktree"><b>${escapeHtml(worktree.branch || 'unknown branch')}</b><br><small>${escapeHtml(worktree.worktree_path || worktree.state_root)}</small></div>
          ${sessions.map(session => `
            <div class="session ${session.session_id === selectedSessionId ? 'active' : ''}" onclick="selectSession('${session.session_id}')">
              <b>${escapeHtml(shortText(session.request))}</b><br>
              <small>${escapeHtml(session.current_state)} / ${escapeHtml(session.active_run?.state || 'no run')}</small>
              <small class="session-meta">${escapeHtml(formatSessionMeta(session))}</small>
            </div>
          `).join('')}
        `;
        }).join('');
        if (!worktreeHtml) return '';
        return `
          <div class="project"><b>${escapeHtml(project.project_name)}</b><br><small>${escapeHtml(project.project_root || 'legacy workspace')}</small></div>
          ${worktreeHtml}
        `;
      }).join('');
      document.getElementById('tree').innerHTML = treeHtml || `<div class="card">No sessions match ${escapeHtml(currentFilterLabel())}.</div>`;
    }

    function renderDetail() {
      const sessions = visibleSessions();
      const match = sessions.find(item => item.session.session_id === selectedSessionId) || sessions[0];
      if (!match) {
        document.getElementById('detail').innerHTML = `<div class="card">No sessions match ${escapeHtml(currentFilterLabel())}.</div>`;
        return;
      }
      selectedSessionId = match.session.session_id;
      const session = match.session;
      const run = session.active_run;
      document.getElementById('detail').innerHTML = `
        <h2>${escapeHtml(shortText(session.request, 90))}</h2>
        <div class="subtitle">${escapeHtml(match.project.project_name)} / ${escapeHtml(match.worktree.branch || 'unknown branch')} / ${escapeHtml(formatSessionMeta(session))}</div>
        <div class="card">
          ${renderBottleneckSummary(session)}
        </div>
        <div class="card">
          <h3>Workflow Run Board</h3>
          ${renderWorkflowRunBoard(session)}
        </div>
        <div class="card">
          <h3>Active Run</h3>
          ${run ? `<span class="pill ${run.state}">${escapeHtml(run.state)}</span>
            <p>${escapeHtml(run.stage)} / ${escapeHtml(run.run_id)}</p>
            <p><b>Gate:</b> ${escapeHtml(run.gate_status || 'not verified')}</p>
            <p><b>Required outputs:</b> ${(run.required_outputs || []).map(escapeHtml).join(', ')}</p>
            <p><b>Required evidence:</b> ${(run.required_evidence || []).map(escapeHtml).join(', ')}</p>` : '<p>当前没有活跃 run。若当前阶段已经进入执行，通常表示还没人认领或这是缺少 stage-run 记录的历史 session。</p>'}
        </div>
        <div class="card">
          <h3>Artifacts</h3>
          ${renderArtifactSections(session)}
          <p id="artifact-preview-title" class="artifact-preview-title">选择一个产物预览</p>
          <pre id="artifact-preview">点击“预览内容”查看文件内容。</pre>
        </div>
        <p class="subtitle">Last refreshed: ${escapeHtml(formatRefreshTime(board.generated_at))}</p>
      `;
    }

    async function loadArtifact(path, title) {
      const decodedTitle = decodeURIComponent(title || '');
      document.getElementById('artifact-preview-title').textContent = decodedTitle || '产物预览';
      const response = await fetch('/api/artifact?path=' + path);
      document.getElementById('artifact-preview').textContent = await response.text();
    }

    function renderBottleneckSummary(session) {
      const summary = bottleneckSummaryFor(session);
      return `
        <div class="workflow-bottleneck ${summary.tone}">
          <p class="workflow-summary-title">当前 bottleneck</p>
          <p class="workflow-summary-main">${escapeHtml(summary.headline)}</p>
          <p class="workflow-summary-reason"><b>原因：</b>${escapeHtml(summary.reason)}</p>
          <p class="workflow-summary-next"><b>下一步：</b>${escapeHtml(summary.nextAction)}</p>
        </div>
      `;
    }

    function renderWorkflowRunBoard(session) {
      return `<div class="workflow-board">${workflowNodesFor(session).map(renderWorkflowNode).join('')}</div>`;
    }

    function renderWorkflowNode(node) {
      return `
        <div class="workflow-node ${node.isCurrent ? 'current' : ''} ${node.tone}">
          <h4>${escapeHtml(node.title)}</h4>
          <span class="workflow-node-owner">负责人：${escapeHtml(node.owner)}</span>
          <span class="workflow-node-status">${escapeHtml(node.statusLabel)}</span>
          <p>${escapeHtml(node.reason)}</p>
          <p><b>交付：</b>${escapeHtml(node.deliverables)}</p>
          <p class="next">下一步：${escapeHtml(node.nextAction)}</p>
        </div>
      `;
    }

    function workflowNodesFor(session) {
      return workflowStageDefinitions.map((definition, index) => {
        const isCurrent = isCurrentWorkflowNode(definition.key, session);
        return {
          ...definition,
          isCurrent,
          ...workflowNodeState(definition.key, index, session, isCurrent)
        };
      });
    }

    function workflowNodeState(stageKey, index, session, isCurrent) {
      const currentIndex = workflowStageIndexFor(session);
      const hasDeliverables = stageDeliverables(session, stageKey);
      if (session.current_state === 'Blocked' && stageKey === session.current_stage) {
        return {
          statusLabel: '已阻塞',
          reason: session.blocked_reason || `${stageKey} 阶段被阻塞。`,
          deliverables: hasDeliverables,
          nextAction: `先处理阻塞原因，再决定是否继续由 ${workflowOwnerFor(stageKey)} 推进。`,
          tone: 'blocked'
        };
      }
      if (isCurrent) {
        if (session.active_run && session.active_run.stage === stageKey) {
          return currentNodeStateFromRun(stageKey, session.active_run, hasDeliverables);
        }
        if (
          stageKey === 'WaitForProductDefinitionApproval'
          || stageKey === 'WaitForTechnicalDesignApproval'
          || stageKey === 'WaitForHumanDecision'
        ) {
          return {
            statusLabel: '等待人工确认',
            reason: waitingHumanReason(stageKey),
            deliverables: hasDeliverables,
            nextAction: waitingHumanNextAction(stageKey),
            tone: 'waiting'
          };
        }
        if (stageKey !== 'Done') {
          return {
            statusLabel: '等待处理',
            reason: missingRunReason(stageKey),
            deliverables: hasDeliverables,
            nextAction: missingRunNextAction(stageKey),
            tone: 'waiting'
          };
        }
      }
      if (stageKey === 'Done') {
        if (session.current_state === 'Done') {
          return {
            statusLabel: '已完成',
            reason: '这条 workflow 已经结束。',
            deliverables: '流程已结束',
            nextAction: '无需进一步处理。',
            tone: ''
          };
        }
        return {
          statusLabel: '未开始',
          reason: '还没有进入完成态。',
          deliverables: '尚无',
          nextAction: '先推进前面的 workflow 节点。',
          tone: ''
        };
      }
      if (index < currentIndex || isCompletedByArtifacts(session, stageKey)) {
        return {
          statusLabel: '已完成',
          reason: completedReasonFor(stageKey),
          deliverables: hasDeliverables,
          nextAction: '等待后续节点继续推进。',
          tone: ''
        };
      }
      return {
        statusLabel: '未开始',
        reason: '前置节点还没有完成，尚未轮到这个阶段。',
        deliverables: '尚无',
        nextAction: `先完成 ${previousWorkflowStage(stageKey)}。`,
        tone: ''
      };
    }

    function currentNodeStateFromRun(stageKey, run, deliverables) {
      if (run.state === 'SUBMITTED' || run.state === 'VERIFYING') {
        return {
          statusLabel: '等待验证',
          reason: `${stageKey} 结果已提交，正在等待 gate 验证。`,
          deliverables,
          nextAction: '等待 gatekeeper 完成验证。',
          tone: 'active'
        };
      }
      return {
        statusLabel: '进行中',
        reason: `${stageKey} 已被认领，当前正在处理。`,
        deliverables,
        nextAction: `${workflowOwnerFor(stageKey)} 提交阶段结果。`,
        tone: 'active'
      };
    }

    function renderArtifactSections(session) {
      const artifacts = Object.entries(session.artifact_paths || {})
        .map(([key, path]) => artifactMetadataFor(key, path));
      if (!artifacts.length) return '<p>暂无产物。</p>';

      const sections = [
        { category: 'business', label: '业务产物' },
        { category: 'runtime', label: '运行时元数据' },
        { category: 'other', label: '其他产物' }
      ];
      return sections.map(section => {
        const items = artifacts.filter(item => item.category === section.category);
        if (!items.length) return '';
        return `
          <div class="artifact-section">
            <p class="artifact-section-label">${section.label}</p>
            <div class="artifact-grid">
              ${items.map(renderArtifactCard).join('')}
            </div>
          </div>
        `;
      }).join('');
    }

    function renderArtifactCard(item) {
      return `
        <div class="artifact-card">
          <h4>${escapeHtml(item.title)}</h4>
          <p class="artifact-description">${escapeHtml(item.description)}</p>
          <button class="link" onclick="loadArtifact('${encodeURIComponent(item.path)}', '${encodeURIComponent(item.title)}')">预览内容</button>
          <p class="artifact-file">文件：${escapeHtml(item.filename)}</p>
          <small class="artifact-path" title="${escapeHtml(item.path)}">${escapeHtml(item.path)}</small>
        </div>
      `;
    }

    function artifactMetadataFor(key, path) {
      const metadata = {
        request: {
          category: 'runtime',
          title: '原始需求',
          description: '启动这个 session 时记录的需求输入。'
        },
        workflow_summary: {
          category: 'runtime',
          title: '流程摘要',
          description: '当前状态、阶段、人工决策和已记录产物。'
        },
        acceptance_contract: {
          category: 'runtime',
          title: '验收约束',
          description: '这条需求的验收条件、证据要求和边界规则。'
        },
        route: {
          category: 'business',
          title: 'Route Packet',
          description: 'Route 阶段产出的层级影响、红线和下游执行路由。'
        },
        product_definition: {
          category: 'business',
          title: 'L1 产品定义增量',
          description: 'ProductDefinition 阶段产出的产品定义增量和需要审批的语义变化。'
        },
        project_runtime: {
          category: 'business',
          title: 'L3 项目落地增量',
          description: 'ProjectRuntime 阶段产出的默认入口、工件落点和项目承载约定。'
        },
        technical_design: {
          category: 'business',
          title: 'L2 技术设计',
          description: 'TechnicalDesign 阶段产出的实现方案、接口和验证计划。'
        },
        implementation: {
          category: 'business',
          title: 'L2 实现交付',
          description: 'Implementation 阶段产出的实现说明、变更证据和自检结果。'
        },
        verification: {
          category: 'business',
          title: 'L2 独立验证',
          description: 'Verification 阶段产出的复跑结果、风险和回流建议。'
        },
        governance_review: {
          category: 'business',
          title: 'L4 治理审查',
          description: 'GovernanceReview 阶段产出的五层边界、门禁和收口检查结论。'
        },
        acceptance: {
          category: 'business',
          title: '验收建议',
          description: 'Acceptance 阶段产出的产品级验收建议。'
        },
        session_handoff: {
          category: 'runtime',
          title: 'L5 Session Handoff',
          description: 'SessionHandoff 阶段产出的本地现场恢复、下一步动作和连续性信息。'
        }
      };
      const known = metadata[key] || {
        category: 'other',
        title: key,
        description: '这个 artifact 暂无内置说明，可预览内容查看。'
      };
      return {
        ...known,
        key,
        path,
        filename: filenameFromPath(path)
      };
    }

    function filenameFromPath(path) {
      const text = String(path || '');
      return text.split('/').filter(Boolean).pop() || text;
    }

    function bottleneckSummaryFor(session) {
      if (session.current_state === 'Blocked') {
        return {
          headline: `当前已阻塞在 ${humanStageName(session.current_stage)}。`,
          reason: session.blocked_reason || '流程被阻塞，需要人工处理。',
          nextAction: `先解决阻塞原因，再决定是否由 ${workflowOwnerFor(session.current_stage)} 继续推进。`,
          tone: 'blocked'
        };
      }
      if (session.active_run) {
        if (session.active_run.state === 'SUBMITTED' || session.active_run.state === 'VERIFYING') {
          return {
            headline: `当前停在 ${humanStageName(session.active_run.stage)}，等待 gate 验证。`,
            reason: `${humanStageName(session.active_run.stage)} 已提交结果，gate 还没有完成验证。`,
            nextAction: '等待 gatekeeper 完成验证并推进到下一节点。',
            tone: 'active'
          };
        }
        return {
          headline: `当前由 ${workflowOwnerFor(session.active_run.stage)} 处理 ${humanStageName(session.active_run.stage)}。`,
          reason: `${humanStageName(session.active_run.stage)} 已被认领，正在执行。`,
          nextAction: `${workflowOwnerFor(session.active_run.stage)} 提交阶段结果。`,
          tone: 'active'
        };
      }
      if (
        session.current_state === 'WaitForProductDefinitionApproval'
        || session.current_state === 'WaitForTechnicalDesignApproval'
        || session.current_state === 'WaitForHumanDecision'
      ) {
        return {
          headline: `当前等待${workflowOwnerFor(session.current_state)}决策。`,
          reason: waitingHumanReason(session.current_state),
          nextAction: waitingHumanNextAction(session.current_state),
          tone: 'waiting'
        };
      }
      if (session.current_stage && session.current_stage !== 'Intake' && session.current_stage !== 'Done') {
        return {
          headline: `当前停在 ${humanStageName(session.current_stage)}。`,
          reason: missingRunReason(session.current_stage),
          nextAction: missingRunNextAction(session.current_stage),
          tone: 'waiting'
        };
      }
      if (session.current_state === 'Done') {
        return {
          headline: '当前 workflow 已完成。',
          reason: '所有阶段已经结束。',
          nextAction: '无需进一步处理。',
          tone: 'active'
        };
      }
      return {
        headline: '当前还在 Intake。',
        reason: '这条 session 还没有进入可执行的 workflow 节点。',
        nextAction: '先由 Route 分类层级影响，再进入 ProductDefinition。',
        tone: 'waiting'
      };
    }

    function visibleSessions() {
      return allSessions().filter(item => sessionMatchesCurrentFilter(item.session));
    }

    function sessionMatchesCurrentFilter(session) {
      return sessionMatchesFilter(session, currentFilter);
    }

    function sessionMatchesFilter(session, filterKey) {
      if (filterKey === 'empty') return isEmptySession(session);
      if (filterKey === 'has_run') return Boolean(session.active_run);
      if (filterKey === 'waiting_human') return session.workflow_status === 'waiting_human'
        || session.current_state === 'WaitForProductDefinitionApproval'
        || session.current_state === 'WaitForTechnicalDesignApproval'
        || session.current_state === 'WaitForHumanDecision';
      if (filterKey === 'active') return !isEmptySession(session) && session.current_state !== 'Done';
      return true;
    }

    function isEmptySession(session) {
      return session.current_state === 'Intake' && !session.active_run;
    }

    function countSessionsForFilter(filterKey) {
      return allSessions().filter(item => sessionMatchesFilter(item.session, filterKey)).length;
    }

    function selectFilter(filterKey) {
      currentFilter = filterKey;
      render();
    }

    function selectSession(sessionId) {
      selectedSessionId = sessionId;
      render();
    }

    function currentFilterLabel() {
      return filterDefinitions.find(item => item.key === currentFilter)?.label || 'All';
    }

    function shortText(value, max = 44) {
      const text = value || '';
      return text.length > max ? text.slice(0, max - 3) + '...' : text;
    }

    function workflowStageIndexFor(session) {
      const key = session.current_state === 'Blocked' ? session.current_stage : session.current_state;
      const index = workflowStageDefinitions.findIndex(item => item.key === key);
      return index >= 0 ? index : 0;
    }

    function isCurrentWorkflowNode(stageKey, session) {
      if (session.current_state === 'Blocked') return stageKey === session.current_stage;
      return stageKey === session.current_state || stageKey === session.current_stage;
    }

    function humanStageName(stageKey) {
      return workflowStageDefinitions.find(item => item.key === stageKey)?.title || stageKey || '当前阶段';
    }

    function workflowOwnerFor(stageKey) {
      return workflowStageDefinitions.find(item => item.key === stageKey)?.owner || '当前负责人';
    }

    function waitingHumanReason(stageKey) {
      if (stageKey === 'WaitForProductDefinitionApproval') {
        return 'ProductDefinition 已产出 L1 增量，需要人工确认是否成为本任务的上层约束。';
      }
      if (stageKey === 'WaitForTechnicalDesignApproval') {
        return 'TechnicalDesign 已产出 L2 设计，需要人工确认是否进入实现。';
      }
      return 'SessionHandoff 已完成，等待最终人工决策。';
    }

    function waitingHumanNextAction(stageKey) {
      if (stageKey === 'WaitForProductDefinitionApproval' || stageKey === 'WaitForTechnicalDesignApproval') {
        return '由审批人决定 go / rework / no-go。';
      }
      return '由人工决定 go / no-go / rework。';
    }

    function missingRunReason(stageKey) {
      if (stageKey === 'Verification') {
        return '当前阶段已经进入 Verification，但还没有可跟踪的 Verification run。';
      }
      return `当前阶段已经进入 ${humanStageName(stageKey)}，但还没有可跟踪的 ${stageKey} run。`;
    }

    function missingRunNextAction(stageKey) {
      return `由 ${workflowOwnerFor(stageKey)} 认领并开始${humanStageName(stageKey)}。`;
    }

    function completedReasonFor(stageKey) {
      if (stageKey === 'WaitForProductDefinitionApproval') return 'L1 人工审批已经放行，流程继续推进。';
      if (stageKey === 'WaitForTechnicalDesignApproval') return '技术设计人工审批已经放行，流程继续推进。';
      if (stageKey === 'WaitForHumanDecision') return '最终人工决策已经完成。';
      return `${humanStageName(stageKey)} 已经完成并流转到后续节点。`;
    }

    function previousWorkflowStage(stageKey) {
      const index = workflowStageDefinitions.findIndex(item => item.key === stageKey);
      if (index <= 0) return '前置阶段';
      return humanStageName(workflowStageDefinitions[index - 1].key);
    }

    function isCompletedByArtifacts(session, stageKey) {
      if (stageKey === 'Route') return Boolean(session.artifact_paths?.route);
      if (stageKey === 'ProductDefinition') return Boolean(session.artifact_paths?.product_definition);
      if (stageKey === 'ProjectRuntime') return Boolean(session.artifact_paths?.project_runtime);
      if (stageKey === 'TechnicalDesign') return Boolean(session.artifact_paths?.technical_design);
      if (stageKey === 'Implementation') return Boolean(session.artifact_paths?.implementation);
      if (stageKey === 'Verification') return Boolean(session.artifact_paths?.verification);
      if (stageKey === 'GovernanceReview') return Boolean(session.artifact_paths?.governance_review);
      if (stageKey === 'Acceptance') return Boolean(session.artifact_paths?.acceptance);
      if (stageKey === 'SessionHandoff') return Boolean(session.artifact_paths?.session_handoff);
      if (stageKey === 'WaitForProductDefinitionApproval') return workflowStageIndexFor(session) > 2;
      if (stageKey === 'WaitForTechnicalDesignApproval') return workflowStageIndexFor(session) > 5;
      if (stageKey === 'WaitForHumanDecision') return session.current_state === 'Done';
      return false;
    }

    function stageDeliverables(session, stageKey) {
      if (stageKey === 'Route') return session.artifact_paths?.route ? 'Route Packet 已产出' : '尚无 Route Packet';
      if (stageKey === 'ProductDefinition') return session.artifact_paths?.product_definition ? 'L1 增量已产出' : '尚无 L1 增量';
      if (stageKey === 'ProjectRuntime') return session.artifact_paths?.project_runtime ? 'L3 落地增量已产出' : '尚无 L3 落地增量';
      if (stageKey === 'TechnicalDesign') return session.artifact_paths?.technical_design ? '技术设计已产出' : '尚无技术设计';
      if (stageKey === 'Implementation') return session.artifact_paths?.implementation ? '实现交付已产出' : '尚无实现交付';
      if (stageKey === 'Verification') return session.artifact_paths?.verification ? '验证报告已产出' : '尚无验证报告';
      if (stageKey === 'GovernanceReview') return session.artifact_paths?.governance_review ? '治理审查已产出' : '尚无治理审查';
      if (stageKey === 'Acceptance') return session.artifact_paths?.acceptance ? '验收建议已产出' : '尚无验收建议';
      if (stageKey === 'SessionHandoff') return session.artifact_paths?.session_handoff ? 'Session Handoff 已产出' : '尚无 Session Handoff';
      if (stageKey === 'WaitForProductDefinitionApproval') return '无需文件产物';
      if (stageKey === 'WaitForTechnicalDesignApproval') return '无需文件产物';
      if (stageKey === 'WaitForHumanDecision') return '无需文件产物';
      if (stageKey === 'Done') return session.current_state === 'Done' ? '流程已结束' : '尚未结束';
      return '尚无';
    }

    function formatSessionMeta(session) {
      const createdAt = formatSessionDateTime(session.created_at);
      const id = shortSessionId(session.session_id);
      return createdAt ? `${createdAt} / ${id}` : id;
    }

    function formatSessionDateTime(value) {
      if (!value) return '';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return new Intl.DateTimeFormat(undefined, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).format(date);
    }

    function shortSessionId(value) {
      const text = value || '';
      return text.length > 20 ? text.slice(0, 20) + '...' : text;
    }

    function formatRefreshTime(value) {
      if (!value) return '';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return new Intl.DateTimeFormat(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).format(date);
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[char]));
    }

    loadBoard();
    setInterval(loadBoard, 5000);
  </script>
</body>
</html>
"""
