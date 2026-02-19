/**
 * Source UI - Utilities
 */

const Utils = {
    // Formatting
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
        
        return date.toLocaleDateString();
    },
    
    formatDate(timestamp) {
        return new Date(timestamp).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    formatDuration(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
        return `${Math.floor(seconds / 86400)}d`;
    },
    
    formatNumber(num) {
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
        return num.toString();
    },
    
    formatPercent(value, decimals = 0) {
        return `${value.toFixed(decimals)}%`;
    },
    
    // DOM helpers
    $(selector, context = document) {
        return context.querySelector(selector);
    },
    
    $$(selector, context = document) {
        return Array.from(context.querySelectorAll(selector));
    },
    
    createElement(tag, props = {}, children = []) {
        const element = document.createElement(tag);
        
        Object.entries(props).forEach(([key, value]) => {
            if (key === 'className') {
                element.className = value;
            } else if (key === 'style' && typeof value === 'object') {
                Object.assign(element.style, value);
            } else if (key.startsWith('on') && typeof value === 'function') {
                element.addEventListener(key.slice(2).toLowerCase(), value);
            } else if (key === 'dataset') {
                Object.entries(value).forEach(([dataKey, dataValue]) => {
                    element.dataset[dataKey] = dataValue;
                });
            } else if (key === 'innerHTML') {
                element.innerHTML = value;
            } else {
                element.setAttribute(key, value);
            }
        });
        
        children.forEach(child => {
            if (typeof child === 'string') {
                element.appendChild(document.createTextNode(child));
            } else if (child instanceof Node) {
                element.appendChild(child);
            }
        });
        
        return element;
    },
    
    // Storage
    storage: {
        get(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch {
                return defaultValue;
            }
        },
        
        set(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
                return true;
            } catch {
                return false;
            }
        },
        
        remove(key) {
            try {
                localStorage.removeItem(key);
                return true;
            } catch {
                return false;
            }
        }
    },
    
    // Debounce
    debounce(fn, delay = 300) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => fn(...args), delay);
        };
    },
    
    // Throttle
    throttle(fn, limit = 100) {
        let inThrottle;
        return (...args) => {
            if (!inThrottle) {
                fn(...args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },
    
    // Random ID
    randomId() {
        return Math.random().toString(36).substring(2, 15);
    },
    
    // Clone object
    clone(obj) {
        return JSON.parse(JSON.stringify(obj));
    },
    
    // Keyboard shortcuts
    parseShortcut(event) {
        const parts = [];
        if (event.metaKey || event.ctrlKey) parts.push('Cmd');
        if (event.shiftKey) parts.push('Shift');
        if (event.altKey) parts.push('Alt');
        if (event.key && !['Control', 'Shift', 'Alt', 'Meta'].includes(event.key)) {
            parts.push(event.key.toUpperCase());
        }
        return parts.join('+');
    },
    
    // Notifications
    notify(title, options = {}) {
        if (!('Notification' in window)) return;
        
        if (Notification.permission === 'granted') {
            new Notification(title, options);
        } else if (Notification.permission !== 'denied') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    new Notification(title, options);
                }
            });
        }
    },
    
    // Copy to clipboard
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch {
            // Fallback
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            return true;
        }
    },
    
    // Cron helper
    describeCron(cron) {
        const parts = cron.split(' ');
        if (parts.length !== 5) return cron;
        
        const [minute, hour, day, month, weekday] = parts;
        
        if (minute === '0' && hour === '0' && day === '*' && month === '*') {
            return 'Daily at midnight';
        }
        if (minute === '0' && hour === '9' && day === '*' && month === '*') {
            return 'Daily at 9:00 AM';
        }
        if (minute === '0' && hour === '9' && day === '*' && month === '*' && weekday === '1') {
            return 'Weekly on Monday at 9:00 AM';
        }
        if (cron.startsWith('*/')) {
            return `Every ${cron.slice(2)} minutes`;
        }
        
        return cron;
    }
};

// Toast notification system
const Toast = {
    container: null,
    
    init() {
        this.container = $('#toast-container');
    },
    
    show(message, type = 'info', duration = 4000) {
        if (!this.container) this.init();
        
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        
        const toast = Utils.createElement('div', { className: 'toast' }, [
            Utils.createElement('div', { className: `toast-icon ${type}` }, [icons[type]]),
            Utils.createElement('div', { className: 'toast-content' }, [
                Utils.createElement('div', { className: 'toast-message' }, [message])
            ]),
            Utils.createElement('span', { 
                className: 'toast-close',
                onClick: () => this.remove(toast)
            }, ['×'])
        ]);
        
        this.container.appendChild(toast);
        
        setTimeout(() => this.remove(toast), duration);
        
        return toast;
    },
    
    remove(toast) {
        if (!toast || !toast.parentNode) return;
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    },
    
    success(message) { return this.show(message, 'success'); },
    error(message) { return this.show(message, 'error'); },
    warning(message) { return this.show(message, 'warning'); },
    info(message) { return this.show(message, 'info'); }
};

