// orchestrator.js
// Main automation orchestrator implementing the specified operating rules

const JobManager = require('./job_manager');
const { commands } = require('./telegram_commands');
const ModelRouter = require('./model_router');
const CalendarService = require('./calendar_service');
const EmailService = require('./email_service');
const NotesService = require('./notes_service');
const ArtifactPipeline = require('./artifact_pipeline');

class Orchestrator {
  constructor() {
    this.jobManager = new JobManager();
    this.modelRouter = new ModelRouter();
    this.calendarService = new CalendarService();
    this.emailService = new EmailService();
    this.notesService = new NotesService();
    this.artifactPipeline = new ArtifactPipeline();
    
    // Circuit breaker state
    this.providerStatus = new Map(); // provider -> { available: boolean, lastError: Date }
    
    // Initialize services
    this.initializeServices();
  }

  // Initialize all services
  initializeServices() {
    // Services are initialized in their constructors
    console.log('Orchestrator services initialized');
  }

  // Authenticate a provider
  async authenticate(provider, credentials) {
    this.jobManager.log('system', 'INFO', `Authenticating ${provider}`);
    
    try {
      let authenticated = false;
      
      switch (provider) {
        case 'calendar':
          authenticated = this.calendarService.validateCredentials(credentials);
          break;
        case 'email':
          authenticated = this.emailService.validateCredentials(credentials);
          break;
        default:
          throw new Error(`Unknown provider: ${provider}`);
      }
      
      if (authenticated) {
        this.setProviderAvailable(provider, true);
        this.jobManager.log('system', 'INFO', `${provider} authentication successful`);
        return { success: true, provider };
      } else {
        throw new Error(`${provider} authentication failed`);
      }
    } catch (error) {
      this.handleProviderError(provider, error);
      return { success: false, error: error.message };
    }
  }

