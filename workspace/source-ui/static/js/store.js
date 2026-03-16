/**
 * Source UI - State Management
 * Simple reactive store for application state
 */

// Create a simple event emitter
class EventEmitter {
    constructor() {
        this.events = {};
    }
    
    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
        return () => this.off(event, callback);
    }
    
    off(event, callback) {
        if (!this.events[event]) return;
        this.events[event] = this.events[event].filter(cb => cb !== callback);
    }
    
    emit(event, data) {
        if (!this.events[event]) return;
        this.events[event].forEach(callback => callback(data));
    }
}

// Application Store
class Store extends EventEmitter {
    constructor() {
        super();
        this.defaultRefreshInterval = 3000;
        this.state = {
            // Navigation
            currentView: 'dashboard',
            
            // System
            connected: false,
            gatewayStatus: 'connecting',
            displayMode: {
                ok: false,
                profile_current: 'unknown',
                requested_mode: 'auto',
                toggle_target: 'work',
                queue: {
                    pending: 0,
                    review_required: 0,
                    completed: 0,
                    discord_pending: 0,
                    router_pending: 0
                }
            },
            portfolio: {
                generated_at: null,
                projects: [],
                sims: [],
                tasks: [],
                work_items: [],
                discord_bridge: {
                    channels: []
                },
                teamchat: {
                    sessions: []
                }
            },
            
            // Agents
            agents: [],
            
            // Tasks
            tasks: [],
            taskFilter: 'all',
            
            // Schedule
            scheduledJobs: [],
            currentWeekStart: null,
            
            // Health
            healthMetrics: {
                cpu: 0,
                memory: 0,
                disk: 0,
                gpu: 0
            },
            components: [],
            
            // Logs
            logs: [],
            logFilter: 'all',

            // Commands
            commands: [],
            commandReceipts: [],

            // Notifications
            notifications: [],
            unreadCount: 0,
            
            // Settings
            settings: {
                theme: 'dark',
                autoRefresh: true,
                refreshInterval: this.defaultRefreshInterval,
                desktopNotifications: false,
                soundAlerts: false,
                enableFallback: true,
                maxQueueDepth: 5
            }
        };
        
        // Load settings from localStorage
        this.loadSettings();
    }
    
    get(key) {
        return key.split('.').reduce((obj, k) => obj && obj[k], this.state);
    }
    
    set(key, value) {
        const keys = key.split('.');
        const lastKey = keys.pop();
        const target = keys.reduce((obj, k) => {
            if (!obj[k]) obj[k] = {};
            return obj[k];
        }, this.state);
        target[lastKey] = value;
        this.emit('change', { key, value });
    }
    
    update(key, updates) {
        const current = this.get(key);
        this.set(key, { ...current, ...updates });
    }
    
    // Agent methods
    addAgent(agent) {
        const agents = [...this.state.agents, agent];
        this.set('agents', agents);
    }
    
    updateAgent(id, updates) {
        const agents = this.state.agents.map(a => 
            a.id === id ? { ...a, ...updates } : a
        );
        this.set('agents', agents);
    }
    
    removeAgent(id) {
        const agents = this.state.agents.filter(a => a.id !== id);
        this.set('agents', agents);
    }
    
    // Task methods
    addTask(task) {
        const tasks = [...this.state.tasks, { ...task, id: Date.now() }];
        this.set('tasks', tasks);
    }
    
    updateTask(id, updates) {
        const tasks = this.state.tasks.map(t => 
            String(t.id) === String(id) ? { ...t, ...updates } : t
        );
        this.set('tasks', tasks);
    }
    
    removeTask(id) {
        const tasks = this.state.tasks.filter(t => String(t.id) !== String(id));
        this.set('tasks', tasks);
    }
    
    moveTask(id, newStatus) {
        this.updateTask(id, { status: newStatus });
    }
    
    // Notification methods
    addNotification(notification) {
        const notifications = [{
            id: Date.now(),
            timestamp: new Date().toISOString(),
            read: false,
            ...notification
        }, ...this.state.notifications];
        
        this.set('notifications', notifications);
        this.set('unreadCount', this.state.unreadCount + 1);
    }
    
