/**
 * Source UI - Main Application
 * The heart of the Source Control Center
 */

// Application state
let currentView = 'dashboard';
let refreshInterval = null;
let refreshInFlight = false;
let refreshQueued = false;
let commandSubmissionInFlight = false;

window.addEventListener('error', (event) => {
    console.error('Source UI runtime error', event.error || event.message);
    const line = document.getElementById('command-status-line');
    if (line) {
        line.textContent = `UI runtime error: ${event.message}`;
        line.dataset.tone = 'error';
    }
});

// Initialize application
async function initApp() {
    console.log('⚡ Source UI initializing...');
    
    // Initialize demo data
    store.initDemoData();
    
    // Initialize UI
    initNavigation();
    initTheme();
    initViews();
    initCommandDeck();
    initDragAndDrop();
    initModals();
    initCommandPalette();
    initNotifications();
    initSettings();
    initKeyboardShortcuts();
    initMoodWidget();
    
    renderCommandStatus('Synchronizing live state…', 'working');
    await refreshAll({ quiet: true });
    renderAll();
    renderCommandStatus('Bounded actions only. Supported: refresh, health check, status snapshot, restart gateway, create task.', 'neutral');

    // Start data refresh after the first live sync so the initial paint is coherent.
    startDataRefresh();
    
    console.log('⚡ Source UI ready');
}

// Navigation
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item[data-view]');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const view = item.dataset.view;
            navigateTo(view);
        });
    });
    
    // Mobile menu toggle
    $('#menu-toggle')?.addEventListener('click', () => {
        $('#sidebar').classList.toggle('open');
    });
    
    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', (e) => {
        const sidebar = $('#sidebar');
        const toggle = $('#menu-toggle');
        if (sidebar && !sidebar.contains(e.target) && !toggle?.contains(e.target)) {
            sidebar.classList.remove('open');
        }
    });
}

function navigateTo(view) {
    // Update nav
    document.querySelectorAll('.nav-item[data-view]').forEach(item => {
        item.classList.toggle('active', item.dataset.view === view);
    });
    
    // Update views
    document.querySelectorAll('.view').forEach(v => {
        v.classList.toggle('active', v.id === `view-${view}`);
    });
    
    // Update title
    const titles = {
        dashboard: 'Dashboard',
        tasks: 'Tasks',
        agents: 'Agents',
        schedule: 'Schedule',
        health: 'System Health',
        logs: 'Logs',
        settings: 'Settings',
        symbiote: 'Collective Intelligence Symbiote'
    };
    
    $('#page-title').textContent = titles[view] || 'Dashboard';
    
    currentView = view;
    
    // Render view-specific content
    renderView(view);
}

// Theme
function initTheme() {
    const savedTheme = store.get('settings.theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    $('#theme-toggle')?.addEventListener('click', toggleTheme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    store.updateSetting('theme', next);
}

// Views
function initViews() {
    // Quick actions
    $('#quick-restart')?.addEventListener('click', restartGateway);
    $('#quick-health')?.addEventListener('click', runHealthCheck);
    
    // New task button
    $('#new-task-btn')?.addEventListener('click', openNewTaskModal);
    
    // Filters
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            store.set('taskFilter', btn.dataset.filter);
            renderTasks();
        });
    });
    
    // Schedule navigation
    $('#prev-week')?.addEventListener('click', () => navigateWeek(-1));
    $('#next-week')?.addEventListener('click', () => navigateWeek(1));
}

function renderAll() {
    renderDashboard();
    renderTasks();
    renderAgents();
    renderSchedule();
    renderHealth();
    renderLogs();
    renderNotifications();
    updateStatusIndicators();
    renderSymbiote();
}

function renderView(view) {
    switch (view) {
        case 'dashboard':
            renderDashboard();
            break;
        case 'tasks':
            renderTasks();
            break;
        case 'agents':
            renderAgents();
            break;
        case 'schedule':
            renderSchedule();
            break;
        case 'health':
            renderHealth();
            break;
        case 'logs':
            renderLogs();
            break;
        case 'settings':
            renderSettings();
            break;
        case 'symbiote':
            renderSymbiote();
            break;
    }
}

// Dashboard
function renderDashboard() {
    const agents = store.get('agents');
    const tasks = store.get('tasks');
    const portfolio = store.get('portfolio') || {};
    const components = (portfolio.components && portfolio.components.length) ? portfolio.components : store.get('components');
    const workItems = portfolio.work_items || [];
    const externalSignals = portfolio.external_signals || [];
    const financeBrain = portfolio.finance_brain || {};
    const sims = (portfolio.sims || []).filter(sim => sim.active_book);
    const discordBridge = portfolio.discord_bridge || {};
    const teamchat = portfolio.teamchat || {};
    const sourceMission = portfolio.source_mission || {};
    const commands = store.get('commands') || [];
    const operatorTimeline = portfolio.operator_timeline || [];
    const simOps = portfolio.sim_ops || {};
    const memoryOps = portfolio.memory_ops || {};
    const modelOps = portfolio.model_ops || {};
    
    renderCommandDeck({ portfolio, tasks, components, commands });
    renderSourceMission(sourceMission);
    renderWorkItems(workItems, tasks);
    renderExternalSignals(externalSignals);
    renderFinanceBrain(financeBrain);
    renderDiscordBridge(discordBridge);
    renderTeamchat(teamchat);
    renderOperatorTimeline(operatorTimeline);
    renderSimOps(simOps, sims);
    renderMemoryOps(memoryOps);
    renderModelOps(modelOps);
    renderSourceIntelligence();

    const pendingTasks = tasks.filter(t => t.status !== 'done').length;
    const taskBadge = $('#task-badge');
    if (taskBadge) taskBadge.textContent = pendingTasks;
}

function renderCommandDeck({ portfolio, tasks, components, commands }) {
    renderCommandLanes(portfolio, tasks, components);
    renderCommandSuggestions();
    renderCommandHistory(commands);
    renderCommandReceipts(store.get('commandReceipts') || []);
}

function renderCommandLanes(portfolio, tasks, components) {
    const container = $('#command-lanes');
    if (!container) return;

    const financeRows = portfolio.finance_brain?.symbols || [];
    const discordChannels = portfolio.discord_bridge?.channels || [];
    const activeWork = portfolio.work_items || [];
    const assistant = (components || []).find(component => component.id === 'assistant');
    const queueDepth = tasks.filter(task => task.status !== 'done').length;
    const dominantModel = financeRows.find(row => row.model_resolved)?.model_resolved || 'local-assistant';
    const activeSignals = financeRows.length;
    const healthyBridgeCount = discordChannels.filter(channel => channel.enabled && channel.has_webhook).length;

    const lanes = [
        {
            label: 'Assistant Lane',
            value: assistant?.status === 'healthy' ? 'live' : (assistant?.status || 'unknown'),
            meta: assistant?.details || 'Local reasoning lane',
            tone: statusTone(assistant?.status || 'neutral'),
        },
        {
            label: 'Finance Loop',
            value: `${activeSignals} symbols`,
            meta: `Primary model ${dominantModel}`,
            tone: activeSignals ? 'healthy' : 'neutral',
        },
        {
            label: 'Coordination',
            value: `${activeWork.length} active`,
            meta: `${healthyBridgeCount}/${discordChannels.length || 0} Discord channels armed`,
            tone: activeWork.length ? 'warning' : 'neutral',
        },
        {
            label: 'Task Queue',
            value: `${queueDepth} open`,
            meta: `${tasks.filter(task => task.status === 'in_progress').length} in progress`,
            tone: queueDepth > 6 ? 'warning' : 'healthy',
        },
    ];

    container.innerHTML = lanes.map(lane => `
        <article class="command-lane command-lane-${lane.tone}">
            <div class="command-lane-label">${escapeHtml(lane.label)}</div>
            <div class="command-lane-value">${escapeHtml(lane.value)}</div>
            <div class="command-lane-meta">${escapeHtml(lane.meta)}</div>
        </article>
    `).join('');
}

function renderCommandSuggestions() {
    const container = $('#command-suggestions');
    if (!container || container.dataset.ready === 'true') return;
    const suggestions = [
        { label: 'Refresh live state', command: 'refresh portfolio state' },
        { label: 'Run health check', command: 'run health check' },
        { label: 'Capture status snapshot', command: 'capture status snapshot' },
        { label: 'Create follow-up task', command: 'create task: tighten source ui command panel polish' },
    ];
    container.innerHTML = suggestions.map(item => `
        <button class="command-chip" type="button" data-command-template="${escapeHtml(item.command)}">${escapeHtml(item.label)}</button>
    `).join('');
    container.dataset.ready = 'true';
}

