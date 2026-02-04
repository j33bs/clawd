// setup_automated_systems.js
// Initializes all automated systems based on memory and architecture

const fs = require('fs');
const path = require('path');

class AutomatedSystemsSetup {
  constructor() {
    this.workspaceDir = '/Users/heathyeager/clawd';
    this.memoryDir = path.join(this.workspaceDir, 'memory');
    this.systems = {};
  }

  async initialize() {
    console.log('🚀 Initializing automated systems...\n');

    // Create memory directory if it doesn't exist
    await this.createMemoryDirectory();
    
    // Initialize all systems
    await this.initializeMemorySystem();
    await this.initializeJobSystem();
    await this.initializeCognitiveRouting();
    await this.initializeSelfImprovementSystem();
    await this.initializeTherapeuticFramework();
    
    // Set up task scheduling
    await this.setupTaskScheduler();
    
    // Create system status report
    await this.generateSystemReport();
    
    console.log('\n✅ All automated systems initialized successfully!');
    console.log('📋 Next steps:');
    console.log('   - Review ARCHITECTURE_OVERVIEW.md for system details');
    console.log('   - Check TASK_SCHEDULER.md for task configurations');
    console.log('   - Monitor memory files for ongoing automated activities');
  }

  async createMemoryDirectory() {
    if (!fs.existsSync(this.memoryDir)) {
      fs.mkdirSync(this.memoryDir, { recursive: true });
      console.log('📁 Created memory directory:', this.memoryDir);
    }
  }

  async initializeMemorySystem() {
    console.log('\n🧠 Setting up Memory Management System...');
    
    // Ensure today's memory file exists
    const today = new Date().toISOString().split('T')[0];
    const todayFile = path.join(this.memoryDir, `${today}.md`);
    
    if (!fs.existsSync(todayFile)) {
      const todayContent = `# Memory - ${today}\n\n## Today's Activities\n- System initialization and automated setup\n\n## Tasks Completed\n- [ ] Memory system initialization\n\n## Notes\n- Automated systems successfully set up\n`;
      fs.writeFileSync(todayFile, todayContent);
      console.log(`   ✅ Created today's memory file: ${todayFile}`);
    }
    
    // Initialize heartbeat state if needed
    const heartbeatStateFile = path.join(this.memoryDir, 'heartbeat-state.json');
    if (!fs.existsSync(heartbeatStateFile)) {
      const heartbeatState = {
        lastChecks: {
          memoryReview: Math.floor(Date.now() / 1000),
          memoryCuration: Math.floor(Date.now() / 1000),
          improvementResearch: Math.floor(Date.now() / 1000)
        },
        maintenanceSchedule: {
          daily: ["reviewRecentLogs"],
          weekly: ["curateLongTermMemory"],
          monthly: ["auditMemoryFiles"]
        }
      };
      fs.writeFileSync(heartbeatStateFile, JSON.stringify(heartbeatState, null, 2));
      console.log('   ✅ Initialized heartbeat state');
    }
    
    // Initialize habits if needed
    const habitsFile = path.join(this.memoryDir, 'habits.json');
    if (!fs.existsSync(habitsFile)) {
      const habitsTemplate = {
        habits: [],
        habitStreaks: {},
        habitHistory: {},
        settings: {
          defaultIdentityFocus: "Who is the person I want to become?",
          habitStackingEnabled: true,
          habitScaling: "tinyHabitsFirst"
        }
      };
      fs.writeFileSync(habitsFile, JSON.stringify(habitsTemplate, null, 2));
      console.log('   ✅ Initialized habits system');
    }
    
    this.systems.memory = true;
  }