    markNotificationRead(id) {
        const notifications = this.state.notifications.map(n => 
            n.id === id ? { ...n, read: true } : n
        );
        this.set('notifications', notifications);
        this.set('unreadCount', Math.max(0, this.state.unreadCount - 1));
    }
    
    clearNotifications() {
        this.set('notifications', []);
        this.set('unreadCount', 0);
    }
    
    // Settings methods
    loadSettings() {
    try {
        const saved = localStorage.getItem('source-ui-settings');
        if (saved) {
            const settings = JSON.parse(saved);
            if (settings.refreshInterval == null || settings.refreshInterval === 10000) {
                settings.refreshInterval = this.defaultRefreshInterval;
            }
            this.set('settings', { ...this.state.settings, ...settings });
        }
    } catch (e) {
        console.warn('Failed to load settings:', e);
    }
}
    
    saveSettings() {
        try {
            localStorage.setItem('source-ui-settings', JSON.stringify(this.state.settings));
        } catch (e) {
            console.warn('Failed to save settings:', e);
        }
    }
    
    updateSetting(key, value) {
        this.set(`settings.${key}`, value);
        this.saveSettings();
    }
    
    // Initialize default tasks for demo
    initDemoData() {
        // Demo agents
        this.set('agents', [
            { id: 'planner', name: 'Planner', model: 'MiniMax-M2.5', status: 'idle', tasksCompleted: 12, cycles: 156 },
            { id: 'coder', name: 'Coder', model: 'Codex', status: 'working', task: 'Implementing Source UI', progress: 65, tasksCompleted: 24, cycles: 89 },
            { id: 'health', name: 'Health Monitor', model: 'MiniMax-M2.5', status: 'idle', tasksCompleted: 8, cycles: 24 },
            { id: 'memory', name: 'Memory Agent', model: 'MiniMax-M2.5', status: 'working', task: 'Indexing memories', progress: 30, tasksCompleted: 15, cycles: 42 }
        ]);
        
        // Tasks are loaded from the canonical JSON store via API.
        this.set('tasks', []);
        
        // Demo scheduled jobs
        this.set('scheduledJobs', [
            { id: 1, name: 'Daily Health Check', cron: '0 9 * * *', nextRun: '9:00 AM', enabled: true },
            { id: 2, name: 'Security Audit', cron: '0 9 * * 1', nextRun: 'Mon 9:00 AM', enabled: true },
            { id: 3, name: 'Memory Cleanup', cron: '0 0 * * *', nextRun: '12:00 AM', enabled: true },
            { id: 4, name: 'Git Auto-commit', cron: '*/15 * * * *', nextRun: 'Every 15min', enabled: true }
        ]);
        
        // Demo health components
        this.set('components', [
            { id: 'gateway', name: 'Gateway', status: 'healthy', details: 'Running on port 18789' },
            { id: 'vllm', name: 'VLLM', status: 'healthy', details: 'Online at localhost:8001' },
            { id: 'telegram', name: 'Telegram', status: 'healthy', details: 'Connected' },
            { id: 'memory', name: 'Memory', status: 'warning', details: 'Low available' },
            { id: 'database', name: 'Database', status: 'healthy', details: 'Connected' },
            { id: 'scheduler', name: 'Scheduler', status: 'healthy', details: '4 jobs active' }
        ]);
        
        // Demo activity
        const now = new Date();
        this.set('notifications', [
            { id: 1, type: 'success', title: 'Task Completed', body: 'Fix memory leak in worker', timestamp: new Date(now - 2 * 60000).toISOString(), read: false },
            { id: 2, type: 'error', title: 'Deploy Failed', body: 'Connection timeout', timestamp: new Date(now - 3600000).toISOString(), read: false },
            { id: 3, type: 'info', title: 'Health Check', body: 'All systems operational', timestamp: new Date(now - 7200000).toISOString(), read: true },
            { id: 4, type: 'success', title: 'Agent Started', body: 'Planner agent is now running', timestamp: new Date(now - 10800000).toISOString(), read: true }
        ]);
        
        this.set('unreadCount', 2);
    }
}

// Create global store instance
const store = new Store();
