// task_scheduler.js
// Task scheduling and monitoring system for the multi-agent framework

class TaskScheduler {
  constructor(framework) {
    this.framework = framework;
    this.pendingTasks = new Map();
    this.runningTasks = new Map();
    this.completedTasks = [];
    this.failedTasks = [];
    this.schedulerInterval = null;
    this.monitoringInterval = null;
    
    this.stats = {
      totalScheduled: 0,
      totalCompleted: 0,
      totalFailed: 0,
      averageWaitTime: 0,
      averageRunTime: 0
    };
  }

  // Schedule a task for processing
  async scheduleTask(task, options = {}) {
    const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
    const scheduledTime = Date.now();
    
    const taskRecord = {
      id: taskId,
      task,
      options,
      scheduledTime,
      priority: options.priority || 'normal',
      deadline: options.deadline || null,
      dependencies: options.dependencies || [],
      status: 'pending',
      agentId: null,
      startTime: null,
      completionTime: null,
      result: null,
      error: null
    };
    
    this.pendingTasks.set(taskId, taskRecord);
    this.stats.totalScheduled++;
    
    // Check dependencies and process if ready
    await this.processReadyTasks();
    
    return taskId;
  }

  // Process tasks that are ready to run
  async processReadyTasks() {
    // Short-circuit if nothing is queued
    if (this.pendingTasks.size === 0) return;

    // Get all pending tasks
    const pending = Array.from(this.pendingTasks.values());
    
    // Sort by priority and dependency readiness
    const readyTasks = pending.filter(task => this.areDependenciesMet(task))
      .sort((a, b) => this.comparePriority(a.priority, b.priority));
    
    for (const task of readyTasks) {
      if (task.status === 'pending') {
        await this.startTask(task);
      }
    }
  }

  // Check if task dependencies are met
  areDependenciesMet(task) {
    if (task.dependencies.length === 0) {
      return true;
    }
    
    for (const depId of task.dependencies) {
      if (this.completedTasks.some(t => t.id === depId)) {
        continue; // Dependency completed
      } else if (this.pendingTasks.has(depId)) {
        return false; // Dependency still pending
      } else if (this.runningTasks.has(depId)) {
        return false; // Dependency still running
      } else {
        return false; // Dependency doesn't exist or failed
      }
    }
    
    return true;
  }

  // Compare task priorities
  comparePriority(a, b) {
    const priorityOrder = { 'high': 3, 'normal': 2, 'low': 1 };
    return (priorityOrder[b] || 0) - (priorityOrder[a] || 0);
  }

  // Start processing a task
  async startTask(taskRecord) {
    taskRecord.status = 'running';
    taskRecord.startTime = Date.now();
    
    // Move from pending to running
    this.pendingTasks.delete(taskRecord.id);
    this.runningTasks.set(taskRecord.id, taskRecord);
    
    try {
      // Process through the framework
      const result = await this.framework.processTask(taskRecord.task, {
        ...taskRecord.options,
        taskId: taskRecord.id
      });
      
      // Complete the task
      taskRecord.status = 'completed';
      taskRecord.completionTime = Date.now();
      taskRecord.result = result;
      taskRecord.agentId = result.agentId;
      
      this.completedTasks.push(taskRecord);
      this.runningTasks.delete(taskRecord.id);
      
      this.stats.totalCompleted++;
      this.updateTimingStats(taskRecord);
      
      // Process any dependent tasks that might now be ready
      await this.processDependentTasks(taskRecord.id);
      
    } catch (error) {
      // Handle task failure
      taskRecord.status = 'failed';
      taskRecord.completionTime = Date.now();
      taskRecord.error = error.message;
      taskRecord.agentId = error.agentId || 'unknown';
      
      this.failedTasks.push(taskRecord);
      this.runningTasks.delete(taskRecord.id);
      
      this.stats.totalFailed++;
    }
  }

  // Process tasks that depend on a completed task
  async processDependentTasks(completedTaskId) {
    const dependentTasks = Array.from(this.pendingTasks.values())
      .filter(task => task.dependencies.includes(completedTaskId));
    
    for (const task of dependentTasks) {
      await this.processReadyTasks(); // Re-check all pending tasks
      break; // Just trigger a re-check, don't process individually
    }
  }

  // Update timing statistics
  updateTimingStats(taskRecord) {
    const waitTime = taskRecord.startTime - taskRecord.scheduledTime;
    const runTime = taskRecord.completionTime - taskRecord.startTime;
    
    // Simple average calculation (could be improved with rolling averages)
    const totalCompleted = this.stats.totalCompleted;
    this.stats.averageWaitTime = ((this.stats.averageWaitTime * (totalCompleted - 1)) + waitTime) / totalCompleted;
    this.stats.averageRunTime = ((this.stats.averageRunTime * (totalCompleted - 1)) + runTime) / totalCompleted;
  }

