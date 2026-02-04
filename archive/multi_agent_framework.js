// multi_agent_framework.js
// Foundation for multi-agent system with dynamic spawning and token management
// To be enhanced with Codex integration after Feb 5th

class MultiAgentFramework {
  constructor(config = {}) {
    this.agents = new Map(); // Store active agents
    this.taskQueue = []; // Queue for incoming tasks
    this.tokenManager = new TokenManager(config.tokenLimits || {});
    this.agentSpawner = new AgentSpawner(this);
    this.communicationHub = new CommunicationHub();
    this.fallbackManager = new FallbackManager();
    
    this.config = {
      primaryTokenLimit: config.primaryTokenLimit || 4000,
      secondaryTokenLimit: config.secondaryTokenLimit || 2000,
      maxConcurrentAgents: config.maxConcurrentAgents || 5,
      tokenThreshold: config.tokenThreshold || 0.8, // 80% threshold
      spawnCooldown: config.spawnCooldown || 1000, // 1 second cooldown
      ...config
    };
    
    this.stats = {
      totalTasks: 0,
      completedTasks: 0,
      spawnedAgents: 0,
      fallbackInvocations: 0,
      currentAgents: 0
    };
    
    // Initialize main agent
    this.mainAgent = new Agent({
      id: 'main_agent',
      type: 'orchestrator',
      tokenLimit: this.config.primaryTokenLimit,
      framework: this
    });
    this.agents.set('main_agent', this.mainAgent);
    this.stats.currentAgents = 1;
  }

  // Classify task to determine handling approach
  classifyTask(task) {
    const classification = {
      type: 'unknown',
      complexity: 'low', // low, medium, high
      estimatedTokens: 0,
      requiresCodex: false, // To be set after Feb 5th
      priority: 'normal', // low, normal, high
      estimatedTime: 0
    };

    // Analyze task content
    const content = typeof task === 'string' ? task : task.content || task.query || '';
    
    // Determine complexity based on content analysis
    const lines = content.split('\n').length;
    const words = content.split(/\s+/).length;
    const hasCode = /(?:function|class|import|export|def|class\s+\w+|struct\s+\w+)/.test(content);
    const hasComplexSyntax = /(?:algorithm|architecture|refactor|debug|performance|optimization)/i.test(content);
    
    // Estimate token usage (rough approximation: 1 token ≈ 4 characters)
    classification.estimatedTokens = Math.ceil(content.length / 4);
    
    // Determine task type
    if (hasCode) {
      classification.type = 'coding';
      if (hasComplexSyntax) {
        classification.complexity = 'high';
        classification.requiresCodex = true; // Mark for Codex after Feb 5th
      } else if (words > 200 || lines > 10) {
        classification.complexity = 'medium';
      }
    } else {
      classification.type = 'general';
      if (words > 500 || lines > 20) {
        classification.complexity = 'medium';
      }
    }
    
    // Estimate completion time (in milliseconds)
    if (classification.complexity === 'high') {
      classification.estimatedTime = 15000; // 15 seconds
    } else if (classification.complexity === 'medium') {
      classification.estimatedTime = 5000; // 5 seconds
    } else {
      classification.estimatedTime = 1000; // 1 second
    }
    
    // Set priority based on complexity and urgency indicators
    if (/(?:urgent|asap|immediate|critical|emergency)/i.test(content)) {
      classification.priority = 'high';
    } else if (/(?:important|needed|required)/i.test(content)) {
      classification.priority = 'normal';
    }
    
    return classification;
  }

