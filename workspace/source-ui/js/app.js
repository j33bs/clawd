/**
 * Source UI - Main Application
 * The heart of the Source Control Center
 */

// Application state
let currentView = 'dashboard';
let refreshInterval = null;
let statusRefreshInterval = null;
const panelRefreshTimestamps = {};

// Local selector helpers
const $ = (selector, context = document) => context.querySelector(selector);

const TACTI_PANEL_ENDPOINTS = {
    dream: '/api/tacti/dream',
    stigmergy: '/api/hivemind/stigmergy',
    immune: '/api/tacti/immune',
    arousal: '/api/tacti/arousal',
    trails: '/api/hivemind/trails',
    'peer-graph': '/api/hivemind/peer-graph',
    skills: '/api/skills',
    ain: '/api/ain/status'
};

// Initialize application
function initApp() {
    console.log('⚡ Source UI initializing...');
    
    // Initialize demo data
    store.initDemoData();
    
    // Initialize UI
    initNavigation();
    initTheme();
    initViews();
    initDragAndDrop();
    initModals();
    initCommandPalette();
    initNotifications();
    initSettings();
    initKeyboardShortcuts();
    initTactiStatus();
    initTactiDashboard();
    
    // Start data refresh
    startDataRefresh();
    
    // Initial render
    renderAll();
    
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
        settings: 'Settings'
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

function initTactiStatus() {
    $('#refresh-status-btn')?.addEventListener('click', () => refreshTactiStatus(true));
    refreshTactiStatus(false);

    if (statusRefreshInterval) {
        clearInterval(statusRefreshInterval);
    }
    statusRefreshInterval = setInterval(() => refreshTactiStatus(false), 20000);
}

async function fetchContract(endpoint, options = {}) {
    const response = await fetch(endpoint, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    const payload = await response.json();
    return payload;
}

function setStatusTile(id, health, value, meta) {
    const tile = $(id);
    if (!tile) return;
    tile.dataset.health = health;
    const valueEl = tile.querySelector('[data-status-field=\"value\"]');
    const metaEl = tile.querySelector('[data-status-field=\"meta\"]');
    if (valueEl) valueEl.textContent = value;
    if (metaEl) metaEl.textContent = meta;
}

async function refreshTactiStatus(showToast) {
    try {
        const payload = await fetchContract('/api/status');
        if (!payload || payload.ok !== true || !payload.data) {
            const reason = payload?.error?.message || 'status unavailable';
            throw new Error(reason);
        }

        const data = payload.data;
        const qmd = data.qmd || {};
        const kb = data.knowledge_base_sync || {};
        const cron = data.cron || {};
        const memory = data.memory || {};

        const qmdReachable = !!qmd.reachable;
        const qmdValue = qmdReachable ? 'Reachable' : 'Unreachable';
        const qmdMeta = qmdReachable
            ? `latency ${qmd.latency_ms ?? '--'} ms`
            : (qmd.reason || 'probe failed');
        setStatusTile('#status-qmd', qmdReachable ? 'ok' : 'bad', qmdValue, qmdMeta);

        const kbStatus = kb.status || 'unknown';
        const kbHealth = kbStatus === 'ok' ? 'ok' : (kbStatus === 'stale' ? 'warn' : 'bad');
        const kbValue = kbStatus.toUpperCase();
        const kbMeta = kb.last_sync
            ? `${Utils.formatTime(kb.last_sync)} (${kb.age_minutes ?? '--'}m)`
            : (kb.reason || 'no sync marker');
        setStatusTile('#status-kb', kbHealth, kbValue, kbMeta);

        const cronStatus = cron.status || 'unknown';
        const cronHealth = cronStatus === 'ok' ? 'ok' : (cronStatus === 'stale' ? 'warn' : 'bad');
        const cronValue = cronStatus.toUpperCase();
        const cronMeta = cron.latest_artifact_ts
            ? `${Utils.formatTime(cron.latest_artifact_ts)} | jobs ${cron.template_jobs ?? '--'}`
            : (cron.reason || 'no cron artifact');
        setStatusTile('#status-cron', cronHealth, cronValue, cronMeta);

        const processMb = typeof memory.process_rss_mb === 'number' ? memory.process_rss_mb.toFixed(1) : '--';
        const usedPct = typeof memory.system_used_pct === 'number' ? `${memory.system_used_pct.toFixed(1)}%` : 'n/a';
        const memHealth = typeof memory.system_used_pct === 'number'
            ? (memory.system_used_pct > 90 ? 'bad' : memory.system_used_pct > 80 ? 'warn' : 'ok')
            : 'warn';
        setStatusTile('#status-memory', memHealth, `${processMb} MB`, `system ${usedPct}`);

        if (showToast) {
            Toast.success('Status refreshed');
        }
    } catch (error) {
        setStatusTile('#status-qmd', 'bad', 'ERROR', 'status endpoint unavailable');
        setStatusTile('#status-kb', 'bad', 'ERROR', 'status endpoint unavailable');
        setStatusTile('#status-cron', 'bad', 'ERROR', 'status endpoint unavailable');
        setStatusTile('#status-memory', 'bad', 'ERROR', 'status endpoint unavailable');
        if (showToast) {
            Toast.error(`Status refresh failed: ${error.message}`);
        }
    }
}

function initTactiDashboard() {
    document.querySelectorAll('.panel-refresh-btn').forEach((btn) => {
        btn.addEventListener('click', async () => {
            const panel = btn.dataset.panelRefresh;
            if (!panel) return;
            await refreshTactiPanel(panel, true);
        });
    });

    initQuickActions();

    Object.keys(TACTI_PANEL_ENDPOINTS).forEach((panelKey) => {
        refreshTactiPanel(panelKey, false);
    });
}

function setQuickActionFeedback(message, isError = false) {
    const el = $('#quick-action-feedback');
    if (!el) return;
    el.textContent = message;
    el.style.color = isError ? 'var(--danger)' : 'var(--text-secondary)';
}

function initQuickActions() {
    $('#qa-run-dream')?.addEventListener('click', runDreamConsolidationAction);
    $('#qa-query-stigmergy')?.addEventListener('click', queryStigmergyAction);
    $('#qa-view-immune')?.addEventListener('click', () => refreshTactiPanel('immune', true));
    $('#qa-trigger-trail')?.addEventListener('click', triggerTrailAction);
    $('#qa-refresh-peer')?.addEventListener('click', () => refreshTactiPanel('peer-graph', true));
    $('#qa-stig-query')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            queryStigmergyAction();
        }
    });
}

