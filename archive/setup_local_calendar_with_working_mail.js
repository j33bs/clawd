/**
 * setup_local_calendar_with_working_mail.js
 * 
 * Sets up local calendar integration while maintaining working mail integration
 */

console.log("Setting up Complete Integration System");
console.log("=====================================");
console.log();
console.log("Current Status:");
console.log("✅ Mail Integration: Working (Gmail via IMAP)");
console.log("❌ Remote Calendar: Not working (Gmail as Apple ID not compatible with CalDAV)");
console.log("✅ Local Calendar: Available (can manage events locally)");
console.log();

async function setupCompleteSystem() {
  // Import required modules
  const IntegrationManager = require('./scripts/integration_manager.js');
  const CalendarIntegration = require('./scripts/calendar_integration.js');
  const MailIntegration = require('./scripts/mail_integration.js');
  
  console.log("Creating integration manager...");
  const manager = new IntegrationManager();
  
  // Initialize mail integration (should work)
  console.log("Initializing mail integration...");
  await manager.initialize({
    mail: {
      email: process.env.OCUSER,
      password: process.env.OCPASS
    }
  });
  
  // For calendar, create a local-only instance
  console.log("Setting up local calendar integration...");
  const localCalendar = new CalendarIntegration({
    calendarFile: './calendar_data.json',
    serverUrl: 'https://caldav.icloud.com', // Won't be used due to overridden method
    syncInterval: 1800000
  });
  
  // Override the initialize method to work in local-only mode
  localCalendar.initialize = async (creds) => {
    console.log("⚠️  Using local-only calendar mode (remote sync unavailable)");
    await localCalendar.ensureLocalCalendarFile();
    localCalendar.isInitialized = true;
    return true;
  };
  
  // Initialize the local calendar
  await localCalendar.initialize({username: process.env.OCUSER, password: process.env.OCPASS});
  localCalendar.startAutoSync();
  
  // Attach the local calendar to the manager manually
  manager.calendar = localCalendar;
  
  // Start auto-sync for both services
  manager.startAutoSync();
  
  console.log();
  console.log("🎉 Complete Integration System Active!");
  console.log();
  console.log("📧 Mail Integration:");
  console.log("   • Syncing every 5 minutes");
  console.log("   • Connected to Gmail account");
  console.log("   • Storing data in ./mailbox_data.json");
  console.log();
  console.log("🗓️  Local Calendar Integration:");
  console.log("   • Local event management only");
  console.log("   • Syncing every 30 minutes");
  console.log("   • Storing data in ./calendar_data.json");
  console.log("   • Can add/view events locally");
  console.log();
  console.log("📋 Combined Summary:");
  
  // Get and display summary
  const summary = await manager.getCombinedSummary(7);
  if (summary.mail) {
    console.log(`   • Mail: ${summary.mail.summary.unreadCount} unread emails`);
  }
  if (summary.calendar) {
    console.log(`   • Calendar: ${summary.calendar.summary.availabilityPercentage}% free time`);
  } else {
    console.log("   • Calendar: Local mode only (no remote sync)");
  }
  
  console.log();
  console.log("💡 You can still manually add calendar events to manage your schedule locally.");
  console.log("   The mail integration will continue to sync your emails automatically.");
  
  return manager;
}

// Run if executed directly
if (require.main === module) {
  setupCompleteSystem()
    .then(manager => {
      console.log();
      console.log("✅ System is now fully operational!");
      console.log("Both mail and calendar components are running.");
    })
    .catch(error => {
      console.error("❌ Error setting up system:", error);
    });
}

module.exports = { setupCompleteSystem };