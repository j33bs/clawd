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
        const controlState = agent.control_state || 'active';
        const showControl = controlState && controlState !== 'active';
        const tasksCompleted = agent.tasksCompleted ?? agent.tasks_completed ?? 0;
        const cycles = agent.cycles ?? 0;
        
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
                        <div class="agent-stat-value">${tasksCompleted}</div>
                        <div class="agent-stat-label">Tasks</div>
                    </div>
                    <div class="agent-stat-item">
                        <div class="agent-stat-value">${cycles}</div>
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
                ${showControl ? `<div class="agent-task-full">Operator control: ${controlState.replaceAll('_', ' ')}</div>` : ''}
                <div class="agent-actions-full">
                    <button class="agent-action-btn" disabled title="Agent controls are not wired to a backend yet">
                        ${agent.status === 'working' ? '⏸ Pause (not wired)' : '▶ Resume (not wired)'}
                    </button>
                    <button class="agent-action-btn danger" disabled title="Agent controls are not wired to a backend yet">
                        ⏹ Stop (not wired)
                    </button>
                </div>
            </div>
        `;
    },
    
    // Task Card
    taskCard(task) {
        const readOnly = Boolean(task.read_only);
        const project = task.project ? `<span class="task-card-project">${task.project}</span>` : '';
        const description = task.description ? `<div class="task-card-desc">${task.description}</div>` : '';
        const taskKind = String(task.task_kind || 'task').toLowerCase();
        const sourceLinks = Array.isArray(task.source_links) ? task.source_links.filter(link => link && (link.href || link.ref || link.label)) : [];
        const sourceBadges = [
            taskKind === 'experiment' ? `<span class="task-card-badge task-card-badge-experiment">experiment</span>` : '',
            task.node_label ? `<span class="task-card-badge">${task.node_label}</span>` : '',
            task.runtime_source_label ? `<span class="task-card-badge">${task.runtime_source_label}</span>` : '',
            readOnly ? `<span class="task-card-badge task-card-badge-readonly">read-only</span>` : ''
        ].filter(Boolean).join('');
        const nextActionLabel = task.status === 'backlog'
            ? 'Start'
            : (task.status === 'in_progress' ? 'Review' : (task.status === 'review' ? 'Done' : 'Reopen'));
        const reviewBadge = task.status === 'review'
            ? `<span class="task-card-badge task-card-badge-review">⏳ awaiting review</span>` : '';
        const reviewOwner = task.reviewer || task.assignee;
        const assigneeBadge = task.status === 'review' && reviewOwner
            ? `<span class="task-card-badge task-card-badge-reviewer">reviewer: ${reviewOwner}</span>` : '';
        const reviewReason = task.status === 'review' && (task.review_status_reason || task.status_reason)
            ? `<div class="task-card-desc">${task.review_status_reason || task.status_reason}</div>` : '';
        const fixInstructions = task.status !== 'done' && task.fix_instructions
            ? `<div class="task-card-desc">${task.fix_instructions}</div>` : '';
        const archiveBtn = (task.status === 'done' || task.status === 'review')
            ? `<button class="task-action-btn task-action-btn-archive" type="button" onclick="taskQuickAction('${task.id}', 'archive')" title="Archive this task">Archive</button>` : '';
        const actionMarkup = readOnly ? `
            <div class="task-card-actions task-card-actions-readonly">
                <span class="task-card-readonly-note">Observed live runtime task. Manage it from the owning session.</span>
            </div>
        ` : `
            <div class="task-card-actions">
                <button class="task-action-btn" type="button" onclick="taskQuickAction('${task.id}', 'advance')">${nextActionLabel}</button>
                <button class="task-action-btn" type="button" onclick="taskQuickAction('${task.id}', 'done')">Done</button>
                <button class="task-action-btn" type="button" onclick="taskQuickAction('${task.id}', 'priority')">Priority</button>
                ${archiveBtn}
            </div>
        `;
        
        return `
            <div class="task-card ${readOnly ? 'task-card-readonly' : ''}" draggable="${readOnly ? 'false' : 'true'}" data-id="${task.id}" data-priority="${task.priority}" data-read-only="${readOnly ? 'true' : 'false'}">
                <div class="task-priority priority-${task.priority}"></div>
                <div class="task-card-title">${task.title}</div>
                ${description}
                ${reviewReason}
                ${fixInstructions}
                <div class="task-card-meta">${task.assignee || 'Unassigned'} ${project}</div>
                ${sourceBadges ? `<div class="task-card-badges">${sourceBadges}</div>` : ''}
                ${(reviewBadge || assigneeBadge) ? `<div class="task-card-badges">${reviewBadge}${assigneeBadge}</div>` : ''}
                ${sourceLinks.length ? `<div class="task-source-links">${sourceLinks.slice(0, 3).map(link => link.href
                    ? `<a class="task-source-link" href="${escapeHtml(link.href)}" target="_blank" rel="noreferrer">${escapeHtml(link.label || link.ref || 'source')}</a>`
                    : `<span class="task-source-link">${escapeHtml(link.label || link.ref || 'source')}</span>`).join('')}</div>` : ''}
                ${actionMarkup}
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
        const nextRun = job.nextRun || job.next_run || 'unscheduled';
        return `
            <div class="job-item">
                <div class="job-info">
                    <div class="job-name">${job.name}</div>
                    <div class="job-cron">${job.cron}</div>
                </div>
                <div class="job-next">${nextRun}</div>
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