  // Process a task through the appropriate agent
  async processTask(task, options = {}) {
    this.stats.totalTasks++;
    
    // Classify the task
    const classification = this.classifyTask(task);
    
    // Check if this is a heavy coding task that should go to Codex (after Feb 5th)
    if (classification.requiresCodex && this.isAfterFeb5th()) {
      return this.divertToCodex(task, classification, options);
    }
    
    // Determine which agent to use
    let targetAgent = null;
    
    // For high priority tasks, try to find an available agent quickly
    if (classification.priority === 'high') {
      // Find the least busy agent
      const availableAgents = Array.from(this.agents.values())
        .filter(agent => agent.isAvailable());
      
      if (availableAgents.length > 0) {
        // Sort by current token usage (lowest first)
        availableAgents.sort((a, b) => a.getCurrentTokenUsage() - b.getCurrentTokenUsage());
        targetAgent = availableAgents[0];
      }
    }
    
    // If no suitable agent found or no agent available, consider spawning
    if (!targetAgent) {
      targetAgent = await this.findOrCreateAgent(classification, options);
    }
    
    // Execute the task
    try {
      const result = await targetAgent.executeTask(task, classification);
      this.stats.completedTasks++;
      
      // Check if agent needs cleanup or recycling
      await this.checkAgentHealth(targetAgent);
      
      return {
        success: true,
        result,
        agentId: targetAgent.id,
        classification,
        tokensUsed: classification.estimatedTokens
      };
    } catch (error) {
      // Handle error and potentially invoke fallback
      this.stats.fallbackInvocations++;
      return this.handleTaskError(task, classification, error, options);
    }
  }

  // Find or create an appropriate agent for the task
  async findOrCreateAgent(classification, options = {}) {
    // First, try to find an existing available agent
    for (const [id, agent] of this.agents) {
      if (agent.isAvailable() && agent.canHandleTask(classification)) {
        // Check if this agent has sufficient tokens remaining
        if (agent.hasSufficientTokens(classification.estimatedTokens)) {
          return agent;
        }
      }
    }
    
    // If no suitable agent found, consider spawning a new one
    if (this.shouldSpawnAgent(classification)) {
      const newAgent = await this.agentSpawner.spawnAgent(classification, options);
      this.agents.set(newAgent.id, newAgent);
      this.stats.spawnedAgents++;
      this.stats.currentAgents++;
      return newAgent;
    }
    
    // If we can't spawn and no agents are available, use main agent (blocking)
    return this.mainAgent;
  }

  // Determine if we should spawn a new agent
  shouldSpawnAgent(classification) {
    // Don't spawn if we're at max capacity
    if (this.stats.currentAgents >= this.config.maxConcurrentAgents) {
      return false;
    }
    
    // Spawn for high complexity tasks if we don't have a suitable agent
    if (classification.complexity === 'high') {
      return true;
    }
    
    // Spawn if main agent is getting busy
    if (this.mainAgent.getCurrentTokenUsage() > this.config.primaryTokenLimit * this.config.tokenThreshold) {
      return true;
    }
    
    // Spawn if we have multiple tasks queued
    if (this.taskQueue.length > 2) {
      return true;
    }
    
    return false;
  }

  // Check agent health and perform cleanup if needed
  async checkAgentHealth(agent) {
    // Recycle agent if it's approaching token limit
    const tokenUsage = agent.getCurrentTokenUsage();
    const tokenLimit = agent.tokenLimit;
    
    if (tokenUsage > tokenLimit * this.config.tokenThreshold) {
      // Agent needs to be recycled or replaced
      await this.recycleAgent(agent);
    }
  }

  // Recycle an agent (cleanup and potentially replace)
  async recycleAgent(agent) {
    // Remove from active agents
    this.agents.delete(agent.id);
    this.stats.currentAgents--;
    
    // Perform cleanup
    await agent.cleanup();
    
    // Optionally spawn a replacement if needed
    if (this.taskQueue.length > 0) {
      const replacement = await this.agentSpawner.spawnAgent(
        { complexity: 'low', type: 'general' },
        { purpose: 'replacement' }
      );
      this.agents.set(replacement.id, replacement);
      this.stats.spawnedAgents++;
      this.stats.currentAgents++;
    }
  }