function renderCommandHistory(commands) {
    const container = $('#command-history-list');
    if (!container) return;
    if (!commands.length) {
        container.innerHTML = `<div class="dashboard-empty">No commands executed yet. Use the panel above to create the first action trail.</div>`;
        return;
    }
    container.innerHTML = commands.slice(0, 8).map(event => `
        <article class="command-history-item ${event.ok ? 'success' : 'error'}">
            <div class="command-history-top">
                <div class="command-history-command">${escapeHtml(event.command || event.action || 'command')}</div>
                <span class="status-pill status-${event.ok ? 'healthy' : 'error'}">${event.ok ? 'ok' : 'error'}</span>
            </div>
            <div class="command-history-summary">${escapeHtml(event.summary || 'No summary')}</div>
            <div class="command-history-meta">
                <span>${escapeHtml(event.action || 'unknown')}</span>
                <span>${escapeHtml(formatRelativeTime(event.timestamp))}</span>
            </div>
            ${event.output ? `<pre class="command-history-output">${escapeHtml(String(event.output).slice(0, 240))}</pre>` : ''}
        </article>
    `).join('');
}

function renderCommandReceipts(receipts) {
    const container = $('#command-receipts-list');
    if (!container) return;
    if (!receipts.length) {
        container.innerHTML = `<div class="dashboard-empty">No command receipts yet. Receipts appear here before and after execution.</div>`;
        return;
    }
    container.innerHTML = receipts.slice(0, 8).map(receipt => {
        const tone = receipt.requires_confirmation ? 'warning' : statusTone(receipt.status || (receipt.ok ? 'healthy' : 'neutral'));
        const actionLabel = receipt.command || receipt.action || 'command';
        const metaBits = [
            receipt.duration_ms ? `${receipt.duration_ms}ms` : null,
            receipt.finished_at ? formatRelativeTime(receipt.finished_at) : formatRelativeTime(receipt.updated_at),
        ].filter(Boolean);
        const approvalButton = receipt.requires_confirmation ? `
            <button class="receipt-approve-btn" type="button" data-receipt-approve="${escapeHtml(receipt.id)}">
                Approve & execute
            </button>
        ` : '';
        return `
            <article class="receipt-item receipt-${tone}">
                <div class="receipt-top">
                    <div class="receipt-title">${escapeHtml(actionLabel)}</div>
                    <span class="status-pill status-${tone}">${escapeHtml(receipt.status || 'queued')}</span>
                </div>
                <div class="receipt-summary">${escapeHtml(receipt.summary || '')}</div>
                <div class="command-history-meta">
                    ${metaBits.map(bit => `<span>${escapeHtml(bit)}</span>`).join('')}
                </div>
                ${receipt.output ? `<pre class="command-history-output">${escapeHtml(String(receipt.output).slice(0, 180))}</pre>` : ''}
                ${approvalButton}
            </article>
        `;
    }).join('');
}

function renderProjectCards(projects) {
    const container = $('#projects-list');
    if (!container) return;
    if (!projects.length) {
        container.innerHTML = `<div class="dashboard-empty">No projects discovered yet. Seed \`workspace/source-ui/config/projects.json\`.</div>`;
        return;
    }
    container.innerHTML = projects.map(project => `
        <article class="dashboard-card project-card">
            <div class="dashboard-card-top">
                <div>
                    <div class="dashboard-card-title">${escapeHtml(project.name || project.id)}</div>
                    <div class="dashboard-card-subtitle">${escapeHtml(project.summary || '')}</div>
                </div>
                <span class="status-pill status-${statusTone(project.status)}">${escapeHtml(project.status || 'unknown')}</span>
            </div>
            <div class="dashboard-card-meta">
                <span class="meta-pill">${escapeHtml(project.kind || 'project')}</span>
                <span class="meta-pill">${escapeHtml(relativePath(project.path || ''))}</span>
                <span class="meta-pill">${project.signals || 0} signals</span>
            </div>
            <div class="dashboard-card-foot">${project.last_activity ? `Active ${formatRelativeTime(project.last_activity)}` : 'No recent signal files'}</div>
        </article>
    `).join('');
}

function renderSourceMission(mission) {
    $('#source-mission-status').textContent = mission.status || 'unknown';
    $('#source-mission-statement').textContent = mission.statement || 'No mission statement configured.';
    $('#source-mission-tagline').textContent = mission.tagline || '';
    $('#source-mission-north-star').textContent = mission.north_star || '';
    $('#source-mission-summary').textContent = mission.summary || '';

    const pillarContainer = $('#source-mission-pillars');
    if (pillarContainer) {
        const pillars = mission.pillars || [];
        pillarContainer.innerHTML = pillars.length ? pillars.map((pillar) => `
            <article class="mission-pillar">
                <div class="mission-pillar-label">${escapeHtml(pillar.label || pillar.id || 'pillar')}</div>
                <div class="mission-pillar-summary">${escapeHtml(pillar.summary || '')}</div>
            </article>
        `).join('') : `<div class="dashboard-empty">No mission pillars configured.</div>`;
    }

    const commitmentContainer = $('#source-mission-commitments');
    if (commitmentContainer) {
        const commitments = mission.operating_commitments || [];
        commitmentContainer.innerHTML = commitments.length ? commitments.map((item) => `
            <div class="mission-commitment">${escapeHtml(item)}</div>
        `).join('') : `<div class="dashboard-empty">No operating commitments configured.</div>`;
    }

    const signalContainer = $('#source-mission-signals');
    if (signalContainer) {
        const signals = mission.signals || [];
        signalContainer.innerHTML = signals.length ? signals.map((signal) => `
            <article class="mission-signal">
                <div class="mission-signal-label">${escapeHtml(signal.label || 'signal')}</div>
                <div class="mission-signal-value">${escapeHtml(signal.value || '--')}</div>
                <div class="mission-signal-detail">${escapeHtml(signal.detail || '')}</div>
            </article>
        `).join('') : `<div class="dashboard-empty">No mission signals available.</div>`;
    }

    const taskContainer = $('#source-mission-tasks');
    if (taskContainer) {
        const tasks = (mission.tasks || []).slice(0, 4);
        taskContainer.innerHTML = tasks.length ? tasks.map((task) => `
            <article class="mission-task-card">
                <div class="mission-task-top">
                    <div>
                        <div class="mission-task-sequence">Task ${escapeHtml(String(task.sequence || ''))}</div>
                        <div class="mission-task-title">${escapeHtml(task.title || task.id || 'task')}</div>
                    </div>
                    <div class="mission-task-meta">
                        <span class="meta-pill">${escapeHtml(task.pillar_label || task.pillar || 'mission')}</span>
                        <span class="meta-pill">${escapeHtml(task.priority || 'medium')}</span>
                    </div>
                </div>
                <div class="mission-task-summary">${escapeHtml(task.summary || '')}</div>
                <div class="mission-task-definition">${escapeHtml(task.definition_of_done || '')}</div>
            </article>
        `).join('') : `<div class="dashboard-empty">No mission tasks configured.</div>`;
    }
}

function renderWorkItems(workItems, tasks = []) {
    const container = $('#work-items-list');
    if (!container) return;
    const runtimeTasks = (tasks || [])
        .filter(task => task.read_only && task.status !== 'done')
        .slice(0, 6)
        .map(task => ({
            title: task.title,
            detail: task.description || `${task.assignee || 'runtime'} ${task.runtime_source_label || ''}`.trim(),
            status: task.status,
            source: task.node_label || task.node_id || 'runtime',
            badges: [
                task.node_label ? `${task.node_label}` : '',
                task.runtime_source_label || '',
                task.channel ? `via ${task.channel}` : '',
            ].filter(Boolean),
        }));
    const liveRows = runtimeTasks.length ? runtimeTasks : workItems.slice(0, 6).map(item => ({
        title: item.title || item.id,
        detail: item.detail || '',
        status: item.status || 'idle',
        source: relativePath(item.source || 'runtime'),
        badges: [],
    }));
    if (!liveRows.length) {
        container.innerHTML = `<div class="dashboard-empty">No active runtime work detected.</div>`;
        return;
    }
    container.innerHTML = liveRows.map(item => `
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(item.title || 'runtime')}</div>
                <div class="compact-row-subtitle">${escapeHtml(item.detail || '')}</div>
                ${item.badges?.length ? `<div class="compact-row-metrics">${item.badges.map(badge => `<span class="meta-pill">${escapeHtml(badge)}</span>`).join('')}</div>` : ''}
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="status-pill status-${statusTone(item.status)}">${escapeHtml(item.status || 'idle')}</span>
                <span class="meta-pill">${escapeHtml(item.source || 'runtime')}</span>
            </div>
        </article>
    `).join('');
}

