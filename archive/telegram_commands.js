// telegram_commands.js
// Telegram control plane commands for the automation orchestrator

const JobManager = require('./job_manager');
const jobManager = new JobManager();

// Command handlers
const commands = {
  // /ping - Simple connectivity check
  ping: async (ctx) => {
    try {
      await ctx.reply('🤖 Automation Orchestrator is alive!');
    } catch (error) {
      console.error('Error in /ping command:', error);
    }
  },

  // /status - System status overview
  status: async (ctx) => {
    try {
      const jobs = jobManager.recent(5);
      const stats = calculateStats(jobs);
      
      let statusMsg = `🤖 Automation Orchestrator Status\n\n`;
      statusMsg += `📅 Active Jobs: ${stats.active}\n`;
      statusMsg += `✅ Successful: ${stats.successful}\n`;
      statusMsg += `❌ Failed: ${stats.failed}\n`;
      statusMsg += `⏳ Pending Approval: ${stats.pendingApproval}\n\n`;
      
      if (jobs.length > 0) {
        statusMsg += `📋 Recent Jobs:\n`;
        jobs.forEach(job => {
          statusMsg += `• ${job.id} (${job.status}) - ${job.type}\n`;
        });
      } else {
        statusMsg += `📋 No recent jobs found.`;
      }
      
      await ctx.reply(statusMsg);
    } catch (error) {
      console.error('Error in /status command:', error);
      await ctx.reply('Error retrieving status.');
    }
  },

  // /jobs - List all jobs with filtering options
  jobs: async (ctx) => {
    try {
      const args = ctx.message.text.split(' ').slice(1);
      let filter = {};
      
      if (args.length > 0) {
        if (args[0].startsWith('status:')) {
          filter.status = args[0].split(':')[1];
        } else if (args[0].startsWith('type:')) {
          filter.type = args[0].split(':')[1];
        }
      }
      
      const jobs = jobManager.list(filter);
      const displayJobs = jobs.slice(0, 10); // Limit to 10 jobs
      
      if (displayJobs.length === 0) {
        await ctx.reply('No jobs found.');
        return;
      }
      
      let jobsList = `📋 Jobs (${jobs.length} total):\n\n`;
      displayJobs.forEach(job => {
        jobsList += `ID: ${job.id}\n`;
        jobsList += `Type: ${job.type}\n`;
        jobsList += `Status: ${job.status}\n`;
        jobsList += `Created: ${job.created_at}\n`;
        if (job.completed_at) {
          jobsList += `Completed: ${job.completed_at}\n`;
        }
        jobsList += `---\n`;
      });
      
      await ctx.reply(jobsList);
    } catch (error) {
      console.error('Error in /jobs command:', error);
      await ctx.reply('Error retrieving jobs list.');
    }
  },

  // /approve - Approve a pending job for execution
  approve: async (ctx) => {
    try {
      const args = ctx.message.text.split(' ').slice(1);
      
      if (args.length === 0) {
        await ctx.reply('Usage: /approve <job_id>');
        return;
      }
      
      const jobId = args[0];
      const job = jobManager.get(jobId);
      
      if (!job) {
        await ctx.reply(`Job ${jobId} not found.`);
        return;
      }
      
      if (job.status !== 'approved') {
        jobManager.updateStatus(jobId, 'approved');
        jobManager.log(jobId, 'INFO', `Job approved by user`);
        
        await ctx.reply(`✅ Job ${jobId} approved for execution.`);
      } else {
        await ctx.reply(`Job ${jobId} is already approved.`);
      }
    } catch (error) {
      console.error('Error in /approve command:', error);
      await ctx.reply('Error approving job.');
    }
  }
};

// Helper function to calculate statistics
function calculateStats(jobs) {
  const stats = {
    active: 0,
    successful: 0,
    failed: 0,
    pendingApproval: 0
  };
  
  jobs.forEach(job => {
    switch (job.status) {
      case 'running':
      case 'pending':
        stats.active++;
        break;
      case 'success':
        stats.successful++;
        break;
      case 'failed':
        stats.failed++;
        break;
      case 'approved':
        stats.pendingApproval++;
        break;
    }
  });
  
  return stats;
}

module.exports = { commands, jobManager };