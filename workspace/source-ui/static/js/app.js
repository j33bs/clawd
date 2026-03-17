/**
 * Source UI - Main Application
 * The heart of the Source Control Center
 */

// Application state
let currentView = 'dashboard';
let refreshInterval = null;
let statusRefreshInterval = null;
const panelRefreshTimestamps = {};
let symbioteCache = null;
const oracleInitializedPanels = new WeakSet();

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

const TASK_STATUS_ALIASES = {
    todo: 'backlog',
    queued: 'backlog',
    queue: 'backlog',
    pending: 'backlog',
    open: 'backlog',
    working: 'in_progress',
    active: 'in_progress',
    'in-progress': 'in_progress',
    'in progress': 'in_progress',
    reviewing: 'review',
    qa: 'review',
    complete: 'done',
    completed: 'done',
    closed: 'done'
};

const TASK_PRIORITY_ALIASES = {
    urgent: 'critical',
    p0: 'critical',
    p1: 'high',
    normal: 'medium',
    default: 'medium',
    minor: 'low'
};

function normalizeTaskStatus(status) {
    const normalized = String(status || '').trim().toLowerCase();
    if (!normalized) return 'backlog';
    const aliasKey = normalized.replace(/[_-]/g, ' ');
    const canonical = TASK_STATUS_ALIASES[normalized] || TASK_STATUS_ALIASES[aliasKey] || normalized.replace(/[\s-]+/g, '_');
    return ['backlog', 'in_progress', 'review', 'done'].includes(canonical) ? canonical : 'backlog';
}

function normalizeTaskPriority(priority) {
    const normalized = String(priority || '').trim().toLowerCase();
    if (!normalized) return 'medium';
    const canonical = TASK_PRIORITY_ALIASES[normalized] || normalized;
    return ['critical', 'high', 'medium', 'low'].includes(canonical) ? canonical : 'medium';
}

function normalizeTaskRecord(task, index = 0) {
    if (!task || typeof task !== 'object') return null;
    return {
        ...task,
        id: task.id ?? `task-${index + 1}`,
        title: String(task.title || task.description || `Task ${index + 1}`).trim(),
        status: normalizeTaskStatus(task.status),
        priority: normalizeTaskPriority(task.priority)
    };
}

function normalizeTaskList(tasks) {
    if (!Array.isArray(tasks)) return [];
    return tasks.map((task, index) => normalizeTaskRecord(task, index)).filter(Boolean);
}

const AGENT_STATUS_ALIASES = {
    active: 'working',
    busy: 'working',
    running: 'working',
    working: 'working',
    idle: 'idle',
    waiting: 'idle',
    queued: 'idle',
    offline: 'idle',
    stopped: 'idle',
};

function normalizeAgentStatus(status) {
    const normalized = String(status || '').trim().toLowerCase();
    if (!normalized) return 'idle';
    return AGENT_STATUS_ALIASES[normalized] || 'idle';
}

function normalizeAgentRecord(agent, index = 0) {
    if (!agent || typeof agent !== 'object') return null;
    const progressValue = Number(agent.progress);
    return {
        ...agent,
        id: String(agent.id || `agent-${index + 1}`),
        name: String(agent.name || agent.id || `Agent ${index + 1}`),
        model: String(agent.model || 'unknown'),
        status: normalizeAgentStatus(agent.status),
        progress: Number.isFinite(progressValue) ? Math.max(0, Math.min(100, progressValue)) : null,
        tasksCompleted: Number(agent.tasksCompleted ?? agent.tasks_completed ?? 0) || 0,
        cycles: Number(agent.cycles || 0) || 0,
        task: String(agent.task || '').trim(),
        detail: String(agent.detail || '').trim(),
        updated_at: agent.updated_at || agent.updatedAt || null,
        available_actions: Array.isArray(agent.available_actions) ? agent.available_actions : [],
    };
}

function normalizeAgentList(agents) {
    if (!Array.isArray(agents)) return [];
    return agents.map((agent, index) => normalizeAgentRecord(agent, index)).filter(Boolean);
}

