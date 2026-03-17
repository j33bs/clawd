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
        this.state = {
            // Navigation
            currentView: 'dashboard',
            
            // System
            connected: false,
            gatewayStatus: 'connecting',
            truth: {},
            lastUpdate: null,
            
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
            
            // Notifications
            notifications: [],
            unreadCount: 0,
            
            // Settings
            settings: {
                theme: 'dark',
                autoRefresh: true,
                refreshInterval: 10000,
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
            String(n.id) === String(id) ? { ...n, read: true } : n
        );
        this.set('notifications', notifications);
        this.set('unreadCount', notifications.filter((notification) => !notification.read).length);
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
}

// Create global store instance
const store = new Store();