function renderExternalSignals(signals) {
    const container = $('#external-signals-list');
    if (!container) return;
    if (!signals.length) {
        container.innerHTML = `<div class="dashboard-empty">No external signals configured.</div>`;
        return;
    }
    container.innerHTML = signals.slice(0, 4).map(signal => {
        const aggregate = signal.aggregate || {};
        const sourceRows = Array.isArray(signal.sources) ? signal.sources : [];
        const modelLabel = signal.model_resolved || signal.model_requested || 'unknown';
        return `
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(signal.name || signal.id)}</div>
                <div class="compact-row-subtitle">${escapeHtml(signal.summary || '')}</div>
                <div class="compact-row-metrics">
                    <span class="meta-pill">${escapeHtml(modelLabel)}</span>
                    <span class="meta-pill">${escapeHtml(aggregate.regime || 'unknown')}</span>
                    <span class="meta-pill">sent ${formatSignedScore(aggregate.sentiment)}</span>
                    <span class="meta-pill">conf ${formatPercent(aggregate.confidence)}</span>
                </div>
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="status-pill status-${statusTone(signal.status)}">${escapeHtml(signal.status || 'unknown')}</span>
                <span class="meta-pill">${sourceRows.length} src</span>
            </div>
        </article>
    `;
    }).join('');
}

function renderFinanceBrain(financeBrain) {
    const container = $('#finance-brain-list');
    if (!container) return;
    const rows = financeBrain.symbols || [];
    if (!rows.length) {
        container.innerHTML = `<div class="dashboard-empty">${escapeHtml(financeBrain.summary || 'No finance brain snapshot yet.')}</div>`;
        return;
    }
    container.innerHTML = rows.map(row => `
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(row.symbol || 'symbol')}</div>
                <div class="compact-row-subtitle">${escapeHtml(row.action || 'hold')} bias ${formatNumber(row.bias, 2)} | confidence ${formatNumber(row.confidence, 2)} | risk ${escapeHtml(row.risk_state || 'normal')}</div>
                <div class="compact-row-metrics">
                    <span class="meta-pill">${escapeHtml(row.model_resolved || 'local heuristic')}</span>
                    <span class="meta-pill">${row.llm_used ? `llm ${escapeHtml(String(row.llm_latency_ms || '0'))}ms` : escapeHtml(row.llm_reason || 'heuristic')}</span>
                </div>
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="status-pill status-${statusTone(row.action === 'buy' ? 'active' : (row.action === 'flat' ? 'warning' : 'idle'))}">${escapeHtml(row.action || 'hold')}</span>
            </div>
        </article>
    `).join('');
}

function renderSimOps(simOps, sims) {
    const activeContainer = $('#sim-ops-active');
    const summaryNode = $('#sim-ops-summary');
    if (!activeContainer || !summaryNode) return;

    const summary = simOps.summary || {};
    summaryNode.innerHTML = `
        <span class="meta-pill">${summary.active_count || 0} active</span>
        <span class="meta-pill">${summary.attention_count || 0} flagged</span>
        <span class="meta-pill">${summary.open_positions || 0} open</span>
    `;

    const activeRows = simOps.active || [];
    activeContainer.innerHTML = activeRows.length ? activeRows.map(sim => `
        <article class="ops-strip ops-strip-${statusTone(sim.tone)}">
            <div class="ops-strip-top">
                <div>
                    <div class="ops-strip-title">${escapeHtml(sim.display_name || sim.id)}</div>
                    <div class="ops-strip-subtitle">${escapeHtml(sim.bucket || 'sim')} | P/L ${formatSignedPercent(sim.net_return_pct)} | fees $${Number(sim.fees_usd || 0).toFixed(2)}</div>
                </div>
                <span class="status-pill status-${statusTone(sim.tone)}">$${Number(sim.final_equity || 0).toFixed(2)}</span>
            </div>
            <div class="ops-strip-meta">
                <span class="meta-pill">${Number(sim.win_rate || 0).toFixed(1)}% win</span>
                <span class="meta-pill">${sim.round_trips || 0} RT</span>
                <span class="meta-pill">${sim.open_positions || 0} open</span>
                ${(sim.flags || []).map(flag => `<span class="meta-pill meta-warning">${escapeHtml(flag)}</span>`).join('')}
            </div>
            <div class="ops-strip-foot">${escapeHtml(sim.status_note || '')}</div>
        </article>
    `).join('') : `<div class="dashboard-empty">No active-book sims are reporting yet.</div>`;
}

function renderOperatorTimeline(events) {
    const container = $('#operator-timeline-list');
    if (!container) return;
    if (!events.length) {
        container.innerHTML = `<div class="dashboard-empty">No recent operator events yet.</div>`;
        return;
    }
    container.innerHTML = events.map(event => `
        <article class="timeline-item timeline-${statusTone(event.tone || event.kind)}">
            <div class="timeline-dot"></div>
            <div class="timeline-body">
                <div class="timeline-top">
                    <div class="timeline-title">${escapeHtml(event.title || event.kind || 'event')}</div>
                    <span class="timeline-time">${escapeHtml(formatRelativeTime(event.timestamp))}</span>
                </div>
                <div class="timeline-detail">${escapeHtml(event.detail || '')}</div>
                <div class="timeline-meta">${escapeHtml(event.kind || 'event')}</div>
            </div>
        </article>
    `).join('');
}

function renderMemoryOps(memoryOps) {
    const sourcesNode = $('#memory-sources-list');
    const inferencesNode = $('#memory-inference-list');
    const researchNode = $('#memory-research-list');
    const summaryNode = $('#memory-ops-summary');
    if (!inferencesNode && !researchNode && !summaryNode && !sourcesNode) return;

    const totals = memoryOps.totals || {};
    if (summaryNode) {
        summaryNode.innerHTML = `
            <span class="meta-pill">${totals.rows || 0} rows</span>
            <span class="meta-pill">${totals.inferences || 0} inferences</span>
            <span class="meta-pill">${totals.discord_research || 0} research</span>
            <span class="meta-pill">${totals.telegram_main || 0} telegram</span>
        `;
    }

    const sources = memoryOps.sources || [];
    if (sourcesNode) {
        sourcesNode.innerHTML = sources.length ? sources.map(source => `
        <article class="compact-row">
            <div>
                <div class="compact-row-title">${escapeHtml(source.label || source.id)}</div>
                <div class="compact-row-subtitle">${escapeHtml(source.latest_excerpt || relativePath(source.path || ''))}</div>
            </div>
            <div class="compact-row-metrics">
                <span class="meta-pill">${source.count || 0} rows</span>
                <span class="meta-pill">${escapeHtml(formatRelativeTime(source.updated_at))}</span>
            </div>
        </article>
    `).join('') : `<div class="dashboard-empty">No memory sources ingested yet.</div>`;
    }

    const inferences = memoryOps.active_inferences || [];
    if (inferencesNode) {
        inferencesNode.innerHTML = inferences.length ? inferences.map(item => `
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(item.profile_section || 'inference')}</div>
                <div class="compact-row-subtitle">${escapeHtml(item.statement || '')}</div>
            </div>
            <div class="compact-row-metrics">
                <span class="meta-pill">${formatPercent(item.confidence)}</span>
                <span class="meta-pill">${escapeHtml(item.review_state || 'active')}</span>
            </div>
        </article>
    `).join('') : `<div class="dashboard-empty">No active inferences distilled yet.</div>`;
    }

    const topics = memoryOps.research_topics || [];
    const promptLines = memoryOps.preference_profile?.top_prompt_lines || [];
    if (researchNode) {
        researchNode.innerHTML = (topics.length || promptLines.length) ? `
        ${topics.length ? `<div class="stack-label">Recent Research Threads</div>${topics.map(topic => `<div class="topic-pill">${escapeHtml(topic)}</div>`).join('')}` : ''}
        ${promptLines.length ? `<div class="stack-label">Prompt Packet</div>${promptLines.map(line => `<div class="memory-line">${escapeHtml(line)}</div>`).join('')}` : ''}
    ` : `<div class="dashboard-empty">No research topics or preference packet lines available yet.</div>`;
    }
}

function renderModelOps(modelOps) {
    const summaryNode = $('#model-ops-summary');
    const countsNode = $('#model-counts-list');
    const agentsNode = $('#model-agents-list');
    if (!summaryNode || !countsNode || !agentsNode) return;

    const summary = modelOps.summary || {};
    const assistant = modelOps.assistant || {};
    summaryNode.innerHTML = `
        <span class="meta-pill">${summary.agent_count || 0} routed agents</span>
        <span class="meta-pill">${summary.distinct_models || 0} models</span>
        <span class="meta-pill">${escapeHtml(summary.default_model || 'no default')}</span>
        <span class="meta-pill">${assistant.reachable ? 'assistant api live' : 'assistant api offline'}</span>
    `;

    const counts = modelOps.model_counts || [];
    countsNode.innerHTML = counts.length ? counts.map(item => `
        <article class="compact-row">
            <div>
                <div class="compact-row-title">${escapeHtml(item.model || 'model')}</div>
                <div class="compact-row-subtitle">${item.count || 0} agent lane${Number(item.count || 0) === 1 ? '' : 's'}</div>
            </div>
            <span class="meta-pill">${item.count || 0}</span>
        </article>
    `).join('') : `<div class="dashboard-empty">No model inventory available.</div>`;

    const agents = modelOps.agents || [];
    agentsNode.innerHTML = agents.length ? agents.map(agent => `
        <article class="compact-row">
            <div>
                <div class="compact-row-title">${escapeHtml(agent.id || 'agent')}</div>
                <div class="compact-row-subtitle">${escapeHtml(agent.model || 'unknown')}</div>
            </div>
            <div class="compact-row-metrics">
                ${agent.is_default ? '<span class="meta-pill">default</span>' : ''}
                <span class="meta-pill">${agent.bindings || 0} bindings</span>
            </div>
        </article>
    `).join('') : `<div class="dashboard-empty">No routed agents available.</div>`;
}

