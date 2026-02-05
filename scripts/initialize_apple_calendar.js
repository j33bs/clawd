/**
 * initialize_apple_calendar.js
 * 
 * Initialize Apple Calendar integration with proper server settings
 */

const CalendarIntegration = require('./calendar_integration.js');
const CredentialLoader = require('./credential_loader.js');

async function initializeAppleCalendar() {
  console.log("📅 Initializing OpenClaw Apple Calendar Integration...");
  console.log("Using Apple Calendar (CalDAV) protocol...");
  
  // Check if credentials are available
  if (!CredentialLoader.hasCalendarCredentials()) {
    console.error("❌ Missing credentials! Please set OCUSER and OCPASS environment variables.");
    console.log("Example for Apple Calendar:");
    console.log("  export OCUSER='your_apple_id@icloud.com'");  // or @me.com, @mac.com
    console.log("  export OCPASS='your_app_specific_password'");
    return;
  }
  
  const calendar = new CalendarIntegration({
    calendarFile: './calendar_data.json',
    serverUrl: 'https://caldav.icloud.com',
    syncInterval: 1800000 // 30 minutes
  });
  
  try {
    const creds = CredentialLoader.getCalendarCredentials();
    
    console.log(`🔧 Initializing calendar integration with server: https://caldav.icloud.com`);
    console.log(`📧 Using email: ${creds.username}`);
    
    // Initialize with credentials
    await calendar.initialize({
      username: creds.username,
      password: creds.password
    });
    
    // Start auto-sync for calendar service
    calendar.startAutoSync();
    
    console.log("✅ Apple Calendar integration initialized!");
    
    // Test the connection
    const testResult = await calendar.testConnection();
    console.log(`📋 Calendar connection test: ${testResult.connected ? '✅ Success' : '❌ Failed'}`);
    
    // Get availability summary
    const summary = await calendar.getAvailabilitySummary(7);
    console.log(`📊 Calendar availability: ${summary.summary.availabilityPercentage}% free time (${summary.summary.busyDays} busy days)`);
    
    console.log("\n🔄 Apple Calendar auto-sync is now running:");
    console.log("   - Calendar syncs every 30 minutes");
    console.log("   - Data stored in ./calendar_data.json");
    
    // Store the calendar instance for other scripts to use
    global.calendarIntegration = calendar;
    
    return calendar;
    
  } catch (error) {
    console.error("❌ Error initializing Apple Calendar integration:", error.message);
    
    // Check if the error is related to the username not being an Apple ID
    if (error.message.includes('Invalid URL') || error.message.includes('undefined')) {
      console.log("\n⚠️  Note: For Apple Calendar, your username should be your Apple ID,");
      console.log("   which typically ends in @icloud.com, @me.com, or @mac.com");
      console.log("   If you're using a different email service, you may need to adjust the server URL.");
    }
    
    throw error;
  }
}

// Run initialization if this file is executed directly
if (require.main === module) {
  initializeAppleCalendar()
    .then(calendar => {
      if (calendar) {
        console.log("\n🎉 OpenClaw Apple Calendar integration is now active!");
        console.log("Your Apple Calendar is being synchronized automatically.");
      }
    })
    .catch(error => {
      console.error("\n💥 Failed to initialize Apple Calendar integration:", error);
      process.exit(1);
    });
}

module.exports = { initializeAppleCalendar };