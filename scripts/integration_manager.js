/**
 * integration_manager.js
 * 
 * Unified integration manager for calendar and mail services
 * Coordinates both calendar and mail integrations
 */

const CalendarIntegration = require('./calendar_integration.js');
const MailIntegration = require('./mail_integration.js');
const fs = require('fs').promises;

class IntegrationManager {
  constructor(options = {}) {
    this.options = {
      autoStart: options.autoStart !== false, // Default to true
      ...options
    };
    
    this.calendar = null;
    this.mail = null;
    this.isInitialized = false;
  }

  /**
   * Initialize both calendar and mail integrations
   */
  async initialize(credentials = {}) {
    console.log("🌐 Initializing OpenClaw Integration Manager...");
    
    try {
      // Initialize calendar integration
      if (credentials.calendar) {
        console.log("📅 Initializing calendar integration...");
        this.calendar = new CalendarIntegration({
          calendarFile: './calendar_data.json',
          serverUrl: 'https://caldav.icloud.com',
          syncInterval: 1800000 // 30 minutes
        });
        
        await this.calendar.initialize({
          username: credentials.calendar.username,
          password: credentials.calendar.password
        });
        
        if (this.options.autoStart) {
          this.calendar.startAutoSync();
        }
        
        console.log("✅ Calendar integration initialized");
      }
      
      // Initialize mail integration
      if (credentials.mail) {
        console.log("📧 Initializing mail integration...");
        this.mail = new MailIntegration({
          mailboxFile: './mailbox_data.json',
          syncInterval: 300000, // 5 minutes
          maxMessages: 100,
          retentionDays: 30
        });
        
        await this.mail.initialize({
          email: credentials.mail.email,
          password: credentials.mail.password
        });
        
        if (this.options.autoStart) {
          this.mail.startAutoSync();
        }
        
        console.log("✅ Mail integration initialized");
      }
      
      this.isInitialized = true;
      console.log("✅ Integration Manager initialized successfully!");
      
      return {
        calendar: !!this.calendar,
        mail: !!this.mail,
        initialized: true
      };
    } catch (error) {
      console.error("❌ Error initializing integration manager:", error);
      throw error;
    }
  }

  /**
   * Get combined status of all integrations
   */
  getStatus() {
    if (!this.isInitialized) {
      return { initialized: false };
    }
    
    const status = {
      initialized: this.isInitialized,
      timestamp: new Date().toISOString(),
      calendar: null,
      mail: null
    };
    
    if (this.calendar) {
      status.calendar = this.calendar.getSyncStatus();
    }
    
    if (this.mail) {
      status.mail = this.mail.getSyncStatus();
    }
    
    return status;
  }

  /**
   * Get combined availability summary (calendar + mail context)
   */
  async getCombinedSummary(dateRange = 7) {
    const summary = {
      timestamp: new Date().toISOString(),
      calendar: null,
      mail: null
    };
    
    // Get calendar summary
    if (this.calendar) {
      try {
        summary.calendar = await this.calendar.getAvailabilitySummary(dateRange);
      } catch (error) {
        console.error('Error getting calendar summary:', error);
      }
    }
    
    // Get mail summary
    if (this.mail) {
      try {
        summary.mail = await this.mail.getMailboxSummary();
      } catch (error) {
        console.error('Error getting mail summary:', error);
      }
    }
    
    // Create a combined context
    summary.context = {
      availability: summary.calendar ? 
        `${summary.calendar.summary.availabilityPercentage}% of the next ${dateRange} days are free` : 
        'Calendar unavailable',
      unreadEmails: summary.mail ? 
        `${summary.mail.summary.unreadCount} unread emails` : 
        'Mail unavailable',
      recommendedAction: this.getRecommendedAction(summary)
    };
    
    return summary;
  }

  /**
   * Get recommended action based on combined data
   */
  getRecommendedAction(summary) {
    const recommendations = [];
    
    if (summary.calendar && summary.calendar.summary.availabilityPercentage < 30) {
      recommendations.push("Your schedule is quite full - consider blocking time for focused work");
    }
    
    if (summary.mail && summary.mail.summary.unreadCount > 20) {
      recommendations.push("You have many unread emails that may require attention");
    }
    
    if (summary.calendar && summary.mail) {
      recommendations.push("Consider scheduling time to process emails during less busy periods");
    }
    
    return recommendations.length > 0 ? recommendations : ["All systems nominal"];
  }

