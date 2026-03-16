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
let displayModeToggleInFlight = false;

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
    initCoordFeedCollapse();
    
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
    $('#display-mode-toggle')?.addEventListener('click', toggleDisplayMode);
    
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
    document.addEventListener('click', (event) => {
        const button = event.target.closest('[data-inference-review]');
        if (!button) return;
        reviewInference(
            button.dataset.inferenceReview || '',
            button.dataset.reviewState || '',
            button.dataset.contradictionState || ''
        );
    });
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
    const tradingStrategy = portfolio.trading_strategy || {};
    const simStrategyReview = portfolio.sim_strategy_review || {};
    const sims = (portfolio.sims || []).filter(sim => sim.active_book);
    const discordBridge = portfolio.discord_bridge || {};
    const teamchat = portfolio.teamchat || {};
    const deliberations = portfolio.deliberations || {};
    const weeklyEvolution = portfolio.weekly_evolution || {};
    const sourceMission = portfolio.source_mission || {};
    const commands = store.get('commands') || [];
    const operatorTimeline = portfolio.operator_timeline || [];
    const simOps = portfolio.sim_ops || {};
    const memoryOps = portfolio.memory_ops || {};
    const modelOps = portfolio.model_ops || {};
    const displayMode = store.get('displayMode') || {};
    const runtimeSources = portfolio.runtime_sources || [];
    const failedUnits = portfolio.failed_units || [];
    
    renderCommandDeck({ portfolio, tasks, components, commands });
    renderClarityDeck({
        tasks,
        components,
        workItems,
        externalSignals,
        runtimeSources,
        failedUnits,
        projects: portfolio.projects || [],
        simStrategyReview,
        teamchat,
    });
    renderDisplayModeControl(displayMode);
    renderSourceMission(sourceMission);
    renderWorkItems(workItems, tasks);
    renderExternalSignals(externalSignals);
    renderFinanceBrain(financeBrain);
    renderTradingStrategy(tradingStrategy, simStrategyReview);
    renderDiscordBridge(discordBridge);
    renderTeamchat(teamchat);
    renderDeliberations(deliberations);
    renderWeeklyEvolution(weeklyEvolution);
    renderOperatorTimeline(operatorTimeline);
    renderSimOps(simOps, sims);
    renderMemoryOps(memoryOps);
    renderModelOps(modelOps);
    renderSourceIntelligence();

    const pendingTasks = visibleTasks(tasks).filter(t => t.status !== 'done').length;
    const taskBadge = $('#task-badge');
    if (taskBadge) taskBadge.textContent = pendingTasks;
}

function renderCommandDeck({ portfolio, tasks, components, commands }) {
    renderCommandLanes(portfolio, tasks, components);
    renderCommandSuggestions();
    renderCommandHistory(commands);
    renderCommandReceipts(store.get('commandReceipts') || []);
}

function buildDashboardAudit({
    tasks = [],
    components = [],
    workItems = [],
    externalSignals = [],
    runtimeSources = [],
    failedUnits = [],
    projects = [],
    simStrategyReview = {},
    teamchat = {},
}) {
    const attentionRows = [];
    const dormantRows = [];
    const liveRows = [];
    const localTasks = visibleTasks(tasks || []).filter(task => !task.read_only);
    const dedupeKeys = new Set();

    function pushRow(bucket, row) {
        const key = `${row.label}::${row.detail}::${row.status}`;
        if (dedupeKeys.has(`${bucket}:${key}`)) return;
        dedupeKeys.add(`${bucket}:${key}`);
        bucket.push(row);
    }

    (components || []).forEach(component => {
        const tone = statusTone(component.status);
        const row = {
            label: component.name || component.id || 'component',
            detail: component.details || '',
            status: component.status || 'unknown',
            source: 'systemd',
            tone,
        };
        if (tone === 'healthy') {
            pushRow(liveRows, row);
        } else {
            pushRow(attentionRows, row);
        }
    });

    (runtimeSources || []).forEach(source => {
        const status = String(source.status || 'unknown');
        const tone = statusTone(status);
        const row = {
            label: source.label || source.id || 'runtime source',
            detail: source.details || '',
            status,
            source: 'remote runtime',
            tone,
        };
        if (tone === 'healthy') {
            pushRow(liveRows, row);
        } else {
            pushRow(attentionRows, row);
        }
    });

    (failedUnits || []).forEach(unit => {
        const row = {
            label: unit.label || unit.unit || 'failed unit',
            detail: unit.details || '',
            status: unit.status || 'error',
            source: unit.kind || 'systemd',
            tone: unit.status === 'error' ? 'error' : 'warning',
        };
        if (unit.optional) {
            pushRow(dormantRows, row);
        } else {
            pushRow(attentionRows, row);
        }
    });

    (workItems || []).forEach(item => {
        const status = String(item.status || 'unknown');
        const row = {
            label: item.title || item.id || 'work',
            detail: item.detail || '',
            status,
            source: 'runtime',
            tone: statusTone(status),
        };
        if (['running', 'active', 'in_progress'].includes(status)) {
            pushRow(liveRows, row);
        } else if (['waiting', 'monitoring', 'skipped', 'idle'].includes(status)) {
            pushRow(dormantRows, row);
        } else {
            pushRow(attentionRows, row);
        }
    });

    (externalSignals || []).forEach(signal => {
        const status = String(signal.status || 'unknown');
        if (['ok', 'healthy', 'active'].includes(status)) return;
        pushRow(attentionRows, {
            label: signal.name || signal.id || 'signal',
            detail: signal.summary || signal.path || '',
            status,
            source: 'signal',
            tone: statusTone(status),
        });
    });

    const reviewRows = Array.isArray(simStrategyReview.recommendations) ? simStrategyReview.recommendations : [];
    reviewRows.forEach(row => {
        const recommendation = String(row.recommendation || '').toLowerCase();
        if (!['retune', 'retire'].includes(recommendation)) return;
        pushRow(attentionRows, {
            label: row.display_name || row.id || 'sim review',
            detail: row.summary || '',
            status: recommendation,
            source: 'sim review',
            tone: recommendation === 'retire' ? 'error' : 'warning',
        });
    });

    localTasks.forEach(task => {
        const status = String(task.status || 'unknown');
        const row = {
            label: task.title || `Task ${task.id}`,
            detail: task.status_reason || task.description || '',
            status,
            source: task.project || 'taskboard',
            tone: statusTone(status),
        };
        if (status === 'in_progress') {
            pushRow(liveRows, row);
        } else if (['review', 'backlog'].includes(status)) {
            pushRow(attentionRows, row);
        } else if (['done', 'closed', 'archived', 'cancelled', 'stopped'].includes(status)) {
            pushRow(dormantRows, row);
        }
    });

    (projects || []).forEach(project => {
        const status = String(project.status || 'unknown');
        if (status === 'active') return;
        pushRow(dormantRows, {
            label: project.name || project.id || 'project',
            detail: project.summary || '',
            status,
            source: project.kind || 'project',
            tone: statusTone(status),
        });
    });

    const sessions = Array.isArray(teamchat.sessions) ? teamchat.sessions : [];
    sessions.forEach(session => {
        const status = String(session.status || 'unknown');
        const loweredStatus = status.toLowerCase();
        if (session.live) {
            pushRow(liveRows, {
                label: session.id || 'teamchat',
                detail: session.task || '',
                status,
                source: 'teamchat',
                tone: statusTone(status),
            });
            return;
        }
        const row = {
            label: session.id || 'teamchat',
            detail: session.task || '',
            status,
            source: 'teamchat',
            tone: loweredStatus.includes('repeated_failures') || loweredStatus === 'failed' ? 'error' : 'neutral',
        };
        if (loweredStatus.includes('repeated_failures') || loweredStatus === 'failed') {
            pushRow(attentionRows, row);
            return;
        }
        pushRow(dormantRows, row);
    });

    const openTaskCount = localTasks.filter(task => !['done', 'closed', 'archived', 'cancelled'].includes(String(task.status || ''))).length;
    const summary = attentionRows.length
        ? `${attentionRows.length} surfaces need eyes. ${liveRows.length} are moving cleanly and ${dormantRows.length} are parked out of the way.`
        : `${liveRows.length} live surfaces are moving cleanly. ${dormantRows.length} parked or completed items are separated below.`;
    const moodline = attentionRows.length
        ? 'Bright focus first, history second.'
        : 'Clear water. Active motion up top, quiet history below.';

    return {
        summary,
        moodline,
        metrics: [
            { label: 'Live motion', value: liveRows.length, tone: 'healthy' },
            { label: 'Need eyes', value: attentionRows.length, tone: attentionRows.length ? 'warning' : 'healthy' },
            { label: 'Parked', value: dormantRows.length, tone: dormantRows.length ? 'neutral' : 'healthy' },
            { label: 'Open tasks', value: openTaskCount, tone: openTaskCount ? 'warning' : 'neutral' },
        ],
        liveRows: liveRows.slice(0, 4),
        attentionRows: attentionRows.slice(0, 6),
        dormantRows: dormantRows.slice(0, 6),
    };
}