  async initializeJobSystem() {
    console.log('\n⚙️  Setting up Job System...');
    
    // Create jobs directory
    const jobsDir = path.join(this.workspaceDir, 'jobs');
    if (!fs.existsSync(jobsDir)) {
      fs.mkdirSync(jobsDir, { recursive: true });
      console.log('   ✅ Created jobs directory:', jobsDir);
    }
    
    // Initialize job queue if needed
    const jobQueueFile = path.join(jobsDir, 'queue.json');
    if (!fs.existsSync(jobQueueFile)) {
      const jobQueue = {
        pending: [],
        running: [],
        completed: [],
        failed: []
      };
      fs.writeFileSync(jobQueueFile, JSON.stringify(jobQueue, null, 2));
      console.log('   ✅ Initialized job queue');
    }
    
    this.systems.jobs = true;
  }

  async initializeCognitiveRouting() {
    console.log('\n🧠 Setting up Cognitive Load Routing...');
    
    // Create cognitive routing configuration
    const cognitiveConfigFile = path.join(this.workspaceDir, 'cognitive_config.json');
    if (!fs.existsSync(cognitiveConfigFile)) {
      const cognitiveConfig = {
        tiers: {
          tier_1_light: { threshold: 1.0, handler: 'simple_response_handler' },
          tier_2_moderate: { threshold: 2.5, handler: 'moderate_reasoning_handler' },
          tier_3_heavy: { threshold: 4.0, handler: 'complex_analysis_handler' },
          tier_4_critical: { threshold: Infinity, handler: 'emergency_handler' }
        },
        intents: [
          'information_request', 'command', 'question', 'feedback',
          'problem_report', 'request_for_help', 'opinion', 'statement',
          'clarification', 'disambiguation', 'context_update', 'task_completion'
        ],
        context_compaction: {
          target_size: 1000,
          essential_keys: ['current_task', 'critical_info', 'urgent_matters'],
          compression_ratio: 0.5
        },
        epistemic_tags: {
          certain_fact: 1.0,
          probable_inference: 0.8,
          observation: 0.7,
          assumption: 0.5,
          hypothetical: 0.3,
          uncertain: 0.2
        }
      };
      fs.writeFileSync(cognitiveConfigFile, JSON.stringify(cognitiveConfig, null, 2));
      console.log('   ✅ Initialized cognitive routing configuration');
    }
    
    this.systems.cognitiveRouting = true;
  }

  async initializeSelfImprovementSystem() {
    console.log('\n📈 Setting up Self-Improvement System...');
    
    // Ensure improvement log exists (we already have one from memory)
    const improvementLogFile = path.join(this.memoryDir, 'improvement_log.json');
    if (!fs.existsSync(improvementLogFile)) {
      const improvementLog = {
        improvements: [],
        researchHistory: [{
          timestamp: new Date().toISOString(),
          categories: {
            productivity: [],
            communication: [],
            learning: [],
            health: [],
            creativity: [],
            relationships: []
          }
        }],
        lastResearch: new Date().toISOString(),
        settings: {
          researchInterval: 86400000, // 24 hours
          improvementCategories: [
            "productivity", "communication", "learning", 
            "health", "creativity", "relationships"
          ],
          maxSearchResults: 5,
          autoApplyThreshold: 0.8
        }
      };
      fs.writeFileSync(improvementLogFile, JSON.stringify(improvementLog, null, 2));
      console.log('   ✅ Initialized improvement log');
    }
    
    this.systems.selfImprovement = true;
  }

  async initializeTherapeuticFramework() {
    console.log('\n🌱 Setting up Therapeutic Framework Integration...');
    
    // Create therapeutic tracking if needed
    const therapeuticTrackingFile = path.join(this.memoryDir, 'therapeutic_tracking.json');
    if (!fs.existsSync(therapeuticTrackingFile)) {
      const therapeuticTracking = {
        clientSessions: [],
        workshopMaterials: [],
        therapeuticTechniques: [],
        ipnbApplications: [],
        actIntegrations: [],
        emotionRegulationTools: [],
        lastUpdated: new Date().toISOString()
      };
      fs.writeFileSync(therapeuticTrackingFile, JSON.stringify(therapeuticTracking, null, 2));
      console.log('   ✅ Initialized therapeutic tracking system');
    }
    
    this.systems.therapeuticFramework = true;
  }

