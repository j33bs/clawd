// performance_monitor.js
// Real-time system performance monitoring dashboard

const fs = require('fs');
const path = require('path');
const os = require('os');

class PerformanceMonitor {
  constructor() {
    this.workspaceDir = '/Users/heathyeager/clawd';
    this.memoryDir = path.join(this.workspaceDir, 'memory');
    this.startTime = new Date();
  }

  async generateReport() {
    const report = {
      timestamp: new Date().toISOString(),
      systemInfo: this.getSystemInfo(),
      memoryStats: await this.getMemoryStats(),
      jobStats: await this.getJobStats(),
      cognitiveRoutingStats: await this.getCognitiveRoutingStats(),
      therapeuticFrameworkStats: await this.getTherapeuticFrameworkStats(),
      performanceMetrics: await this.getPerformanceMetrics(),
      healthIndicators: await this.getHealthIndicators()
    };

    // Save report to memory directory
    const reportFile = path.join(this.memoryDir, `performance_report_${new Date().toISOString().split('T')[0]}.json`);
    fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));

    return report;
  }

  getSystemInfo() {
    return {
      platform: os.platform(),
      arch: os.arch(),
      totalMemory: os.totalmem(),
      freeMemory: os.freemem(),
      uptime: os.uptime(),
      loadAverage: os.loadavg(),
      cpuCount: os.cpus().length,
      hostname: os.hostname()
    };
  }

  async getMemoryStats() {
    try {
      const files = fs.readdirSync(this.memoryDir);
      const mdFiles = files.filter(f => f.endsWith('.md'));
      const jsonFiles = files.filter(f => f.endsWith('.json'));
      
      let totalSize = 0;
      let recentActivity = 0;
      
      for (const file of files) {
        const filePath = path.join(this.memoryDir, file);
        const stat = fs.statSync(filePath);
        totalSize += stat.size;
        
        // Count files modified in the last 24 hours
        const oneDayAgo = Date.now() - (24 * 60 * 60 * 1000);
        if (stat.mtimeMs > oneDayAgo) {
          recentActivity++;
        }
      }
      
      return {
        totalFiles: files.length,
        markdownFiles: mdFiles.length,
        jsonFiles: jsonFiles.length,
        totalSize: totalSize,
        recentActivity: recentActivity, // Files modified in last 24h
        directory: this.memoryDir
      };
    } catch (error) {
      console.error('Error getting memory stats:', error);
      return { error: error.message };
    }
  }

  async getJobStats() {
    try {
      const jobsDir = path.join(this.workspaceDir, 'jobs');
      if (!fs.existsSync(jobsDir)) {
        return { status: 'jobs directory not found' };
      }
      
      const files = fs.readdirSync(jobsDir);
      const queueFile = path.join(jobsDir, 'queue.json');
      
      if (fs.existsSync(queueFile)) {
        const queueData = JSON.parse(fs.readFileSync(queueFile, 'utf8'));
        return {
          totalJobFiles: files.length,
          pendingJobs: queueData.pending?.length || 0,
          runningJobs: queueData.running?.length || 0,
          completedJobs: queueData.completed?.length || 0,
          failedJobs: queueData.failed?.length || 0,
          jobsDirectory: jobsDir
        };
      }
      
      return {
        totalJobFiles: files.length,
        jobsDirectory: jobsDir
      };
    } catch (error) {
      console.error('Error getting job stats:', error);
      return { error: error.message };
    }
  }

  async getCognitiveRoutingStats() {
    try {
      const configPath = path.join(this.workspaceDir, 'cognitive_config.json');
      if (!fs.existsSync(configPath)) {
        return { status: 'cognitive config not found' };
      }
      
      const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
      
      return {
        tiersConfigured: Object.keys(config.cognitive_load_router.tiers).length,
        intentsTracked: config.cognitive_load_router.intent_classification.known_intents.length,
        contextCompactionEnabled: config.cognitive_load_router.context_compaction.default_target_size,
        epistemicTaggingEnabled: config.cognitive_load_router.epistemic_tagging.default_tag,
        performanceLogging: config.cognitive_load_router.performance.logging_enabled
      };
    } catch (error) {
      console.error('Error getting cognitive routing stats:', error);
      return { error: error.message };
    }
  }

  async getTherapeuticFrameworkStats() {
    try {
      const files = [
        'THERAPEUTIC_STACKING_FRAMEWORK.md',
        'therapeutic_stacking_implementation.json',
        'therapeutic_tracking.json'
      ];
      
      const existingFiles = files.filter(file => 
        fs.existsSync(path.join(this.workspaceDir, file)) ||
        fs.existsSync(path.join(this.memoryDir, file.replace('.md', '.json')))
      );
      
      return {
        frameworkDocs: existingFiles.length,
        implementationGuide: fs.existsSync(path.join(this.workspaceDir, 'therapeutic_stacking_implementation.json')),
        trackingSystem: fs.existsSync(path.join(this.memoryDir, 'therapeutic_tracking.json'))
      };
    } catch (error) {
      console.error('Error getting therapeutic framework stats:', error);
      return { error: error.message };
    }
  }

  async getPerformanceMetrics() {
    try {
      // Calculate uptime since monitor started
      const uptimeMs = Date.now() - this.startTime.getTime();
      
      // Check for recent system reports
      const files = fs.readdirSync(this.memoryDir);
      const recentReports = files.filter(f => f.startsWith('performance_report_'));
      
      return {
        monitorUptimeMs: uptimeMs,
        recentReportsGenerated: recentReports.length,
        avgReportSize: this.calculateAvgReportSize(recentReports),
        lastReport: recentReports.length > 0 ? recentReports.sort().pop() : null
      };
    } catch (error) {
      console.error('Error getting performance metrics:', error);
      return { error: error.message };
    }
  }

  calculateAvgReportSize(reports) {
    if (reports.length === 0) return 0;
    
    const sizes = reports.map(report => {
      try {
        const filePath = path.join(this.memoryDir, report);
        return fs.statSync(filePath).size;
      } catch (e) {
        return 0;
      }
    }).filter(size => size > 0);
    
    if (sizes.length === 0) return 0;
    
    const totalSize = sizes.reduce((sum, size) => sum + size, 0);
    return Math.round(totalSize / sizes.length);
  }

  async getHealthIndicators() {
    try {
      // Check if key systems are properly configured
      const health = {
        memorySystem: fs.existsSync(path.join(this.memoryDir, 'heartbeat-state.json')),
        jobSystem: fs.existsSync(path.join(this.workspaceDir, 'jobs', 'queue.json')),
        cognitiveRouting: fs.existsSync(path.join(this.workspaceDir, 'cognitive_config.json')),
        selfImprovement: fs.existsSync(path.join(this.memoryDir, 'improvement_log.json')),
        therapeuticTracking: fs.existsSync(path.join(this.memoryDir, 'therapeutic_tracking.json')),
        taskScheduler: fs.existsSync(path.join(this.workspaceDir, 'cron_jobs.json')),
        systemInitialized: fs.existsSync(path.join(this.memoryDir, `system_setup_report_${new Date().toISOString().split('T')[0]}.json`))
      };
      
      // Calculate overall health score
      const totalSystems = Object.keys(health).length;
      const healthySystems = Object.values(health).filter(status => status === true).length;
      health.overallHealthPercentage = Math.round((healthySystems / totalSystems) * 100);
      health.status = healthySystems === totalSystems ? 'optimal' : healthySystems >= totalSystems * 0.8 ? 'good' : 'needs_attention';
      
      return health;
    } catch (error) {
      console.error('Error getting health indicators:', error);
      return { error: error.message };
    }
  }

  async displayConsoleReport(report) {
    console.log('\n=== PERFORMANCE MONITOR REPORT ===');
    console.log(`Generated: ${report.timestamp}`);
    console.log('');

    console.log('🔧 SYSTEM INFO');
    console.log(`  Platform: ${report.systemInfo.platform} (${report.systemInfo.arch})`);
    console.log(`  CPU Cores: ${report.systemInfo.cpuCount}`);
    console.log(`  Total Memory: ${(report.systemInfo.totalMemory / (1024**3)).toFixed(2)} GB`);
    console.log(`  Free Memory: ${(report.systemInfo.freeMemory / (1024**3)).toFixed(2)} GB`);
    console.log('');

    console.log('🧠 MEMORY SYSTEM');
    console.log(`  Total Files: ${report.memoryStats.totalFiles}`);
    console.log(`  Markdown Files: ${report.memoryStats.markdownFiles}`);
    console.log(`  Recent Activity: ${report.memoryStats.recentActivity} files`);
    console.log(`  Directory Size: ${(report.memoryStats.totalSize / (1024**2)).toFixed(2)} MB`);
    console.log('');

    console.log('⚙️  JOB SYSTEM');
    if (report.jobStats.pendingJobs !== undefined) {
      console.log(`  Pending: ${report.jobStats.pendingJobs}`);
      console.log(`  Running: ${report.jobStats.runningJobs}`);
      console.log(`  Completed: ${report.jobStats.completedJobs}`);
      console.log(`  Failed: ${report.jobStats.failedJobs}`);
    } else {
      console.log(`  Status: ${report.jobStats.status}`);
    }
    console.log('');

    console.log('🎯 COGNITIVE ROUTING');
    console.log(`  Tiers Configured: ${report.cognitiveRoutingStats.tiersConfigured}`);
    console.log(`  Intents Tracked: ${report.cognitiveRoutingStats.intentsTracked}`);
    console.log(`  Performance Logging: ${report.cognitiveRoutingStats.performanceLogging}`);
    console.log('');

    console.log('🌱 THERAPEUTIC FRAMEWORK');
    console.log(`  Framework Docs: ${report.therapeuticFrameworkStats.frameworkDocs}`);
    console.log(`  Implementation Guide: ${report.therapeuticFrameworkStats.implementationGuide}`);
    console.log(`  Tracking System: ${report.therapeuticFrameworkStats.trackingSystem}`);
    console.log('');

    console.log('🏥 SYSTEM HEALTH');
    console.log(`  Overall Score: ${report.healthIndicators.overallHealthPercentage}%`);
    console.log(`  Status: ${report.healthIndicators.status}`);
    console.log(`  Memory System: ${report.healthIndicators.memorySystem ? '✅' : '❌'}`);
    console.log(`  Job System: ${report.healthIndicators.jobSystem ? '✅' : '❌'}`);
    console.log(`  Cognitive Routing: ${report.healthIndicators.cognitiveRouting ? '✅' : '❌'}`);
    console.log(`  Self Improvement: ${report.healthIndicators.selfImprovement ? '✅' : '❌'}`);
    console.log(`  Therapeutic Tracking: ${report.healthIndicators.therapeuticTracking ? '✅' : '❌'}`);
    console.log(`  Task Scheduler: ${report.healthIndicators.taskScheduler ? '✅' : '❌'}`);
    console.log(`  System Initialized: ${report.healthIndicators.systemInitialized ? '✅' : '❌'}`);
    console.log('');
  }
}

// Run the monitor if executed directly
if (require.main === module) {
  (async () => {
    const monitor = new PerformanceMonitor();
    console.log('🔍 Running performance analysis...');
    
    try {
      const report = await monitor.generateReport();
      await monitor.displayConsoleReport(report);
      
      console.log(`📊 Report saved to: ${path.join(monitor.memoryDir, `performance_report_${new Date().toISOString().split('T')[0]}.json`)}`);
    } catch (error) {
      console.error('❌ Error generating performance report:', error);
    }
  })();
}

module.exports = PerformanceMonitor;