function renderAuditRows(container, rows, emptyText) {
    if (!container) return;
    if (!rows.length) {
        container.innerHTML = `<div class="dashboard-empty">${escapeHtml(emptyText)}</div>`;
        return;
    }
    container.innerHTML = rows.map(row => `
        <article class="compact-row compact-row-rich clarity-row clarity-row-${escapeHtml(row.tone || 'neutral')}">
            <div>
                <div class="compact-row-title">${escapeHtml(row.label || 'item')}</div>
                <div class="compact-row-subtitle">${escapeHtml(row.detail || '')}</div>
                <div class="compact-row-metrics">
                    <span class="meta-pill">${escapeHtml(row.source || 'source')}</span>
                </div>
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="status-pill status-${escapeHtml(row.tone || 'neutral')}">${escapeHtml(row.status || 'unknown')}</span>
            </div>
        </article>
    `).join('');
}

function renderClarityDeck(data) {
    const summaryNode = $('#clarity-summary');
    const metricsNode = $('#clarity-metrics');
    const liveNode = $('#clarity-live-list');
    const attentionNode = $('#attention-now-list');
    const dormantNode = $('#dormant-audit-list');
    if (!summaryNode || !metricsNode || !liveNode || !attentionNode || !dormantNode) return;

    const audit = buildDashboardAudit(data);
    summaryNode.innerHTML = `
        <div class="clarity-kicker">Clarity Lens</div>
        <div class="clarity-headline">${escapeHtml(audit.summary)}</div>
        <div class="clarity-copy">${escapeHtml(audit.moodline)}</div>
    `;
    metricsNode.innerHTML = audit.metrics.map(metric => `
        <article class="clarity-metric clarity-metric-${escapeHtml(metric.tone || 'neutral')}">
            <div class="clarity-metric-label">${escapeHtml(metric.label)}</div>
            <div class="clarity-metric-value">${escapeHtml(String(metric.value))}</div>
        </article>
    `).join('');
    renderAuditRows(liveNode, audit.liveRows, 'Nothing is actively moving right now.');
    renderAuditRows(attentionNode, audit.attentionRows, 'Nothing urgent is blocked or stale right now.');
    renderAuditRows(dormantNode, audit.dormantRows, 'No parked, skipped, or closed surfaces need explanation right now.');
}

function renderDisplayModeControl(displayMode) {
    const currentNode = $('#display-mode-current');
    const subtitleNode = $('#display-mode-subtitle');
    const metricsNode = $('#display-mode-metrics');
    const statusNode = $('#display-mode-status-pill');
    const button = $('#display-mode-toggle');
    if (!currentNode || !subtitleNode || !metricsNode || !statusNode || !button) return;

    const profile = String(displayMode.profile_current || 'unknown');
    const requestedMode = String(displayMode.requested_mode || 'auto');
    const effectiveMode = String(displayMode.effective_mode || requestedMode || 'unknown');
    const displayActive = Boolean(displayMode.display_mode_active);
    const queue = displayMode.queue || {};
    const toggleTarget = String(displayMode.toggle_target || (profile === 'fishtank' ? 'work' : 'fishtank'));
    const tone = profile === 'work' ? 'healthy' : (profile === 'fishtank' ? 'warning' : 'neutral');

    currentNode.textContent = profile === 'unknown' ? 'Display mode unavailable' : `${profile.toUpperCase()} profile`;
    subtitleNode.textContent = `Requested ${requestedMode} · effective ${effectiveMode} · display ${displayActive ? 'attached' : 'hidden'}`;
    metricsNode.innerHTML = `
        <span class="meta-pill">${queue.pending || 0} queued</span>
        <span class="meta-pill">${queue.review_required || 0} review</span>
        <span class="meta-pill">${queue.discord_pending || 0} discord</span>
        <span class="meta-pill">${queue.router_pending || 0} router</span>
    `;
    statusNode.className = `status-pill status-${tone}`;
    statusNode.textContent = profile === 'unknown' ? 'syncing' : profile;
    button.disabled = displayModeToggleInFlight || !displayMode.ok;
    button.innerHTML = `
        <span class="quick-command-label">${displayModeToggleInFlight ? 'Switching…' : `Switch to ${toggleTarget[0].toUpperCase()}${toggleTarget.slice(1)}`}</span>
        <span class="quick-command-meta">${displayModeToggleInFlight ? 'Applying cathedral mode change' : 'Flip the live work/fishtank profile'}</span>
    `;
}

