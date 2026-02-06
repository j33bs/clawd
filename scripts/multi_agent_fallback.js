/**
 * multi_agent_fallback.js
 * 
 * Implements a multi-agent fallback system that switches to Qwen when API credits are exhausted.
 * Monitors API usage and automatically falls back to local Qwen model when needed.
 */

const path = require('path');
const { appendJsonArray } = require('./guarded_fs');
const { callModel } = require('../core/model_call');
const { BACKENDS } = require('../core/model_constants');

class MultiAgentFallback {
  constructor(config = {}) {
    this.config = {
      primaryProvider: config.primaryProvider || 'anthropic', // or 'openai', 'google', etc.
      fallbackProvider: config.fallbackProvider || 'qwen',
      creditThreshold: config.creditThreshold || 0.1, // Switch when credits fall below this threshold
      checkInterval: config.checkInterval || 60000, // Check every minute
      configPath: config.configPath || './config.json',
      ...config
    };
    
    this.currentProvider = this.config.primaryProvider;
    this.isFallbackActive = false;
    this.monitorInterval = null;
    this.usageStats = {
      primaryRequests: 0,
      fallbackRequests: 0,
      lastSwitchTime: null,
      switchReason: null
    };
  }

  /**
   * Check if API credits are sufficient for primary provider
   */
  async checkCredits() {
    try {
      // Different providers have different ways to check credits
      switch (this.config.primaryProvider) {
        case 'anthropic':
          return await this.checkAnthropicCredits();
        case 'openai':
          return await this.checkOpenAICredits();
        case 'google':
          return await this.checkGoogleCredits();
        case 'openrouter':
          return await this.checkOpenRouterCredits();
        default:
          // If we can't check, assume insufficient credits
          return { sufficient: false, balance: 0, provider: this.config.primaryProvider };
      }
    } catch (error) {
      console.warn(`Could not check credits for ${this.config.primaryProvider}:`, error.message);
      // If we can't check, assume insufficient credits
      return { sufficient: false, balance: 0, provider: this.config.primaryProvider };
    }
  }

  /**
   * Check Anthropic credits (placeholder - would need actual API integration)
   */
  async checkAnthropicCredits() {
    // In a real implementation, this would call Anthropic's usage API
    // For now, we'll look for a local configuration or environment variable
    const creditBalance = parseFloat(process.env.ANTHROPIC_CREDIT_BALANCE || '0');
    
    return {
      sufficient: creditBalance > this.config.creditThreshold,
      balance: creditBalance,
      provider: 'anthropic'
    };
  }

  /**
   * Check OpenAI credits (placeholder - would need actual API integration)
   */
  async checkOpenAICredits() {
    // In a real implementation, this would call OpenAI's billing API
    const creditBalance = parseFloat(process.env.OPENAI_CREDIT_BALANCE || '0');
    
    return {
      sufficient: creditBalance > this.config.creditThreshold,
      balance: creditBalance,
      provider: 'openai'
    };
  }

  /**
   * Check Google credits (placeholder - would need actual API integration)
   */
  async checkGoogleCredits() {
    // In a real implementation, this would check Google's billing
    const creditBalance = parseFloat(process.env.GOOGLE_CREDIT_BALANCE || '0');
    
    return {
      sufficient: creditBalance > this.config.creditThreshold,
      balance: creditBalance,
      provider: 'google'
    };
  }

  /**
   * Check OpenRouter credits (placeholder - would need actual API integration)
   */
  async checkOpenRouterCredits() {
    // In a real implementation, this would call OpenRouter's API
    const creditBalance = parseFloat(process.env.OPENROUTER_CREDIT_BALANCE || '0');
    
    return {
      sufficient: creditBalance > this.config.creditThreshold,
      balance: creditBalance,
      provider: 'openrouter'
    };
  }

