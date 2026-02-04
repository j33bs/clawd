// email_service.js
// Read-only email daily digest and draft reply generator

const fs = require('fs');
const path = require('path');

class EmailService {
  constructor(config = {}) {
    this.config = {
      emailDataFile: config.emailDataFile || './email_data.json',
      maxDigestItems: config.maxDigestItems || 10,
      defaultDateRange: config.defaultDateRange || 1, // days
      ...config
    };
    
    // Initialize email data store
    this.initEmailStore();
  }

  // Initialize email data store
  initEmailStore() {
    if (!fs.existsSync(this.config.emailDataFile)) {
      const initialData = {
        accounts: {},
        lastCheck: null,
        settings: {
          maxDigestItems: this.config.maxDigestItems
        }
      };
      fs.writeFileSync(this.config.emailDataFile, JSON.stringify(initialData, null, 2));
    }
  }

  // Get daily email digest
  async getDailyDigest(accountId = 'default', daysBack = 1) {
    try {
      const emailData = JSON.parse(fs.readFileSync(this.config.emailDataFile, 'utf8'));
      const account = emailData.accounts[accountId] || { messages: [] };
      
      // Filter messages by date
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - daysBack);
      
      const recentMessages = account.messages.filter(msg => {
        const msgDate = new Date(msg.date);
        return msgDate >= cutoffDate;
      }).sort((a, b) => new Date(b.date) - new Date(a.date)); // Sort by newest first
      
      // Generate digest
      const digest = {
        accountId,
        period: `Last ${daysBack} day${daysBack > 1 ? 's' : ''}`,
        totalMessages: recentMessages.length,
        unreadCount: recentMessages.filter(m => !m.read).length,
        importantCount: recentMessages.filter(m => m.important).length,
        fromSenders: [...new Set(recentMessages.map(m => m.from))],
        subjectLines: recentMessages.slice(0, this.config.maxDigestItems).map(m => ({
          subject: m.subject,
          from: m.from,
          date: m.date,
          read: m.read,
          important: m.important
        })),
        summary: this.generateDigestSummary(recentMessages)
      };
      
      return digest;
    } catch (error) {
      throw new Error(`Email service error: ${error.message}`);
    }
  }

  // Generate digest summary
  generateDigestSummary(messages) {
    if (messages.length === 0) {
      return 'No new messages.';
    }
    
    const stats = {
      total: messages.length,
      unread: messages.filter(m => !m.read).length,
      important: messages.filter(m => m.important).length,
      fromUniqueSenders: [...new Set(messages.map(m => m.from))].length
    };
    
    return `You have ${stats.total} messages (${stats.unread} unread, ${stats.important} important) from ${stats.fromUniqueSenders} different senders.`;
  }

  // Generate draft reply
  async generateDraftReply(messageId, accountId = 'default', customPrompt = '') {
    const emailData = JSON.parse(fs.readFileSync(this.config.emailDataFile, 'utf8'));
    const account = emailData.accounts[accountId];
    
    if (!account) {
      throw new Error(`Account ${accountId} not found`);
    }
    
    const originalMessage = account.messages.find(msg => msg.id === messageId);
    if (!originalMessage) {
      throw new Error(`Message ${messageId} not found`);
    }
    
    // In a real implementation, this would use AI to generate a draft
    // For now, we'll create a template-based draft
    const draft = this.createReplyDraft(originalMessage, customPrompt);
    
    return {
      originalMessage: {
        id: originalMessage.id,
        subject: originalMessage.subject,
        from: originalMessage.from,
        bodyPreview: originalMessage.body.substring(0, 200) + '...'
      },
      draft: draft,
      accountId: accountId,
      generatedAt: new Date().toISOString()
    };
  }

  // Create a draft reply based on the original message
  createReplyDraft(originalMessage, customPrompt) {
    // This would normally use an AI model to generate contextually appropriate responses
    // For now, we'll create a template-based response
    
    const senderName = this.extractSenderName(originalMessage.from);
    const messageSubject = originalMessage.subject;
    
    // Basic response templates
    const templates = {
      inquiry: `Hi ${senderName},

Thank you for your message regarding "${messageSubject}". I appreciate you reaching out and will look into this matter.

I'll get back to you with more details shortly.

Best regards,
Heath`,
      
      meeting: `Hi ${senderName},

Thanks for the meeting invitation for "${messageSubject}". I've reviewed the proposed time and it looks good to me.

Looking forward to our discussion.

Best regards,
Heath`,
      
      general: `Hi ${senderName},

Thank you for your message about "${messageSubject}". I appreciate you taking the time to reach out.

I'll review your request and respond appropriately.

Best regards,
Heath`
    };
    
    // Determine template based on subject/content keywords
    const lowerSubject = messageSubject.toLowerCase();
    let templateType = 'general';
    
    if (lowerSubject.includes('meeting') || lowerSubject.includes('schedule') || lowerSubject.includes('appointment')) {
      templateType = 'meeting';
    } else if (lowerSubject.includes('inquiry') || lowerSubject.includes('question') || lowerSubject.includes('info')) {
      templateType = 'inquiry';
    }
    
    return {
      subject: `Re: ${originalMessage.subject}`,
      body: templates[templateType],
      to: originalMessage.from,
      cc: '',
      bcc: ''
    };
  }

  // Extract sender name from email address
  extractSenderName(emailAddress) {
    if (emailAddress.includes('<')) {
      // Handle format: "Name <email@domain.com>"
      const nameMatch = emailAddress.match(/^(.*?)\s*</);
      if (nameMatch && nameMatch[1]) {
        return nameMatch[1].trim();
      }
    }
    
    // Extract name from email address itself
    const namePart = emailAddress.split('@')[0];
    return namePart.charAt(0).toUpperCase() + namePart.slice(1);
  }

  // Get unread messages
  async getUnreadMessages(accountId = 'default') {
    const emailData = JSON.parse(fs.readFileSync(this.config.emailDataFile, 'utf8'));
    const account = emailData.accounts[accountId] || { messages: [] };
    
    return account.messages.filter(msg => !msg.read);
  }

  // Mark message as read (without actually sending)
  async markAsRead(messageId, accountId = 'default') {
    const emailData = JSON.parse(fs.readFileSync(this.config.emailDataFile, 'utf8'));
    const account = emailData.accounts[accountId];
    
    if (!account) return false;
    
    const message = account.messages.find(msg => msg.id === messageId);
    if (message) {
      message.read = true;
      message.readAt = new Date().toISOString();
      
      fs.writeFileSync(this.config.emailDataFile, JSON.stringify(emailData, null, 2));
      return true;
    }
    
    return false;
  }

  // Mock sync method (in real implementation, this would connect to actual email)
  async mockSync(accountId, messages) {
    const emailData = JSON.parse(fs.readFileSync(this.config.emailDataFile, 'utf8'));
    
    if (!emailData.accounts[accountId]) {
      emailData.accounts[accountId] = { messages: [] };
    }
    
    emailData.accounts[accountId].messages = messages || [];
    emailData.lastCheck = new Date().toISOString();
    
    fs.writeFileSync(this.config.emailDataFile, JSON.stringify(emailData, null, 2));
  }

  // Validate email credentials (placeholder for real auth)
  validateCredentials(credentials) {
    // In a real implementation, this would validate actual email credentials
    // For now, we just check if required fields exist
    return !!(credentials && credentials.provider && credentials.username);
  }
}

module.exports = EmailService;