function renderCommandLanes(portfolio, tasks, components) {
    const container = $('#command-lanes');
    if (!container) return;

    const financeRows = portfolio.finance_brain?.symbols || [];
    const discordChannels = portfolio.discord_bridge?.channels || [];
    const activeWork = portfolio.work_items || [];
    const assistant = (components || []).find(component => component.id === 'assistant');
    const boardTasks = visibleTasks(tasks);
    const queueDepth = boardTasks.filter(task => task.status !== 'done').length;
    const dominantModel = financeRows.find(row => row.analysis_model_resolved || row.analysis_model_requested || row.model_resolved);
    const dominantModelLabel = dominantModel?.analysis_model_resolved || dominantModel?.analysis_model_requested || dominantModel?.model_resolved || 'local-assistant';
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
            meta: `Primary model ${dominantModelLabel}`,
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
            meta: `${boardTasks.filter(task => task.status === 'in_progress').length} in progress`,
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
                ${renderBoundaryState(receipt.boundary)}
                ${approvalButton}
            </article>
        `;
    }).join('');
}

function renderBoundaryState(boundary) {
    const items = Array.isArray(boundary?.items)
        ? boundary.items.filter(item => item && item.label)
        : [];
    if (!items.length) return '';
    const detail = String(boundary?.detail || '').trim();
    const prefixMap = {
        provenance: 'from',
        shareability: 'share',
        approval: 'approval',
    };
    return `
        <div class="boundary-state">
            <div class="boundary-pill-list">
                ${items.map(item => {
                    const tone = statusTone(item.tone || 'neutral');
                    const prefix = prefixMap[item.key] || item.key || 'boundary';
                    const title = item.detail ? ` title="${escapeHtml(item.detail)}"` : '';
                    return `<span class="boundary-pill boundary-${tone}"${title}>${escapeHtml(prefix)}: ${escapeHtml(item.label || '')}</span>`;
                }).join('')}
            </div>
            ${detail ? `<div class="boundary-detail">${escapeHtml(detail)}</div>` : ''}
        </div>
    `;
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
    const summaryNode = $('#source-mission-summary');
    if (summaryNode) {
        const summaryBits = [mission.summary]
            .concat((mission.context_packet?.summary_lines || []).slice(0, 2))
            .filter(Boolean);
        summaryNode.textContent = summaryBits.join(' • ');
    }

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
                        ${task.status ? `<span class="status-pill status-${statusTone(task.status)}">${escapeHtml(task.status)}</span>` : ''}
                        <span class="meta-pill">${escapeHtml(task.pillar_label || task.pillar || 'mission')}</span>
                        <span class="meta-pill">${escapeHtml(task.priority || 'medium')}</span>
                        ${task.assignee ? `<span class="meta-pill">${escapeHtml(task.assignee)}</span>` : ''}
                    </div>
                </div>
                <div class="mission-task-summary">${escapeHtml(task.summary || '')}</div>
                ${task.status_reason ? `<div class="mission-task-status-note">${escapeHtml(task.status_reason)}</div>` : ''}
                <div class="mission-task-definition">${escapeHtml(task.definition_of_done || '')}</div>
            </article>
        `).join('') : `<div class="dashboard-empty">No mission tasks configured.</div>`;
    }
}

