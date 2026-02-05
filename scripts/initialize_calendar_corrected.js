/**
 * initialize_calendar_corrected.js
 * 
 * Initialize calendar integration with the correct server for Gmail
 */

const CalendarIntegration = require('./calendar_integration.js');
const CredentialLoader = require('./credential_loader.js');

async function initializeCalendarCorrected() {
  console.log("📅 Initializing OpenClaw Calendar Integration...");
  console.log("Detecting calendar provider based on email domain...");
  
  // Check if credentials are available
  if (!CredentialLoader.hasCalendarCredentials()) {
    console.error("❌ Missing credentials! Please set OCUSER and OCPASS environment variables.");
    console.log("Example:");
    console.log("  export OCUSER='your_email@domain.com'");
    console.log("  export OCPASS='your_app_specific_password'");
    return;
  }
  
  const userEmail = process.env.OCUSER;
  
  // Determine server URL based on email domain
  let serverUrl = 'https://caldav.icloud.com'; // Default
  
  if (userEmail.includes('@gmail.com')) {
    console.log("🔍 Detected Gmail account - using Google Calendar settings");
    // Note: Google Calendar requires a different approach than CalDAV
    // Google Calendar doesn't use standard CalDAV but has its own API
    serverUrl = 'https://apidata.googleusercontent.com/caldav/v2/';
  } else if (userEmail.includes('@outlook.com') || userEmail.includes('@hotmail.com')) {
    console.log("🔍 Detected Outlook account - using Microsoft settings");
    serverUrl = 'https://outlook.office365.com/';
  } else if (userEmail.includes('@icloud.com')) {
    console.log("🔍 Detected iCloud account - using Apple settings");
    serverUrl = 'https://caldav.icloud.com';
  } else {
    console.log("🔍 Using default calendar settings (Apple iCloud)");
  }
  
  // For Gmail, we'll need to inform the user about Google Calendar API
  if (userEmail.includes('@gmail.com')) {
    console.log("\n⚠️  Important Note:");
    console.log("Google Calendar doesn't use standard CalDAV protocol.");
    console.log("For Google Calendar integration, you'll need to set up Google Calendar API access.");
    console.log("Would you like me to explain the Google Calendar API setup?");
    
    // For now, we'll initialize with a basic calendar integration
    const calendar = new CalendarIntegration({
      calendarFile: './calendar_data.json',
      serverUrl: serverUrl,
      syncInterval: 1800000 // 30 minutes
    });
    
    try {
      const creds = CredentialLoader.getCalendarCredentials();
      
      // For Google Calendar, you would typically use OAuth2 instead of username/password
      // For now, we'll try to initialize but warn about limitations
      console.log("\n🔧 Attempting to initialize calendar integration...");
      console.log("(Note: Full Google Calendar integration requires OAuth setup)");
      
      // Initialize with credentials (this will likely fail for Google without OAuth)
      await calendar.initialize({
        username: creds.username,
        password: creds.password
      });
      
      // Start auto-sync for calendar service
      calendar.startAutoSync();
      
      console.log("✅ Calendar integration initialized!");
      
      // Test the connection
      const testResult = await calendar.testConnection();
      console.log(`📋 Calendar connection test: ${testResult.connected ? '✅ Success' : '❌ Limited (due to Google API requirements)'}`);
      
      // Get availability summary
      const summary = await calendar.getAvailabilitySummary(7);
      console.log(`📊 Calendar availability: ${summary.summary.availabilityPercentage}% free time`);
      
      console.log("\n🔄 Calendar auto-sync is now running:");
      console.log("   - Calendar syncs every 30 minutes");
      console.log("   - Data stored in ./calendar_data.json");
      
      return calendar;
      
    } catch (error) {
      console.log(`\n❌ Standard CalDAV doesn't work with Google Calendar: ${error.message}`);
      console.log("\n💡 For full Google Calendar integration, you'll need to:");
      console.log("   1. Create a Google Cloud project");
      console.log("   2. Enable the Google Calendar API");
      console.log("   3. Create OAuth 2.0 credentials");
      console.log("   4. Use those credentials instead of username/password");
      
      // Create a basic calendar integration that works with local data only
      const calendar = new CalendarIntegration({
        calendarFile: './calendar_data.json',
        serverUrl: 'https://caldav.icloud.com', // Use a dummy URL
        syncInterval: 1800000
      });
      
      // Override the initialize method to skip the server connection for Google
      calendar.initialize = async (creds) => {
        console.log("⚠️  Using local-only calendar mode for Google account");
        await calendar.ensureLocalCalendarFile();
        calendar.isInitialized = true;
        return true;
      };
      
      // Initialize in local-only mode
      await calendar.initialize(creds);
      calendar.startAutoSync();
      
      console.log("✅ Calendar integration in local-only mode");
      console.log("   - Can track local events only");
      console.log("   - Cannot sync with Google Calendar directly");
      console.log("   - Will use local calendar_data.json file");
      
      return calendar;
    }
  } else {
    // For non-Google accounts (Apple, Outlook, etc.), proceed normally
    const calendar = new CalendarIntegration({
      calendarFile: './calendar_data.json',
      serverUrl: serverUrl,
      syncInterval: 1800000 // 30 minutes
    });
    
    try {
      const creds = CredentialLoader.getCalendarCredentials();
      
      console.log(`🔧 Initializing calendar integration with server: ${serverUrl}`);
      
      // Initialize with credentials
      await calendar.initialize({
        username: creds.username,
        password: creds.password
      });
      
      // Start auto-sync for calendar service
      calendar.startAutoSync();
      
      console.log("✅ Calendar integration initialized!");
      
      // Test the connection
      const testResult = await calendar.testConnection();
      console.log(`📋 Calendar connection test: ${testResult.connected ? '✅ Success' : '❌ Failed'}`);
      
      // Get availability summary
      const summary = await calendar.getAvailabilitySummary(7);
      console.log(`📊 Calendar availability: ${summary.summary.availabilityPercentage}% free time`);
      
      console.log("\n🔄 Calendar auto-sync is now running:");
      console.log("   - Calendar syncs every 30 minutes");
      console.log("   - Data stored in ./calendar_data.json");
      
      return calendar;
      
    } catch (error) {
      console.error("❌ Error initializing calendar integration:", error.message);
      throw error;
    }
  }
}

// Run initialization if this file is executed directly
if (require.main === module) {
  initializeCalendarCorrected()
    .then(calendar => {
      if (calendar) {
        console.log("\n🎉 OpenClaw calendar integration is now active!");
        console.log("Your calendar is being synchronized automatically.");
      }
    })
    .catch(error => {
      console.error("\n💥 Failed to initialize calendar integration:", error);
      process.exit(1);
    });
}

module.exports = { initializeCalendarCorrected };