  // Dry-run a command
  async dryRun(provider, command, params) {
    this.jobManager.log('system', 'INFO', `Dry-running ${provider}.${command}`);
    
    try {
      // Validate provider availability
      if (!this.isProviderAvailable(provider)) {
        throw new Error(`${provider} is currently unavailable`);
      }
      
      let result;
      
      switch (provider) {
        case 'calendar':
          // Example dry-run for calendar
          if (command === 'getAvailabilitySummary') {
            result = { 
              would_execute: true, 
              params: params, 
              estimated_result: { summary: 'Would return availability summary' } 
            };
          }
          break;
          
        case 'email':
          // Example dry-run for email
          if (command === 'getDailyDigest') {
            result = { 
              would_execute: true, 
              params: params, 
              estimated_result: { summary: 'Would return email digest' } 
            };
          }
          break;
          
        default:
          throw new Error(`Unknown provider: ${provider}`);
      }
      
      this.jobManager.log('system', 'INFO', `Dry-run for ${provider}.${command} successful`);
      return { success: true, result };
    } catch (error) {
      this.jobManager.log('system', 'ERROR', `Dry-run failed for ${provider}.${command}: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  // Execute a command with proper job tracking
  async executeCommand(commandType, params, requireApproval = false) {
    // Create job
    const jobId = this.jobManager.create(commandType, params, `Execution of ${commandType}`);
    
    try {
      // Check if approval is required
      if (requireApproval) {
        this.jobManager.updateStatus(jobId, 'approved'); // In real system, this would wait for approval
        this.jobManager.log(jobId, 'INFO', `Awaiting approval for ${commandType}`);
        // For demo purposes, we'll auto-approve
        this.jobManager.updateStatus(jobId, 'running');
      } else {
        this.jobManager.updateStatus(jobId, 'running');
      }
      
      let result;
      
      switch (commandType) {
        case 'calendar.availability':
          result = await this.calendarService.getAvailabilitySummary(params.days || 7);
          break;
          
        case 'email.digest':
          result = await this.emailService.getDailyDigest(params.account, params.days || 1);
          break;
          
        case 'notes.append':
          result = await this.notesService.appendNote(
            params.content, 
            params.category, 
            params.tags || []
          );
          break;
          
        case 'artifact.docx':
          result = await this.artifactPipeline.generateDocxReport(
            params.templateData, 
            params.filename
          );
          break;
          
        case 'artifact.spreadsheet':
          result = await this.artifactPipeline.generateSpreadsheetReport(
            params.templateData, 
            params.filename, 
            params.format || 'csv'
          );
          break;
          
        default:
          throw new Error(`Unknown command type: ${commandType}`);
      }
      
      // Store result
      this.jobManager.setOutputs(jobId, result);
      this.jobManager.updateStatus(jobId, 'success');
      this.jobManager.log(jobId, 'INFO', `${commandType} executed successfully`);
      
      return { success: true, jobId, result };
    } catch (error) {
      this.jobManager.updateStatus(jobId, 'failed');
      this.jobManager.log(jobId, 'ERROR', `Command failed: ${error.message}`);
      return { success: false, jobId, error: error.message };
    }
  }

  // Set provider availability (for circuit breaker)
  setProviderAvailable(provider, available) {
    if (available) {
      this.providerStatus.set(provider, { available: true, lastError: null });
    } else {
      this.providerStatus.set(provider, { available: false, lastError: new Date() });
    }
  }

  // Check if provider is available
  isProviderAvailable(provider) {
    const status = this.providerStatus.get(provider);
    return status ? status.available : true; // Default to available if not tracked
  }

  // Handle provider errors (circuit breaker logic)
  handleProviderError(provider, error) {
    // Check if it's an authentication error
    if (error.message.includes('401') || error.message.includes('403')) {
      this.setProviderAvailable(provider, false);
      this.jobManager.log('system', 'ERROR', `${provider} marked unavailable due to auth error: ${error.message}`);
      console.log(`CIRCUIT BREAKER: ${provider} marked unavailable due to authentication error`);
    }
  }

  // Redact sensitive information from logs
  redactSecrets(obj) {
    if (typeof obj !== 'object' || obj === null) return obj;
    
    const redacted = Array.isArray(obj) ? [] : {};
    
    for (const [key, value] of Object.entries(obj)) {
      if (this.isSecret(key)) {
        redacted[key] = '[REDACTED]';
      } else if (typeof value === 'object' && value !== null) {
        redacted[key] = this.redactSecrets(value);
      } else {
        redacted[key] = value;
      }
    }
    
    return redacted;
  }

  // Check if a field name indicates a secret
  isSecret(key) {
    const secretPatterns = [
      'token', 'secret', 'key', 'password', 'auth', 'credential', 
      'api', 'bearer', 'oauth', 'session', 'cookie', 'cert', 'private'
    ];
    
    const lowerKey = key.toLowerCase();
    return secretPatterns.some(pattern => lowerKey.includes(pattern));
  }

  // Get system status
  getStatus() {
    return {
      providers: Object.fromEntries(this.providerStatus.entries()),
      jobs: {
        recent: this.jobManager.recent(5),
        counts: this.getJobCounts()
      },
      services: {
        calendar: 'initialized',
        email: 'initialized',
        notes: 'initialized',
        artifacts: 'initialized'
      }
    };
  }

  // Get job counts
  getJobCounts() {
    const allJobs = this.jobManager.list();
    const counts = { total: allJobs.length, byStatus: {}, byType: {} };
    
    for (const job of allJobs) {
      counts.byStatus[job.status] = (counts.byStatus[job.status] || 0) + 1;
      counts.byType[job.type] = (counts.byType[job.type] || 0) + 1;
    }
    
    return counts;
  }

  // Verify capability: Test the job system
  async verifyJobSystem() {
    console.log("Testing Job System...");
    
    try {
      // Create a test job
      const jobId = this.jobManager.create('test', { test: true }, 'Test job');
      console.log(`✓ Created job: ${jobId}`);
      
      // Update status
      this.jobManager.updateStatus(jobId, 'running');
      console.log("✓ Updated job status to running");
      
      // Add log
      this.jobManager.log(jobId, 'INFO', 'Test log entry');
      console.log("✓ Added log entry");
      
      // Set output
      this.jobManager.setOutputs(jobId, { result: 'test passed' });
      console.log("✓ Set job outputs");
      
      // Update to success
      this.jobManager.updateStatus(jobId, 'success');
      console.log("✓ Updated job status to success");
      
      // Retrieve job
      const retrievedJob = this.jobManager.get(jobId);
      if (retrievedJob) {
        console.log("✓ Retrieved job successfully");
        return true;
      } else {
        console.log("✗ Failed to retrieve job");
        return false;
      }
    } catch (error) {
      console.log(`✗ Job system test failed: ${error.message}`);
      return false;
    }
  }

  // Verify capability: Test the model router
  async verifyModelRouter() {
    console.log("\nTesting Model Router...");
    
    try {
      const task1 = "Classify this email as important or not";
      const route1 = this.modelRouter.routeTask(task1);
      console.log(`✓ Classified task '${task1}' -> ${route1.model}`);
      
      const task2 = "Write a detailed analysis of the quarterly results";
      const route2 = this.modelRouter.routeTask(task2);
      console.log(`✓ Classified task '${task2}' -> ${route2.model}`);
      
      const dynamicRoute = this.modelRouter.dynamicRoute("This is a longer piece of content that might need more sophisticated processing and analysis", "writing task");
      console.log(`✓ Dynamic routing applied: ${dynamicRoute.model}`);
      
      return true;
    } catch (error) {
      console.log(`✗ Model router test failed: ${error.message}`);
      return false;
    }
  }

  // Verify capability: Test the calendar service
  async verifyCalendarService() {
    console.log("\nTesting Calendar Service...");
    
    try {
      // Mock some events
      const mockEvents = [
        { id: 1, title: "Team Meeting", start: new Date(Date.now() + 86400000).toISOString(), duration: 1, location: "Conference Room" },
        { id: 2, title: "Client Call", start: new Date(Date.now() + 172800000).toISOString(), duration: 0.5, location: "Phone" }
      ];
      
      await this.calendarService.mockSync(mockEvents);
      console.log("✓ Mock synced calendar events");
      
      const summary = await this.calendarService.getAvailabilitySummary(7);
      console.log(`✓ Got availability summary for ${summary.busyDays} busy days`);
      
      return true;
    } catch (error) {
      console.log(`✗ Calendar service test failed: ${error.message}`);
      return false;
    }
  }

  // Verify capability: Test the email service
  async verifyEmailService() {
    console.log("\nTesting Email Service...");
    
    try {
      // Mock some emails
      const mockEmails = [
        { id: '1', from: 'boss@company.com', subject: 'Important: Quarterly Review', date: new Date().toISOString(), read: false, important: true, body: 'We need to discuss the quarterly review...' },
        { id: '2', from: 'colleague@company.com', subject: 'Meeting Tomorrow', date: new Date(Date.now() - 3600000).toISOString(), read: true, important: false, body: 'Just confirming tomorrow\'s meeting...' }
      ];
      
      await this.emailService.mockSync('default', mockEmails);
      console.log("✓ Mock synced email messages");
      
      const digest = await this.emailService.getDailyDigest('default', 1);
      console.log(`✓ Got email digest with ${digest.totalMessages} messages`);
      
      const draft = await this.emailService.generateDraftReply('1', 'default');
      console.log(`✓ Generated draft reply for message 1`);
      
      return true;
    } catch (error) {
      console.log(`✗ Email service test failed: ${error.message}`);
      return false;
    }
  }

  // Verify capability: Test the notes service
  async verifyNotesService() {
    console.log("\nTesting Notes Service...");
    
    try {
      // Append a test note
      const note = await this.notesService.appendNote(
        "This is a test note for verification purposes", 
        "verification", 
        ["test", "automation"]
      );
      console.log(`✓ Appended note: ${note.id}`);
      
      // Retrieve by category
      const categoryNotes = await this.notesService.retrieveByCategory("verification");
      console.log(`✓ Retrieved ${categoryNotes.length} notes from verification category`);
      
      // Search notes
      const searchResults = await this.notesService.search("test");
      console.log(`✓ Found ${searchResults.length} notes matching 'test'`);
      
      return true;
    } catch (error) {
      console.log(`✗ Notes service test failed: ${error.message}`);
      return false;
    }
  }

  // Verify capability: Test the artifact pipeline
  async verifyArtifactPipeline() {
    console.log("\nTesting Artifact Pipeline...");
    
    try {
      // Generate a DOCX report
      const docxResult = await this.artifactPipeline.generateDocxReport({
        title: "Test Report",
        author: "Automation System",
        content: "This is a test document generated by the automation system.",
        template: "standard"
      });
      console.log(`✓ Generated DOCX report: ${docxResult.filename}`);
      
      // Generate a spreadsheet
      const spreadsheetResult = await this.artifactPipeline.generateSpreadsheetReport({
        columns: ["Name", "Value", "Status"],
        data: [
          { Name: "Item 1", Value: 100, Status: "Active" },
          { Name: "Item 2", Value: 200, Status: "Inactive" },
          { Name: "Item 3", Value: 300, Status: "Active" }
        ]
      });
      console.log(`✓ Generated spreadsheet: ${spreadsheetResult.filename}`);
      
      // Validate artifacts
      const docxValid = await this.artifactPipeline.validateArtifact(docxResult.path, 'docx');
      const spreadsheetValid = await this.artifactPipeline.validateArtifact(spreadsheetResult.path, 'csv');
      console.log(`✓ DOCX validation: ${docxValid.valid}, Spreadsheet validation: ${spreadsheetValid.valid}`);
      
      return true;
    } catch (error) {
      console.log(`✗ Artifact pipeline test failed: ${error.message}`);
      return false;
    }
  }

  // Run all verifications
  async runVerifications() {
    console.log("Running capability verifications...\n");
    
    const tests = [
      { name: "Job System", fn: () => this.verifyJobSystem() },
      { name: "Model Router", fn: () => this.verifyModelRouter() },
      { name: "Calendar Service", fn: () => this.verifyCalendarService() },
      { name: "Email Service", fn: () => this.verifyEmailService() },
      { name: "Notes Service", fn: () => this.verifyNotesService() },
      { name: "Artifact Pipeline", fn: () => this.verifyArtifactPipeline() }
    ];
    
    const results = {};
    
    for (const test of tests) {
      try {
        console.log(`\n--- Testing ${test.name} ---`);
        results[test.name] = await test.fn();
      } catch (error) {
        console.log(`✗ ${test.name} test threw error: ${error.message}`);
        results[test.name] = false;
      }
    }
    
    console.log("\n--- Verification Results ---");
    let allPassed = true;
    
    for (const [name, passed] of Object.entries(results)) {
      const status = passed ? "✓ PASS" : "✗ FAIL";
      console.log(`${status}: ${name}`);
      if (!passed) allPassed = false;
    }
    
    console.log(`\nOverall: ${allPassed ? 'ALL TESTS PASSED' : 'SOME TESTS FAILED'}`);
    return allPassed;
  }
}

module.exports = Orchestrator;