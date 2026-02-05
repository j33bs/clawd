/**
 * initialize_integrations.js
 * 
 * Initialize calendar and mail integrations using OCUSER/OCPASS convention
 */

const IntegrationManager = require('./integration_manager.js');
const CredentialLoader = require('./credential_loader.js');

async function initializeIntegrations() {
  console.log("🚀 Initializing OpenClaw Integrations...");
  console.log("Using credential convention: OCUSER and OCPASS");
  
  // Check if credentials are available
  if (!CredentialLoader.hasCalendarCredentials()) {
    console.error("❌ Missing credentials! Please set OCUSER and OCPASS environment variables.");
    console.log("Example:");
    console.log("  export OCUSER='your_email@domain.com'");
    console.log("  export OCPASS='your_app_specific_password'");
    return;
  }
  
  const manager = new IntegrationManager();
  
  try {
    // Get credentials using the established convention
    const calendarCreds = CredentialLoader.getCalendarCredentials();
    const mailCreds = CredentialLoader.getMailCredentials();
    
    console.log("📅 Setting up calendar integration...");
    console.log("📧 Setting up mail integration...");
    
    // Initialize with credentials
    await manager.initialize({
      calendar: {
        username: calendarCreds.username,
        password: calendarCreds.password
      },
      mail: {
        email: mailCreds.email,
        password: mailCreds.password
      }
    });
    
    // Start auto-sync for both services
    manager.startAutoSync();
    
    console.log("✅ Both integrations initialized and running!");
    
    // Get and display combined summary
    const summary = await manager.getCombinedSummary(7);
    console.log("\n📊 Your integrated summary:");
    console.log(`   Availability: ${summary.context.availability}`);
    console.log(`   Unread emails: ${summary.context.unreadEmails}`);
    console.log(`   Recommended: ${summary.context.recommendedAction[0] || 'All systems nominal'}`);
    
    // Store the manager instance for other scripts to use
    global.integrationManager = manager;
    
    console.log("\n🔄 Auto-sync is now running:");
    console.log("   - Calendar syncs every 30 minutes");
    console.log("   - Mail syncs every 5 minutes");
    
    return manager;
    
  } catch (error) {
    console.error("❌ Error initializing integrations:", error.message);
    throw error;
  }
}

// Run initialization if this file is executed directly
if (require.main === module) {
  initializeIntegrations()
    .then(manager => {
      if (manager) {
        console.log("\n🎉 OpenClaw integrations are now active!");
        console.log("Your calendar and mail are being synchronized automatically.");
      }
    })
    .catch(error => {
      console.error("\n💥 Failed to initialize integrations:", error);
      process.exit(1);
    });
}

module.exports = { initializeIntegrations };