function normalizeScheduleJobRecord(job, index = 0) {
    if (!job || typeof job !== 'object') return null;
    const nextRunAt = job.next_run_at || job.nextRunAt || null;
    const lastRunAt = job.last_run_at || job.lastRunAt || null;
    const enabled = typeof job.enabled === 'boolean' ? job.enabled : true;
    const lastStatus = String(job.last_status || job.lastStatus || '').trim();
    return {
        ...job,
        id: String(job.id || `job-${index + 1}`),
        name: String(job.name || job.description || `Schedule ${index + 1}`),
        cron: String(job.cron || job.schedule || job.expression || 'manual'),
        enabled,
        next_run_at: nextRunAt,
        last_run_at: lastRunAt,
        nextRun: nextRunAt ? Utils.formatDate(nextRunAt) : String(job.nextRun || job.next_run || 'No next run scheduled'),
        nextRunShort: nextRunAt
            ? new Date(nextRunAt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
            : '',
        lastRun: lastRunAt ? Utils.formatDate(lastRunAt) : '',
        meta: [
            job.agent_id ? `Agent ${job.agent_id}` : null,
            lastStatus ? `Last ${lastStatus}` : null,
        ].filter(Boolean).join(' · '),
    };
}

function normalizeScheduleJobList(jobs) {
    if (!Array.isArray(jobs)) return [];
    return jobs.map((job, index) => normalizeScheduleJobRecord(job, index)).filter(Boolean);
}

function normalizeLogRecord(log, index = 0) {
    if (!log || typeof log !== 'object') return null;
    const rawLevel = String(log.level || 'info').trim().toLowerCase();
    const level = rawLevel === 'warning' ? 'warn' : rawLevel;
    return {
        ...log,
        id: String(log.id || `log-${index + 1}`),
        level: ['info', 'warn', 'error'].includes(level) ? level : 'info',
        message: String(log.message || log.summary || 'log event'),
        timestamp: log.timestamp || new Date().toISOString(),
    };
}

function normalizeLogList(logs) {
    if (!Array.isArray(logs)) return [];
    return logs.map((log, index) => normalizeLogRecord(log, index)).filter(Boolean);
}

function normalizeNotificationRecord(notification, index = 0) {
    if (!notification || typeof notification !== 'object') return null;
    const kind = String(notification.type || notification.kind || 'info').trim().toLowerCase();
    return {
        ...notification,
        id: String(notification.id || `notification-${index + 1}`),
        type: kind === 'warn' ? 'warning' : kind,
        body: String(notification.body || notification.message || notification.detail || ''),
        title: String(notification.title || notification.kind || 'Notification'),
        read: Boolean(notification.read),
        timestamp: notification.timestamp || notification.created_at || new Date().toISOString(),
    };
}

function normalizeNotificationList(notifications) {
    if (!Array.isArray(notifications)) return [];
    return notifications.map((notification, index) => normalizeNotificationRecord(notification, index)).filter(Boolean);
}

function normalizeHealthMetrics(metrics) {
    const source = metrics && typeof metrics === 'object' ? metrics : {};
    return {
        cpu: Number(source.cpu || 0) || 0,
        memory: Number(source.memory || 0) || 0,
        disk: Number(source.disk || 0) || 0,
        gpu: Number(source.gpu || 0) || 0,
    };
}

function emptyState(message) {
    return `<div class="empty-state">${message}</div>`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function activityFeedItems(notifications, logs) {
    if (notifications.length > 0) return notifications.slice(0, 5);
    return logs.slice(0, 5).map((log) => ({
        id: `log-activity-${log.id}`,
        type: log.level === 'warn' ? 'warning' : log.level,
        body: log.message,
        timestamp: log.timestamp,
    }));
}

// Initialize application
async function initApp() {
    console.log('⚡ Source UI initializing...');

    await loadInitialState();
    
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
        symbiote: 'Collective Intelligence Symbiote',
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
    $('#add-schedule-btn')?.addEventListener('click', openScheduleModal);
    
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

    $('#log-level-filter')?.addEventListener('change', (event) => {
        store.set('logFilter', event.target.value);
        renderLogs();
    });

    const globalSearch = $('#global-search');
    if (globalSearch) {
        const openSearch = Utils.debounce((query) => CommandPalette.openWithQuery(query), 100);
        globalSearch.addEventListener('focus', () => CommandPalette.openWithQuery(globalSearch.value.trim()));
        globalSearch.addEventListener('input', () => openSearch(globalSearch.value.trim()));
        globalSearch.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                CommandPalette.openWithQuery(globalSearch.value.trim());
            }
        });
    }

    initOracle();
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
    if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'ok')) {
        return payload;
    }
    if (!response.ok) {
        const message = payload?.error?.message || payload?.error || payload?.message || response.statusText || 'request failed';
        return { ok: false, error: { message }, status: response.status };
    }
    return {
        ok: true,
        data: payload,
        ts: payload?.ts || new Date().toISOString()
    };
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
        const memorySystem = data.memory_system || {};
        const cron = data.cron || {};
        const memory = data.memory || {};

        const memoryStatus = String(memorySystem.status || '').trim().toLowerCase();
        const memoryHealth = memoryStatus === 'active' ? 'ok' : (memoryStatus === 'warning' ? 'warn' : 'bad');
        const memoryValue = typeof memorySystem.total_rows === 'number'
            ? `${memorySystem.total_rows} rows`
            : 'Unavailable';
        const memoryMetaBits = [];
        if (typeof memorySystem.active_inferences === 'number') {
            memoryMetaBits.push(`${memorySystem.active_inferences} inferences`);
        }
        if (memorySystem.latest_source_label) {
            memoryMetaBits.push(String(memorySystem.latest_source_label));
        }
        if (memorySystem.latest_updated_at) {
            memoryMetaBits.push(`updated ${Utils.formatTime(memorySystem.latest_updated_at)}`);
        }
        setStatusTile(
            '#status-memory-system',
            memoryHealth,
            memoryValue,
            memoryMetaBits.join(' · ') || String(memorySystem.summary || 'no live memory summary')
        );

        const cronStatus = String(cron.status || 'unknown').trim().toLowerCase();
        const cronHealth = cronStatus === 'ok' ? 'ok' : (cronStatus === 'stale' || cronStatus === 'warning' ? 'warn' : 'bad');
        const cronValue = typeof cron.enabled_jobs === 'number'
            ? `${cron.enabled_jobs} live`
            : cronStatus.toUpperCase();
        const cronMetaBits = [];
        if (cron.latest_run_at) {
            cronMetaBits.push(`last ${Utils.formatTime(cron.latest_run_at)}`);
        } else if (cron.latest_artifact_ts) {
            cronMetaBits.push(`last ${Utils.formatTime(cron.latest_artifact_ts)}`);
        }
        if (cron.next_run_at) {
            cronMetaBits.push(`next ${Utils.formatTime(cron.next_run_at)}`);
        }
        if (typeof cron.jobs_total === 'number') {
            cronMetaBits.push(`jobs ${cron.jobs_total}`);
        } else if (typeof cron.template_jobs === 'number') {
            cronMetaBits.push(`jobs ${cron.template_jobs}`);
        }
        if (typeof cron.failing_jobs === 'number' && cron.failing_jobs > 0) {
            cronMetaBits.push(`issues ${cron.failing_jobs}`);
        }
        const cronMeta = cronMetaBits.join(' · ') || (cron.reason || 'no cron artifact');
        setStatusTile('#status-cron', cronHealth, cronValue, cronMeta);

        const processMb = typeof memory.process_rss_mb === 'number' ? memory.process_rss_mb.toFixed(1) : '--';
        const usedPct = typeof memory.system_used_pct === 'number' ? `${memory.system_used_pct.toFixed(1)}%` : 'n/a';
        const memHealth = typeof memory.system_used_pct === 'number'
            ? (memory.system_used_pct > 90 ? 'bad' : memory.system_used_pct > 80 ? 'warn' : 'ok')
            : 'warn';
        setStatusTile('#status-system-memory', memHealth, `${processMb} MB`, `system ${usedPct}`);

        if (showToast) {
            Toast.success('Status refreshed');
        }
    } catch (error) {
        setStatusTile('#status-memory-system', 'bad', 'ERROR', 'status endpoint unavailable');
        setStatusTile('#status-cron', 'bad', 'ERROR', 'status endpoint unavailable');
        setStatusTile('#status-system-memory', 'bad', 'ERROR', 'status endpoint unavailable');
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
    $('#qa-open-oracle')?.addEventListener('click', openOracleAction);
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

function openOracleAction() {
    const query = ($('#qa-stig-query')?.value || '').trim();
    navigateTo('dashboard');
    const oracleInput = $('#dashboard-oracle-query') || $('#oracle-query');
    if (oracleInput) {
        if (query) {
            oracleInput.value = query;
        }
        window.setTimeout(() => oracleInput.focus(), 60);
    }
    setQuickActionFeedback(query ? 'Oracle ready with current query' : 'Oracle ready');
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

async function shapePanelData(panel, payload) {
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
        const shaped = await shapePanelData(panel, payload.data || {});
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
    renderSymbiote();
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
        case 'symbiote':
            renderSymbiote();
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
    const logs = store.get('logs');
    const scheduledJobs = store.get('scheduledJobs');
    const truth = store.get('truth') || {};
    
    // Stats
    const activeAgents = agents.filter(a => a.status === 'working').length;
    const todayTasks = tasks.length;
    const pendingTasks = tasks.filter(t => t.status !== 'done').length;
    const truthSource = truth.source || 'runtime_state';
    const truthUpdatedAt = truth.source_mission_updated_at || store.get('lastUpdate');
    
    $('#stat-agents').textContent = String(activeAgents);
    $('#stat-agents-change').textContent = agents.length ? `${agents.length} runtime rows visible` : 'No active runtime rows';
    $('#stat-tasks').textContent = String(todayTasks);
    $('#stat-tasks-change').textContent = pendingTasks ? `${pendingTasks} open on the board` : 'No open tasks';
    $('#stat-schedule').textContent = String(scheduledJobs.length || 0);
    $('#stat-schedule-change').textContent = scheduledJobs.filter(job => job.enabled).length
        ? `${scheduledJobs.filter(job => job.enabled).length} enabled jobs`
        : 'No live schedules';
    $('#stat-uptime').textContent = truthSource;
    $('#stat-truth-change').textContent = truthUpdatedAt ? `Updated ${Utils.formatTime(truthUpdatedAt)}` : 'No canonical timestamp';
    renderTruthProvenance(truth);
    
    // Active agents
    $('#dashboard-agents').innerHTML = agents.length
        ? agents.slice(0, 3).map(a => Components.agentCardMini(a)).join('')
        : emptyState('No active runtime agents');
    
    // Activity feed
    const activityItems = activityFeedItems(notifications, logs);
    $('#activity-feed').innerHTML = activityItems.length
        ? activityItems.map(item => Components.activityItem(item)).join('')
        : emptyState('No recent activity');
    
    // Health grid
    $('#health-grid').innerHTML = components.length
        ? components.slice(0, 4).map(c => Components.healthItem(c)).join('')
        : emptyState('No component health data');
    
    // Update badge
    $('#task-badge').textContent = pendingTasks;
}

// Tasks
function renderTasks() {
    const filter = store.get('taskFilter');
    let tasks = normalizeTaskList(store.get('tasks'));
    
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
            container.innerHTML = taskList.length > 0
                ? taskList.map(t => Components.taskCard(t)).join('')
                : '<div class="task-empty">No tasks</div>';
        }
    });
}