async function runDreamConsolidationAction() {
    setQuickActionFeedback('Running dream consolidation...');
    try {
        const payload = await fetchContract('/api/tacti/dream/run', {
            method: 'POST',
            body: JSON.stringify({})
        });
        if (!payload || payload.ok !== true) {
            throw new Error(payload?.error?.message || 'run failed');
        }
        await refreshTactiPanel('dream', false);
        setQuickActionFeedback('Dream consolidation completed');
        Toast.success('Dream consolidation completed');
    } catch (error) {
        setQuickActionFeedback(`Dream run failed: ${error.message}`, true);
        Toast.error('Dream consolidation failed');
    }
}

async function queryStigmergyAction() {
    const query = ($('#qa-stig-query')?.value || '').trim();
    setQuickActionFeedback(query ? `Querying stigmergy: ${query}` : 'Querying stigmergy...');
    try {
        const payload = await fetchContract('/api/hivemind/stigmergy/query', {
            method: 'POST',
            body: JSON.stringify({ query })
        });
        if (!payload || payload.ok !== true) {
            throw new Error(payload?.error?.message || 'query failed');
        }
        const matches = Array.isArray(payload.data?.matches) ? payload.data.matches : [];
        renderPanelDetails('stigmergy', matches.slice(0, 5).map((row) => `${row.topic} · ${row.effective_intensity}`));
        renderPanelError('stigmergy', null);
        updatePanelTimestamp('stigmergy', payload.ts);
        setQuickActionFeedback(`Stigmergy matches: ${matches.length}`);
        Toast.success('Stigmergy query complete');
    } catch (error) {
        setQuickActionFeedback(`Stigmergy query failed: ${error.message}`, true);
        Toast.error('Stigmergy query failed');
    }
}

