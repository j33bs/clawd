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
        const name = agent.name || agent.id || 'Agent';
        return `
            <div class="agent-card-mini">
                <div class="agent-avatar-mini">${name[0]}</div>
                <div class="agent-info-mini">
                    <div class="agent-name-mini">${name}</div>
                    <div class="agent-model-mini">${agent.model || 'unknown'}</div>
                </div>
                <div class="agent-status-mini ${agent.status || 'idle'}"></div>
            </div>
        `;
    },
    
    // Agent Card (full)
    agentCardFull(agent) {
        const name = agent.name || agent.id || 'Agent';
        const initials = name.split(' ').map((part) => part[0]).join('').slice(0, 2) || '?';
        const progressValue = Number.isFinite(agent.progress) ? agent.progress : null;
        const actionButtons = Array.isArray(agent.available_actions) && agent.available_actions.includes('stop')
            ? `
                <button class="agent-action-btn danger" data-agent-id="${agent.id}" data-agent-action="stop">
                    Stop Work
                </button>
            `
            : '<div class="agent-control-note">No direct stop surface exposed for this runtime row.</div>';
        
        return `
            <div class="agent-card-full">
                <div class="agent-header-full">
                    <div class="agent-avatar-full">${initials}</div>
                    <div class="agent-details-full">
                        <div class="agent-name-full">${name}</div>
                        <div class="agent-model-full">${agent.model || 'unknown'}</div>
                    </div>
                    <div class="agent-status-mini ${agent.status || 'idle'}"></div>
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
                        <div class="agent-stat-value">${agent.status === 'working' && progressValue !== null ? progressValue + '%' : '--'}</div>
                        <div class="agent-stat-label">Progress</div>
                    </div>
                </div>
                ${agent.status === 'working' && progressValue !== null ? `
                    <div class="agent-progress-full">
                        <div class="agent-progress-label">
                            <span>Current Task</span>
                            <span>${progressValue}%</span>
                        </div>
                        <div class="agent-progress-bar">
                            <div class="agent-progress-fill" style="width: ${progressValue}%"></div>
                        </div>
                    </div>
                    <div class="agent-task-full">${agent.task || agent.detail || 'Processing...'}</div>
                ` : ''}
                ${agent.detail && agent.detail !== agent.task ? `<div class="agent-detail-full">${agent.detail}</div>` : ''}
                ${agent.updated_at ? `<div class="agent-updated-full">Updated ${Utils.formatTime(agent.updated_at)}</div>` : ''}
                <div class="agent-actions-full">
                    ${actionButtons}
                </div>
            </div>
        `;
    },
    
    // Task Card
    taskCard(task) {
        const priority = String(task.priority || 'medium').trim().toLowerCase();
        const summary = String(task.summary || task.description || '').trim();
        const meta = [
            task.pillar ? `Pillar: ${task.pillar}` : null,
            task.assignee ? `Owner: ${task.assignee}` : 'Unassigned'
        ].filter(Boolean).join(' · ');
        const reason = String(task.status_reason || '').trim();
        
        return `
            <div class="task-card" draggable="true" data-id="${task.id}" data-priority="${priority}">
                <div class="task-priority priority-${priority}"></div>
                <div class="task-card-title">${task.title}</div>
                ${summary ? `<div class="task-card-summary">${summary}</div>` : ''}
                <div class="task-card-meta">${meta}</div>
                ${reason ? `<div class="task-card-reason">${reason}</div>` : ''}
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
        const body = activity.body || activity.detail || activity.message || '';
        
        return `
            <div class="activity-item">
                <div class="activity-icon ${activity.type}">${icons[activity.type] || '•'}</div>
                <div class="activity-content">
                    <div class="activity-text">${body}</div>
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
            assistant: '🚀',
            vllm: '🚀',
            telegram: '💬',
            memory: '🧠',
            database: '💾',
            scheduler: '⏰',
            dali: '🎨',
            market_stream: '📈',
            itc_cycle: '⏲️'
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
        return `
            <div class="schedule-event" title="${event.title || event.name}">
                <div class="schedule-event-name">${event.name}</div>
                ${event.time ? `<div class="schedule-event-time">${event.time}</div>` : ''}
            </div>
        `;
    },
    
    // Job Item
    jobItem(job) {
        return `
            <div class="job-item">
                <div class="job-info">
                    <div class="job-name">${job.name}</div>
                    <div class="job-cron">${job.cron || 'manual'}</div>
                    ${job.meta ? `<div class="job-meta">${job.meta}</div>` : ''}
                </div>
                <div class="job-next">
                    <div class="job-status ${job.enabled ? 'enabled' : 'disabled'}">${job.enabled ? 'Enabled' : 'Disabled'}</div>
                    <div>${job.nextRun || 'No next run'}</div>
                    ${job.lastRun ? `<div class="job-timestamps">Last run ${job.lastRun}</div>` : ''}
                </div>
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
            const dayLabel = date.getDate();
            date.setDate(date.getDate() + 1);
            
            return `
                <div class="schedule-day" data-date="${dateStr}">
                    <div class="schedule-day-date">${day} ${dayLabel}</div>
                    <div class="schedule-day-events">
                    ${events.map(e => Components.scheduleEvent(e)).join('')}
                    </div>
                </div>
            `;
        }).join('');
    },
    
    getEventsForDay(dateStr) {
        const jobs = Array.isArray(store?.get('scheduledJobs')) ? store.get('scheduledJobs') : [];
        return jobs
            .filter((job) => {
                if (!job.next_run_at) return false;
                const nextRun = new Date(job.next_run_at);
                if (Number.isNaN(nextRun.getTime())) return false;
                return nextRun.toISOString().split('T')[0] === dateStr;
            })
            .slice(0, 4)
            .map((job) => ({
                name: job.name,
                title: `${job.name} · ${job.cron || 'manual'}`,
                time: job.nextRunShort || '',
            }));
    }
};

// Make Components available globally
window.Components = Components;