// Agents
function renderAgents() {
    const agents = store.get('agents');
    const container = $('#agents-grid-full');
    if (!container) return;
    container.innerHTML = agents.length
        ? agents.map(a => Components.agentCardFull(a)).join('')
        : emptyState('No active agent work is visible right now.');
    container.querySelectorAll('[data-agent-action]').forEach((button) => {
        button.addEventListener('click', async () => {
            await controlAgent(button.dataset.agentId, button.dataset.agentAction);
        });
    });
}

function renderAgentsGrid() {
    renderAgents();
}

// Schedule
function renderSchedule() {
    const jobs = store.get('scheduledJobs');
    
    // Week grid
    const weekStart = store.get('currentWeekStart') || getWeekStart(new Date());
    store.set('currentWeekStart', weekStart);
    
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const headerHtml = days.map(d => `<div class="schedule-day-header">${d}</div>`).join('');
    
    $('#schedule-grid').innerHTML = headerHtml + Components.weekGrid(weekStart);
    
    // Jobs list
    $('#jobs-list').innerHTML = jobs.length
        ? jobs.map(j => Components.jobItem(j)).join('')
        : emptyState('No scheduled jobs found');
    
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

async function renderSymbiote(force = false) {
    if (!symbioteCache || force) {
        try {
            const payload = await fetchContract('/api/symbiote');
            if (!payload || payload.ok !== true) {
                throw new Error(payload?.error?.message || 'symbiote unavailable');
            }
            symbioteCache = payload.data || {};
        } catch (error) {
            symbioteCache = null;
            const grid = $('#symbiote-grid');
            if (grid) {
                grid.innerHTML = '<div class="task-empty">Unable to load symbiote data</div>';
            }
            return;
        }
    }

    const data = symbioteCache;
    if (!data) return;

    const titleEl = $('#symbiote-title');
    const subtitleEl = $('#symbiote-subtitle');
    const countEl = $('#symbiote-section-count');
    const filedEl = $('#symbiote-filed');
    if (titleEl) titleEl.textContent = String(data.title || 'Collective Intelligence Symbiote');
    if (subtitleEl) subtitleEl.textContent = String(data.subtitle || '');
    if (countEl) countEl.textContent = `${Number(data.section_count || 0) || 0} sections`;
    if (filedEl) filedEl.textContent = `filed ${String(data.filed || 'unknown')}`;

    const dimensionColors = {
        think: 'var(--accent-primary)',
        feel: '#f43f5e',
        remember: '#f59e0b',
        coordinate: '#06b6d4',
        evolve: 'var(--success)'
    };

    const dimensionsEl = $('#symbiote-dimensions');
    if (dimensionsEl) {
        dimensionsEl.innerHTML = (Array.isArray(data.dimensions) ? data.dimensions : []).map((dimension) => `
            <div class="sym-dim-card" style="--dim-clr:${dimensionColors[dimension.id] || 'var(--accent-primary)'}">
                <div class="sym-dim-emoji">${escapeHtml(dimension.emoji || '•')}</div>
                <div class="sym-dim-label">${escapeHtml(dimension.label || 'Dimension')}</div>
                <div class="sym-dim-count">${escapeHtml(dimension.count || 0)} enhancements</div>
                <div class="sym-dim-desc">${escapeHtml(dimension.desc || '')}</div>
            </div>
        `).join('');
    }

    const phaseLabels = ['', 'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4'];
    const statusLabels = {
        designed: { text: 'Designed', cls: 'sym-status-designed' },
        'in-dev': { text: 'In Dev', cls: 'sym-status-indev' },
        live: { text: 'Live', cls: 'sym-status-live' }
    };
    const gridEl = $('#symbiote-grid');
    if (gridEl) {
        gridEl.innerHTML = (Array.isArray(data.enhancements) ? data.enhancements : []).map((item) => {
            const color = dimensionColors[item.dimension] || 'var(--accent-primary)';
            const statusLabel = statusLabels[item.status] || statusLabels.designed;
            const invBadge = item.inv ? `<span class="sym-inv-badge">${escapeHtml(item.inv)}</span>` : '';
            return `
                <div class="sym-card phase-border-${escapeHtml(item.phase || '')}" style="--card-clr:${color}">
                    <div class="sym-card-top">
                        <span class="sym-card-num">${escapeHtml(String(item.id || '').padStart(2, '0'))}</span>
                        <span class="sym-card-code">${escapeHtml(item.code || '')}</span>
                        <span class="sym-dim-badge" style="background:${color}22;color:${color}">${escapeHtml(item.dimension || '')}</span>
                        <span class="${statusLabel.cls} sym-status-badge">${statusLabel.text}</span>
                    </div>
                    <div class="sym-card-name">${escapeHtml(item.name || 'Untitled enhancement')}</div>
                    <div class="sym-card-pitch">${escapeHtml(item.pitch || '')}</div>
                    <div class="sym-card-footer">
                        <span class="sym-phase-tag phase-tag-${escapeHtml(item.phase || '')}">${escapeHtml(phaseLabels[item.phase] || `Phase ${item.phase || '?'}`)}</span>
                        <span class="sym-owner">→ ${escapeHtml(item.owner || 'unassigned')}</span>
                        ${invBadge}
                    </div>
                    <div class="sym-metric">
                        <span class="sym-metric-label">metric</span>
                        <span class="sym-metric-value">${escapeHtml(item.metric_value ?? item.key_metric ?? '')}</span>
                    </div>
                </div>
            `;
        }).join('') || emptyState('No symbiote enhancements available');
    }

    const roadmapEl = $('#roadmap-phases');
    const phaseStatusIcon = { next: '▶', planned: '○', live: '✓', done: '✓' };
    if (roadmapEl) {
        roadmapEl.innerHTML = (Array.isArray(data.roadmap) ? data.roadmap : []).map((phase) => `
            <div class="roadmap-phase roadmap-${escapeHtml(phase.status || 'planned')}">
                <div class="roadmap-phase-header">
                    <span class="roadmap-icon">${phaseStatusIcon[phase.status] || '○'}</span>
                    <span class="roadmap-phase-name">Phase ${escapeHtml(phase.phase || '?')}: ${escapeHtml(phase.name || '')}</span>
                    <span class="roadmap-weeks">Wk ${escapeHtml(phase.weeks || '?')}</span>
                </div>
                <div class="roadmap-tags">
                    ${(Array.isArray(phase.enhancements) ? phase.enhancements : []).map((code) => `<span class="roadmap-code-tag">${escapeHtml(code)}</span>`).join('')}
                </div>
            </div>
        `).join('') || emptyState('No roadmap phases available');
    }

    const questionsEl = $('#questions-list');
    if (questionsEl) {
        questionsEl.innerHTML = (Array.isArray(data.open_questions) ? data.open_questions : []).map((question) => `
            <div class="sym-question">
                <div class="sym-question-meta">
                    <span class="sym-question-for">FOR: ${escapeHtml(question.for_being || 'unknown')}</span>
                    <span class="sym-question-enh">${escapeHtml(question.enhancement || '')}</span>
                </div>
                <div class="sym-question-text">${escapeHtml(question.question || '')}</div>
            </div>
        `).join('') || emptyState('No open questions available');
    }

    const experimentStatusIcon = {
        closed: '✓',
        partial: '◑',
        live: '▶',
        designed: '○',
        pending: '·'
    };
    const experimentsEl = $('#symbiote-experiments');
    if (experimentsEl) {
        experimentsEl.innerHTML = `
            <div class="sym-exp-table">
                ${(Array.isArray(data.experiments) ? data.experiments : []).map((experiment) => `
                    <div class="sym-exp-row sym-exp-${escapeHtml(experiment.status || 'pending')}">
                        <span class="sym-exp-icon">${experimentStatusIcon[experiment.status] || '·'}</span>
                        <span class="sym-exp-id">${escapeHtml(experiment.id || '')}</span>
                        <span class="sym-exp-label sym-exp-lbl-${escapeHtml(experiment.status || 'pending')}">${escapeHtml(experiment.label || '')}</span>
                        <span class="sym-exp-name">${escapeHtml(experiment.name || '')}</span>
                        <span class="sym-exp-result">${escapeHtml(experiment.result || '')}</span>
                        ${experiment.open ? '<span class="sym-exp-open">open</span>' : '<span class="sym-exp-closed">closed</span>'}
                    </div>
                `).join('')}
            </div>
        `;
    }
}

function initOracle() {
    document.querySelectorAll('[data-oracle-surface]').forEach((panel) => {
        if (oracleInitializedPanels.has(panel)) return;
        const input = $('[data-oracle-query]', panel);
        const button = $('[data-oracle-submit]', panel);
        const output = $('[data-oracle-results]', panel);
        const kSelect = $('[data-oracle-k]', panel);
        if (!input || !button || !output || !kSelect) return;

        const runQuery = async () => {
            const query = input.value.trim();
            if (!query) return;
            button.disabled = true;
            output.innerHTML = '<div class="oracle-loading">querying corpus and drafting answer…</div>';
            try {
                const payload = await fetchContract('/api/oracle', {
                    method: 'POST',
                    body: JSON.stringify({
                        q: query,
                        k: parseInt(kSelect.value || '10', 10),
                        answer: true
                    })
                });
                if (!payload || payload.ok !== true || !payload.data) {
                    throw new Error(payload?.error?.message || 'oracle unavailable');
                }
                output.innerHTML = renderOracleResult(payload.data);
            } catch (error) {
                output.innerHTML = `<div class="oracle-error">${escapeHtml(error.message)}</div>`;
            } finally {
                button.disabled = false;
            }
        };

        button.addEventListener('click', runQuery);
        input.addEventListener('keydown', (event) => {
            const isTextarea = input.tagName === 'TEXTAREA';
            if (event.key !== 'Enter') return;
            if (isTextarea && !event.ctrlKey && !event.metaKey) return;
            event.preventDefault();
            runQuery();
        });
        oracleInitializedPanels.add(panel);
    });
}

function renderOracleResult(data) {
    const counts = data.being_counts || {};
    const totalSlots = Number(data.total_slots || 0) || 1;
    const centroid = String(data.centroid || '');
    const results = Array.isArray(data.results) ? data.results : [];
    const k = Number(data.k || results.length) || results.length;
    const sourceKind = String(data.source || '');
    const answer = String(data.answer || '').trim();
    const answerModel = String(data.answer_model || '').trim();
    const answerMode = String(data.answer_mode || '').trim();
    const answerProvider = String(data.answer_provider || '').trim();
    const labelMap = {
        claude_code: 'Claude Code',
        chatgpt: 'ChatGPT',
        grok: 'Grok',
        c_lawd: 'c_lawd',
        dali: 'Dali',
        lumen: 'Lumen',
        gemini: 'Gemini',
        claude_ext: 'Claude (ext)',
        jeebs: 'jeebs',
        the_correspondence: 'The Correspondence'
    };
    const labels = Object.entries(counts).sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0));
    const bars = labels.map(([being, count]) => {
        const pct = Math.round((Number(count || 0) / totalSlots) * 100);
        return `
            <div class="oracle-bar-row${being === centroid ? ' oracle-centroid' : ''}">
                <span class="oracle-bar-label">${escapeHtml(labelMap[being] || being)}</span>
                <div class="oracle-bar-track"><div class="oracle-bar-fill" style="width:${pct}%"></div></div>
                <span class="oracle-bar-pct">${pct}%${being === centroid ? ' ◀' : ''}</span>
            </div>
        `;
    }).join('');
    const notInTopK = (Array.isArray(data.not_in_top_k) ? data.not_in_top_k : []).map((being) => escapeHtml(labelMap[being] || being)).join(', ');
    const answerMeta = [answerProvider, answerModel, answerMode].filter(Boolean).join(' · ');
    const answerBlock = answer
        ? `
            <div class="oracle-answer-block">
                <div class="oracle-sub">${escapeHtml(answerMeta || 'plain-text answer')}</div>
                <div class="oracle-answer-text">${escapeHtml(answer).replaceAll('\n', '<br>')}</div>
            </div>
        `
        : '';
    const rows = results.map((row, index) => {
        const section = row.section_number_filed || row.canonical_section_number || '?';
        const authors = Array.isArray(row.authors) ? row.authors.join(', ') : String(row.authors || '');
        const date = String(row.created_at || '').slice(0, 10);
        const title = String(row.title || '').trim();
        const snippet = String(row.body || '').replaceAll('\n', ' ').trim();
        const sourceLabel = String(row.source_label || row.corpus_kind || 'System Corpus').trim();
        const location = String(row.location || row.corpus_path || '').trim();
        const metaBits = [escapeHtml(sourceLabel)];
        if (section && section !== '?') {
            metaBits.push(`§${escapeHtml(section)}`);
        }
        if (authors) {
            metaBits.push(`<strong>${escapeHtml(authors)}</strong>`);
        }
        if (date) {
            metaBits.push(escapeHtml(date));
        }
        const locationLine = location
            ? `<div class="oracle-result-location">${escapeHtml(location)}</div>`
            : '';
        return `
            <div class="oracle-result-row">
                <span class="oracle-result-num">[${index + 1}]</span>
                <div class="oracle-result-body">
                    <div class="oracle-result-meta">${metaBits.join(' · ')}${title ? ` — ${escapeHtml(title)}` : ''}</div>
                    <div class="oracle-result-snip">${escapeHtml(snippet)}</div>
                    ${locationLine}
                </div>
            </div>
        `;
    }).join('');
    const resultSub = sourceKind.includes('system_corpus')
        ? `top ${results.length} results from the local system corpus`
        : `top ${results.length} sections by semantic distance`;
    return `
        ${answerBlock}
        <div class="oracle-being-weights">
            <div class="oracle-sub">being weight in top-${escapeHtml(String(k))}</div>
            ${bars || '<div class="oracle-loading">No beings ranked for this query.</div>'}
            ${notInTopK ? `<div class="oracle-not-in-k">not ranked: ${notInTopK}</div>` : ''}
        </div>
        <div class="oracle-top-results">
            <div class="oracle-sub">${escapeHtml(resultSub)}</div>
            ${rows || '<div class="oracle-loading">No matching corpus sections found.</div>'}
        </div>
    `;
}

