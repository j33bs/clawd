/**
 * Source UI - API Client
 * Handles communication with OpenClaw Gateway
 */

class APIClient {
    constructor(baseUrl = null) {
        this.baseUrl = baseUrl || this.detectGatewayUrl();
        this.token = null;
        this.pollInterval = null;
    }
    
    detectGatewayUrl() {
        // Try to detect the gateway URL from the current location
        const protocol = window.location.protocol;
        const host = window.location.host;
        return `${protocol}//${host}`;
    }
    
    setToken(token) {
        this.token = token;
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        try {
            const response = await fetch(url, {
                ...options,
                headers
            });
            const contentType = response.headers.get('content-type');
            let payload = null;
            if (contentType && contentType.includes('application/json')) {
                payload = await response.json();
            } else {
                payload = await response.text();
            }
            if (!response.ok) {
                const message = typeof payload === 'object' && payload !== null
                    ? (payload.error || payload.message || `HTTP ${response.status}: ${response.statusText}`)
                    : `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(String(message));
            }
            return payload;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }
    
    // Gateway Status
    async getStatus() {
        return this.request('/api/status');
    }
    
    async getHealth() {
        return this.request('/api/health');
    }
    
    // Agents
    async getAgents() {
        return this.request('/api/agents');
    }
    
    async getAgent(id) {
        return this.request(`/api/agents/${id}`);
    }
    
    async controlAgent(id, action) {
        return this.request(`/api/agents/${id}/${action}`, { method: 'POST' });
    }
    
    // Tasks
    async getTasks() {
        return this.request('/api/tasks');
    }
    
    async createTask(task) {
        return this.request('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(task)
        });
    }
    
    async updateTask(id, updates) {
        return this.request(`/api/tasks/${id}`, {
            method: 'PATCH',
            body: JSON.stringify(updates)
        });
    }
    
    async deleteTask(id) {
        return this.request(`/api/tasks/${id}`, { method: 'DELETE' });
    }
    
    // Schedule
    async getScheduledJobs() {
        return this.request('/api/schedule');
    }
    
    async createScheduledJob(job) {
        return this.request('/api/schedule', {
            method: 'POST',
            body: JSON.stringify(job)
        });
    }
    
    async deleteScheduledJob(id) {
        return this.request(`/api/schedule/${id}`, { method: 'DELETE' });
    }
    
    // Logs
    async getLogs(options = {}) {
        const params = new URLSearchParams(options);
        return this.request(`/api/logs?${params}`);
    }
    
    // System
    async restartGateway() {
        return this.request('/api/gateway/restart', { method: 'POST' });
    }
    
    async runHealthCheck() {
        return this.request('/api/health/check', { method: 'POST' });
    }
    
    // Polling helper
    startPolling(callback, interval = 10000) {
        this.stopPolling();
        this.pollInterval = setInterval(callback, interval);
    }
    
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }
}

// Create global API client
const api = new APIClient();