function renderDiscordBridge(bridge) {
    const container = $('#discord-bridge-list');
    if (!container) return;
    const channels = bridge.channels || [];
    if (!channels.length) {
        container.innerHTML = `<div class="dashboard-empty">No Discord bridge channels configured.</div>`;
        return;
    }
    container.innerHTML = channels.map(channel => `
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(channel.label || channel.id)}</div>
                <div class="compact-row-subtitle">${escapeHtml(channel.description || '')}</div>
                <div class="compact-row-metrics">
                    <span class="meta-pill">${escapeHtml(channel.delivery || 'webhook')}</span>
                    <span class="meta-pill">${channel.has_webhook ? 'webhook present' : 'preview only'}</span>
                </div>
            </div>
            <span class="status-pill status-${statusTone(channel.enabled ? (channel.has_webhook ? 'active' : 'warning') : 'idle')}">${channel.enabled ? (channel.has_webhook ? 'ready' : 'preview') : 'disabled'}</span>
        </article>
    `).join('');
}

function renderTeamchat(teamchat) {
    const container = $('#teamchat-list');
    if (!container) return;
    const sessions = teamchat.sessions || [];
    if (!sessions.length) {
        container.innerHTML = `<div class="dashboard-empty">No teamchat sessions recorded yet.</div>`;
        return;
    }
    container.innerHTML = sessions.map(session => `
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(session.id || 'teamchat')}</div>
                <div class="compact-row-subtitle">${escapeHtml(session.task || '')}</div>
                <div class="compact-row-metrics">
                    <span class="meta-pill">cycle ${session.cycle || 0}</span>
                    <span class="meta-pill">${session.live ? 'live' : 'offline'}</span>
                </div>
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="status-pill status-${statusTone(session.status)}">${escapeHtml(session.status || 'unknown')}</span>
                <span class="meta-pill">${session.updated_at ? formatRelativeTime(session.updated_at) : 'no ts'}</span>
            </div>
        </article>
    `).join('');
}

function statusTone(status) {
    const raw = String(status || '').toLowerCase();
    if (raw === 'healthy' || raw === 'active' || raw === 'running') return 'healthy';
    if (raw === 'warning' || raw === 'busy' || raw === 'queued' || raw === 'dry_run' || raw === 'configured') return 'warning';
    if (raw === 'critical' || raw === 'error' || raw === 'failed') return 'error';
    return 'neutral';
}