async function triggerTrailAction() {
    const queryText = ($('#qa-stig-query')?.value || '').trim();
    const text = queryText ? `manual trail: ${queryText}` : 'manual trail trigger';
    setQuickActionFeedback('Triggering memory trail...');
    try {
        const payload = await fetchContract('/api/hivemind/trails/trigger', {
            method: 'POST',
            body: JSON.stringify({
                text,
                tags: ['source-ui', 'manual-trigger']
            })
        });
        if (!payload || payload.ok !== true) {
            throw new Error(payload?.error?.message || 'trail trigger failed');
        }
        await refreshTactiPanel('trails', false);
        setQuickActionFeedback(`Trail created: ${payload.data?.trail_id || 'ok'}`);
        Toast.success('Memory trail triggered');
    } catch (error) {
        setQuickActionFeedback(`Trail trigger failed: ${error.message}`, true);
        Toast.error('Trail trigger failed');
    }
}

function panelMetric(label, value) {
    return `
        <div class="panel-metric">
            <span class="panel-metric-label">${label}</span>
            <span class="panel-metric-value">${value}</span>
        </div>
    `;
}

function renderPanelDetails(panel, details) {
    const container = $(`#panel-${panel}-details`);
    if (!container) return;
    if (!details || details.length === 0) {
        container.innerHTML = '<div class="panel-detail-empty">No recent details available</div>';
        return;
    }
    container.innerHTML = details.map((item) => `<div class="panel-detail-item">${item}</div>`).join('');
}

function renderPanelMetrics(panel, metrics) {
    const container = $(`#panel-${panel}-metrics`);
    if (!container) return;
    container.innerHTML = metrics.map((metric) => panelMetric(metric.label, metric.value)).join('');
}

function renderPanelError(panel, message) {
    const errEl = $(`#panel-${panel}-error`);
    if (!errEl) return;
    if (!message) {
        errEl.classList.add('hidden');
        errEl.textContent = '';
        return;
    }
    errEl.textContent = message;
    errEl.classList.remove('hidden');
}

function updatePanelTimestamp(panel, timestamp) {
    panelRefreshTimestamps[panel] = timestamp || new Date().toISOString();
    const updatedEl = $(`#panel-${panel}-updated`);
    if (updatedEl) {
        updatedEl.textContent = `Last updated: ${Utils.formatTime(panelRefreshTimestamps[panel])}`;
    }
}