  // Handle task errors with fallback mechanisms
  async handleTaskError(task, classification, error, options) {
    // Log the error
    console.error(`Task failed on agent ${options.agentId || 'unknown'}:`, error);
    
    // Try fallback mechanisms
    try {
      // Fallback 1: Try with main agent
      if (this.mainAgent.isAvailable()) {
        const result = await this.mainAgent.executeTask(task, classification);
        return {
          success: true,
          result,
          agentId: 'main_agent',
          classification,
          tokensUsed: classification.estimatedTokens,
          fallback: true
        };
      }
      
      // Fallback 2: Spawn a new agent specifically for this task
      const fallbackAgent = await this.agentSpawner.spawnAgent(classification, { 
        purpose: 'fallback', 
        error: error.message 
      });
      this.agents.set(fallbackAgent.id, fallbackAgent);
      this.stats.spawnedAgents++;
      this.stats.currentAgents++;
      
      const result = await fallbackAgent.executeTask(task, classification);
      return {
        success: true,
        result,
        agentId: fallbackAgent.id,
        classification,
        tokensUsed: classification.estimatedTokens,
        fallback: true
      };
    } catch (fallbackError) {
      // All fallbacks failed
      return {
        success: false,
        error: fallbackError.message,
        originalError: error.message,
        classification
      };
    }
  }

  // Divert heavy coding tasks to Codex (after Feb 5th)
  async divertToCodex(task, classification, options) {
    // This will be implemented after Feb 5th with actual Codex integration
    // For now, simulate the process
    
    console.log(`[SIMULATION] Would divert heavy coding task to Codex:`, {
      taskId: options.taskId || 'unknown',
      complexity: classification.complexity,
      estimatedTokens: classification.estimatedTokens
    });
    
    // For simulation purposes, we'll still process it locally
    // Actual implementation will call Codex API
    return {
      success: true,
      result: `[CODEX SIMULATION] Processed heavy coding task: ${task.substring(0, 50)}...`,
      agentId: 'codex_simulation',
      classification,
      tokensUsed: classification.estimatedTokens,
      divertedToCodex: true
    };
  }

  // Check if current date is after Feb 5th
  isAfterFeb5th() {
    const now = new Date();
    const feb5th = new Date(now.getFullYear(), 1, 5); // Month is 0-indexed (Jan=0, Feb=1)
    return now >= feb5th;
  }

  // Get system statistics
  getStats() {
    return {
      ...this.stats,
      agentCount: this.agents.size,
      queueLength: this.taskQueue.length,
      averageTaskTime: this.stats.totalTasks > 0 ? 
        (Date.now() - this.startTime) / this.stats.totalTasks : 0
    };
  }

  // Get agent information
  getAgentInfo() {
    const info = {};
    for (const [id, agent] of this.agents) {
      info[id] = {
        type: agent.type,
        tokenUsage: agent.getCurrentTokenUsage(),
        tokenLimit: agent.tokenLimit,
        status: agent.getStatus(),
        lastTask: agent.lastTask,
        tasksProcessed: agent.tasksProcessed
      };
    }
    return info;
  }
}

// Token Manager class
class TokenManager {
  constructor(limits = {}) {
    this.limits = {
      primary: limits.primary || 4000,
      secondary: limits.secondary || 2000,
      ...limits
    };
    this.usage = new Map();
  }

  // Track token usage for an agent
  trackUsage(agentId, tokensUsed) {
    if (!this.usage.has(agentId)) {
      this.usage.set(agentId, 0);
    }
    const current = this.usage.get(agentId);
    this.usage.set(agentId, current + tokensUsed);
  }

  // Get current usage for an agent
  getCurrentUsage(agentId) {
    return this.usage.get(agentId) || 0;
  }

  // Get limit for agent type
  getLimit(agentType = 'primary') {
    return this.limits[agentType] || this.limits.primary;
  }

  // Reset usage for an agent
  resetUsage(agentId) {
    this.usage.set(agentId, 0);
  }
}

