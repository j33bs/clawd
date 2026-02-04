// job_manager.js
// Job management system for the automation orchestrator

const fs = require('fs');
const path = require('path');

class JobManager {
  constructor(jobsDir = './jobs') {
    this.jobsDir = jobsDir;
    if (!fs.existsSync(this.jobsDir)) {
      fs.mkdirSync(this.jobsDir, { recursive: true });
    }
  }

  // Create a new job
  create(type, inputs, description = '') {
    const jobId = `job_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const job = {
      id: jobId,
      status: 'pending',
      type,
      inputs,
      description,
      outputs: {},
      artifacts: [],
      created_at: new Date().toISOString(),
      completed_at: null,
      logs: []
    };
    
    this.log(jobId, 'INFO', `Job created: ${type}`);
    this.saveJob(job);
    return jobId;
  }

  // Get job by ID
  get(jobId) {
    try {
      const jobPath = path.join(this.jobsDir, `${jobId}.json`);
      const jobData = fs.readFileSync(jobPath, 'utf8');
      return JSON.parse(jobData);
    } catch (error) {
      return null;
    }
  }

  // Update job status
  updateStatus(jobId, status) {
    const job = this.get(jobId);
    if (!job) return false;
    
    job.status = status;
    if (['success', 'failed', 'rejected'].includes(status)) {
      job.completed_at = new Date().toISOString();
    }
    
    this.saveJob(job);
    return true;
  }

  // Add log entry to job
  log(jobId, level, message) {
    const job = this.get(jobId);
    if (!job) return false;
    
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      message
    };
    
    job.logs.push(logEntry);
    this.saveJob(job);
    return true;
  }

  // Add artifact to job
  addArtifact(jobId, artifactPath) {
    const job = this.get(jobId);
    if (!job) return false;
    
    job.artifacts.push(artifactPath);
    this.saveJob(job);
    return true;
  }

  // Set job outputs
  setOutputs(jobId, outputs) {
    const job = this.get(jobId);
    if (!job) return false;
    
    job.outputs = { ...job.outputs, ...outputs };
    this.saveJob(job);
    return true;
  }

  // Save job to disk
  saveJob(job) {
    const jobPath = path.join(this.jobsDir, `${job.id}.json`);
    fs.writeFileSync(jobPath, JSON.stringify(job, null, 2));
  }

  // List all jobs
  list(filter = {}) {
    const files = fs.readdirSync(this.jobsDir);
    const jobs = files
      .filter(file => file.endsWith('.json'))
      .map(file => {
        const jobPath = path.join(this.jobsDir, file);
        try {
          return JSON.parse(fs.readFileSync(jobPath, 'utf8'));
        } catch (error) {
          return null;
        }
      })
      .filter(job => job !== null);

    // Apply filters
    if (filter.status) {
      jobs.filter(j => j.status === filter.status);
    }
    if (filter.type) {
      jobs.filter(j => j.type === filter.type);
    }

    return jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }

  // Get recent jobs
  recent(limit = 10) {
    return this.list().slice(0, limit);
  }
}

module.exports = JobManager;