function shapePanelData(panel, payload) {
    switch (panel) {
        case 'dream': {
            return {
                metrics: [
                    { label: 'Status', value: payload.status || 'unknown' },
                    { label: 'Store Items', value: payload.store_items ?? 0 },
                    { label: 'Reports', value: payload.report_count ?? 0 }
                ],
                details: [
                    payload.last_outcome_summary ? `Summary: ${payload.last_outcome_summary}` : 'Summary: unavailable',
                    payload.last_run ? `Last Run: ${Utils.formatTime(payload.last_run)}` : 'Last Run: never',
                    payload.latest_report ? `Report: ${payload.latest_report}` : 'Report: unavailable'
                ]
            };
        }
        case 'stigmergy': {
            const summary = payload.intensity_summary || {};
            const marks = Array.isArray(payload.marks) ? payload.marks : [];
            return {
                metrics: [
                    { label: 'Active Marks', value: payload.active_marks_count ?? 0 },
                    { label: 'Intensity Avg', value: summary.avg ?? 0 },
                    { label: 'Intensity Max', value: summary.max ?? 0 }
                ],
                details: marks.slice(0, 5).map((mark) => `${mark.topic} · ${mark.effective_intensity}`)
            };
        }
        case 'immune': {
            const blocks = Array.isArray(payload.recent_blocks) ? payload.recent_blocks : [];
            return {
                metrics: [
                    { label: 'Quarantine', value: payload.quarantine_count ?? 0 },
                    { label: 'Approvals', value: payload.approval_count ?? 0 },
                    { label: 'Accepted', value: payload.accepted_count ?? 0 }
                ],
                details: blocks.slice(0, 5).map((block) => `${block.reason} · ${block.content_hash}`)
            };
        }
        case 'arousal': {
            const histogram = Array.isArray(payload.hourly_histogram) ? payload.hourly_histogram : [];
            const top = histogram
                .sort((a, b) => (b.value || 0) - (a.value || 0))
                .slice(0, 4)
                .map((bucket) => `h${bucket.hour}: ${bucket.value}`);
            return {
                metrics: [
                    { label: 'Energy', value: payload.current_energy ?? 0 },
                    { label: 'Baseline', value: payload.baseline ?? 0 },
                    { label: 'Bins Used', value: payload.bins_used ?? 0 }
                ],
                details: top
            };
        }
        case 'trails': {
            const summary = payload.memory_heatmap_summary || {};
            const strength = summary.strength_summary || {};
            const recent = Array.isArray(payload.recent_trails) ? payload.recent_trails : [];
            return {
                metrics: [
                    { label: 'Trail Count', value: summary.trail_count ?? 0 },
                    { label: 'Strength Avg', value: strength.avg ?? 0 },
                    { label: 'Top Tags', value: (summary.top_tags || []).length || 0 }
                ],
                details: recent.slice(0, 5).map((item) => item.text)
            };
        }
        case 'peer-graph': {
            const sample = Array.isArray(payload.adjacency_sample) ? payload.adjacency_sample : [];
            return {
                metrics: [
                    { label: 'Nodes', value: payload.nodes_count ?? 0 },
                    { label: 'Edges', value: payload.edges_count ?? 0 },
                    { label: 'Source', value: payload.source ? 'artifact' : 'n/a' }
                ],
                details: sample.slice(0, 5).map((edge) => `${edge.src} -> ${edge.dst} (${edge.weight})`)
            };
        }
        case 'skills': {
            const skills = Array.isArray(payload.skills) ? payload.skills : [];
            const links = Array.isArray(payload.links) ? payload.links : [];
            return {
                metrics: [
                    { label: 'Skills', value: payload.count ?? skills.length },
                    { label: 'MOCs', value: (payload.mocs || []).length || 0 },
                    { label: 'Links', value: links.length }
                ],
                details: [
                    ...links.slice(0, 3).map((link) => `${link.name}: ${link.path}`),
                    ...skills.slice(0, 3).map((skill) => `Skill: ${skill.name}`)
                ]
            };
        }
        case 'ain': {
            // AIN Agent panel - consciousness measurement
            const phiRes = await fetch('/api/ain/phi').catch(() => ({}));
            const phi = phiRes.ok ? await phiRes.json() : {};
            
            return {
                metrics: [
                    { label: 'Agent', value: payload.running ? 'Running' : 'Not Running' },
                    { label: 'State', value: payload.state || 'idle' },
                    { label: 'Φ (Consciousness)', value: (phi.phi || 0).toFixed(4) },
                    { label: 'Total Drive', value: (payload.total_drive || 0).toFixed(3) }
                ],
                details: [
                    payload.message ? `Note: ${payload.message}` : 'AIN agent ready',
                    phi.integration ? `Integration: ${phi.integration.toFixed(4)}` : 'Integration: —',
                    phi.complexity ? `Complexity: ${phi.complexity.toFixed(4)}` : 'Complexity: —'
                ]
            };
        }
        default:
            return {
                metrics: [{ label: 'Status', value: 'unavailable' }],
                details: ['No data shape available']
            };
    }
}

async function refreshTactiPanel(panel, showToast) {
    const endpoint = TACTI_PANEL_ENDPOINTS[panel];
    if (!endpoint) return;
    try {
        const payload = await fetchContract(endpoint);
        if (!payload || payload.ok !== true) {
            const reason = payload?.error?.message || payload?.error?.code || 'endpoint unavailable';
            throw new Error(reason);
        }
        const shaped = shapePanelData(panel, payload.data || {});
        renderPanelMetrics(panel, shaped.metrics);
        renderPanelDetails(panel, shaped.details);
        renderPanelError(panel, null);
        updatePanelTimestamp(panel, payload.ts);
        if (showToast) {
            Toast.success(`${panel} refreshed`);
        }
    } catch (error) {
        renderPanelMetrics(panel, [{ label: 'Status', value: 'Unavailable' }]);
        renderPanelDetails(panel, ['Module data unavailable']);
        renderPanelError(panel, `Unavailable: ${error.message}`);
        updatePanelTimestamp(panel, new Date().toISOString());
        if (showToast) {
            Toast.error(`${panel} refresh failed`);
        }
    }
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
    }
}

