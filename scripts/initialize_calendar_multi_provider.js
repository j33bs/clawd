/**
 * initialize_calendar_multi_provider.js
 * 
 * Initialize calendar integration with provider detection based on email domain
 */

const CalendarIntegration = require('./calendar_integration.js');
const CredentialLoader = require('./credential_loader.js');

async function initializeCalendarMultiProvider() {
  console.log("📅 Initializing OpenClaw Calendar Integration...");
  
  // Check if credentials are available
  if (!CredentialLoader.hasCalendarCredentials()) {
    console.error("❌ Missing credentials! Please set OCUSER and OCPASS environment variables.");
    console.log("Examples:");
    console.log("  Apple Calendar: export OCUSER='your_id@icloud.com'");
    console.log("  Google Calendar: export OCUSER='your_id@gmail.com'");
    console.log("  Outlook: export OCUSER='your_id@outlook.com'");
    return;
  }
  
  const userEmail = process.env.OCUSER;
  let serverUrl = '';
  let providerName = '';
  
  // Determine server URL based on email domain
  if (userEmail.includes('@icloud.com') || userEmail.includes('@me.com') || userEmail.includes('@mac.com')) {
    serverUrl = 'https://caldav.icloud.com';
    providerName = 'Apple Calendar';
  } else if (userEmail.includes('@gmail.com')) {
    // For Gmail users wanting to use Apple Calendar, we'll assume they have an Apple ID too
    console.log("🔍 Detected Gmail account, but you mentioned using Apple Calendar.");
    console.log("💡 Note: For Apple Calendar, you typically need an Apple ID (ending in @icloud.com, @me.com, or @mac.com)");
    console.log("   If you have an Apple ID, please update your OCUSER to use that instead.");
    console.log("   Otherwise, Google Calendar requires a different integration method.");
    
    // For now, let's assume you want to use Apple Calendar with an Apple ID
    // but your OCUSER is set to Gmail - this won't work with CalDAV
    console.log("\n❌ Cannot connect Gmail account to Apple Calendar via CalDAV.");
    console.log("   You need to use your actual Apple ID to connect to Apple Calendar.");
    
    // For demonstration purposes, let's create a local-only calendar instance
    console.log("\n🔧 Creating local-only calendar instance for now...");
    const calendar = new CalendarIntegration({
      calendarFile: './calendar_data.json',
      serverUrl: 'https://caldav.icloud.com', // This won't be used due to error handling
      syncInterval: 1800000
    });
    
    // Override initialize to work in local-only mode
    calendar.initialize = async (creds) => {
      console.log("⚠️  Using local-only calendar mode");
      await calendar.ensureLocalCalendarFile();
      calendar.isInitialized = true;
      return true;
    };
    
    await calendar.initialize(CredentialLoader.getCalendarCredentials());
    calendar.startAutoSync();
    
    console.log("✅ Calendar integration in local-only mode");
    console.log("   - Can track local events only");
    console.log("   - Cannot sync with remote calendar");
    console.log("   - Will use local calendar_data.json file");
    
    return calendar;
  } else if (userEmail.includes('@outlook.com') || userEmail.includes('@hotmail.com') || userEmail.includes('@live.com')) {
    serverUrl = 'https://outlook.office365.com/';
    providerName = 'Microsoft Outlook';
  } else {
    // Default to Apple Calendar
    serverUrl = 'https://caldav.icloud.com';
    providerName = 'Apple Calendar (default)';
  }
  
  if (!serverUrl) {
    console.log("❌ Could not determine calendar provider from email address.");
    return;
  }
  
  console.log(`🔧 Initializing calendar integration for: ${providerName}`);
  console.log(`🌐 Server URL: ${serverUrl}`);
  
  const calendar = new CalendarIntegration({
    calendarFile: './calendar_data.json',
    serverUrl: serverUrl,
    syncInterval: 1800000 // 30 minutes
  });
  
  try {
    const creds = CredentialLoader.getCalendarCredentials();
    
    console.log(`📧 Using email: ${creds.username}`);
    
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
    console.log(`📊 Calendar availability: ${summary.summary.availabilityPercentage}% free time (${summary.summary.busyDays} busy days)`);
    
    console.log("\n🔄 Calendar auto-sync is now running:");
    console.log("   - Calendar syncs every 30 minutes");
    console.log("   - Data stored in ./calendar_data.json");
    
    // Store the calendar instance for other scripts to use
    global.calendarIntegration = calendar;
    
    return calendar;
    
  } catch (error) {
    console.error("❌ Error initializing calendar integration:", error.message);
    
    // Handle the case where someone tries to use Gmail with Apple Calendar
    if (userEmail.includes('@gmail.com') && serverUrl.includes('icloud.com')) {
      console.log("\n💡 You're trying to use a Gmail address with Apple Calendar CalDAV.");
      console.log("   This combination typically doesn't work because:");
      console.log("   1. Your Gmail account isn't an Apple ID");
      console.log("   2. Apple Calendar expects an Apple ID for CalDAV authentication");
      console.log("");
      console.log("   Solutions:");
      console.log("   1. If you have an Apple ID, use that instead of your Gmail address");
      console.log("   2. If you want to sync with Google Calendar, we need different integration");
      console.log("   3. For now, the system will work in local-only mode");
    }
    
    // Create a local-only instance as fallback
    console.log("\n🔧 Creating local-only calendar instance as fallback...");
    const localCalendar = new CalendarIntegration({
      calendarFile: './calendar_data.json',
      serverUrl: 'https://caldav.icloud.com', // Won't be used
      syncInterval: 1800000
    });
    
    // Override to work in local-only mode
    localCalendar.initialize = async (creds) => {
      console.log("⚠️  Using local-only calendar mode (remote sync unavailable)");
      await localCalendar.ensureLocalCalendarFile();
      localCalendar.isInitialized = true;
      return true;
    };
    
    await localCalendar.initialize(creds);
    localCalendar.startAutoSync();
    
    console.log("✅ Fallback calendar integration active (local only)");
    
    return localCalendar;
  }
}

// Run initialization if this file is executed directly
if (require.main === module) {
  initializeCalendarMultiProvider()
    .then(calendar => {
      if (calendar) {
        console.log("\n🎉 Calendar integration is now active!");
        console.log("Calendar data is being managed by the system.");
      }
    })
    .catch(error => {
      console.error("\n💥 Failed to initialize calendar integration:", error);
      process.exit(1);
    });
}

module.exports = { initializeCalendarMultiProvider };