function escapeHtml(value) {
    return String(value || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function formatSignedPercent(value) {
    const num = Number(value || 0);
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
}

function formatSignedScore(value) {
    if (value === null || value === undefined || value === '') return 'n/a';
    const num = Number(value);
    if (Number.isNaN(num)) return 'n/a';
    return `${num >= 0 ? '+' : ''}${num.toFixed(3)}`;
}

function formatPercent(value) {
    if (value === null || value === undefined || value === '') return 'n/a';
    const num = Number(value);
    if (Number.isNaN(num)) return 'n/a';
    return `${(num * 100).toFixed(1)}%`;
}

function formatNumber(value, decimals = 2) {
    const num = Number(value);
    if (Number.isNaN(num)) return 'n/a';
    return num.toFixed(decimals);
}

function renderInlineObject(value) {
    if (!value || typeof value !== 'object') return 'n/a';
    const parts = Object.entries(value)
        .slice(0, 6)
        .map(([key, entry]) => `${escapeHtml(key)}=${escapeHtml(formatNumber(entry, 2))}`);
    return parts.length ? parts.join(' ') : 'n/a';
}

function formatRelativeTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'recently';
    const diffMs = Date.now() - date.getTime();
    const diffMinutes = Math.round(diffMs / 60000);
    if (diffMinutes < 1) return 'just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.round(diffMinutes / 60);
    if (diffHours < 48) return `${diffHours}h ago`;
    const diffDays = Math.round(diffHours / 24);
    return `${diffDays}d ago`;
}

function relativePath(value) {
    return String(value || '').replace(`${window.location.origin}/`, '').replace('/home/jeebs/src/clawd/', '');
}

// Tasks
function renderTasks() {
    const filter = store.get('taskFilter');
    let tasks = store.get('tasks') || [];

    // Exclude runtime session tasks from the kanban by default
    tasks = tasks.filter(t => !String(t.id || '').startsWith('runtime:'));
    
    if (filter !== 'all') {
        tasks = tasks.filter(t => t.status === filter);
    }
    
    // Group by status
    const columns = {
        backlog: tasks.filter(t => t.status === 'backlog'),
        in_progress: tasks.filter(t => t.status === 'in_progress'),
        review: tasks.filter(t => t.status === 'review'),
        done: tasks.filter(t => t.status === 'done')
    };
    
    // Update counts
    $('#count-backlog').textContent = columns.backlog.length;
    $('#count-in_progress').textContent = columns.in_progress.length;
    $('#count-review').textContent = columns.review.length;
    $('#count-done').textContent = columns.done.length;
    
    // Render tasks in columns
    Object.entries(columns).forEach(([status, taskList]) => {
        const container = $(`#tasks-${status}`);
        if (container) {
            container.innerHTML = taskList.map(t => Components.taskCard(t)).join('');
        }
    });
}

// Agents
function renderAgents() {
    const agents = store.get('agents');
    $('#agents-grid-full').innerHTML = agents.map(a => Components.agentCardFull(a)).join('');
}

function renderAgentsGrid() {
    const agents = store.get('agents');
    $('#agentsGridFull').innerHTML = agents.map(a => Components.agentCardFull(a)).join('');
}

// Schedule
function renderSchedule() {
    const jobs = store.get('scheduledJobs');
    
    // Week grid
    const weekStart = store.get('currentWeekStart') || getWeekStart(new Date());
    store.set('currentWeekStart', weekStart);
    
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const headerHtml = days.map(d => `<div class="schedule-day-header">${d}</div>`).join('');
    
    document.querySelector('.schedule-grid').innerHTML = headerHtml + Components.weekGrid(weekStart);
    
    // Jobs list
    $('#jobs-list').innerHTML = jobs.map(j => Components.jobItem(j)).join('');
    
    // Title
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    $('#schedule-title').textContent = `${formatDateShort(weekStart)} - ${formatDateShort(weekEnd)}`;
}

function getWeekStart(date) {
    const d = new Date(date);
    const day = d.getDay();
    d.setDate(d.getDate() - day);
    d.setHours(0, 0, 0, 0);
    return d;
}

function navigateWeek(delta) {
    let weekStart = store.get('currentWeekStart') || getWeekStart(new Date());
    weekStart.setDate(weekStart.getDate() + (delta * 7));
    store.set('currentWeekStart', weekStart);
    renderSchedule();
}

function formatDateShort(date) {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Health
function renderHealth() {
    const metrics = store.get('healthMetrics');
    const components = store.get('components');
    
    // Metrics
    updateMetricCard('cpu', metrics.cpu, 80);
    updateMetricCard('memory', metrics.memory, 80);
    updateMetricCard('disk', metrics.disk, 90);
    updateMetricCard('gpu', metrics.gpu, 90);
    
    // Components
    $('#components-grid').innerHTML = components.map(c => Components.componentCard(c)).join('');
}

function updateMetricCard(type, value, threshold) {
    const key = type === 'memory' ? 'mem' : type;
    const status = value > threshold ? 'error' : value > threshold * 0.8 ? 'warning' : 'healthy';
    const metricNode = $(`#metric-${key}`);
    const barNode = $(`#${key}-bar`);
    const statusNode = $(`#${key}-status`);
    if (metricNode) {
        metricNode.textContent = `${Number(value || 0).toFixed(0)}%`;
    }
    if (barNode) {
        barNode.style.width = `${Math.min(Number(value || 0), 100)}%`;
    }
    if (statusNode) {
        statusNode.textContent = status;
        statusNode.className = `metric-status ${status}`;
    }
}

// Logs
function renderLogs() {
    const logs = store.get('logs');
    const filter = store.get('logFilter');
    
    let filteredLogs = logs;
    if (filter !== 'all') {
        filteredLogs = logs.filter(l => l.level === filter);
    }
    
    $('#logs-list').innerHTML = filteredLogs.map(l => Components.logEntry(l)).join('');
    
    if (filteredLogs.length === 0) {
        // Generate demo logs
        const demoLogs = [
            { level: 'info', message: 'Gateway started successfully', timestamp: new Date().toISOString() },
            { level: 'info', message: 'Connected to VLLM at localhost:8001', timestamp: new Date(Date.now() - 60000).toISOString() },
            { level: 'warn', message: 'Memory usage high: 78%', timestamp: new Date(Date.now() - 120000).toISOString() },
            { level: 'info', message: 'Telegram bot authenticated', timestamp: new Date(Date.now() - 180000).toISOString() },
            { level: 'error', message: 'Failed to connect to external API', timestamp: new Date(Date.now() - 240000).toISOString() }
        ];
        
        store.set('logs', demoLogs);
        $('#logs-list').innerHTML = demoLogs.map(l => Components.logEntry(l)).join('');
    }
}

function refreshLogs() {
    renderLogs();
    Toast.info('Logs refreshed');
}

$('#refresh-logs')?.addEventListener('click', refreshLogs);

// Notifications
function initNotifications() {
    const btn = $('#notifications-btn');
    const panel = $('#notifications-panel');
    
    btn?.addEventListener('click', (e) => {
        e.stopPropagation();
        panel.classList.toggle('open');
    });
    
    document.addEventListener('click', (e) => {
        if (!panel.contains(e.target)) {
            panel.classList.remove('open');
        }
    });
    
    $('#clear-notifications')?.addEventListener('click', () => {
        store.clearNotifications();
        renderNotifications();
        Toast.info('Notifications cleared');
    });
}

function renderNotifications() {
    const notifications = store.get('notifications');
    const unreadCount = store.get('unreadCount');
    
    $('#notifications-list').innerHTML = notifications.map(n => Components.notificationItem(n)).join('');
    
    // Update dot
    const dot = $('#notification-dot');
    if (dot) {
        dot.classList.toggle('visible', unreadCount > 0);
    }
    
    // Click to mark read
    $('#notifications-list')?.querySelectorAll('.notification-item').forEach(item => {
        item.addEventListener('click', () => {
            const id = parseInt(item.dataset.id);
            store.markNotificationRead(id);
            renderNotifications();
        });
    });
}

// Settings
function initSettings() {
    const settings = store.get('settings');
    
    // Theme
    $('#setting-theme').value = settings.theme;
    $('#setting-theme').addEventListener('change', (e) => {
        store.updateSetting('theme', e.target.value);
        document.documentElement.setAttribute('data-theme', e.target.value);
    });
    
    // Auto refresh
    $('#setting-autorefresh').checked = settings.autoRefresh;
    $('#setting-autorefresh').addEventListener('change', (e) => {
        store.updateSetting('autoRefresh', e.target.checked);
        if (e.target.checked) {
            startDataRefresh();
        } else {
            stopDataRefresh();
        }
    });
    
    // Refresh interval
    $('#setting-refresh-interval').value = settings.refreshInterval;
    $('#setting-refresh-interval').addEventListener('change', (e) => {
        store.updateSetting('refreshInterval', parseInt(e.target.value));
        if (store.get('settings.autoRefresh')) {
            startDataRefresh();
        }
    });
    
    // Desktop notifications
    $('#setting-desktop-notif').checked = settings.desktopNotifications;
    $('#setting-desktop-notif').addEventListener('change', (e) => {
        store.updateSetting('desktopNotifications', e.target.checked);
        if (e.target.checked) {
            Utils.notify('Desktop notifications enabled', { body: 'You will receive alerts here' });
        }
    });
    
    // Sound
    $('#setting-sound').checked = settings.soundAlerts;
    $('#setting-sound').addEventListener('change', (e) => {
        store.updateSetting('soundAlerts', e.target.checked);
    });
    
    // Fallback
    $('#setting-fallback').checked = settings.enableFallback;
    $('#setting-fallback').addEventListener('change', (e) => {
        store.updateSetting('enableFallback', e.target.checked);
    });
    
    // Max queue
    $('#setting-max-queue').value = settings.maxQueueDepth;
    $('#setting-max-queue').addEventListener('change', (e) => {
        store.updateSetting('maxQueueDepth', parseInt(e.target.value));
    });
}

function renderSettings() {
    // Settings are rendered by initSettings
}

// Drag and Drop
function initDragAndDrop() {
    // Task drag and drop
    document.addEventListener('dragstart', (e) => {
        if (e.target.classList.contains('task-card')) {
            if (e.target.dataset.readOnly === 'true') {
                e.preventDefault();
                return;
            }
            e.target.classList.add('dragging');
            e.dataTransfer.setData('text/plain', e.target.dataset.id);
        }
    });
    
    document.addEventListener('dragend', (e) => {
        if (e.target.classList.contains('task-card')) {
            e.target.classList.remove('dragging');
        }
    });
    
    document.addEventListener('dragover', (e) => {
        e.preventDefault();
        const column = e.target.closest('.kanban-column');
        if (column) {
            column.classList.add('drag-over');
        }
    });
    
    document.addEventListener('dragleave', (e) => {
        const column = e.target.closest('.kanban-column');
        if (column) {
            column.classList.remove('drag-over');
        }
    });
    
    document.addEventListener('drop', async (e) => {
        e.preventDefault();
        const column = e.target.closest('.kanban-column');
        if (column) {
            column.classList.remove('drag-over');
            const taskId = e.dataTransfer.getData('text/plain');
            const newStatus = column.dataset.status;
            const task = (store.get('tasks') || []).find(item => String(item.id) === String(taskId));
            if (!task || task.read_only) {
                Toast.info('Live runtime tasks are read-only here');
                return;
            }
            const previousTasks = [...store.get('tasks')];
            store.moveTask(taskId, newStatus);
            renderTasks();
            try {
                const updated = await api.updateTask(taskId, { status: newStatus });
                const nextTasks = store.get('tasks').map(task => String(task.id) === String(taskId) ? updated : task);
                store.set('tasks', nextTasks);
                renderTasks();
                renderDashboard();
            } catch (error) {
                console.error('Task move failed', error);
                store.set('tasks', previousTasks);
                renderTasks();
                Toast.error('Failed to move task');
            }
        }
    });
}

// Modals
function initModals() {
    Modal.init();
    
    // Close on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            Modal.close();
        }
    });
}

function openNewTaskModal() {
    const projects = store.get('portfolio.projects') || [];
    const projectOptions = ['<option value="">Unscoped</option>']
        .concat(projects.map(project => `<option value="${escapeHtml(project.id || '')}">${escapeHtml(project.name || project.id || 'project')}</option>`))
        .join('');
    const content = `
        <div class="form-group">
            <label class="form-label">Task Title</label>
            <input type="text" class="form-input" id="new-task-title" placeholder="Enter task title">
        </div>
        <div class="form-group">
            <label class="form-label">Description</label>
            <textarea class="form-textarea" id="new-task-desc" placeholder="Describe the task..."></textarea>
        </div>
        <div class="form-group">
            <label class="form-label">Priority</label>
            <select class="form-select" id="new-task-priority">
                <option value="low">Low</option>
                <option value="medium" selected>Medium</option>
                <option value="high">High</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Assign to</label>
            <select class="form-select" id="new-task-assignee">
                <option value="">Unassigned</option>
                <option value="planner">Planner</option>
                <option value="coder">Coder</option>
                <option value="health">Health Monitor</option>
                <option value="memory">Memory Agent</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Project</label>
            <select class="form-select" id="new-task-project">${projectOptions}</select>
        </div>
    `;
    
    const footer = `
        <button class="btn btn-secondary" onclick="Modal.close()">Cancel</button>
        <button class="btn btn-primary" onclick="createTask()">Create Task</button>
    `;
    
    Modal.open('Create New Task', content, footer);
}

async function createTask() {
    const title = $('#new-task-title')?.value;
    const desc = $('#new-task-desc')?.value;
    const priority = $('#new-task-priority')?.value;
    const assignee = $('#new-task-assignee')?.value;
    const project = $('#new-task-project')?.value;
    
    if (!title) {
        Toast.error('Please enter a task title');
        return;
    }

    try {
        const task = await api.createTask({
            title,
            description: desc,
            priority,
            assignee,
            project,
            status: 'backlog',
            origin: 'dashboard'
        });
        store.set('tasks', [...store.get('tasks'), task]);
        Modal.close();
        renderTasks();
        renderDashboard();
        Toast.success('Task created successfully');
    } catch (error) {
        console.error('Task creation failed', error);
        Toast.error('Failed to create task');
    }
}