  /**
   * Switch to fallback provider
   */
  async activateFallback(reason = 'credit_exhausted') {
    if (!this.isFallbackActive) {
      console.log(`[FALLBACK ACTIVATED] Switching to ${this.config.fallbackProvider} due to: ${reason}`);
      
      // Update current provider
      this.currentProvider = this.config.fallbackProvider;
      this.isFallbackActive = true;
      this.usageStats.lastSwitchTime = new Date().toISOString();
      this.usageStats.switchReason = reason;
      
      // Log the switch for monitoring
      await this.logFallbackEvent(reason);
      
      // Send notification about the switch
      await this.notifyFallbackActivation(reason);
      
      return true;
    }
    return false;
  }

  /**
   * Attempt to return to primary provider if credits are restored
   */
  async attemptReturnToPrimary() {
    if (this.isFallbackActive) {
      const creditCheck = await this.checkCredits();
      
      if (creditCheck.sufficient) {
        console.log(`[PRIMARY RESTORED] Returning to ${this.config.primaryProvider} - credits restored`);
        
        this.currentProvider = this.config.primaryProvider;
        this.isFallbackActive = false;
        this.usageStats.lastSwitchTime = new Date().toISOString();
        this.usageStats.switchReason = 'credits_restored';
        
        await this.logFallbackEvent('credits_restored');
        await this.notifyPrimaryRestoration();
        
        return true;
      }
    }
    return false;
  }

  /**
   * Log fallback events
   */
  async logFallbackEvent(reason) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      fromProvider: this.isFallbackActive ? this.config.primaryProvider : this.config.fallbackProvider,
      toProvider: this.isFallbackActive ? this.config.fallbackProvider : this.config.primaryProvider,
      reason: reason,
      isFallbackActive: this.isFallbackActive
    };

    try {
      await appendJsonArray(path.join('logs', 'fallback_events.json'), logEntry, {
        maxEntries: 100
      });
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      console.warn(`[multi-agent-fallback] fallback log append failed: ${message}`);
    }
  }

  /**
   * Notify about fallback activation
   */
  async notifyFallbackActivation(reason) {
    const notification = {
      type: 'fallback_activation',
      timestamp: new Date().toISOString(),
      reason: reason,
      currentProvider: this.currentProvider,
      message: `API credits exhausted for primary provider. Switched to ${this.config.fallbackProvider} fallback.`
    };
    
    console.log(`\n🔔 FALLBACK NOTIFICATION:`);
    console.log(`   Status: Fallback activated`);
    console.log(`   Reason: ${reason}`);
    console.log(`   Current provider: ${this.currentProvider}`);
    console.log(`   Message: API credits exhausted for primary provider. Switched to ${this.config.fallbackProvider} fallback.\n`);
    
    // Log to a notifications file as well
    await this.logNotification(notification);
  }

  /**
   * Notify about primary restoration
   */
  async notifyPrimaryRestoration() {
    const notification = {
      type: 'primary_restoration',
      timestamp: new Date().toISOString(),
      currentProvider: this.currentProvider,
      message: `Primary provider credits restored. Returned to ${this.config.primaryProvider}.`
    };
    
    console.log(`\n🔔 RESTORATION NOTIFICATION:`);
    console.log(`   Status: Primary provider restored`);
    console.log(`   Current provider: ${this.currentProvider}`);
    console.log(`   Message: Primary provider credits restored. Returned to ${this.config.primaryProvider}.\n`);
    
    await this.logNotification(notification);
  }

  /**
   * Log notifications
   */
  async logNotification(notification) {
    try {
      await appendJsonArray(path.join('logs', 'notifications.json'), notification, {
        maxEntries: 50
      });
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      console.warn(`[multi-agent-fallback] notification log append failed: ${message}`);
    }
  }

  /**
   * Start monitoring for credit exhaustion
   */
  startMonitoring() {
    if (this.monitorInterval) {
      clearInterval(this.monitorInterval);
    }
    
    console.log(`Starting multi-agent fallback monitoring...`);
    console.log(`Primary provider: ${this.config.primaryProvider}`);
    console.log(`Fallback provider: ${this.config.fallbackProvider}`);
    console.log(`Check interval: ${this.config.checkInterval}ms`);
    
    this.monitorInterval = setInterval(async () => {
      try {
        if (!this.isFallbackActive) {
          // Check if we need to switch to fallback
          const creditCheck = await this.checkCredits();
          
          if (!creditCheck.sufficient) {
            await this.activateFallback('credit_threshold_reached');
          }
        } else {
          // We're in fallback mode, check if we can return to primary
          await this.attemptReturnToPrimary();
        }
        
        // Update usage stats
        if (this.isFallbackActive) {
          this.usageStats.fallbackRequests++;
        } else {
          this.usageStats.primaryRequests++;
        }
      } catch (error) {
        console.error('Error during credit monitoring:', error);
      }
    }, this.config.checkInterval);
    
    return this.monitorInterval;
  }

  /**
   * Stop monitoring
   */
  stopMonitoring() {
    if (this.monitorInterval) {
      clearInterval(this.monitorInterval);
      this.monitorInterval = null;
      console.log('Multi-agent fallback monitoring stopped.');
    }
  }

  /**
   * Get current status
   */
  getStatus() {
    return {
      currentProvider: this.currentProvider,
      isFallbackActive: this.isFallbackActive,
      usageStats: this.usageStats,
      config: this.config
    };
  }

  /**
   * Make a request using the appropriate provider
   */
  async makeRequest(prompt, options = {}) {
    const metadata = options.metadata && typeof options.metadata === 'object' ? { ...options.metadata } : {};
    if (options.simulation && typeof options.simulation === 'object') {
      metadata.simulation = options.simulation;
    }

    const messages =
      Array.isArray(options.messages) && options.messages.length > 0
        ? options.messages
        : [{ role: 'user', content: typeof prompt === 'string' ? prompt : String(prompt || '') }];

    const result = await callModel({
      taskId: options.taskId || `fallback_${Date.now()}`,
      messages,
      taskClass: options.taskClass || options.task_class,
      requiresClaude: Boolean(
        options.requiresClaude === true ||
          options.requires_claude === true ||
          metadata.requires_claude === true
      ),
      allowNetwork: options.allowNetwork !== false && options.allow_network !== false,
      preferredBackend: options.preferredBackend || options.preferred_backend,
      metadata
    });

    this.isFallbackActive = result.backend === BACKENDS.LOCAL_QWEN;
    this.currentProvider = this.isFallbackActive
      ? this.config.fallbackProvider
      : result.backend === BACKENDS.OATH_CLAUDE
      ? 'oath'
      : 'anthropic';

    if (this.isFallbackActive) {
      this.usageStats.fallbackRequests += 1;
    } else {
      this.usageStats.primaryRequests += 1;
    }

    return {
      provider: result.backend,
      timestamp: new Date().toISOString(),
      promptLength: typeof prompt === 'string' ? prompt.length : JSON.stringify(messages).length,
      isFallbackActive: this.isFallbackActive,
      response: result.response,
      usage: result.usage,
      events: result.events
    };
  }
}

