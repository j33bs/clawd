/**
 * setup_mail.js
 * 
 * Setup script for mail integration
 * Helps configure mail credentials and initialize the integration
 */

const MailIntegration = require('./mail_integration.js');
const fs = require('fs').promises;
const path = require('path');

async function setupMailIntegration() {
  console.log("📧 OpenClaw Mail Integration Setup");
  console.log("=================================");
  
  // Load configuration
  let config = {};
  try {
    const configData = await fs.readFile('./config/mail_config.json', 'utf8');
    config = JSON.parse(configData);
  } catch (error) {
    console.log("⚠️  Configuration file not found, using defaults");
    config.mailIntegration = {
      enabled: true,
      provider: "imap",
      server: "",
      port: 993,
      secure: true,
      mailboxFile: "./mailbox_data.json",
      syncInterval: 300000,
      maxMessages: 100,
      retentionDays: 30,
      autoSync: true,
      credentials: {
        email: "",
        password: ""
      }
    };
  }
  
  if (!config.mailIntegration.enabled) {
    console.log("❌ Mail integration is disabled in configuration");
    return;
  }
  
  console.log("\nTo set up mail integration, you'll need:");
  console.log("1. Your email address");
  console.log("2. An app-specific password or your regular password (depending on your provider)");
  
  console.log("\nFor different email providers:");
  console.log("• Gmail: Use app-specific password or enable 'Less secure app access'");
  console.log("• Outlook/Hotmail: Use app-specific password");
  console.log("• Apple iCloud: Use app-specific password");
  console.log("• Yahoo: Use app-specific password");
  console.log("• Other providers: Check their IMAP settings documentation");
  
  console.log("\n📝 Server Settings by Provider:");
  console.log("• Gmail: imap.gmail.com:993 (SSL)");
  console.log("• Outlook: outlook.office365.com:993 (SSL)");
  console.log("• Apple iCloud: imap.mail.me.com:993 (SSL)");
  console.log("• Yahoo: imap.mail.yahoo.com:993 (SSL)");
  
  console.log("\n📋 Configuration Details:");
  console.log(`   Provider: ${config.mailIntegration.provider}`);
  console.log(`   Server: ${config.mailIntegration.server || 'Not set - please configure'}`);
  console.log(`   Port: ${config.mailIntegration.port}`);
  console.log(`   Secure: ${config.mailIntegration.secure ? 'Yes (SSL/TLS)' : 'No'}`);
  console.log(`   Sync Interval: ${config.mailIntegration.syncInterval / 1000} seconds`);
  console.log(`   Data File: ${config.mailIntegration.mailboxFile}`);
  
  // Create the mail integration instance
  const mail = new MailIntegration({
    mailboxFile: config.mailIntegration.mailboxFile,
    syncInterval: config.mailIntegration.syncInterval,
    maxMessages: config.mailIntegration.maxMessages,
    retentionDays: config.mailIntegration.retentionDays
  });
  
  console.log("\n🧪 Testing mail integration setup...");
  
  console.log("\n💡 To complete setup, you need to provide your mail credentials.");
  console.log("You can do this by setting environment variables:");
  console.log("");
  console.log("export MAIL_USERNAME='your_email@domain.com'");
  console.log("export MAIL_PASSWORD='your_app_specific_password'");
  console.log("export MAIL_SERVER='your_imap_server.com'  # Optional, defaults to provider-specific");
  console.log("");
  console.log("Then run the integration with:");
  console.log("node -e \"const MailIntegration = require('./mail_integration.js'); const mail = new MailIntegration(); mail.initialize({email: process.env.MAIL_USERNAME, password: process.env.MAIL_PASSWORD}).then(() => console.log('✅ Success!')).catch(e => console.error('❌ Error:', e.message));\"");
  
  console.log("\n🔄 Alternatively, you can use this helper function:");
  
  console.log(`
// In your application:
const MailIntegration = require('./mail_integration.js');

async function initializeMail() {
  const mail = new MailIntegration({
    mailboxFile: '${config.mailIntegration.mailboxFile}',
    syncInterval: ${config.mailIntegration.syncInterval},
    maxMessages: ${config.mailIntegration.maxMessages},
    retentionDays: ${config.mailIntegration.retentionDays}
  });
  
  try {
    await mail.initialize({
      email: process.env.MAIL_USERNAME,  // Your email address
      password: process.env.MAIL_PASSWORD   // Your app-specific password
    });
    
    // Start automatic synchronization
    mail.startAutoSync();
    
    // Test the connection
    const testResult = await mail.testConnection();
    console.log('Mail connection test:', testResult.connected ? '✅ Success' : '❌ Failed');
    
    // Get mailbox summary
    const summary = await mail.getMailboxSummary();
    console.log('Mailbox summary: ${config.mailIntegration.maxMessages} max messages, ' + summary.summary.unreadCount + ' unread');
    
    return mail;
  } catch (error) {
    console.error('Mail initialization failed:', error.message);
    throw error;
  }
}

// Call the function
initializeMail().catch(console.error);
  `);
  
  console.log("\n📋 Once configured, the mail integration will:");
  console.log("   • Automatically sync your emails every", config.mailIntegration.syncInterval / 60000, "minutes");
  console.log("   • Store mail data locally in", config.mailIntegration.mailboxFile);
  console.log("   • Track unread messages and folder organization");
  console.log("   • Allow searching and managing your email programmatically");
  
  return mail;
}

// Run setup if this file is executed directly
if (require.main === module) {
  setupMailIntegration()
    .then(() => {
      console.log("\n✅ Mail integration setup instructions complete!");
      console.log("Follow the instructions above to finish the configuration.");
    })
    .catch(error => {
      console.error("❌ Error during setup:", error);
    });
}

module.exports = { setupMailIntegration };