  // Start the scheduler loop
  startScheduler(interval = 100) { // Check every 100ms
    if (this.schedulerInterval) {
      clearInterval(this.schedulerInterval);
    }
    
    this.schedulerInterval = setInterval(() => {
      this.processReadyTasks().catch(console.error);
    }, interval);
    
    return this.schedulerInterval;
  }

  // Stop the scheduler
  stopScheduler() {
    if (this.schedulerInterval) {
      clearInterval(this.schedulerInterval);
      this.schedulerInterval = null;
    }
  }

  // Start monitoring
  startMonitoring(interval = 5000) { // Check every 5 seconds
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }
    
    this.monitoringInterval = setInterval(() => {
      this.monitorSystemHealth().catch(console.error);
    }, interval);
    
    return this.monitoringInterval;
  }

  // Stop monitoring
  stopMonitoring() {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }
  }

  // Monitor system health
  async monitorSystemHealth() {
    const frameworkStats = this.framework.getStats();
    const agentInfo = this.framework.getAgentInfo();
    
    // Check for system health issues
    const issues = [];
    
    // Check for stuck tasks
    const now = Date.now();
    for (const [id, task] of this.runningTasks) {
      if (now - task.startTime > 300000) { // 5 minutes
        issues.push(`Task ${id} has been running for more than 5 minutes`);
      }
    }
    
    // Check agent health
    for (const [id, agent] of Object.entries(agentInfo)) {
      if (agent.status === 'error') {
        issues.push(`Agent ${id} is in error state`);
      }
      if (agent.tokenUsage > 95) {
        issues.push(`Agent ${id} token usage is critically high: ${agent.tokenUsage}%`);
      }
    }
    
    // Check queue buildup
    if (this.pendingTasks.size > 10) {
      issues.push(`Large task queue: ${this.pendingTasks.size} pending tasks`);
    }
    
    // Log issues if any
    if (issues.length > 0) {
      console.warn('System Health Issues Detected:', issues);
    }
    
    // Take corrective actions if needed
    await this.takeCorrectiveActions(issues, frameworkStats);
  }

  // Take corrective actions based on issues
  async takeCorrectiveActions(issues, frameworkStats) {
    for (const issue of issues) {
      if (issue.includes('token usage is critically high')) {
        // Find agent ID from issue
        const match = issue.match(/Agent (\w+) token usage/);
        if (match) {
          const agentId = match[1];
          // In a real system, we'd recycle the agent
          console.log(`Would recycle agent ${agentId} due to high token usage`);
        }
      } else if (issue.includes('stuck tasks')) {
        // Cancel stuck tasks or spawn new agents
        console.log('Checking for stuck tasks to cancel or reassign');
      } else if (issue.includes('Large task queue')) {
        // Spawn more agents if possible
        if (frameworkStats.currentAgents < frameworkStats.maxConcurrentAgents) {
          console.log('Spawning additional agents to handle queue');
          // In a real system, we'd spawn more agents
        }
      }
    }
  }

  // Get task status
  getTaskStatus(taskId) {
    if (this.pendingTasks.has(taskId)) {
      return this.pendingTasks.get(taskId);
    }
    if (this.runningTasks.has(taskId)) {
      return this.runningTasks.get(taskId);
    }
    return this.completedTasks.find(t => t.id === taskId) || 
           this.failedTasks.find(t => t.id === taskId) || null;
  }

  // Cancel a pending task
  cancelTask(taskId) {
    if (this.pendingTasks.has(taskId)) {
      const task = this.pendingTasks.get(taskId);
      task.status = 'cancelled';
      task.completionTime = Date.now();
      
      this.pendingTasks.delete(taskId);
      this.completedTasks.push(task);
      
      return true;
    }
    return false;
  }

  // Get scheduler statistics
  getStats() {
    return {
      ...this.stats,
      pendingTasks: this.pendingTasks.size,
      runningTasks: this.runningTasks.size,
      completedTasks: this.completedTasks.length,
      failedTasks: this.failedTasks.length,
      queueHealth: this.calculateQueueHealth()
    };
  }

  // Calculate queue health score (0-100)
  calculateQueueHealth() {
    const total = this.stats.totalScheduled || 1;
    const successRate = (this.stats.totalCompleted / total) * 100;
    const queueSize = this.pendingTasks.size;
    
    // Base score on success rate, penalized by queue size
    let health = successRate;
    if (queueSize > 5) {
      health -= (queueSize - 5) * 2; // Deduct 2 points for each task over 5
    }
    
    return Math.max(0, Math.min(100, health));
  }

  // Get task history
  getTaskHistory(limit = 50) {
    // Combine completed and failed tasks, sort by completion time
    const allTasks = [...this.completedTasks, ...this.failedTasks]
      .sort((a, b) => (b.completionTime || 0) - (a.completionTime || 0));
    
    return allTasks.slice(0, limit);
  }
}

module.exports = TaskScheduler;