  async setupTaskScheduler() {
    console.log('\n🕒 Setting up Task Scheduler...');
    
    // Create cron jobs for automated tasks
    const cronJobs = [
      {
        id: 'memory_maintenance',
        schedule: '0 2 * * *', // Daily at 2 AM
        description: 'Perform daily memory maintenance tasks',
        command: `cd ${this.workspaceDir} && ./memory_daily_review.sh`,
        enabled: true
      },
      {
        id: 'self_improvement_research',
        schedule: '30 10 * * 1', // Weekly on Mondays at 10:30 AM
        description: 'Run self-improvement research during downtime',
        command: `cd ${this.workspaceDir} && ./self_improvement_research.sh`,
        enabled: true
      },
      {
        id: 'therapeutic_review',
        schedule: '0 9 * * 0', // Weekly on Sundays at 9 AM
        description: 'Review and update therapeutic frameworks',
        command: `cd ${this.workspaceDir} && node review_therapeutic_updates.js`,
        enabled: false // Will need implementation
      }
    ];
    
    const cronConfigFile = path.join(this.workspaceDir, 'cron_jobs.json');
    fs.writeFileSync(cronConfigFile, JSON.stringify(cronJobs, null, 2));
    console.log('   ✅ Created cron job configuration');
    
    // Create placeholder for therapeutic review script
    const therapeuticReviewScript = path.join(this.workspaceDir, 'review_therapeutic_updates.js');
    if (!fs.existsSync(therapeuticReviewScript)) {
      const reviewScript = `// review_therapeutic_updates.js
// Placeholder for therapeutic framework review

console.log('Reviewing therapeutic frameworks and updates...');
console.log('This script would normally check for new research in IPNB, ACT, and emotional regulation.');
console.log('It would update the therapeutic stacking framework based on latest findings.');
console.log('Last updated:', new Date().toISOString());
`;
      fs.writeFileSync(therapeuticReviewScript, reviewScript);
      console.log('   ✅ Created therapeutic review script placeholder');
    }
    
    this.systems.taskScheduler = true;
  }

  async generateSystemReport() {
    console.log('\n📊 Generating System Report...');
    
    const report = {
      timestamp: new Date().toISOString(),
      workspace: this.workspaceDir,
      memoryDirectory: this.memoryDir,
      initializedSystems: Object.keys(this.systems).filter(sys => this.systems[sys]),
      fileCounts: {
        memoryFiles: fs.readdirSync(this.memoryDir).filter(f => f.endsWith('.md')).length,
        totalMemoryFiles: fs.readdirSync(this.memoryDir).length,
        workspaceMarkdownFiles: fs.readdirSync(this.workspaceDir).filter(f => f.endsWith('.md')).length
      },
      systemStatus: this.systems
    };
    
    const reportFile = path.join(this.memoryDir, `system_setup_report_${new Date().toISOString().split('T')[0]}.json`);
    fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
    
    console.log('   📄 System report generated:', reportFile);
    console.log('   📊 Report summary:');
    console.log(`      - Memory files: ${report.fileCounts.memoryFiles}`);
    console.log(`      - Total memory items: ${report.fileCounts.totalMemoryFiles}`);
    console.log(`      - Workspace docs: ${report.fileCounts.workspaceMarkdownFiles}`);
    console.log(`      - Active systems: ${report.initializedSystems.length}`);
  }
}

// Run the setup
async function runSetup() {
  const setup = new AutomatedSystemsSetup();
  try {
    await setup.initialize();
  } catch (error) {
    console.error('❌ Error during setup:', error);
    process.exit(1);
  }
}

// Only run if this file is executed directly
if (require.main === module) {
  runSetup();
}

module.exports = AutomatedSystemsSetup;