function nextTaskStatus(status) {
    if (status === 'backlog') return 'in_progress';
    if (status === 'in_progress') return 'review';
    if (status === 'review') return 'done';
    return 'backlog';
}

async function taskQuickAction(taskId, action) {
    const tasks = store.get('tasks') || [];
    const task = tasks.find(item => String(item.id) === String(taskId));
    if (!task) return;
    if (task.read_only) {
        Toast.info('Live runtime tasks are read-only here');
        return;
    }

    let updates = {};
    if (action === 'advance') {
        updates = { status: nextTaskStatus(task.status) };
    } else if (action === 'done') {
        updates = { status: 'done' };
    } else if (action === 'priority') {
        const nextPriority = task.priority === 'low' ? 'medium' : (task.priority === 'medium' ? 'high' : 'low');
        updates = { priority: nextPriority };
    } else {
        return;
    }

    try {
        const updated = await api.updateTask(taskId, updates);
        const nextTasks = tasks.map(item => String(item.id) === String(taskId) ? updated : item);
        store.set('tasks', nextTasks);
        renderTasks();
        renderDashboard();
        Toast.success(`Task updated: ${task.title}`);
    } catch (error) {
        console.error('Task quick action failed', error);
        Toast.error('Task update failed');
    }
}

function initCommandDeck() {
    const form = $('#command-deck-form');
    const input = $('#command-deck-input');
    const quickActions = document.querySelectorAll('.quick-command-card[data-command-action]');
    const suggestionContainer = $('#command-suggestions');

    form?.addEventListener('submit', submitCommandDeck);
    input?.addEventListener('keydown', (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
            event.preventDefault();
            form?.requestSubmit();
        }
    });
    quickActions.forEach(button => {
        button.addEventListener('click', () => executeQuickCommand(button.dataset.commandAction || ''));
    });
    suggestionContainer?.addEventListener('click', (event) => {
        const button = event.target.closest('[data-command-template]');
        if (!button || !input) return;
        input.value = button.dataset.commandTemplate || '';
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
    });
    document.addEventListener('click', (event) => {
        const button = event.target.closest('[data-receipt-approve]');
        if (!button) return;
        approveCommandReceipt(button.dataset.receiptApprove || '');
    });
}

async function submitCommandDeck(event) {
    event?.preventDefault();
    if (commandSubmissionInFlight) return;

    const input = $('#command-deck-input');
    const rawCommand = input?.value?.trim() || '';
    if (!rawCommand) {
        renderCommandStatus('Enter a command first.', 'error');
        Toast.error('Enter a command first');
        return;
    }

    commandSubmissionInFlight = true;
    setCommandDeckBusy(true);
    renderCommandStatus(`Executing: ${rawCommand}`, 'working');

    try {
        const result = await api.runCommand({ command: rawCommand });
        await handleCommandResult(result, rawCommand);
        if (result.ok && input) {
            input.value = '';
        }
        await refreshAll({ quiet: true });
    } catch (error) {
        console.error('Command execution failed', error);
        renderCommandStatus(`Command failed: ${error.message}`, 'error');
        Toast.error('Command failed');
    } finally {
        commandSubmissionInFlight = false;
        setCommandDeckBusy(false);
    }
}

async function executeQuickCommand(action) {
    if (!action || commandSubmissionInFlight) return;
    commandSubmissionInFlight = true;
    setCommandDeckBusy(true);
    renderCommandStatus(`Executing ${action.replaceAll('_', ' ')}`, 'working');
    try {
        const result = await api.runCommand({ action });
        await handleCommandResult(result, action.replaceAll('_', ' '));
        await refreshAll({ quiet: true });
    } catch (error) {
        console.error('Quick command failed', error);
        renderCommandStatus(`Command failed: ${error.message}`, 'error');
        Toast.error('Command failed');
    } finally {
        commandSubmissionInFlight = false;
        setCommandDeckBusy(false);
    }
}

async function handleCommandResult(result, commandLabel) {
    if (result.receipt) {
        const nextReceipts = [result.receipt, ...(store.get('commandReceipts') || []).filter(item => item.id !== result.receipt.id)].slice(0, 20);
        store.set('commandReceipts', nextReceipts);
        renderCommandReceipts(nextReceipts);
    }

    if (result.requires_confirmation) {
        renderCommandStatus(result.summary || 'Approval required.', 'error');
        Toast.info('Approval required before execution');
        return;
    }

    if (result.queued) {
        renderCommandStatus(result.summary || 'Command queued.', 'working');
        Toast.info(result.summary || 'Command queued');
        return;
    }

    const nextHistory = [{
        id: `command-${Date.now()}`,
        command: commandLabel,
        action: result.action || 'unknown',
        ok: Boolean(result.ok),
        summary: result.summary || '',
        output: result.output || '',
        timestamp: new Date().toISOString(),
    }, ...(store.get('commands') || [])].slice(0, 20);
    store.set('commands', nextHistory);
    renderCommandHistory(nextHistory);
    renderCommandStatus(result.summary || 'Command completed.', result.ok ? 'success' : 'error');
    if (result.ok) {
        Toast.success(result.summary || 'Command completed');
    } else {
        Toast.error(result.summary || 'Command failed');
    }
}

async function approveCommandReceipt(receiptId) {
    if (!receiptId || commandSubmissionInFlight) return;
    const receipt = (store.get('commandReceipts') || []).find(item => item.id === receiptId);
    if (!receipt) return;

    Modal.confirm(
        'Approve Command',
        `Execute ${receipt.command || receipt.action || 'this command'} now?`,
        async () => {
            commandSubmissionInFlight = true;
            setCommandDeckBusy(true);
            renderCommandStatus(`Approving ${receipt.command || receipt.action}`, 'working');
            try {
                const result = await api.runCommand({
                    receipt_id: receipt.id,
                    action: receipt.action,
                    command: receipt.command,
                    title: receipt.title,
                    description: receipt.description,
                    confirmed: true,
                });
                await handleCommandResult(result, receipt.command || receipt.action || 'command');
                await refreshAll({ quiet: true });
            } catch (error) {
                console.error('Receipt approval failed', error);
                renderCommandStatus(`Approval failed: ${error.message}`, 'error');
                Toast.error('Approval failed');
            } finally {
                commandSubmissionInFlight = false;
                setCommandDeckBusy(false);
            }
        }
    );
}

function setCommandDeckBusy(isBusy) {
    const input = $('#command-deck-input');
    const submit = document.querySelector('.command-submit');
    const quickActions = document.querySelectorAll('.quick-command-card[data-command-action]');
    if (input) input.disabled = isBusy;
    if (submit) {
        submit.disabled = isBusy;
        submit.textContent = isBusy ? 'Executing…' : 'Execute';
    }
    quickActions.forEach(button => {
        button.disabled = isBusy;
    });
}

function renderCommandStatus(message, tone = 'neutral') {
    const line = $('#command-status-line');
    if (!line) return;
    line.textContent = message;
    line.dataset.tone = tone;
}

// Command Palette
function initCommandPalette() {
    CommandPalette.init();
}

// Keyboard shortcuts
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Don't trigger shortcuts when typing in inputs
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        
        // Navigation shortcuts
        if (e.key === 'g' && !e.metaKey && !e.ctrlKey) {
            // Will be handled by Command Palette
        }
    });
}

// Data refresh
function startDataRefresh() {
    stopDataRefresh();
    
    const interval = store.get('settings.refreshInterval') || 10000;
    
    refreshInterval = setInterval(() => {
        if (store.get('settings.autoRefresh')) {
            refreshAll();
        }
    }, interval);
}

function stopDataRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

async function refreshAll(options = {}) {
    if (refreshInFlight) {
        refreshQueued = true;
        return;
    }

    refreshInFlight = true;
    try {
        const [portfolioResult, tasksResult, commandsResult, receiptsResult, agentsResult] = await Promise.allSettled([
            api.getPortfolio(),
            api.getTasks(),
            api.getCommandHistory(),
            api.getCommandReceipts(),
            api.getAgents()
        ]);
        if (portfolioResult.status !== 'fulfilled') {
            throw portfolioResult.reason;
        }
        const portfolio = portfolioResult.value;
        const tasks = tasksResult.status === 'fulfilled' ? tasksResult.value : (portfolio.tasks || []);
        store.set('portfolio', portfolio);
        store.set('tasks', Array.isArray(tasks) ? tasks : (portfolio.tasks || []));
        if (agentsResult.status === 'fulfilled' && Array.isArray(agentsResult.value)) {
            store.set('agents', agentsResult.value);
        }
        if (portfolio.health_metrics) {
            store.set('healthMetrics', portfolio.health_metrics);
        }
        if (portfolio.components) {
            store.set('components', portfolio.components);
        }
        if (commandsResult.status === 'fulfilled') {
            store.set('commands', Array.isArray(commandsResult.value) ? commandsResult.value : []);
        } else if (Array.isArray(portfolio.command_history)) {
            store.set('commands', portfolio.command_history);
        }
        if (receiptsResult.status === 'fulfilled') {
            store.set('commandReceipts', Array.isArray(receiptsResult.value) ? receiptsResult.value : []);
        }
        store.set('notifications', buildLiveNotifications(portfolio, tasks, store.get('commands') || []));
        store.set('connected', true);
        store.set('gatewayStatus', 'connected');
    } catch (error) {
        console.error('Portfolio refresh failed', error);
        store.set('connected', false);
        store.set('gatewayStatus', 'error');
        if (!options.quiet) {
            renderCommandStatus('Live refresh degraded. Showing last known local state.', 'error');
        }
    } finally {
        refreshInFlight = false;
        if (refreshQueued) {
            refreshQueued = false;
            window.setTimeout(() => refreshAll(options), 50);
        }
    }
    
    if (currentView === 'health') {
        renderHealth();
    }
    if (currentView === 'dashboard') {
        renderDashboard();
    }
    if (currentView === 'tasks') {
        renderTasks();
    }
    updateStatusIndicators();
}

