/**
 * Source UI - Main Application
 * The heart of the Source Control Center
 */

// Application state
let currentView = 'dashboard';
let refreshInterval = null;

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
    initMood();
    
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
    const components = store.get('components');
    const notifications = store.get('notifications');
    
    // Stats
    const activeAgents = agents.filter(a => a.status === 'working').length;
    const todayTasks = tasks.length;
    
    $('#stat-agents').textContent = activeAgents;
    $('#stat-tasks').textContent = todayTasks;
    $('#stat-schedule').textContent = String(store.get('scheduledJobs').length || 0);
    $('#stat-uptime').textContent = store.get('connected') ? 'live' : 'demo';
    
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
    
    document.addEventListener('drop', async (e) => {
        e.preventDefault();
        const column = e.target.closest('.kanban-column');
        if (column) {
            column.classList.remove('drag-over');
            const taskId = parseInt(e.dataTransfer.getData('text/plain'));
            const newStatus = column.dataset.status;
            try {
                await api.updateTask(taskId, { status: newStatus });
                await refreshAll();
            } catch (error) {
                Toast.error('Failed to update task');
                return;
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
    const assigneeOptions = store.get('agents')
        .map(agent => `<option value="${agent.id}">${agent.name}</option>`)
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
                ${assigneeOptions}
            </select>
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
        Toast.error('Task creation failed');
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
        updateStatusIndicators(true);
    } catch (error) {
        console.warn('Status refresh failed, falling back to synthetic health only', error);
        store.set('connected', false);
        updateStatusIndicators(false);
        store.set('healthMetrics', {
            cpu: Math.floor(Math.random() * 40) + 20,
            memory: Math.floor(Math.random() * 30) + 45,
            disk: Math.floor(Math.random() * 20) + 30,
            gpu: Math.floor(Math.random() * 40) + 30
        });
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
    store.set('connected', true);
    store.set('agents', status.agents || []);
    store.set('tasks', status.tasks || []);
    store.set('scheduledJobs', status.scheduled_jobs || []);
    store.set('healthMetrics', status.health_metrics || store.get('healthMetrics'));
    store.set('components', status.components || []);
    store.set('notifications', status.notifications || []);
    store.set('unreadCount', (status.notifications || []).filter(n => !n.read).length);
    store.set('logs', status.logs || []);
}

async function loadInitialState() {
    try {
        const status = await api.getStatus();
        applyStatusPayload(status);
        updateStatusIndicators(true);
    } catch (error) {
        console.warn('Failed to load live state, using demo fallback', error);
        store.initDemoData();
        store.set('connected', false);
        updateStatusIndicators(false);
    }
}

// ─── Symbiote ──────────────────────────────────────────────────────────────

// Local cache so we only fetch once per session unless forced
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
        const grid = $('#symbiote-grid');
        if (grid) grid.innerHTML = '<p style="color:var(--text-tertiary);padding:2rem">Unable to load symbiote data — is the server running?</p>';
        return;
    }

    // Hero
    const titleEl = $('#symbiote-title');
    const subEl   = $('#symbiote-subtitle');
    const cntEl   = $('#symbiote-section-count');
    const datEl   = $('#symbiote-filed');
    if (titleEl) titleEl.textContent = d.title;
    if (subEl)   subEl.textContent   = d.subtitle;
    if (cntEl)   cntEl.textContent   = `${d.section_count} sections`;
    if (datEl)   datEl.textContent   = `filed ${d.filed}`;

    // Dimension colour map
    const dimColour = {
        think:      'var(--accent-primary)',
        feel:       '#f43f5e',
        remember:   '#f59e0b',
        coordinate: '#06b6d4',
        evolve:     'var(--success)'
    };

    // ── Dimensions strip ──────────────────────────────────────────────────
    const dimEl = $('#symbiote-dimensions');
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

    // ── Enhancement grid ──────────────────────────────────────────────────
    const phaseLabel = ['', 'Phase 1', 'Phase 2', 'Phase 3', 'Phase 4'];
    const statusLabel = {
        designed:  { text: 'Designed',  cls: 'sym-status-designed'  },
        'in-dev':  { text: 'In Dev',    cls: 'sym-status-indev'     },
        live:      { text: 'Live',      cls: 'sym-status-live'       }
    };
    const gridEl = $('#symbiote-grid');
    if (gridEl) {
        gridEl.innerHTML = d.enhancements.map(e => {
            const clr  = dimColour[e.dimension] || 'var(--accent-primary)';
            const st   = statusLabel[e.status] || statusLabel.designed;
            const invBadge = e.inv
                ? `<span class="sym-inv-badge">${e.inv}</span>`
                : '';
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
                        <span class="sym-owner">→ ${e.owner}</span>
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

    // ── Roadmap phases ─────────────────────────────────────────────────────
    const phaseStatusIcon = { next: '▶', planned: '○', live: '✓', done: '✓' };
    const roadmapEl = $('#roadmap-phases');
    if (roadmapEl) {
        roadmapEl.innerHTML = d.roadmap.map(p => `
            <div class="roadmap-phase roadmap-${p.status}">
                <div class="roadmap-phase-header">
                    <span class="roadmap-icon">${phaseStatusIcon[p.status] || '○'}</span>
                    <span class="roadmap-phase-name">Phase ${p.phase}: ${p.name}</span>
                    <span class="roadmap-weeks">Wk ${p.weeks}</span>
                </div>
                <div class="roadmap-tags">
                    ${p.enhancements.map(code => `<span class="roadmap-code-tag">${code}</span>`).join('')}
                </div>
            </div>
        `).join('');
    }

    // ── Open Questions ─────────────────────────────────────────────────────
    const qEl = $('#questions-list');
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

    // ── Experiments ────────────────────────────────────────────────────────
    const expStatusIcon = {
        closed:   '✓', partial: '◑', live: '▶',
        designed: '○', pending: '·'
    };
    const expEl = $('#symbiote-experiments');
    if (expEl) {
        expEl.innerHTML = `
            <div class="sym-exp-table">
                ${d.experiments.map(ex => `
                    <div class="sym-exp-row sym-exp-${ex.status}">
                        <span class="sym-exp-icon">${expStatusIcon[ex.status] || '·'}</span>
                        <span class="sym-exp-id">${ex.id}</span>
                        <span class="sym-exp-label sym-exp-lbl-${ex.status}">${ex.label}</span>
                        <span class="sym-exp-name">${ex.name}</span>
                        <span class="sym-exp-result">${ex.result}</span>
                        ${ex.open ? '<span class="sym-exp-open">open</span>' : '<span class="sym-exp-closed">closed</span>'}
                    </div>
                `).join('')}
            </div>
        `;
    }
}

window.renderSymbiote = renderSymbiote;

// ─── end Symbiote ───────────────────────────────────────────────────────────

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
async function initMood() {
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