function renderWorkItems(workItems, tasks = []) {
    const container = $('#work-items-list');
    if (!container) return;
    const runtimeTasks = (tasks || [])
        .filter(task => task.read_only && String(task.status || '') === 'in_progress')
        .slice(0, 3)
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
    const curatedRows = (workItems || []).map(item => ({
        title: item.title || item.id,
        detail: item.detail || '',
        status: item.status || 'idle',
        source: relativePath(item.source || 'runtime'),
        badges: item.status && ['waiting', 'monitoring', 'skipped'].includes(String(item.status || '')) ? [String(item.status)] : [],
    }));
    const liveRows = [...curatedRows, ...runtimeTasks].filter((item, index, rows) => {
        const key = `${item.title}::${item.detail}`;
        return rows.findIndex(candidate => `${candidate.title}::${candidate.detail}` === key) === index;
    }).slice(0, 6);
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
                    <span class="meta-pill">${escapeHtml(row.analysis_model_resolved || row.analysis_model_requested || row.model_resolved || 'local heuristic')}</span>
                    ${row.sentiment_model_resolved ? `<span class="meta-pill">sent ${escapeHtml(row.sentiment_model_resolved)}</span>` : ''}
                    <span class="meta-pill">${row.llm_used ? `llm ${escapeHtml(String(row.llm_latency_ms || '0'))}ms` : escapeHtml(row.llm_reason || 'heuristic')}</span>
                </div>
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="status-pill status-${statusTone(row.action === 'buy' ? 'active' : (row.action === 'flat' ? 'warning' : 'idle'))}">${escapeHtml(row.action || 'hold')}</span>
            </div>
        </article>
    `).join('');
}

function renderTradingStrategy(report, simStrategyReview = {}) {
    const metaNode = $('#trading-strategy-meta');
    const listNode = $('#trading-strategy-list');
    if (!metaNode || !listNode) return;

    if (!report || report.status === 'offline') {
        metaNode.innerHTML = '';
        listNode.innerHTML = `<div class="dashboard-empty">${escapeHtml(report?.summary || 'No trading strategy brief wired into the system yet.')}</div>`;
        return;
    }

    const integration = report.integration || {};
    const configPaths = Array.isArray(report.config_paths) ? report.config_paths : [];
    const existingConfigs = configPaths.filter(item => item && item.exists);
    metaNode.innerHTML = `
        <span class="status-pill status-${statusTone(integration.status || report.status)}">${escapeHtml(integration.status || report.status || 'active')}</span>
        <span class="meta-pill">${(report.live_scope || []).length} live lanes</span>
        <span class="meta-pill">${existingConfigs.length}/${configPaths.length} configs</span>
        <span class="meta-pill">${escapeHtml(formatRelativeTime(report.updated_at) || 'now')}</span>
    `;

    const enabledSims = Array.isArray(integration.enabled_sims) ? integration.enabled_sims : [];
    const notes = Array.isArray(integration.notes) ? integration.notes : [];
    const liveScope = Array.isArray(report.live_scope) ? report.live_scope : [];
    const nextSteps = Array.isArray(report.next_steps) ? report.next_steps : [];
    const hardLimits = Array.isArray(report.hard_limits) ? report.hard_limits : [];
    const strategyStack = Array.isArray(report.strategy_stack) ? report.strategy_stack : [];
    const reviewSummary = simStrategyReview.summary || {};
    const reviewRows = Array.isArray(simStrategyReview.recommendations) ? simStrategyReview.recommendations : [];
    const freeSignal = simStrategyReview.free_realtime_signal || {};
    const weeklyX = simStrategyReview.weekly_x_review || {};

    const cards = [];
    cards.push(`
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(report.title || 'Trading brief')}</div>
                <div class="compact-row-subtitle">${escapeHtml(report.summary || '')}</div>
                <div class="compact-row-metrics">
                    ${strategyStack.slice(0, 4).map(item => `<span class="meta-pill">${escapeHtml(item)}</span>`).join('')}
                </div>
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="meta-pill">${escapeHtml(relativePath(report.path || 'strategy report'))}</span>
            </div>
        </article>
    `);

    if (enabledSims.length || notes.length) {
        cards.push(`
            <article class="compact-row compact-row-rich">
                <div>
                    <div class="compact-row-title">System Integration</div>
                    <div class="compact-row-subtitle">${escapeHtml(integration.summary || 'No integration summary available.')}</div>
                    <div class="compact-row-metrics">
                        ${enabledSims.slice(0, 4).map(row => `<span class="meta-pill ${row.status === 'blocked' ? 'meta-warning' : ''}">${escapeHtml(row.id || 'sim')} ${escapeHtml(row.status || 'unknown')}</span>`).join('')}
                    </div>
                    ${notes.length ? notes.slice(0, 3).map(note => `<div class="memory-line">${escapeHtml(note)}</div>`).join('') : ''}
                </div>
            </article>
        `);
    }

    if (liveScope.length || hardLimits.length) {
        cards.push(`
            <article class="compact-row compact-row-rich">
                <div>
                    <div class="compact-row-title">Recommended Live Scope</div>
                    <div class="compact-row-subtitle">${escapeHtml(liveScope.join(' • ') || 'No live scope parsed.')}</div>
                    <div class="compact-row-metrics">
                        ${hardLimits.slice(0, 4).map(item => `<span class="meta-pill">${escapeHtml(item)}</span>`).join('')}
                    </div>
                </div>
            </article>
        `);
    }

    if (nextSteps.length || configPaths.length) {
        cards.push(`
            <article class="compact-row compact-row-rich">
                <div>
                    <div class="compact-row-title">Next Build Steps</div>
                    ${nextSteps.slice(0, 4).map(step => `<div class="memory-line">${escapeHtml(step)}</div>`).join('')}
                    <div class="compact-row-metrics">
                        ${configPaths.map(item => `<span class="meta-pill ${item.exists ? '' : 'meta-warning'}">${escapeHtml(item.label || 'config')} ${item.exists ? 'ready' : 'missing'}</span>`).join('')}
                    </div>
                </div>
            </article>
        `);
    }

    if (reviewRows.length) {
        cards.push(`
            <article class="compact-row compact-row-rich">
                <div>
                    <div class="compact-row-title">Periodic Review</div>
                    <div class="compact-row-subtitle">${escapeHtml(simStrategyReview.focus || 'No periodic review focus set.')}</div>
                    <div class="compact-row-metrics">
                        <span class="meta-pill">${reviewSummary.keep_count || 0} keep</span>
                        <span class="meta-pill">${reviewSummary.retune_count || 0} retune</span>
                        <span class="meta-pill">${reviewSummary.retire_count || 0} retire</span>
                        <span class="meta-pill">${Number(simStrategyReview.review_interval_hours || 0)}h cadence</span>
                        <span class="meta-pill ${freeSignal.ready ? 'meta-growth' : 'meta-warning'}">free sentiment ${escapeHtml(freeSignal.ready ? 'ready' : 'limited')}</span>
                        <span class="meta-pill ${weeklyX.status === 'fresh' ? 'meta-growth' : 'meta-warning'}">weekly X ${escapeHtml(weeklyX.status || 'pending')}</span>
                    </div>
                    ${reviewRows.slice(0, 3).map(row => `<div class="memory-line">${escapeHtml(`${row.display_name || row.id}: ${row.recommendation} — ${row.summary}`)}</div>`).join('')}
                </div>
                <div class="compact-row-metrics compact-row-metrics-end">
                    <span class="meta-pill">${escapeHtml(formatRelativeTime(simStrategyReview.generated_at) || 'now')}</span>
                </div>
            </article>
        `);
    }

    listNode.innerHTML = cards.join('');
}

function renderSimOps(simOps, sims) {
    const activeContainer = $('#sim-ops-active');
    const summaryNode = $('#sim-ops-summary');
    if (!activeContainer || !summaryNode) return;

    const summary = simOps.summary || {};
    const livePnl = Number(summary.live_pnl || 0);
    const liveReturnPct = Number(summary.live_return_pct || 0);
    summaryNode.innerHTML = `
        <span class="meta-pill">${summary.active_count || 0} active</span>
        <span class="meta-pill">${summary.trade_count || 0} trades</span>
        <span class="meta-pill">live $${Number(summary.live_equity || 0).toFixed(2)}</span>
        <span class="meta-pill">live P/L ${formatSignedCurrency(livePnl)} (${formatSignedPercent(liveReturnPct)})</span>
        <span class="meta-pill">${summary.growing_count || 0} growing</span>
        <span class="meta-pill">${summary.attention_count || 0} flagged</span>
        <span class="meta-pill">${summary.open_positions || 0} open</span>
    `;

    const activeRows = simOps.active || [];
    activeContainer.innerHTML = activeRows.length ? activeRows.map(sim => `
        <article class="ops-strip ops-strip-${statusTone(sim.tone)}">
            <div class="ops-strip-top">
                <div>
                    <div class="ops-strip-title">${escapeHtml(sim.display_name || sim.id)}</div>
                    <div class="ops-strip-subtitle">${escapeHtml(sim.bucket || 'sim')}${sim.stage ? ` | ${escapeHtml(String(sim.stage).replaceAll('_', ' '))}` : ''}${sim.target_venue ? ` | ${escapeHtml(sim.target_venue)}` : ''} | ${Number(sim.open_positions || 0) > 0 && Math.abs(Number(sim.mark_equity || sim.final_equity || 0) - Number(sim.final_equity || 0)) >= 0.01 ? `book $${Number(sim.final_equity || 0).toFixed(2)} | mark $${Number(sim.mark_equity || sim.final_equity || 0).toFixed(2)}` : `capital $${Number(sim.live_equity || sim.final_equity || 0).toFixed(2)}`} | live P/L ${formatSignedCurrency(sim.live_equity_change ?? sim.net_equity_change)} (${formatSignedPercent(sim.live_return_pct ?? sim.net_return_pct)})</div>
                </div>
                <span class="status-pill status-${statusTone(sim.tone)}">${Number((sim.live_return_pct ?? sim.net_return_pct) || 0) > 0 ? 'growing' : escapeHtml(sim.tone || 'steady')}</span>
            </div>
            <div class="ops-strip-meta">
                <span class="meta-pill ${Number((sim.live_return_pct ?? sim.net_return_pct) || 0) > 0 ? 'meta-growth' : ''}">${Number((sim.live_return_pct ?? sim.net_return_pct) || 0) > 0 ? 'growth lane' : 'watch'}</span>
                ${sim.strategy_role ? `<span class="meta-pill">${escapeHtml(String(sim.strategy_role).replaceAll('_', ' '))}</span>` : ''}
                <span class="meta-pill">${Number(sim.win_rate || 0).toFixed(1)}% win</span>
                <span class="meta-pill">${sim.round_trips || 0} trades</span>
                <span class="meta-pill">${sim.open_positions || 0} open</span>
                <span class="meta-pill">fees $${Number(sim.fees_usd || 0).toFixed(2)}</span>
                ${Number(sim.open_positions || 0) > 0 && Math.abs(Number(sim.mark_equity || sim.final_equity || 0) - Number(sim.final_equity || 0)) >= 0.01 ? `<span class="meta-pill">booked ${formatSignedCurrency(sim.net_equity_change)}</span>` : ''}
                ${Number(sim.avg_hold_hours || 0) > 0 ? `<span class="meta-pill">${Number(sim.avg_hold_hours || 0).toFixed(1)}h hold</span>` : ''}
                ${(sim.flags || []).map(flag => `<span class="meta-pill meta-warning">${escapeHtml(flag)}</span>`).join('')}
            </div>
            <div class="ops-strip-foot">${escapeHtml(sim.status_note || '')}${sim.improvement_focus ? ` Focus: ${escapeHtml(sim.improvement_focus)}.` : ''}</div>
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
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(source.label || source.id)}</div>
                <div class="compact-row-subtitle">${escapeHtml(source.latest_excerpt || relativePath(source.path || ''))}</div>
                ${renderBoundaryState(source.boundary)}
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="meta-pill">${source.count || 0} rows</span>
                <span class="meta-pill">${source.user_count || 0} user</span>
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
                <div class="compact-row-subtitle">${escapeHtml((item.evidence_refs || []).join(' • ') || `${item.evidence_count || 0} evidence refs`)}</div>
                ${renderBoundaryState(item.boundary)}
                ${item.review_notes ? `<div class="memory-line">${escapeHtml(item.review_notes)}</div>` : ''}
                <div class="compact-row-metrics">
                    <span class="meta-pill">${formatPercent(item.confidence)}</span>
                    <span class="meta-pill">${escapeHtml(item.review_state || 'pending_review')}</span>
                    <span class="meta-pill">${escapeHtml(item.contradiction_state || 'no_known_contradiction')}</span>
                    <span class="meta-pill">${item.evidence_count || 0} evidence</span>
                </div>
                <div class="compact-row-metrics">
                    ${(item.operator_actions || []).includes('operator_approved') ? `<button class="command-chip" type="button" data-inference-review="${escapeHtml(item.id || '')}" data-review-state="operator_approved">Approve</button>` : ''}
                    ${(item.operator_actions || []).includes('needs_review') ? `<button class="command-chip" type="button" data-inference-review="${escapeHtml(item.id || '')}" data-review-state="needs_review">Needs Review</button>` : ''}
                    <button class="command-chip" type="button" data-inference-review="${escapeHtml(item.id || '')}" data-contradiction-state="contradicted" data-review-state="needs_review">Mark Contradicted</button>
                </div>
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                ${item.reviewed_by ? `<span class="meta-pill">${escapeHtml(item.reviewed_by)}</span>` : ''}
                ${item.reviewed_at ? `<span class="meta-pill">${escapeHtml(formatRelativeTime(item.reviewed_at))}</span>` : ''}
            </div>
        </article>
    `).join('') : `<div class="dashboard-empty">No active inferences distilled yet.</div>`;
    }

    const topics = memoryOps.research_topics || [];
    const researchItems = memoryOps.research_items || [];
    const researchBoundary = memoryOps.research_boundary || {};
    const promptLines = memoryOps.preference_profile?.top_prompt_lines || [];
    const promptBoundary = memoryOps.preference_profile?.boundary || {};
    if (researchNode) {
        researchNode.innerHTML = `
            <div class="memory-panel-section">
                <div class="stack-label">Research to Action</div>
                ${renderBoundaryState(researchBoundary)}
                <div class="compact-list">${researchItems.length ? researchItems.map(item => `
                    <article class="compact-row compact-row-rich research-action-row">
                        <div>
                            <div class="compact-row-title">${escapeHtml(item.excerpt || item.content || 'research item')}</div>
                            <div class="compact-row-subtitle">${escapeHtml(`#${item.channel_name || 'research'} • ${formatRelativeTime(item.created_at) || 'recent'} • ${item.author_name || 'unknown author'}`)}</div>
                            <div class="compact-row-metrics">
                                <span class="meta-pill">${escapeHtml(item.source_ref || 'research')}</span>
                                ${item.promotion_count ? `<span class="meta-pill meta-growth">${item.promotion_count} promoted</span>` : ''}
                                ${item.source_links?.[0]?.href ? `<a class="task-source-link" href="${escapeHtml(item.source_links[0].href)}" target="_blank" rel="noreferrer">source</a>` : ''}
                            </div>
                            ${item.promotions?.length ? item.promotions.map(promotion => `<div class="memory-line">${escapeHtml(`${promotion.task_kind || 'task'} #${promotion.task_id}: ${promotion.title} (${promotion.status}, ${promotion.assignee || 'unassigned'})`)}</div>`).join('') : ''}
                        </div>
                        <div class="compact-row-metrics compact-row-metrics-end">
                            <button class="command-chip" type="button" onclick="openResearchPromotionModal('${escapeHtml(item.id || '')}', 'task')">Promote Task</button>
                            <button class="command-chip" type="button" onclick="openResearchPromotionModal('${escapeHtml(item.id || '')}', 'experiment')">Promote Experiment</button>
                        </div>
                    </article>
                `).join('') : `<div class="dashboard-empty">No recent research items ready for promotion.</div>`}</div>
            </div>
            <div class="memory-panel-section">
                <div class="stack-label">Research Topics</div>
                ${topics.length ? topics.map(topic => `<span class="topic-pill">${escapeHtml(topic)}</span>`).join('') : `<div class="dashboard-empty">No recent research topics.</div>`}
            </div>
            <div class="memory-panel-section">
                <div class="stack-label">Prompt Packet</div>
                ${renderBoundaryState(promptBoundary)}
                ${promptLines.length ? promptLines.map(line => `<div class="memory-line">${escapeHtml(line)}</div>`).join('') : `<div class="dashboard-empty">No prompt packet lines distilled yet.</div>`}
            </div>
        `;
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
                ${renderBoundaryState(channel.boundary)}
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="status-pill status-${statusTone(channel.enabled ? (channel.has_webhook ? 'active' : 'warning') : 'idle')}">${channel.enabled ? (channel.has_webhook ? 'ready' : 'preview') : 'disabled'}</span>
            </div>
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

function renderDeliberations(deliberations) {
    const container = $('#deliberation-list');
    if (!container) return;
    const items = Array.isArray(deliberations.items) ? deliberations.items : [];
    if (!items.length) {
        container.innerHTML = `<div class="dashboard-empty">No deliberation cells recorded yet. Launch one to capture attributed reasoning in Source.</div>`;
        return;
    }
    container.innerHTML = items.map(cell => {
        const participantRows = Object.entries(cell.participants || {}).map(([agent, role]) => `${agent}:${role}`);
        const latestContribution = Array.isArray(cell.contributions) && cell.contributions.length
            ? cell.contributions[cell.contributions.length - 1]
            : null;
        return `
            <article class="compact-row compact-row-rich">
                <div>
                    <div class="compact-row-title">${escapeHtml(cell.title || cell.id || 'deliberation')}</div>
                    <div class="compact-row-subtitle">${escapeHtml(cell.prompt_excerpt || '')}</div>
                    <div class="compact-row-metrics">
                        <span class="meta-pill">${escapeHtml(`${cell.contribution_count || 0} contributions`)}</span>
                        <span class="meta-pill">${escapeHtml(`${cell.dissent_count || 0} dissent`)}</span>
                        ${(cell.roles || []).slice(0, 3).map(role => `<span class="meta-pill">${escapeHtml(role)}</span>`).join('')}
                    </div>
                    ${participantRows.length ? `<div class="compact-row-subtitle">${escapeHtml(`Participants: ${participantRows.join(' • ')}`)}</div>` : ''}
                    ${latestContribution ? `<div class="compact-row-subtitle">${escapeHtml(`Last: ${latestContribution.agent_id} (${latestContribution.role}) • ${latestContribution.content}`)}</div>` : ''}
                    ${cell.synthesis_excerpt ? `<div class="compact-row-subtitle">${escapeHtml(`Synthesis: ${cell.synthesis_excerpt}`)}</div>` : ''}
                    <div class="compact-row-metrics">
                        <button class="task-action-btn" type="button" onclick="addDeliberationContribution('${escapeHtml(cell.id || '')}')">Add note</button>
                        <button class="task-action-btn" type="button" onclick="addDeliberationSynthesis('${escapeHtml(cell.id || '')}')">Synthesize</button>
                    </div>
                </div>
                <div class="compact-row-metrics compact-row-metrics-end">
                    <span class="status-pill status-${statusTone(cell.status)}">${escapeHtml(cell.status || 'unknown')}</span>
                    <span class="meta-pill">${cell.updated_at ? formatRelativeTime(cell.updated_at) : 'no ts'}</span>
                </div>
            </article>
        `;
    }).join('');
}

function renderWeeklyEvolution(summary) {
    const container = $('#weekly-evolution-list');
    if (!container) return;
    const wins = Array.isArray(summary.wins) ? summary.wins : [];
    const regressions = Array.isArray(summary.regressions) ? summary.regressions : [];
    const upgrades = Array.isArray(summary.upgrades) ? summary.upgrades : [];
    const latestLabel = summary.week_of || summary.generated_at || 'No report yet';
    const schedulerLabel = summary.scheduler_configured ? 'timer wired' : 'timer missing';
    const generatorLabel = summary.generator_configured ? 'generator wired' : 'generator missing';

    if (!summary.latest_report_path) {
        container.innerHTML = `
            <article class="compact-row compact-row-rich">
                <div>
                    <div class="compact-row-title">No weekly evolution report yet</div>
                    <div class="compact-row-subtitle">Source can generate one now, and the scheduler wiring is tracked below.</div>
                    <div class="compact-row-metrics">
                        <span class="meta-pill">${escapeHtml(schedulerLabel)}</span>
                        <span class="meta-pill">${escapeHtml(generatorLabel)}</span>
                    </div>
                </div>
                <div class="compact-row-metrics compact-row-metrics-end">
                    <span class="status-pill status-${statusTone(summary.scheduler_configured ? 'review' : 'backlog')}">${summary.scheduler_configured ? 'configured' : 'backlog'}</span>
                </div>
            </article>
        `;
        return;
    }

    container.innerHTML = `
        <article class="compact-row compact-row-rich">
            <div>
                <div class="compact-row-title">${escapeHtml(latestLabel)}</div>
                <div class="compact-row-subtitle">${escapeHtml(summary.generated_at ? `Generated ${summary.generated_at}` : 'Latest weekly evolution snapshot')}</div>
                <div class="compact-row-metrics">
                    <span class="meta-pill">${escapeHtml(schedulerLabel)}</span>
                    <span class="meta-pill">${escapeHtml(generatorLabel)}</span>
                    <span class="meta-pill">${escapeHtml(`${wins.length} wins`)}</span>
                    <span class="meta-pill">${escapeHtml(`${regressions.length} regressions`)}</span>
                </div>
                ${wins.length ? `<div class="compact-row-subtitle">${escapeHtml(`Wins: ${wins.join(' • ')}`)}</div>` : ''}
                ${regressions.length ? `<div class="compact-row-subtitle">${escapeHtml(`Regressions: ${regressions.join(' • ')}`)}</div>` : ''}
                ${upgrades.length ? `<div class="compact-row-subtitle">${escapeHtml(`Top upgrades: ${upgrades.join(' • ')}`)}</div>` : ''}
                ${summary.notes_excerpt ? `<div class="compact-row-subtitle">${escapeHtml(summary.notes_excerpt)}</div>` : ''}
            </div>
            <div class="compact-row-metrics compact-row-metrics-end">
                <span class="status-pill status-${statusTone(summary.status)}">${escapeHtml(summary.status || 'unknown')}</span>
                <span class="meta-pill">${summary.updated_at ? formatRelativeTime(summary.updated_at) : 'no ts'}</span>
            </div>
        </article>
    `;
}

function statusTone(status) {
    const raw = String(status || '').toLowerCase();
    if (raw === 'healthy' || raw === 'active' || raw === 'running' || raw === 'in_progress' || raw === 'ok') return 'healthy';
    if (raw === 'warning' || raw === 'busy' || raw === 'queued' || raw === 'dry_run' || raw === 'configured' || raw === 'partial' || raw === 'legacy' || raw === 'staged' || raw === 'research_only' || raw === 'backlog' || raw === 'review' || raw === 'offline' || raw === 'stopped' || raw.startsWith('stopped:')) return 'warning';
    if (raw === 'critical' || raw === 'error' || raw === 'failed' || raw === 'misaligned' || raw === 'blocked' || raw === 'retire') return 'error';
    if (raw === 'waiting' || raw === 'monitoring' || raw === 'skipped' || raw === 'idle' || raw === 'done' || raw === 'closed' || raw === 'archived' || raw === 'cancelled') return 'neutral';
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

function formatSignedCurrency(value) {
    const num = Number(value || 0);
    if (Number.isNaN(num)) return 'n/a';
    return `${num >= 0 ? '+' : '-'}$${Math.abs(num).toFixed(2)}`;
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

function visibleTasks(tasks) {
    return (tasks || []).filter(task => !String(task.id || '').startsWith('runtime:'));
}

// Tasks
function renderTasks() {
    const filter = store.get('taskFilter');
    let tasks = visibleTasks(store.get('tasks') || []);
    
    if (filter !== 'all') {
        tasks = tasks.filter(t => t.status === filter);
    }
    
    // Sort by priority: critical/high first
    const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    const sortByPriority = (a, b) => {
        const pa = priorityOrder[a.priority] !== undefined ? priorityOrder[a.priority] : 1;
        const pb = priorityOrder[b.priority] !== undefined ? priorityOrder[b.priority] : 1;
        if (pa !== pb) return pa - pb;
        return String(a.id || 0) < String(b.id || 0) ? -1 : 1;
    };

    // Group by status with backlog leftmost in the live board
const columns = {
    backlog: tasks.filter(t => t.status === 'backlog').sort(sortByPriority),
    in_progress: tasks.filter(t => t.status === 'in_progress').sort(sortByPriority),
    review: tasks.filter(t => t.status === 'review').sort(sortByPriority),
    done: tasks.filter(t => t.status === 'done').sort(sortByPriority)
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


function researchPromotionDefaultTitle(item, taskKind) {
    const prefix = taskKind === 'experiment' ? 'Experiment' : 'Research follow-up';
    return `${prefix}: ${String(item?.excerpt || item?.content || 'research item').slice(0, 72)}`;
}

function researchPromotionDefaultDescription(item) {
    const sourceHref = item?.source_links?.[0]?.href || '';
    return [
        'Promoted from Discord research.',
        '',
        item?.content || '',
        '',
        item?.source_ref ? `Source ref: ${item.source_ref}` : '',
        sourceHref ? `Source link: ${sourceHref}` : ''
    ].filter(Boolean).join('\n');
}

function openResearchPromotionModal(researchId, taskKind = 'task') {
    const items = store.get('portfolio.memory_ops.research_items') || [];
    const item = items.find(entry => String(entry.id) === String(researchId));
    if (!item) {
        Toast.error('Research item not found');
        return;
    }
    const projects = store.get('portfolio.projects') || [];
    const projectOptions = ['<option value="">Unscoped</option>']
        .concat(projects.map(project => `<option value="${escapeHtml(project.id || '')}">${escapeHtml(project.name || project.id || 'project')}</option>`))
        .join('');
    const selectedTask = taskKind === 'experiment' ? ' selected' : '';
    const selectedExperiment = taskKind === 'experiment' ? ' selected' : '';
    const content = `
        <input type="hidden" id="research-promote-id" value="${escapeHtml(item.id || '')}">
        <div class="form-group">
            <label class="form-label">Research Source</label>
            <div class="task-card-desc">${escapeHtml(item.excerpt || item.content || 'research item')}</div>
            <div class="compact-row-metrics">
                <span class="meta-pill">${escapeHtml(item.source_ref || 'research')}</span>
                ${item.source_links?.[0]?.href ? `<a class="task-source-link" href="${escapeHtml(item.source_links[0].href)}" target="_blank" rel="noreferrer">open source</a>` : ''}
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Action Type</label>
            <select class="form-select" id="research-promote-kind">
                <option value="task"${taskKind === 'task' ? ' selected' : ''}>Task</option>
                <option value="experiment"${selectedExperiment}>Experiment</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Title</label>
            <input type="text" class="form-input" id="research-promote-title" value="${escapeHtml(researchPromotionDefaultTitle(item, taskKind))}">
        </div>
        <div class="form-group">
            <label class="form-label">Description</label>
            <textarea class="form-textarea" id="research-promote-desc">${escapeHtml(researchPromotionDefaultDescription(item))}</textarea>
        </div>
        <div class="form-group">
            <label class="form-label">Priority</label>
            <select class="form-select" id="research-promote-priority">
                <option value="medium">Medium</option>
                <option value="high" selected>High</option>
                <option value="low">Low</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Assign to</label>
            <select class="form-select" id="research-promote-assignee">
                <option value="dali" selected>dali</option>
                <option value="c_lawd">c_lawd</option>
                <option value="codex">codex</option>
                <option value="planner">planner</option>
                <option value="coder">coder</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Project</label>
            <select class="form-select" id="research-promote-project">${projectOptions}</select>
        </div>
    `;
    const footer = `
        <button class="btn btn-secondary" onclick="Modal.close()">Cancel</button>
        <button class="btn btn-primary" onclick="submitResearchPromotion()">Promote</button>
    `;
    Modal.open(taskKind === 'experiment' ? 'Promote Research to Experiment' : 'Promote Research to Task', content, footer);
}

async function submitResearchPromotion() {
    const researchId = $('#research-promote-id')?.value;
    const taskKind = $('#research-promote-kind')?.value || 'task';
    const title = $('#research-promote-title')?.value?.trim();
    const description = $('#research-promote-desc')?.value || '';
    const priority = $('#research-promote-priority')?.value || 'high';
    const assignee = $('#research-promote-assignee')?.value || '';
    const project = $('#research-promote-project')?.value || '';

    if (!researchId || !title || !assignee) {
        Toast.error('Research item, title, and assignee are required');
        return;
    }

    try {
        const result = await api.promoteResearchItem({
            research_id: researchId,
            task_kind: taskKind,
            title,
            description,
            priority,
            assignee,
            project
        });
        const task = result.task || result;
        const nextTasks = [task, ...(store.get('tasks') || []).filter(item => String(item.id) !== String(task.id))];
        store.set('tasks', nextTasks);
        Modal.close();
        renderTasks();
        renderDashboard();
        Toast.success(taskKind === 'experiment' ? 'Research promoted to experiment' : 'Research promoted to task');
        await refreshAll({ quiet: true });
    } catch (error) {
        console.error('Research promotion failed', error);
        Toast.error('Research promotion failed');
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
    } else if (action === 'archive') {
        // Archive: remove from active tasks, no status update needed
        try {
            await api.archiveTask(taskId);
            const nextTasks = tasks.filter(item => String(item.id) !== String(taskId));
            store.set('tasks', nextTasks);
            renderTasks();
            renderDashboard();
            Toast.success(`Task archived: ${task.title}`);
        } catch (error) {
            console.error('Task archive failed', error);
            Toast.error('Archive failed');
        }
        return;
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
        const [portfolioResult, tasksResult, commandsResult, receiptsResult, agentsResult, displayModeResult] = await Promise.allSettled([
            api.getPortfolio(),
            api.getTasks(),
            api.getCommandHistory(),
            api.getCommandReceipts(),
            api.getAgents(),
            api.getDisplayMode()
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
        if (displayModeResult.status === 'fulfilled' && displayModeResult.value) {
            store.set('displayMode', displayModeResult.value);
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

async function toggleDisplayMode() {
    if (displayModeToggleInFlight) return;
    displayModeToggleInFlight = true;
    renderDisplayModeControl(store.get('displayMode') || {});
    renderCommandStatus('Applying display mode change…', 'working');
    try {
        const result = await api.toggleDisplayMode();
        store.set('displayMode', result);
        renderDisplayModeControl(result);
        renderCommandStatus(`Display mode switched to ${String(result.profile_current || 'unknown')}.`, 'success');
        Toast.success(`Display mode switched to ${String(result.profile_current || 'unknown')}`);
        await refreshAll({ quiet: true });
    } catch (error) {
        console.error('Display mode toggle failed', error);
        renderCommandStatus('Display mode change failed.', 'error');
        Toast.error('Display mode change failed');
    } finally {
        displayModeToggleInFlight = false;
        renderDisplayModeControl(store.get('displayMode') || {});
    }
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

async function reviewInference(id, reviewState, contradictionState = '') {
    if (!id) return;
    const payload = {};
    if (reviewState) payload.review_state = reviewState;
    if (contradictionState) payload.contradiction_state = contradictionState;
    try {
        await api.updateUserInference(id, payload);
        await refreshAll({ quiet: true });
        Toast.success(`Inference updated: ${id}`);
    } catch (error) {
        console.error('Inference review failed', error);
        Toast.error('Inference review failed');
    }
}

async function launchDeliberationCell() {
    const title = window.prompt('Deliberation title?');
    if (!title) return;
    const promptText = window.prompt('Prompt for the cell?');
    if (!promptText) return;
    const roles = window.prompt('Roles (comma-separated)', 'synthesist,skeptic,builder') || '';
    const participants = window.prompt('Participants (agent:role, comma-separated)', 'c_lawd:synthesist,dali:skeptic,codex:builder') || '';
    try {
        await api.createDeliberation({ title, prompt: promptText, roles, participants });
        await refreshAll({ quiet: true });
        Toast.success('Deliberation cell created');
    } catch (error) {
        console.error('Deliberation creation failed', error);
        Toast.error('Deliberation creation failed');
    }
}

async function addDeliberationContribution(deliberationId) {
    if (!deliberationId) return;
    const agentId = window.prompt('Agent id?', 'c_lawd');
    if (!agentId) return;
    const role = window.prompt('Role?', 'synthesist');
    if (!role) return;
    const content = window.prompt('Contribution text?');
    if (!content) return;
    const disagreesWith = window.prompt('Disagrees with contribution id? Leave blank if none.', '') || '';
    try {
        await api.addDeliberationContribution(deliberationId, {
            agent_id: agentId,
            role,
            content,
            disagrees_with: disagreesWith || null,
        });
        await refreshAll({ quiet: true });
        Toast.success('Contribution recorded');
    } catch (error) {
        console.error('Contribution failed', error);
        Toast.error('Contribution failed');
    }
}

async function addDeliberationSynthesis(deliberationId) {
    if (!deliberationId) return;
    const synthesis = window.prompt('Synthesis text?');
    if (!synthesis) return;
    const dissentNoted = window.confirm('Should this synthesis explicitly note dissent?');
    try {
        await api.addDeliberationSynthesis(deliberationId, {
            synthesis,
            dissent_noted: dissentNoted,
        });
        await refreshAll({ quiet: true });
        Toast.success('Synthesis recorded');
    } catch (error) {
        console.error('Synthesis failed', error);
        Toast.error('Synthesis failed');
    }
}

async function generateWeeklyEvolutionNow() {
    try {
        renderCommandStatus('Generating weekly evolution report…', 'working');
        await api.generateWeeklyEvolution();
        await refreshAll({ quiet: true });
        renderCommandStatus('Weekly evolution report generated.', 'success');
        Toast.success('Weekly evolution report generated');
    } catch (error) {
        console.error('Weekly evolution generation failed', error);
        renderCommandStatus('Weekly evolution generation failed.', 'error');
        Toast.error('Weekly evolution generation failed');
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
    const tradingStrategy = portfolio.trading_strategy || {};
    const openTasks = visibleTasks(tasks).filter(task => task.status !== 'done');

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

    if (String(tradingStrategy.integration?.status || '').toLowerCase() === 'misaligned') {
        items.push({
            id: 'trading-strategy-misaligned',
            type: 'warning',
            body: tradingStrategy.integration?.summary || 'Trading stack is not yet aligned with the AU live brief',
            timestamp: tradingStrategy.updated_at || new Date().toISOString(),
        });
    }

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
window.reviewInference = reviewInference;
window.launchDeliberationCell = launchDeliberationCell;
window.addDeliberationContribution = addDeliberationContribution;
window.addDeliberationSynthesis = addDeliberationSynthesis;
window.generateWeeklyEvolutionNow = generateWeeklyEvolutionNow;
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

    // meta strip (title el removed; subtitle/count/filed remain)
    const subEl   = document.querySelector('#symbiote-subtitle');
    const cntEl   = document.querySelector('#symbiote-section-count');
    const datEl   = document.querySelector('#symbiote-filed');
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
            <div class="sym-dim-card" style="--dim-clr:${dimColour[dim.id]}" data-dim="${dim.id}">
                <div class="sym-dim-emoji">${dim.emoji}</div>
                <div class="sym-dim-label">${dim.label}</div>
                <div class="sym-dim-count">${dim.count} enhancements</div>
                <div class="sym-dim-desc">${dim.desc}</div>
            </div>
        `).join('');
    }

    const phaseLabel = ['', 'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4'];
    const statusLabel = {
        designed:     { text: 'Designed',    cls: 'sym-status-designed'     },
        'in-dev':     { text: 'In Dev',      cls: 'sym-status-indev'        },
        live:         { text: 'Live',        cls: 'sym-status-live'         },
        operational:  { text: 'Operational', cls: 'sym-status-operational'  }
    };
    // Merge writable state overlay onto base enhancement data
    const stateMap = d.enhancement_state || {};
    const enhancements = d.enhancements.map(e => {
        const ov = stateMap[String(e.id)] || {};
        return { ...e, ...ov };
    });

    // Phase filter
    const filterBar = document.querySelector('#symbiote-phase-filter');
    if (filterBar && !filterBar.dataset.wired) {
        filterBar.dataset.wired = '1';
        filterBar.addEventListener('click', (ev) => {
            const btn = ev.target.closest('.sym-filter-btn');
            if (!btn) return;
            filterBar.querySelectorAll('.sym-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const phase = btn.dataset.phase;
            const cards = document.querySelectorAll('#symbiote-grid .sym-card');
            cards.forEach(c => {
                const match = phase === 'all' || c.dataset.phase === phase;
                c.style.display = match ? '' : 'none';
            });
        });
    }

    // Live per-dimension counts
    const dimCountEl = document.querySelector('#symbiote-dimensions');
    if (dimCountEl) {
        const dimCounts = {};
        enhancements.forEach(e => { dimCounts[e.dimension] = (dimCounts[e.dimension] || 0) + 1; });
        dimCountEl.querySelectorAll('.sym-dim-card').forEach(card => {
            const dim = card.dataset.dim;
            if (dim && dimCounts[dim] !== undefined) {
                const cnt = card.querySelector('.sym-dim-count');
                if (cnt) cnt.textContent = dimCounts[dim] + ' enhancements';
            }
        });
    }

    const gridEl = document.querySelector('#symbiote-grid');
    if (gridEl) {
        gridEl.innerHTML = enhancements.map(e => {
            const clr = dimColour[e.dimension] || 'var(--accent-primary)';
            const st  = statusLabel[e.status] || statusLabel.designed;
            const invBadge = e.inv ? `<span class="sym-inv-badge">${e.inv}</span>` : '';
            return `
                <div class="sym-card phase-border-${e.phase}" style="--card-clr:${clr}" data-phase="${e.phase}" data-dim="${e.dimension}">
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

    const expStatusIcon = { closed: '&#x2713;', partial: '&#x25D1;', live: '&#x25BA;', operational: '&#x25CF;', designed: '&#x25CB;', pending: '&middot;' };
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
        let barColor = 'var(--accent)';
        let statusMsg = `${d.proxy_method} · n=${d.n_samples}`;
        if (phi > 0.8) {
            barColor = 'var(--accent-cool)';
            statusMsg += ' · ✨ thriving';
        } else if (phi > 0.5) {
            barColor = 'var(--accent-primary)';
            statusMsg += ' · 🌱 growing';
        } else if (phi > 0.2) {
            barColor = '#f59e0b';
            statusMsg += ' · 💤 resting';
        } else {
            barColor = '#ef4444';
            statusMsg += ' · 🌙 dreaming';
        }
        if (bar) { bar.style.width = pct + '%'; bar.style.background = barColor; }
        if (meta) meta.textContent = statusMsg + ' · ' + ((d.timestamp_utc||'').slice(11,19) || '') + ' UTC';
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

function initCoordFeedCollapse() {
    const header = document.querySelector('.source-intelligence-feed-header');
    const feed   = document.getElementById('coord-feed');
    if (!header || !feed) return;
    header.style.cursor = 'pointer';
    header.addEventListener('click', (e) => {
        if (e.target.closest('#coord-feed-refresh')) return;
        const collapsed = feed.dataset.collapsed === '1';
        feed.dataset.collapsed = collapsed ? '0' : '1';
        feed.style.display = collapsed ? '' : 'none';
        const tog = header.querySelector('.coord-collapse-toggle');
        if (tog) tog.textContent = collapsed ? '▾' : '▸';
    });
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
        const session = d.session || {};
        const style = d.response_style || {};
        const fillsSpace = pc.fills_space != null ? pc.fills_space.toFixed(2) : '—';
        const valueAdd  = pc.value_add  != null ? pc.value_add.toFixed(2)  : '—';
        const attunement = session.attunement_index != null ? Number(session.attunement_index).toFixed(2) : '—';
        const trust = session.trust_score != null ? Number(session.trust_score).toFixed(2) : (d.trust_note || '—');
        const arousal = session.arousal != null
            ? Number(session.arousal).toFixed(2)
            : (d.tacti && d.tacti.arousal != null ? Number(d.tacti.arousal).toFixed(2) : '—');
        const promptMode = style.mode || 'steady';
        const di = d.diversity_index != null ? d.diversity_index.toFixed(3) : '—';
        const diAlert = d.di_alert ? ' ⚠ DI<0.0' : '';
        rows.innerHTML = `
            <div class="ci-rel-row"><span>fills_space</span><span>${fillsSpace}</span></div>
            <div class="ci-rel-row"><span>value_add</span><span>${valueAdd}</span></div>
            <div class="ci-rel-row"><span>prompt_mode</span><span>${escapeHtml(promptMode)}</span></div>
            <div class="ci-rel-row"><span>attune / trust</span><span>${attunement} / ${trust}</span></div>
            <div class="ci-rel-row"><span>arousal</span><span>${arousal}</span></div>
            <div class="ci-rel-row"><span>author_sil (DI)</span><span>${di}${diAlert}</span></div>
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