// Actions
async function restartGateway() {
    Modal.confirm(
        'Restart Gateway',
        'Are you sure you want to restart the gateway? This will briefly interrupt all connections.',
        async () => {
            Toast.info('Restarting gateway...');
            try {
                await api.restartGateway();
                await refreshAll({ quiet: true });
                Toast.success('Gateway restarted successfully');
            } catch (e) {
                Toast.error('Failed to restart gateway');
            }
        }
    );
}

async function runHealthCheck() {
    Toast.info('Running health check...');
    try {
        const result = await api.runHealthCheck();
        if (result && result.metrics) {
            store.set('healthMetrics', result.metrics);
        }
        await refreshAll({ quiet: true });
        Toast.success('Health check complete');
        renderHealth();
    } catch (e) {
        Toast.error('Health check failed');
    }
}

async function controlAgent(agentId, action) {
    Toast.info(`${action} agent...`);
    try {
        const result = await api.controlAgent(agentId, action);
        const nextAgents = (store.get('agents') || []).map(agent => (
            agent.id === agentId
                ? {
                    ...agent,
                    control_state: result.control_state || 'active',
                    control_last_action: result.action,
                }
                : agent
        ));
        store.set('agents', nextAgents);
        renderAgents();
        renderDashboard();
        Toast.success(`Agent ${action} recorded`);
    } catch (error) {
        console.error('Agent control failed', error);
        Toast.error('Agent control failed');
    }
}

window.taskQuickAction = taskQuickAction;

// Update status indicators
function updateStatusIndicators() {
    const gateway = $('#gateway-status');
    const text = $('#gateway-status-text');
    
    if (gateway && text) {
        const components = store.get('components') || [];
        const gatewayComponent = components.find(c => c.id === 'gateway');
        const isHealthy = gatewayComponent ? gatewayComponent.status === 'healthy' : store.get('connected');
        gateway.classList.toggle('connected', Boolean(isHealthy));
        gateway.classList.toggle('error', !isHealthy);
        text.textContent = gatewayComponent ? gatewayComponent.details : (isHealthy ? 'Connected' : 'Disconnected');
    }
}

function buildLiveNotifications(portfolio, tasks, commands) {
    const items = [];
    const components = Array.isArray(portfolio.components) ? portfolio.components : [];
    const workItems = Array.isArray(portfolio.work_items) ? portfolio.work_items : [];
    const financeRows = Array.isArray(portfolio.finance_brain?.symbols) ? portfolio.finance_brain.symbols : [];
    const externalSignals = Array.isArray(portfolio.external_signals) ? portfolio.external_signals : [];
    const openTasks = (tasks || []).filter(task => task.status !== 'done');

    components
        .filter(component => String(component.status || '').toLowerCase() !== 'healthy')
        .slice(0, 2)
        .forEach(component => {
            items.push({
                id: `component-${component.id}`,
                type: 'warning',
                body: `${component.name || component.id} requires attention`,
                timestamp: new Date().toISOString(),
            });
        });

    workItems.slice(0, 2).forEach(item => {
        items.push({
            id: `work-${item.id || item.title}`,
            type: 'info',
            body: `${item.title || item.id}: ${item.detail || item.status || 'active'}`,
            timestamp: new Date().toISOString(),
        });
    });

    financeRows.slice(0, 2).forEach(row => {
        items.push({
            id: `finance-${row.symbol}`,
            type: row.action === 'buy' ? 'success' : 'info',
            body: `${row.symbol}: ${row.action || 'hold'} bias ${formatNumber(row.bias, 2)} conf ${formatNumber(row.confidence, 2)}`,
            timestamp: new Date().toISOString(),
        });
    });

    externalSignals
        .filter(signal => ['warning', 'error', 'optional_offline'].includes(String(signal.status || '').toLowerCase()))
        .slice(0, 2)
        .forEach(signal => {
            items.push({
                id: `signal-${signal.id}`,
                type: 'warning',
                body: `${signal.name || signal.id}: ${signal.status}`,
                timestamp: new Date().toISOString(),
            });
        });

    if (openTasks.length) {
        items.push({
            id: 'tasks-open',
            type: 'info',
            body: `${openTasks.length} open tasks across the current book`,
            timestamp: new Date().toISOString(),
        });
    }

    if (commands.length) {
        const latest = commands[0];
        items.push({
            id: `command-${latest.id || latest.timestamp}`,
            type: latest.ok ? 'success' : 'error',
            body: latest.summary || latest.command || 'Recent command',
            timestamp: latest.timestamp || new Date().toISOString(),
        });
    }

    return items.slice(0, 8);
}

// Global functions for onclick handlers
window.navigateTo = navigateTo;
window.toggleTheme = toggleTheme;
window.restartGateway = restartGateway;
window.runHealthCheck = runHealthCheck;
window.refreshAll = refreshAll;
window.controlAgent = controlAgent;
window.openNewTaskModal = openNewTaskModal;
window.createTask = createTask;
window.Modal = Modal;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// Mood Widget


// Mood initialization - calls the living mood widget
async function initMoodWidget() {
    // This is now handled by the mood.js module
    // Just wait for DOM to be ready and let mood.js handle it
    if (typeof renderLivingMood === 'function') {
        try {
            const response = await fetch('/api/state/valence/planner.json');
            if (response.ok) {
                const state = await response.json();
                const v = state.valence || 0;
                const hour = new Date().getHours();
                const a = (hour >= 9 && hour <= 17) ? 0.7 : (hour >= 22 || hour <= 6) ? 0.2 : 0.5;
                renderLivingMood(v, a);
            }
        } catch (e) {
            renderLivingMood(0, 0.5);
        }
        
        setInterval(async () => {
            try {
                const response = await fetch('/api/state/valence/planner.json');
                if (response.ok) {
                    const state = await response.json();
                    renderLivingMood(state.valence || 0, 0.5);
                }
            } catch (e) {}
        }, 15000);
    }
}

// ─── Symbiote ──────────────────────────────────────────────────────────────

let _symbioteData = null;

