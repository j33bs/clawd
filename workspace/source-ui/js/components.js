/**
 * Source UI - Components
 * Reusable UI components
 */

const Components = {
    // Stat Card
    statCard(label, value, change = '', iconClass = '', changeType = '') {
        return `
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-label">${label}</span>
                    <div class="stat-icon ${iconClass}"></div>
                </div>
                <div class="stat-value">${value}</div>
                ${change ? `<div class="stat-change ${changeType}">${change}</div>` : ''}
            </div>
        `;
    },
    
    // Agent Card (mini)
    agentCardMini(agent) {
        return `
            <div class="agent-card-mini">
                <div class="agent-avatar-mini">${agent.name[0]}</div>
                <div class="agent-info-mini">
                    <div class="agent-name-mini">${agent.name}</div>
                    <div class="agent-model-mini">${agent.model}</div>
                </div>
                <div class="agent-status-mini ${agent.status}"></div>
            </div>
        `;
    },
    
    // Agent Card (full)
    agentCardFull(agent) {
        const initials = agent.name.split(' ').map(n => n[0]).join('');
        
        return `
            <div class="agent-card-full">
                <div class="agent-header-full">
                    <div class="agent-avatar-full">${initials}</div>
                    <div class="agent-details-full">
                        <div class="agent-name-full">${agent.name}</div>
                        <div class="agent-model-full">${agent.model}</div>
                    </div>
                    <div class="agent-status-mini ${agent.status}"></div>
                </div>
                <div class="agent-stats-full">
                    <div class="agent-stat-item">
                        <div class="agent-stat-value">${agent.tasksCompleted || 0}</div>
                        <div class="agent-stat-label">Tasks</div>
                    </div>
                    <div class="agent-stat-item">
                        <div class="agent-stat-value">${agent.cycles || 0}</div>
                        <div class="agent-stat-label">Cycles</div>
                    </div>
                    <div class="agent-stat-item">
                        <div class="agent-stat-value">${agent.status === 'working' ? (agent.progress || 0) + '%' : '--'}</div>
                        <div class="agent-stat-label">Progress</div>
                    </div>
                </div>
                ${agent.status === 'working' ? `
                    <div class="agent-progress-full">
                        <div class="agent-progress-label">
                            <span>Current Task</span>
                            <span>${agent.progress || 0}%</span>
                        </div>
                        <div class="agent-progress-bar">
                            <div class="agent-progress-fill" style="width: ${agent.progress || 0}%"></div>
                        </div>
                    </div>
                    <div class="agent-task-full">${agent.task || 'Processing...'}</div>
                ` : ''}
                <div class="agent-actions-full">
                    <button class="agent-action-btn" onclick="controlAgent('${agent.id}', 'pause')">
                        ${agent.status === 'working' ? '⏸ Pause' : '▶ Resume'}
                    </button>
                    <button class="agent-action-btn danger" onclick="controlAgent('${agent.id}', 'stop')">
                        ⏹ Stop
                    </button>
                </div>
            </div>
        `;
    },
    
    // Task Card
    taskCard(task) {
        const priorityColors = {
            high: 'danger',
            medium: 'warning',
            low: 'success'
        };
        
        return `
            <div class="task-card" draggable="true" data-id="${task.id}" data-priority="${task.priority}">
                <div class="task-priority priority-${task.priority}"></div>
                <div class="task-card-title">${task.title}</div>
                <div class="task-card-meta">${task.assignee || 'Unassigned'}</div>
            </div>
        `;
    },
    
    // Activity Item
    activityItem(activity) {
        const icons = {
            success: '✓',
            warning: '⚠',
            error: '✕',
            info: 'ℹ'
        };
        
        return `
            <div class="activity-item">
                <div class="activity-icon ${activity.type}">${icons[activity.type]}</div>
                <div class="activity-content">
                    <div class="activity-text">${activity.body}</div>
                    <div class="activity-time">${Utils.formatTime(activity.timestamp)}</div>
                </div>
            </div>
        `;
    },
    
    // Health Item
    healthItem(component) {
        return `
            <div class="health-item">
                <div class="health-indicator ${component.status}"></div>
                <span class="health-name">${component.name}</span>
                <span class="health-value">${component.details}</span>
            </div>
        `;
    },
    
    // Component Card
    componentCard(component) {
        const icons = {
            gateway: '🌐',
            vllm: '🚀',
            telegram: '💬',
            memory: '🧠',
            database: '💾',
            scheduler: '⏰'
        };
        
        return `
            <div class="component-card">
                <div class="component-icon">${icons[component.id] || '⚙️'}</div>
                <div class="component-info">
                    <div class="component-name">${component.name}</div>
                    <div class="component-status">${component.details}</div>
                </div>
                <div class="health-indicator ${component.status}"></div>
            </div>
        `;
    },
    
    // Schedule Event
    scheduleEvent(event) {
        return `<div class="schedule-event">${event.name}</div>`;
    },
    
    // Job Item
    jobItem(job) {
        return `
            <div class="job-item">
                <div class="job-info">
                    <div class="job-name">${job.name}</div>
                    <div class="job-cron">${job.cron}</div>
                </div>
                <div class="job-next">${job.nextRun}</div>
            </div>
        `;
    },
    
    // Log Entry
    logEntry(log) {
        return `
            <div class="log-entry">
                <span class="log-level ${log.level}">${log.level}</span>
                <span class="log-message">${log.message}</span>
                <span class="log-time">${Utils.formatDate(log.timestamp)}</span>
            </div>
        `;
    },
    
    // Notification Item
    notificationItem(notification) {
        return `
            <div class="notification-item ${notification.read ? '' : 'unread'}" data-id="${notification.id}">
                <div class="notification-title">${notification.title}</div>
                <div class="notification-body">${notification.body}</div>
                <div class="notification-time">${Utils.formatTime(notification.timestamp)}</div>
            </div>
        `;
    },
    
    // Metric Card
    metricCard(metric) {
        return `
            <div class="metric-card">
                <div class="metric-header">
                    <span class="metric-label">${metric.label}</span>
                    <span class="metric-status ${metric.status}">${metric.status}</span>
                </div>
                <div class="metric-value">${metric.value}</div>
                <div class="metric-bar">
                    <div class="metric-bar-fill" style="width: ${metric.percent}%"></div>
                </div>
            </div>
        `;
    },
    
    // Week Grid
    weekGrid(weekStart) {
        const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        const date = new Date(weekStart);
        
        return days.map(day => {
            const dateStr = date.toISOString().split('T')[0];
            const events = Components.getEventsForDay(dateStr);
            date.setDate(date.getDate() + 1);
            
            return `
                <div class="schedule-day" data-date="${dateStr}">
                    ${events.map(e => Components.scheduleEvent(e)).join('')}
                </div>
            `;
        }).join('');
    },
    
    getEventsForDay(dateStr) {
        // Get events for a specific day from store
        // This is a placeholder - in real app would filter from store
        return [];
    }
};

// Make Components available globally
window.Components = Components;
