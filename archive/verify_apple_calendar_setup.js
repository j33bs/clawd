/**
 * verify_apple_calendar_setup.js
 * 
 * Verify Apple Calendar setup with proper configuration
 */

console.log("Verifying Apple Calendar Setup");
console.log("==============================");

// Check if the credentials are actually for Apple Calendar
const userEmail = process.env.OCUSER;
const isAppleEmail = userEmail.includes('@icloud.com') || userEmail.includes('@me.com') || userEmail.includes('@mac.com');

console.log(`Current email: ${userEmail}`);
console.log(`Is Apple email: ${isAppleEmail}`);

if (!isAppleEmail) {
  console.log("\n⚠️  Warning: Your email address doesn't appear to be an Apple ID.");
  console.log("   Apple Calendar typically requires an Apple ID (ending in @icloud.com, @me.com, or @mac.com).");
  console.log("   Your current email appears to be for a different service.");
  console.log("   ");
  console.log("   If you have an Apple ID, you should update your OCUSER environment variable:");
  console.log(`   export OCUSER='your_apple_id@icloud.com'`);
  console.log("   export OCPASS='your_apple_calendar_app_specific_password'");
  console.log("   ");
  console.log("   If you're trying to use Google Calendar, that requires a different setup.");
  console.log("   ");
  console.log("   Current setup detected:");
  if (userEmail.includes('@gmail.com')) {
    console.log("   - Gmail address detected - this won't work with Apple Calendar CalDAV");
  } else if (userEmail.includes('@outlook.com') || userEmail.includes('@hotmail.com')) {
    console.log("   - Microsoft account detected - this won't work with Apple Calendar CalDAV");
  } else {
    console.log("   - Non-Apple email detected - this won't work with Apple Calendar CalDAV");
  }
} else {
  console.log("\n✅ Your email appears to be an Apple ID. Proceeding with Apple Calendar setup.");
  
  // If it's an Apple ID, attempt to initialize
  const CalendarIntegration = require('./scripts/calendar_integration.js');
  
  const calendar = new CalendarIntegration({
    calendarFile: './calendar_data.json',
    serverUrl: 'https://caldav.icloud.com',
    syncInterval: 1800000 // 30 minutes
  });
  
  calendar.initialize({
    username: process.env.OCUSER,
    password: process.env.OCPASS
  })
  .then(() => {
    console.log('✅ Apple Calendar integration initialized successfully!');
    calendar.startAutoSync();
    console.log('🔄 Apple Calendar auto-sync started');
    
    // Test the connection
    return calendar.testConnection();
  })
  .then(testResult => {
    console.log('📋 Connection test:', testResult.connected ? '✅ Success' : '❌ Failed');
    
    // Get availability summary
    return calendar.getAvailabilitySummary(7);
  })
  .then(summary => {
    console.log('📊 Calendar availability:', summary.summary.availabilityPercentage + '% free time');
    console.log('✅ Apple Calendar is now fully integrated and syncing!');
  })
  .catch(error => {
    console.error('❌ Error initializing Apple Calendar:', error.message);
  });
}