  /**
   * Add event to calendar and optionally send notification via email
   */
  async addCalendarEventWithNotification(eventData, notificationOptions = {}) {
    if (!this.calendar) {
      throw new Error('Calendar integration not initialized');
    }
    
    // Add event to calendar
    const eventResult = await this.calendar.addEvent(eventData);
    
    // Optionally send notification via email
    if (notificationOptions.sendEmail && this.mail && notificationOptions.recipients) {
      const subject = `Calendar Event: ${eventData.title}`;
      const body = `A new calendar event has been added:\n\n` +
                  `Title: ${eventData.title}\n` +
                  `Date: ${new Date(eventData.start).toLocaleString()}\n` +
                  `Duration: ${eventData.duration || 1} hour(s)\n` +
                  `Location: ${eventData.location || 'Not specified'}\n\n` +
                  `${eventData.description || ''}`;
      
      await this.mail.sendEmail(
        notificationOptions.recipients,
        subject,
        body
      );
    }
    
    return eventResult;
  }

  /**
   * Search across both calendar and mail
   */
  async unifiedSearch(query, options = {}) {
    const results = {
      query,
      timestamp: new Date().toISOString(),
      calendar: [],
      mail: [],
      combined: []
    };
    
    // Search calendar if available
    if (this.calendar) {
      // Calendar search would be implemented based on event titles, descriptions, etc.
      // For now, we'll just return upcoming events
      try {
        const calendarSummary = await this.calendar.getAvailabilitySummary(options.dateRange || 7);
        results.calendar = calendarSummary.events || [];
      } catch (error) {
        console.error('Error searching calendar:', error);
      }
    }
    
    // Search mail if available
    if (this.mail) {
      try {
        const mailSearch = await this.mail.searchMessages(query, options);
        results.mail = mailSearch.results || [];
      } catch (error) {
        console.error('Error searching mail:', error);
      }
    }
    
    // Combine results with metadata
    results.combined = [
      ...results.calendar.map(item => ({ ...item, type: 'calendar', relevance: 0.8 })),
      ...results.mail.map(item => ({ ...item, type: 'mail', relevance: 0.8 }))
    ];
    
    // Sort by date/relevance
    results.combined.sort((a, b) => {
      const dateA = new Date(a.date || a.start || a.timestamp || 0);
      const dateB = new Date(b.date || b.start || b.timestamp || 0);
      return dateB - dateA; // Newest first
    });
    
    return results;
  }

  /**
   * Start auto-sync for both integrations
   */
  startAutoSync() {
    if (this.calendar) {
      this.calendar.startAutoSync();
    }
    
    if (this.mail) {
      this.mail.startAutoSync();
    }
    
    console.log("🔄 Auto-sync started for all integrations");
  }

  /**
   * Stop auto-sync for both integrations
   */
  stopAutoSync() {
    if (this.calendar) {
      this.calendar.stopAutoSync();
    }
    
    if (this.mail) {
      this.mail.stopAutoSync();
    }
    
    console.log("⏹️  Auto-sync stopped for all integrations");
  }

  /**
   * Test all connections
   */
  async testAllConnections() {
    const results = {
      timestamp: new Date().toISOString(),
      calendar: null,
      mail: null
    };
    
    if (this.calendar) {
      results.calendar = await this.calendar.testConnection();
    }
    
    if (this.mail) {
      results.mail = await this.mail.testConnection();
    }
    
    return results;
  }

  /**
   * Close all integrations
   */
  async close() {
    if (this.calendar) {
      await this.calendar.close();
    }
    
    if (this.mail) {
      await this.mail.close();
    }
    
    this.isInitialized = false;
    console.log("🔒 All integrations closed");
  }
}

module.exports = IntegrationManager;

// Example usage:
/*
const IntegrationManager = require('./integration_manager.js');

async function setupIntegrations() {
  const manager = new IntegrationManager();
  
  // Initialize with credentials
  await manager.initialize({
    calendar: {
      username: process.env.CALENDAR_USERNAME,
      password: process.env.CALENDAR_PASSWORD
    },
    mail: {
      email: process.env.MAIL_USERNAME,
      password: process.env.MAIL_PASSWORD
    }
  });
  
  // Get combined summary
  const summary = await manager.getCombinedSummary(7);
  console.log('Combined summary:', summary.context);
  
  return manager;
}
*/