async function renderSymbiote(force = false) {
    if (!_symbioteData || force) {
        try {
            const res = await fetch('/api/symbiote');
            _symbioteData = await res.json();
        } catch (e) {
            _symbioteData = null;
        }
    }
    const d = _symbioteData;
    if (!d) {
        const grid = document.querySelector('#symbiote-grid');
        if (grid) grid.innerHTML = '<p style="color:var(--text-tertiary);padding:2rem">Unable to load symbiote data.</p>';
        return;
    }

    const titleEl = document.querySelector('#symbiote-title');
    const subEl   = document.querySelector('#symbiote-subtitle');
    const cntEl   = document.querySelector('#symbiote-section-count');
    const datEl   = document.querySelector('#symbiote-filed');
    if (titleEl) titleEl.textContent = d.title;
    if (subEl)   subEl.textContent   = d.subtitle;
    if (cntEl)   cntEl.textContent   = d.section_count + ' sections';
    if (datEl)   datEl.textContent   = 'filed ' + d.filed;

    const dimColour = {
        think:      'var(--accent-primary)',
        feel:       '#f43f5e',
        remember:   '#f59e0b',
        coordinate: '#06b6d4',
        evolve:     'var(--success)'
    };

    const dimEl = document.querySelector('#symbiote-dimensions');
    if (dimEl) {
        dimEl.innerHTML = d.dimensions.map(dim => `
            <div class="sym-dim-card" style="--dim-clr:${dimColour[dim.id]}">
                <div class="sym-dim-emoji">${dim.emoji}</div>
                <div class="sym-dim-label">${dim.label}</div>
                <div class="sym-dim-count">${dim.count} enhancements</div>
                <div class="sym-dim-desc">${dim.desc}</div>
            </div>
        `).join('');
    }

    const phaseLabel = ['', 'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4'];
    const statusLabel = {
        designed: { text: 'Designed', cls: 'sym-status-designed' },
        'in-dev': { text: 'In Dev',   cls: 'sym-status-indev'    },
        live:     { text: 'Live',     cls: 'sym-status-live'      }
    };
    // Merge writable state overlay onto base enhancement data
    const stateMap = d.enhancement_state || {};
    const enhancements = d.enhancements.map(e => {
        const ov = stateMap[String(e.id)] || {};
        return { ...e, ...ov };
    });

    const gridEl = document.querySelector('#symbiote-grid');
    if (gridEl) {
        gridEl.innerHTML = enhancements.map(e => {
            const clr = dimColour[e.dimension] || 'var(--accent-primary)';
            const st  = statusLabel[e.status] || statusLabel.designed;
            const invBadge = e.inv ? `<span class="sym-inv-badge">${e.inv}</span>` : '';
            return `
                <div class="sym-card phase-border-${e.phase}" style="--card-clr:${clr}">
                    <div class="sym-card-top">
                        <span class="sym-card-num">${String(e.id).padStart(2,'0')}</span>
                        <span class="sym-card-code">${e.code}</span>
                        <span class="sym-dim-badge" style="background:${clr}22;color:${clr}">${e.dimension}</span>
                        <span class="${st.cls} sym-status-badge">${st.text}</span>
                    </div>
                    <div class="sym-card-name">${e.name}</div>
                    <div class="sym-card-pitch">${e.pitch}</div>
                    <div class="sym-card-footer">
                        <span class="sym-phase-tag phase-tag-${e.phase}">${phaseLabel[e.phase]}</span>
                        <span class="sym-owner">&#x2192; ${e.owner}</span>
                        ${invBadge}
                    </div>
                    <div class="sym-metric">
                        <span class="sym-metric-label">metric</span>
                        <span class="sym-metric-value">${e.metric_value != null ? e.metric_value : e.key_metric}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    const phaseStatusIcon = { next: '&#x25BA;', planned: '&#x25CB;', live: '&#x2713;', done: '&#x2713;' };
    const roadmapEl = document.querySelector('#roadmap-phases');
    if (roadmapEl) {
        roadmapEl.innerHTML = d.roadmap.map(p => `
            <div class="roadmap-phase roadmap-${p.status}">
                <div class="roadmap-phase-header">
                    <span class="roadmap-icon">${phaseStatusIcon[p.status] || '&#x25CB;'}</span>
                    <span class="roadmap-phase-name">Phase ${p.phase}: ${p.name}</span>
                    <span class="roadmap-weeks">Wk ${p.weeks}</span>
                </div>
                <div class="roadmap-tags">
                    ${p.enhancements.map(code => `<span class="roadmap-code-tag">${code}</span>`).join('')}
                </div>
            </div>
        `).join('');
    }

    const qEl = document.querySelector('#questions-list');
    if (qEl) {
        qEl.innerHTML = d.open_questions.map(q => `
            <div class="sym-question">
                <div class="sym-question-meta">
                    <span class="sym-question-for">FOR: ${q.for_being}</span>
                    <span class="sym-question-enh">${q.enhancement}</span>
                </div>
                <div class="sym-question-text">${q.question}</div>
            </div>
        `).join('');
    }

    const expStatusIcon = { closed: '&#x2713;', partial: '&#x25D1;', live: '&#x25BA;', designed: '&#x25CB;', pending: '&middot;' };
    const expEl = document.querySelector('#symbiote-experiments');
    if (expEl) {
        expEl.innerHTML = `<div class="sym-exp-table">` + d.experiments.map(ex => `
            <div class="sym-exp-row sym-exp-${ex.status}">
                <span class="sym-exp-icon">${expStatusIcon[ex.status] || '&middot;'}</span>
                <span class="sym-exp-id">${ex.id}</span>
                <span class="sym-exp-label sym-exp-lbl-${ex.status}">${ex.label}</span>
                <span class="sym-exp-name">${ex.name}</span>
                <span class="sym-exp-result">${ex.result}</span>
                ${ex.open ? '<span class="sym-exp-open">open</span>' : '<span class="sym-exp-closed">closed</span>'}
            </div>
        `).join('') + '</div>';
    }
}

window.renderSymbiote = renderSymbiote;


// ─── Source Intelligence Panels ────────────────────────────────────────────

async function renderSourceIntelligence() {
    renderSourcePhi();
    renderCoordFeed();
    renderRelationalState();
}

async function renderSourcePhi() {
    try {
        const r = await fetch('/api/source/phi');
        const d = await r.json();
        const val = document.getElementById('ci-phi-value');
        const bar = document.getElementById('ci-phi-bar');
        const meta = document.getElementById('ci-phi-meta');
        if (!val) return;
        if (!d.ok || d.phi === null) {
            val.textContent = 'offline';
            if (meta) meta.textContent = d.error || 'AIN unreachable';
            return;
        }
        const phi = parseFloat(d.phi || 0);
        val.textContent = phi.toFixed(3);
        // Phi is 0..1+; normalise display bar at 0..1
        const pct = Math.min(100, phi * 100);
        if (bar) { bar.style.width = pct + '%'; bar.style.background = phi > 0.5 ? 'var(--accent)' : phi > 0.2 ? '#f59e0b' : '#ef4444'; }
        if (meta) meta.textContent = `${d.proxy_method} · n=${d.n_samples} · ${(d.timestamp_utc||'').slice(11,19)} UTC`;
    } catch(e) {
        const v = document.getElementById('ci-phi-value');
        if (v) v.textContent = 'err';
    }
}

async function renderCoordFeed() {
    const el = document.getElementById('coord-feed');
    if (!el) return;
    try {
        const r = await fetch('/api/source/coordination-feed');
        const d = await r.json();
        if (!d.ok || !d.messages || !d.messages.length) {
            el.innerHTML = '<div class="coord-empty">No messages yet</div>';
            return;
        }
        const roleIcon = { user: '👤', assistant: '🤖' };
        el.innerHTML = d.messages.slice(-12).map(m => {
            const isAgent = m.role === 'assistant';
            const name = m.author || (isAgent ? 'agent' : 'user');
            const ts = (m.ts || '').slice(11, 16);
            const text = escapeHtml((m.content || '').slice(0, 350));
            return `<div class="coord-msg ${isAgent ? 'coord-msg-agent' : 'coord-msg-user'}">
                <span class="coord-msg-author">${escapeHtml(name)}</span>
                <span class="coord-msg-ts">${ts}</span>
                <div class="coord-msg-text">${text}</div>
            </div>`;
        }).join('');
        el.scrollTop = el.scrollHeight;
    } catch(e) {
        if (el) el.innerHTML = '<div class="coord-empty">Feed unavailable</div>';
    }
}

async function renderRelationalState() {
    const rows = document.getElementById('ci-rel-rows');
    const silence = document.getElementById('ci-rel-silence');
    if (!rows) return;
    try {
        const r = await fetch('/api/source/relational');
        const d = await r.json();
        // Pause check summary
        const pc = (d.pause_check || []).slice(-1)[0] || {};
        const fillsSpace = pc.fills_space != null ? pc.fills_space.toFixed(2) : '—';
        const valueAdd  = pc.value_add  != null ? pc.value_add.toFixed(2)  : '—';
        const di = d.diversity_index != null ? d.diversity_index.toFixed(3) : '—';
        const diAlert = d.di_alert ? ' ⚠ DI<0.0' : '';
        rows.innerHTML = `
            <div class="ci-rel-row"><span>fills_space</span><span>${fillsSpace}</span></div>
            <div class="ci-rel-row"><span>value_add</span><span>${valueAdd}</span></div>
            <div class="ci-rel-row"><span>author_sil (DI)</span><span>${di}${diAlert}</span></div>
            <div class="ci-rel-row"><span>trust</span><span>${d.trust_note || 'stable'}</span></div>
        `;
        // Silence per being
        if (silence && d.silence_per_being && d.silence_per_being.length) {
            silence.innerHTML = d.silence_per_being.map(b =>
                `<span class="ci-silence-pill ${b.sections_behind > 10 ? 'ci-silence-warn' : ''}">${escapeHtml(b.being)} ${b.sections_behind > 0 ? b.sections_behind+'▴' : '✓'}</span>`
            ).join('');
        }
    } catch(e) {
        if (rows) rows.innerHTML = '<span style="color:var(--text-tertiary)">unavailable</span>';
    }
}

// Wire refresh button
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('coord-feed-refresh');
    if (btn) btn.addEventListener('click', () => { renderCoordFeed(); renderSourcePhi(); renderRelationalState(); });
});

window.renderSourceIntelligence = renderSourceIntelligence;
// ─── end Source Intelligence ────────────────────────────────────────────────
// ─── end Symbiote ───────────────────────────────────────────────────────────