// Example usage:
/*
const fallbackSystem = new MultiAgentFallback({
  primaryProvider: 'anthropic',
  fallbackProvider: 'qwen',
  creditThreshold: 0.1,
  checkInterval: 60000
});

fallbackSystem.startMonitoring();
*/

module.exports = MultiAgentFallback;

// If run directly, start monitoring
if (require.main === module) {
  console.log("Multi-Agent Fallback System");
  console.log("===========================");
  
  const fallbackSystem = new MultiAgentFallback({
    primaryProvider: 'anthropic', // Could be 'openai', 'google', etc.
    fallbackProvider: 'qwen',     // Local Qwen model
    creditThreshold: 0.1,         // Switch when credits fall below $0.10
    checkInterval: 60000          // Check every minute
  });
  
  console.log("Configuration:");
  console.log("- Primary Provider:", fallbackSystem.config.primaryProvider);
  console.log("- Fallback Provider:", fallbackSystem.config.fallbackProvider);
  console.log("- Credit Threshold:", fallbackSystem.config.creditThreshold);
  console.log("- Check Interval:", fallbackSystem.config.checkInterval, "ms");
  
  fallbackSystem.startMonitoring();
  
  console.log("\nThe system will now monitor API credits and automatically switch to Qwen fallback when credits are exhausted.");
  console.log("Notifications will be displayed when switching occurs.");
  
  // Keep the process alive
  process.stdin.resume();
}