// Agent Spawner class
class AgentSpawner {
  constructor(framework) {
    this.framework = framework;
    this.lastSpawnTime = 0;
  }

  // Spawn a new agent based on task classification
  async spawnAgent(classification, options = {}) {
    const now = Date.now();
    
    // Enforce spawn cooldown
    if (now - this.lastSpawnTime < this.framework.config.spawnCooldown) {
      // Wait for cooldown
      await new Promise(resolve => 
        setTimeout(resolve, this.lastSpawnTime + this.framework.config.spawnCooldown - now)
      );
    }
    
    const agentId = `agent_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
    const agentType = this.determineAgentType(classification, options);
    
    const tokenLimit = this.framework.config.secondaryTokenLimit;
    
    const newAgent = new Agent({
      id: agentId,
      type: agentType,
      tokenLimit: tokenLimit,
      framework: this.framework,
      classification
    });
    
    this.lastSpawnTime = Date.now();
    return newAgent;
  }

  // Determine appropriate agent type based on classification
  determineAgentType(classification, options) {
    if (options.purpose === 'fallback') {
      return 'fallback';
    }
    
    if (classification.type === 'coding') {
      if (classification.complexity === 'high') {
        return 'coding_specialist';
      }
      return 'coding_general';
    }
    
    if (classification.complexity === 'high') {
      return 'specialist';
    }
    
    return 'general';
  }
}

// Communication Hub class
class CommunicationHub {
  constructor() {
    this.channels = new Map(); // Agent-to-agent communication
    this.broadcastListeners = new Set();
  }

  // Send message to specific agent
  sendMessage(fromAgent, toAgent, message) {
    // Implementation for inter-agent communication
    return true;
  }

  // Broadcast message to all agents
  broadcast(fromAgent, message) {
    // Notify all registered listeners
    this.broadcastListeners.forEach(listener => {
      listener(fromAgent, message);
    });
  }

  // Register broadcast listener
  registerBroadcastListener(callback) {
    this.broadcastListeners.add(callback);
    return () => this.broadcastListeners.delete(callback);
  }
}

// Fallback Manager class
class FallbackManager {
  constructor() {
    this.strategies = [
      'retry_with_same_agent',
      'try_different_agent',
      'spawn_new_agent',
      'escalate_to_main',
      'queue_for_later'
    ];
    this.currentStrategyIndex = 0;
  }

  // Get next fallback strategy
  getNextStrategy() {
    const strategy = this.strategies[this.currentStrategyIndex];
    this.currentStrategyIndex = (this.currentStrategyIndex + 1) % this.strategies.length;
    return strategy;
  }

  // Execute fallback strategy
  async executeFallback(strategy, context) {
    // Implementation of different fallback strategies
    switch (strategy) {
      case 'retry_with_same_agent':
        // Retry the same task with same agent
        return context.originalAgent.retry(context.task);
      case 'try_different_agent':
        // Try with a different available agent
        return context.framework.findOrCreateAgent(context.classification)
          .executeTask(context.task, context.classification);
      case 'spawn_new_agent':
        // Spawn a new agent specifically for this task
        const newAgent = await context.framework.agentSpawner.spawnAgent(
          context.classification, 
          { purpose: 'fallback' }
        );
        return newAgent.executeTask(context.task, context.classification);
      case 'escalate_to_main':
        // Escalate to main agent
        return context.framework.mainAgent.executeTask(
          context.task, 
          context.classification
        );
      case 'queue_for_later':
        // Add to queue for later processing
        context.framework.taskQueue.push({
          task: context.task,
          classification: context.classification,
          retryCount: (context.retryCount || 0) + 1
        });
        return { queued: true };
      default:
        throw new Error(`Unknown fallback strategy: ${strategy}`);
    }
  }
}

// Agent class
class Agent {
  constructor(config) {
    this.id = config.id;
    this.type = config.type;
    this.tokenLimit = config.tokenLimit;
    this.framework = config.framework;
    this.currentTokenUsage = 0;
    this.status = 'ready'; // ready, busy, unavailable
    this.lastTask = null;
    this.tasksProcessed = 0;
    this.creationTime = new Date();
    
    // Type-specific configurations
    this.specializations = this.getTypeSpecializations();
  }

  // Get specializations based on agent type
  getTypeSpecializations() {
    const specializations = {
      'coding_specialist': ['complex_algorithms', 'architecture', 'refactoring', 'debugging'],
      'coding_general': ['code_snippets', 'documentation', 'simple_logic'],
      'specialist': ['complex_analysis', 'research', 'planning'],
      'general': ['conversations', 'simple_tasks', 'documentation'],
      'fallback': ['error_recovery', 'alternative_processing', 'contingency'],
      'orchestrator': ['task_coordination', 'agent_management', 'workflow']
    };
    
    return specializations[this.type] || specializations.general;
  }

  // Execute a task
  async executeTask(task, classification) {
    this.status = 'busy';
    this.lastTask = {
      content: typeof task === 'string' ? task.substring(0, 100) : 'complex_task',
      timestamp: new Date(),
      classification
    };
    
    try {
      // Simulate task processing
      await this.simulateProcessing(classification.estimatedTime || 1000);
      
      // Update token usage
      this.currentTokenUsage += classification.estimatedTokens || 100;
      this.tasksProcessed++;
      
      // Simulate result generation
      const result = this.generateResult(task, classification);
      
      this.status = 'ready';
      return result;
    } catch (error) {
      this.status = 'error';
      throw error;
    }
  }

  // Simulate processing time
  async simulateProcessing(timeMs) {
    return new Promise(resolve => setTimeout(resolve, Math.min(timeMs, 10000))); // Max 10 seconds
  }

  // Generate result based on task and classification
  generateResult(task, classification) {
    if (classification.type === 'coding') {
      if (classification.complexity === 'high') {
        return `/* Complex coding solution for: ${task.toString().substring(0, 50)}... */\n// Generated by ${this.type} agent\n// Complexity: ${classification.complexity}`;
      }
      return `// Code solution: ${task.toString().substring(0, 100)}...`;
    }
    
    return `Processed: ${task.toString().substring(0, 200)}... [via ${this.type} agent]`;
  }

  // Check if agent is available
  isAvailable() {
    return this.status === 'ready';
  }

  // Check if agent can handle a specific task
  canHandleTask(classification) {
    if (this.type === 'coding_specialist' && classification.type === 'coding') {
      return true;
    }
    
    if (this.type === 'coding_general' && classification.type === 'coding') {
      return classification.complexity !== 'high';
    }
    
    if (this.type === 'specialist' && classification.complexity === 'high') {
      return true;
    }
    
    return this.type === 'general' || this.type === 'orchestrator';
  }

  // Check if agent has sufficient tokens for a task
  hasSufficientTokens(tokensNeeded) {
    const availableTokens = this.tokenLimit - this.currentTokenUsage;
    return availableTokens >= tokensNeeded * 1.2; // 20% buffer
  }

  // Get current token usage percentage
  getCurrentTokenUsage() {
    return (this.currentTokenUsage / this.tokenLimit) * 100;
  }

  // Get agent status
  getStatus() {
    return {
      status: this.status,
      tokenUsage: this.getCurrentTokenUsage(),
      tasksProcessed: this.tasksProcessed,
      uptime: Date.now() - this.creationTime.getTime()
    };
  }

  // Cleanup agent resources
  async cleanup() {
    this.status = 'unavailable';
    // Perform any necessary cleanup
    this.currentTokenUsage = 0;
  }

  // Retry a task
  async retry(task) {
    // Reset status and retry
    this.status = 'ready';
    return this.executeTask(task, { type: 'general', complexity: 'low', estimatedTokens: 100 });
  }
}

module.exports = { MultiAgentFramework, Agent, TokenManager, AgentSpawner, CommunicationHub, FallbackManager };