// Health
function renderHealth() {
    const metrics = store.get('healthMetrics') || {};
    const components = store.get('components');
    
    // Metrics
    updateMetricCard('cpu', metrics.cpu, 80);
    updateMetricCard('memory', metrics.memory, 80);
    updateMetricCard('disk', metrics.disk, 90);
    updateMetricCard('gpu', metrics.gpu, 90);
    
    // Components
    $('#components-grid').innerHTML = components.length
        ? components.map(c => Components.componentCard(c)).join('')
        : emptyState('No component status available');
}

function updateMetricCard(type, value, threshold) {
    const status = value > threshold ? 'error' : value > threshold * 0.8 ? 'warning' : 'healthy';
    const metricId = type === 'memory' ? 'mem' : type;
    const metricEl = $(`#metric-${metricId}`);
    const barEl = $(`#${metricId}-bar`);
    const statusEl = $(`#${metricId}-status`);
    if (!metricEl || !barEl || !statusEl) return;
    metricEl.textContent = type === 'gpu' ? value : `${value}%`;
    barEl.style.width = `${Math.min(value, 100)}%`;
    statusEl.textContent = status;
    statusEl.className = `metric-status ${status}`;
}

// Logs
function renderLogs() {
    const logs = store.get('logs') || [];
    const filter = store.get('logFilter') || 'all';
    
    let filteredLogs = logs;
    if (filter !== 'all') {
        filteredLogs = logs.filter(l => l.level === filter);
    }
    
    $('#logs-list').innerHTML = filteredLogs.length
        ? filteredLogs.map(l => Components.logEntry(l)).join('')
        : emptyState(filter === 'all' ? 'No recent logs' : `No ${filter} logs`);
}