// Modal system
const Modal = {
    overlay: null,
    
    init() {
        this.overlay = $('#modal-overlay');
        $('#modal-close').addEventListener('click', () => this.close());
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) this.close();
        });
    },
    
    open(title, content, footer = '') {
        if (!this.overlay) this.init();
        
        $('#modal-title').innerHTML = title;
        $('#modal-body').innerHTML = content;
        $('#modal-footer').innerHTML = footer;
        
        this.overlay.classList.add('open');
        document.body.style.overflow = 'hidden';
        
        // Focus first input
        const firstInput = $('#modal-body .form-input, #modal-body .form-select');
        if (firstInput) firstInput.focus();
    },
    
    close() {
        if (!this.overlay) return;
        this.overlay.classList.remove('open');
        document.body.style.overflow = '';
    },
    
    confirm(title, message, onConfirm, onCancel) {
        const content = `<p>${message}</p>`;
        const footer = `
            <button class="btn btn-secondary" onclick="Modal.close()">Cancel</button>
            <button class="btn btn-primary" id="modal-confirm-btn">Confirm</button>
        `;
        
        this.open(title, content, footer);
        
        $('#modal-confirm-btn').addEventListener('click', () => {
            this.close();
            if (onConfirm) onConfirm();
        });
    },
    
    alert(title, message, onClose) {
        const content = `<p>${message}</p>`;
        const footer = `<button class="btn btn-primary" onclick="Modal.close()">OK</button>`;
        
        this.open(title, content, footer);
        
        if (onClose) {
            this.overlay.addEventListener('click', () => {
                this.close();
                onClose();
            }, { once: true });
        }
    }
};

// Command Palette
const CommandPalette = {
    element: null,
    input: null,
    results: null,
    commands: [],
    
    init() {
        this.element = $('#command-palette');
        this.input = $('#command-input');
        this.results = $('#command-results');
        
        // Default commands
        this.commands = [
            { id: 'dashboard', title: 'Go to Dashboard', shortcut: 'G D', action: () => navigateTo('dashboard') },
            { id: 'tasks', title: 'Go to Tasks', shortcut: 'G T', action: () => navigateTo('tasks') },
            { id: 'agents', title: 'Go to Agents', shortcut: 'G A', action: () => navigateTo('agents') },
            { id: 'schedule', title: 'Go to Schedule', shortcut: 'G S', action: () => navigateTo('schedule') },
            { id: 'health', title: 'Go to Health', shortcut: 'G H', action: () => navigateTo('health') },
            { id: 'settings', title: 'Go to Settings', shortcut: 'G S', action: () => navigateTo('settings') },
            { id: 'new-task', title: 'Create New Task', shortcut: 'N', action: () => openNewTaskModal() },
            { id: 'restart', title: 'Restart Gateway', action: () => restartGateway() },
            { id: 'health-check', title: 'Run Health Check', action: () => runHealthCheck() },
            { id: 'toggle-theme', title: 'Toggle Theme', shortcut: 'T', action: () => toggleTheme() },
            { id: 'refresh', title: 'Refresh Data', shortcut: 'R', action: () => refreshAll() }
        ];
        
        // Open on Cmd+K
        document.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                this.open();
            }
            if (e.key === 'Escape' && this.element.classList.contains('open')) {
                this.close();
            }
        });
        
        // Close on overlay click
        this.element.querySelector('.command-palette-overlay').addEventListener('click', () => this.close());
        
        // Search
        this.input.addEventListener('input', () => this.search(this.input.value));
        
        // Keyboard navigation
        this.input.addEventListener('keydown', (e) => {
            const selected = this.results.querySelector('.selected');
            const items = this.results.querySelectorAll('.command-result');
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (selected) selected.classList.remove('selected');
                const next = selected ? selected.nextElementSibling : items[0];
                if (next) next.classList.add('selected');
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (selected) selected.classList.remove('selected');
                const prev = selected ? selected.previousElementSibling : items[items.length - 1];
                if (prev) prev.classList.add('selected');
            }
            if (e.key === 'Enter' && selected) {
                e.preventDefault();
                const command = this.commands.find(c => c.id === selected.dataset.id);
                if (command) {
                    this.close();
                    command.action();
                }
            }
        });
    },
    
    open() {
        this.element.classList.add('open');
        this.input.value = '';
        this.search('');
        this.input.focus();
    },
    
    close() {
        this.element.classList.remove('open');
    },
    
    search(query) {
        const filtered = query 
            ? this.commands.filter(c => c.title.toLowerCase().includes(query.toLowerCase()))
            : this.commands;
        
        this.results.innerHTML = filtered.map((command, i) => `
            <div class="command-result ${i === 0 ? 'selected' : ''}" data-id="${command.id}">
                <div class="command-result-icon">${command.title[0]}</div>
                <div class="command-result-info">
                    <div class="command-result-title">${command.title}</div>
                </div>
                ${command.shortcut ? `<kbd class="command-result-shortcut">${command.shortcut}</kbd>` : ''}
            </div>
        `).join('');
        
        this.results.querySelectorAll('.command-result').forEach(el => {
            el.addEventListener('click', () => {
                const command = this.commands.find(c => c.id === el.dataset.id);
                if (command) {
                    this.close();
                    command.action();
                }
            });
        });
    }
};

// Export for global use
window.Utils = Utils;
window.Toast = Toast;
window.Modal = Modal;
window.CommandPalette = CommandPalette;
