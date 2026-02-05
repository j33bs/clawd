/**
 * setup_unified_integrations.js
 * 
 * Setup script for unified calendar and mail integrations
 * Helps configure both services and initialize the integration manager
 */

const IntegrationManager = require('./integration_manager.js');
const fs = require('fs').promises;

async function setupUnifiedIntegrations() {
  console.log("🌐 OpenClaw Unified Integrations Setup");
  console.log("=====================================");
  
  console.log("\nThis setup will configure both calendar and mail integrations.");
  console.log("You can configure either or both services.");
  
  console.log("\n📅 Calendar Setup:");
  console.log("• Requires: Calendar email and app-specific password");
  console.log("• Works with: Apple Calendar (CalDAV), Google Calendar, Outlook");
  console.log("• Syncs events and provides availability tracking");
  
  console.log("\n📧 Mail Setup:");
  console.log("• Requires: Email address and app-specific password");
  console.log("• Works with: Gmail, Outlook, Apple Mail, Yahoo, other IMAP providers");
  console.log("• Syncs emails and provides mailbox management");
  
  console.log("\n🔐 Credentials Required:");
  console.log("You'll need to set environment variables for each service you want to enable:");
  
  console.log("\nFor Calendar (Apple, Google, etc.):");
  console.log("  export CALENDAR_USERNAME='your_calendar_email@domain.com'");
  console.log("  export CALENDAR_PASSWORD='your_app_specific_password'");
  
  console.log("\nFor Mail (Gmail, Outlook, etc.):");
  console.log("  export MAIL_USERNAME='your_mail_email@domain.com'");
  console.log("  export MAIL_PASSWORD='your_app_specific_password'");
  
  console.log("\n💡 Pro Tips:");
  console.log("• Use app-specific passwords when possible for better security");
  console.log("• Calendar syncs every 30 minutes, Mail syncs every 5 minutes");
  console.log("• All data is stored locally in your workspace");
  console.log("• Both integrations can work together for coordinated scheduling");
  
  console.log("\n📋 Once configured, you'll be able to:");
  console.log("  • See your availability based on calendar events");
  console.log("  • Track unread emails and mailbox status");
  console.log("  • Get combined recommendations for time management");
  console.log("  • Add calendar events with email notifications");
  console.log("  • Search across both calendar and mail simultaneously");
  
  console.log("\n🔄 To initialize both integrations, run:");
  console.log(`
const IntegrationManager = require('./integration_manager.js');

async function initializeIntegrations() {
  const manager = new IntegrationManager();
  
  await manager.initialize({
    // Include only the services you want to enable
    calendar: {
      username: process.env.CALENDAR_USERNAME,
      password: process.env.CALENDAR_PASSWORD
    },
    mail: {
      email: process.env.MAIL_USERNAME,
      password: process.env.MAIL_PASSWORD
    }
  });
  
  // Start auto-sync for both services
  manager.startAutoSync();
  
  // Get combined summary
  const summary = await manager.getCombinedSummary(7);
  console.log('Your integrated summary:', summary.context);
  
  return manager;
}

initializeIntegrations().catch(console.error);
  `);
  
  console.log("\n📊 Example Usage After Setup:");
  console.log(`
// Get combined availability and email status
const summary = await manager.getCombinedSummary(7);
console.log(\`You have \${summary.context.availability} and \${summary.context.unreadEmails}\`);

// Add a calendar event with email notification
await manager.addCalendarEventWithNotification(
  {
    title: "Team Meeting",
    start: new Date(Date.now() + 24 * 60 * 60 * 1000), // Tomorrow
    duration: 1, // 1 hour
    location: "Conference Room",
    description: "Weekly team sync meeting"
  },
  {
    sendEmail: true,
    recipients: ["team@company.com"]
  }
);

// Search across both calendar and mail
const results = await manager.unifiedSearch("project deadline");
console.log(\`Found \${results.combined.length} results\`);
  `);
  
  console.log("\n✅ Unified integrations setup complete!");
  console.log("Follow the instructions above to configure your services.");
  
  return {
    calendar: "Ready for configuration",
    mail: "Ready for configuration",
    status: "Setup complete - awaiting credentials"
  };
}

// Run setup if this file is executed directly
if (require.main === module) {
  setupUnifiedIntegrations()
    .then(result => {
      console.log("\n🎯 Next Steps:");
      console.log("1. Set your environment variables with your credentials");
      console.log("2. Run the initialization code above");
      console.log("3. Start using your integrated calendar and mail services!");
    })
    .catch(error => {
      console.error("❌ Error during setup:", error);
    });
}

module.exports = { setupUnifiedIntegrations };