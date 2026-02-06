/**
 * init_fallback_system.js
 * 
 * Initializes the multi-agent fallback system to switch to Qwen when API credits are exhausted.
 */

const MultiAgentFallback = require('./multi_agent_fallback.js');
const fs = require('fs').promises;
const path = require('path');
const { createModelRuntime } = require('../core/model_runtime');
const { callModel } = require('../core/model_call');

function resolveWorkspacePath(relativePath) {
  return path.resolve(__dirname, '..', relativePath);
}

async function readJsonFile(filePath) {
  const data = await fs.readFile(filePath, 'utf8');
  return JSON.parse(data);
}

async function initializeFallbackSystem() {
  console.log("🔄 Initializing Multi-Agent Fallback System");
  console.log("========================================");
  
  try {
    // Load configuration
    let config = {};
    try {
      const configPath = resolveWorkspacePath('config/agent_fallback.json');
      const configData = configPath ? await readJsonFile(configPath) : null;
      if (configData) {
        config = configData;
      } else {
        throw new Error('Config not found');
      }
    } catch (error) {
      console.log("⚠️  Configuration file not found, using defaults");
      config.multiAgentFallback = {
        enabled: true,
        primaryProvider: 'anthropic',
        fallbackProvider: 'qwen-portal/coder-model',
        creditThreshold: 0.1,
        checkInterval: 60000,
        monitoringEnabled: true
      };
    }
    
    // Initialize canonical model-call runtime for router/provider selection.
    const modelRuntime = createModelRuntime();
    global.__OPENCLAW_MODEL_RUNTIME = modelRuntime;
    global.__OPENCLAW_CALL_MODEL = callModel;

    if (!config.multiAgentFallback.enabled) {
      console.log("❌ Multi-agent fallback system is disabled in configuration");
      return null;
    }
    
    // Create the fallback system
    const fallbackSystem = new MultiAgentFallback({
      primaryProvider: config.multiAgentFallback.primaryProvider,
      fallbackProvider: config.multiAgentFallback.fallbackProvider,
      creditThreshold: config.multiAgentFallback.creditThreshold,
      checkInterval: config.multiAgentFallback.checkInterval
    });
    
    console.log("📋 Configuration Loaded:");
    console.log(`   Primary Provider: ${config.multiAgentFallback.primaryProvider}`);
    console.log(`   Fallback Provider: ${config.multiAgentFallback.fallbackProvider}`);
    console.log(`   Credit Threshold: $${config.multiAgentFallback.creditThreshold}`);
    console.log(`   Check Interval: ${config.multiAgentFallback.checkInterval}ms`);
    
    // Start monitoring
    if (config.multiAgentFallback.monitoringEnabled) {
      fallbackSystem.startMonitoring();
      
      console.log("\n✅ Multi-Agent Fallback System Active");
      console.log("✨ The system will now monitor API credits and automatically switch to Qwen when credits are exhausted");
      console.log("🔔 You will be notified immediately when a switch occurs");
      
      // Store the system instance for other parts of the application to access
      global.fallbackSystem = fallbackSystem;
      
      // Display current status
      const status = fallbackSystem.getStatus();
      console.log(`\n📊 Current Status:`);
      console.log(`   Active Provider: ${status.currentProvider}`);
      console.log(`   Fallback Active: ${status.isFallbackActive ? 'YES' : 'NO'}`);
      console.log(`   Primary Requests: ${status.usageStats.primaryRequests}`);
      console.log(`   Fallback Requests: ${status.usageStats.fallbackRequests}`);
      
    } else {
      console.log("\n⚠️  Monitoring is disabled in configuration");
    }
    
    console.log("\n📝 System Notes:");
    console.log("- The system will automatically detect when primary API credits are exhausted");
    console.log("- Upon detection, it will seamlessly switch to the Qwen local model");
    console.log("- You will receive immediate notification when a fallback occurs");
    console.log("- When primary credits are restored, it will switch back automatically");
    console.log("- All fallback events are logged for review in ./logs/fallback_events.json");
    
    return fallbackSystem;
    
  } catch (error) {
    console.error("❌ Error initializing fallback system:", error);
    throw error;
  }
}

// Run the initialization
if (require.main === module) {
  initializeFallbackSystem()
    .then(system => {
      if (system) {
        console.log("\n🚀 Multi-Agent Fallback System initialized successfully!");
        console.log("💡 The system is now actively monitoring API usage.");
      }
    })
    .catch(error => {
      console.error("\n💥 Failed to initialize fallback system:", error);
      process.exit(1);
    });
}

module.exports = { initializeFallbackSystem, callModel };
