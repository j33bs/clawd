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
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
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

// Mock API for demo (when gateway is not available)
class MockAPIClient extends APIClient {
    constructor() {
        super();
        this.connected = false;
    }
    
    async getStatus() {
        return {
            gateway: {
                status: 'running',
                uptime: 604800,
                version: '2026.2.15'
            },
            agents: store.get('agents'),
            tasks: store.get('tasks')
        };
    }
    
    async getHealth() {
        return {
            cpu: Math.floor(Math.random() * 60) + 20,
            memory: Math.floor(Math.random() * 40) + 40,
            disk: Math.floor(Math.random() * 30) + 30,
            gpu: Math.floor(Math.random() * 50) + 30
        };
    }
    
    async restartGateway() {
        await new Promise(r => setTimeout(r, 1000));
        return { success: true };
    }
    
    async runHealthCheck() {
        await new Promise(r => setTimeout(r, 1500));
        return { success: true, results: store.get('components') };
    }
}

// Use mock API in demo mode
const mockApi = new MockAPIClient();
