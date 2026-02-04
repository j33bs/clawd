// setup_apple_calendar.js
// Script to set up Apple Calendar integration

const CalendarSyncService = require('./calendar_sync_service.js');

async function setupAppleCalendarIntegration() {
  console.log("Setting up Apple Calendar Integration");
  console.log("=====================================");
  
  console.log("\nTo integrate with your Apple Calendar, you'll need:");
  console.log("1. Your iCloud email address (e.g., yourname@icloud.com)");
  console.log("2. An app-specific password from your Apple ID account");
  
  console.log("\nTo create an app-specific password:");
  console.log("- Go to appleid.apple.com");
  console.log("- Sign in with your Apple ID");
  console.log("- Go to Security > Generate Passwords");
  console.log("- Create a new app-specific password for 'OpenClaw'");
  
  console.log("\nOnce you have these, you can configure the integration.");
  console.log("\nFor security reasons, we recommend storing your credentials in environment variables:");
  console.log("export APPLE_CALENDAR_USERNAME='yourname@icloud.com'");
  console.log("export APPLE_CALENDAR_APP_PASSWORD='your-generated-password'");
  
  // Example of how to initialize the service programmatically
  console.log("\nExample code to initialize the service:");
  console.log(`
const CalendarSyncService = require('./calendar_sync_service.js');

const config = {
  appleUsername: process.env.APPLE_CALENDAR_USERNAME,
  applePassword: process.env.APPLE_CALENDAR_APP_PASSWORD,
  localCalendarFile: './calendar_data.json',
  syncInterval: 30 * 60 * 1000 // Sync every 30 minutes
};

const service = new CalendarSyncService(config);

// Initialize and start the service
async function startCalendarService() {
  try {
    await service.initialize();
    service.startAutoSync();
    
    // Get availability summary
    const summary = await service.getAvailabilitySummary(7);
    console.log('Availability Summary:', summary.summary.availabilityPercentage + '% free time');
    
    console.log("Calendar service is now running and synced with Apple Calendar!");
  } catch (error) {
    console.error("Error starting calendar service:", error);
  }
}

startCalendarService();
  `);
  
  console.log("\nThe integration will:");
  console.log("- Connect to your Apple Calendar via CalDAV");
  console.log("- Sync your events to the local calendar_data.json file");
  console.log("- Update regularly to keep your schedule current");
  console.log("- Provide availability summaries based on your real calendar");
  
  console.log("\nAfter setting up your environment variables, you can run the service with:");
  console.log("node calendar_sync_service.js");
}

// Run the setup instructions
setupAppleCalendarIntegration().catch(console.error);