async function refreshLogs() {
    await refreshAll();
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
            const id = item.dataset.id;
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
            if (!taskId || !newStatus) return;
            try {
                await api.updateTask(taskId, { status: newStatus });
                await refreshAll();
            } catch (error) {
                Toast.error(`Failed to move task: ${error.message}`);
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
    const assigneeValue = Array.isArray(store.get('agents')) && store.get('agents').length
        ? store.get('agents')[0].name
        : '';
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
                <option value="critical">Critical</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Owner</label>
            <input type="text" class="form-input" id="new-task-assignee" placeholder="Optional owner or lane" value="${assigneeValue}">
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
    
    if (!title) {
        Toast.error('Please enter a task title');
        return;
    }
    
    try {
        await api.createTask({
            title,
            description: desc,
            priority,
            assignee,
            status: 'backlog'
        });
        Modal.close();
        await refreshAll();
        Toast.success('Task created successfully');
    } catch (error) {
        Toast.error(`Failed to create task: ${error.message}`);
    }
}

function openScheduleModal() {
    const content = `
        <div class="form-group">
            <label class="form-label">Schedule Name</label>
            <input type="text" class="form-input" id="schedule-job-name" placeholder="Daily review">
        </div>
        <div class="form-group">
            <label class="form-label">Message</label>
            <textarea class="form-textarea" id="schedule-job-message" placeholder="What should the agent do?"></textarea>
        </div>
        <div class="form-group">
            <label class="form-label">Mode</label>
            <select class="form-select" id="schedule-job-mode">
                <option value="cron" selected>Cron</option>
                <option value="every">Every</option>
                <option value="at">At</option>
            </select>
        </div>
        <div class="form-group">
            <label class="form-label">Schedule Value</label>
            <input type="text" class="form-input" id="schedule-job-value" placeholder="0 9 * * *">
        </div>
        <div class="form-group">
            <label class="form-label">Agent</label>
            <input type="text" class="form-input" id="schedule-job-agent" value="main" placeholder="main">
        </div>
        <div class="form-group">
            <label class="form-label">Timezone</label>
            <input type="text" class="form-input" id="schedule-job-tz" value="Australia/Brisbane" placeholder="Australia/Brisbane">
        </div>
    `;

    const footer = `
        <button class="btn btn-secondary" onclick="Modal.close()">Cancel</button>
        <button class="btn btn-primary" onclick="createScheduledJob()">Create Schedule</button>
    `;

    Modal.open('Create Scheduled Job', content, footer);
}

async function createScheduledJob() {
    const name = $('#schedule-job-name')?.value?.trim();
    const message = $('#schedule-job-message')?.value?.trim();
    const mode = $('#schedule-job-mode')?.value || 'cron';
    const schedule = $('#schedule-job-value')?.value?.trim();
    const agent_id = $('#schedule-job-agent')?.value?.trim() || 'main';
    const tz = $('#schedule-job-tz')?.value?.trim();

    if (!name || !message || !schedule) {
        Toast.error('Schedule name, message, and value are required');
        return;
    }

    try {
        await api.createScheduledJob({ name, message, mode, schedule, agent_id, tz });
        Modal.close();
        await refreshAll();
        Toast.success('Schedule created successfully');
    } catch (error) {
        Toast.error(`Failed to create schedule: ${error.message}`);
    }
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
    try {
        const status = await api.getStatus();
        applyStatusPayload(status);
        updateStatusIndicators(store.get('connected'));
    } catch (error) {
        console.warn('Status refresh failed', error);
        store.set('connected', false);
        updateStatusIndicators(false);
    }
    renderView(currentView);
    renderDashboard();
    renderNotifications();
}

// Actions
async function restartGateway() {
    Modal.confirm(
        'Restart Gateway',
        'Are you sure you want to restart the gateway? This will briefly interrupt all connections.',
        async () => {
            Toast.info('Restarting gateway...');
            try {
                const payload = await api.restartGateway();
                Toast.success('Gateway restarted successfully');
                setTimeout(() => refreshAll(), 1500);
                if (payload?.summary) {
                    Toast.info(payload.summary);
                }
            } catch (e) {
                Toast.error(`Failed to restart gateway: ${e.message}`);
            }
        }
    );
}

async function runHealthCheck() {
    Toast.info('Running health check...');
    try {
        const payload = await api.runHealthCheck();
        if (payload?.metrics) {
            store.set('healthMetrics', normalizeHealthMetrics(payload.metrics));
        }
        if (Array.isArray(payload?.components)) {
            store.set('components', payload.components);
        }
        if (typeof payload?.gateway_connected === 'boolean') {
            store.set('connected', payload.gateway_connected);
        }
        Toast.success('Health check complete');
        updateStatusIndicators(store.get('connected'));
        renderHealth();
    } catch (e) {
        Toast.error(`Health check failed: ${e.message}`);
    }
}

async function controlAgent(agentId, action) {
    if (!agentId || !action) return;
    Modal.confirm(
        `${action[0].toUpperCase()}${action.slice(1)} Agent Work`,
        `Run ${action} on ${agentId}?`,
        async () => {
            Toast.info(`${action} requested for ${agentId}`);
            try {
                const payload = await api.controlAgent(agentId, action);
                Toast.success(payload?.summary || `${action} completed`);
                await refreshAll();
            } catch (error) {
                Toast.error(`Agent control failed: ${error.message}`);
            }
        }
    );
}

// Update status indicators
function updateStatusIndicators(connected = store.get('connected')) {
    const gateway = $('#gateway-status');
    const text = $('#gateway-status-text');
    
    if (gateway && text) {
        gateway.classList.toggle('connected', connected);
        gateway.classList.toggle('error', !connected);
        text.textContent = connected ? 'Connected' : 'Disconnected';
    }
}

function applyStatusPayload(status) {
    store.set('connected', Boolean(status.gateway_connected));
    store.set('agents', normalizeAgentList(status.agents || []));
    store.set('tasks', normalizeTaskList(status.tasks || []));
    store.set('scheduledJobs', normalizeScheduleJobList(status.scheduled_jobs || []));
    store.set('memorySystem', status.memory_system || {});
    store.set('healthMetrics', normalizeHealthMetrics(status.health_metrics));
    store.set('components', status.components || []);
    store.set('notifications', normalizeNotificationList(status.notifications || []));
    store.set('unreadCount', (store.get('notifications') || []).filter((notification) => !notification.read).length);
    store.set('logs', normalizeLogList(status.logs || []));
    store.set('truth', status.truth || {});
    store.set('lastUpdate', status.last_update || null);
}

function renderTruthProvenance(truth = store.get('truth') || {}) {
    const banner = $('#truth-provenance-banner');
    if (!banner) return;
    const source = truth.source || 'runtime_state';
    const path = truth.source_mission_path || 'n/a';
    const updatedAt = truth.source_mission_updated_at || store.get('lastUpdate') || 'unknown';
    banner.textContent = `Truth source: ${source} · Canonical file: ${path} · Updated: ${updatedAt}`;
}

async function loadInitialState() {
    try {
        const status = await api.getStatus();
        applyStatusPayload(status);
        updateStatusIndicators(store.get('connected'));
    } catch (error) {
        console.warn('Failed to load live state', error);
        store.set('agents', []);
        store.set('tasks', []);
        store.set('scheduledJobs', []);
        store.set('memorySystem', {});
        store.set('healthMetrics', normalizeHealthMetrics({}));
        store.set('components', []);
        store.set('logs', []);
        store.set('notifications', []);
        store.set('unreadCount', 0);
        store.set('truth', {});
        store.set('lastUpdate', null);
        store.set('connected', false);
        updateStatusIndicators(false);
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
window.openScheduleModal = openScheduleModal;
window.createScheduledJob = createScheduledJob;
window.Modal = Modal;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