// Dashboard
function renderDashboard() {
    const agents = store.get('agents');
    const tasks = store.get('tasks');
    const components = store.get('components');
    const notifications = store.get('notifications');
    
    // Stats
    const activeAgents = agents.filter(a => a.status === 'working').length;
    const todayTasks = tasks.length;
    
    $('#stat-agents').textContent = activeAgents;
    $('#stat-tasks').textContent = todayTasks;
    $('#stat-schedule').textContent = '4';
    $('#stat-uptime').textContent = '7d';
    
    // Active agents
    $('#dashboard-agents').innerHTML = agents.slice(0, 3).map(a => Components.agentCardMini(a)).join('');
    
    // Activity feed
    $('#activity-feed').innerHTML = notifications.slice(0, 5).map(n => Components.activityItem(n)).join('');
    
    // Health grid
    $('#health-grid').innerHTML = components.slice(0, 4).map(c => Components.healthItem(c)).join('');
    
    // Update badge
    const pendingTasks = tasks.filter(t => t.status !== 'done').length;
    $('#task-badge').textContent = pendingTasks;
}

// Tasks
function renderTasks() {
    const filter = store.get('taskFilter');
    let tasks = store.get('tasks');
    
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
    const status = value > threshold ? 'error' : value > threshold * 0.8 ? 'warning' : 'healthy';
    $(`#metric-${type}`).textContent = type === 'gpu' ? value : `${value}%`;
    $(`#${type}-bar`).style.width = `${Math.min(value, 100)}%`;
    $(`#${type}-status`).textContent = status;
    $(`#${type}-status`).className = `metric-status ${status}`;
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
        store.updateSetting('soundAlerts', e.target.value);
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
    
    document.addEventListener('drop', (e) => {
        e.preventDefault();
        const column = e.target.closest('.kanban-column');
        if (column) {
            column.classList.remove('drag-over');
            const taskId = parseInt(e.dataTransfer.getData('text/plain'));
            const newStatus = column.dataset.status;
            store.moveTask(taskId, newStatus);
            renderTasks();
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
    `;
    
    const footer = `
        <button class="btn btn-secondary" onclick="Modal.close()">Cancel</button>
        <button class="btn btn-primary" onclick="createTask()">Create Task</button>
    `;
    
    Modal.open('Create New Task', content, footer);
}

function createTask() {
    const title = $('#new-task-title')?.value;
    const desc = $('#new-task-desc')?.value;
    const priority = $('#new-task-priority')?.value;
    const assignee = $('#new-task-assignee')?.value;
    
    if (!title) {
        Toast.error('Please enter a task title');
        return;
    }
    
    store.addTask({
        title,
        description: desc,
        priority,
        assignee,
        status: 'backlog',
        createdAt: new Date().toISOString()
    });
    
    Modal.close();
    renderTasks();
    Toast.success('Task created successfully');
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

async function refreshAll() {
    // Simulate data refresh
    const metrics = {
        cpu: Math.floor(Math.random() * 40) + 20,
        memory: Math.floor(Math.random() * 30) + 45,
        disk: Math.floor(Math.random() * 20) + 30,
        gpu: Math.floor(Math.random() * 40) + 30
    };
    
    store.set('healthMetrics', metrics);
    
    if (currentView === 'health') {
        renderHealth();
    }
    if (currentView === 'dashboard') {
        renderDashboard();
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
        await api.runHealthCheck();
        Toast.success('Health check complete');
        renderHealth();
    } catch (e) {
        Toast.error('Health check failed');
    }
}

async function controlAgent(agentId, action) {
    Toast.info(`${action} agent...`);
    // In real implementation, would call API
    Toast.success(`Agent ${action} successful`);
    renderAgents();
}

// Update status indicators
function updateStatusIndicators() {
    const gateway = $('#gateway-status');
    const text = $('#gateway-status-text');
    
    if (gateway && text) {
        // For demo, always show connected
        gateway.classList.add('connected');
        gateway.classList.remove('error');
        text.textContent = 'Connected';
    }
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
