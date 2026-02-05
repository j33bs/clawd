/**
 * initialize_mail_only.js
 * 
 * Initialize only the mail integration using OCUSER/OCPASS convention
 */

const MailIntegration = require('./mail_integration.js');
const CredentialLoader = require('./credential_loader.js');

async function initializeMailOnly() {
  console.log("📧 Initializing OpenClaw Mail Integration...");
  console.log("Using credential convention: OCUSER and OCPASS");
  
  // Check if credentials are available
  if (!CredentialLoader.hasMailCredentials()) {
    console.error("❌ Missing credentials! Please set OCUSER and OCPASS environment variables.");
    console.log("Example:");
    console.log("  export OCUSER='your_email@domain.com'");
    console.log("  export OCPASS='your_app_specific_password'");
    return;
  }
  
  const mail = new MailIntegration({
    mailboxFile: './mailbox_data.json',
    syncInterval: 300000, // 5 minutes
    maxMessages: 100,
    retentionDays: 30
  });
  
  try {
    // Get credentials using the established convention
    const mailCreds = CredentialLoader.getMailCredentials();
    
    console.log("🔐 Authenticating with mail service...");
    
    // Initialize with credentials
    await mail.initialize({
      email: mailCreds.email,
      password: mailCreds.password
    });
    
    // Start auto-sync for mail service
    mail.startAutoSync();
    
    console.log("✅ Mail integration initialized and running!");
    
    // Test the connection
    const testResult = await mail.testConnection();
    console.log(`📋 Mail connection test: ${testResult.connected ? '✅ Success' : '❌ Failed'}`);
    
    // Get mailbox summary
    const summary = await mail.getMailboxSummary();
    console.log(`📊 Mailbox summary: ${summary.summary.totalMessages} total, ${summary.summary.unreadCount} unread`);
    
    console.log("\n🔄 Mail auto-sync is now running:");
    console.log("   - Mail syncs every 5 minutes");
    console.log("   - Data stored in ./mailbox_data.json");
    
    // Store the mail instance for other scripts to use
    global.mailIntegration = mail;
    
    return mail;
    
  } catch (error) {
    console.error("❌ Error initializing mail integration:", error.message);
    throw error;
  }
}

// Run initialization if this file is executed directly
if (require.main === module) {
  initializeMailOnly()
    .then(mail => {
      if (mail) {
        console.log("\n🎉 OpenClaw mail integration is now active!");
        console.log("Your mail is being synchronized automatically.");
      }
    })
    .catch(error => {
      console.error("\n💥 Failed to initialize mail integration:", error);
      process.exit(1);
    });
}

module.exports = { initializeMailOnly };