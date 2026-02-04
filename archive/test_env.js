// test_env.js
// Test if environment variables are accessible

console.log('Testing environment variables...');
console.log('APPLE_CALENDAR_USERNAME:', process.env.APPLE_CALENDAR_USERNAME ? 'SET' : 'NOT SET');
console.log('APPLE_CALENDAR_APP_PASSWORD exists:', !!process.env.APPLE_CALENDAR_APP_PASSWORD);

if (process.env.APPLE_CALENDAR_USERNAME && process.env.APPLE_CALENDAR_APP_PASSWORD) {
  console.log('\\nEnvironment variables are properly set. Attempting to initialize calendar integration...');
  
  const CalendarSyncService = require('./calendar_sync_service.js');

  const config = {
    appleUsername: process.env.APPLE_CALENDAR_USERNAME,
    applePassword: process.env.APPLE_CALENDAR_APP_PASSWORD,
    localCalendarFile: './calendar_data.json'
  };

  const service = new CalendarSyncService(config);

  service.initialize()
    .then(() => {
      console.log('\\n✓ Connected to Apple Calendar successfully!');
      return service.getAvailabilitySummary(7);
    })
    .then(summary => {
      console.log('\\n✓ Got availability summary:');
      console.log('  Period:', summary.summary.period);
      console.log('  Free days:', summary.summary.freeDays, 'out of', summary.summary.totalDays);
      console.log('  Availability:', summary.summary.availabilityPercentage + '%');
      console.log('  Upcoming events:', summary.summary.upcomingEvents.length);
      console.log('\\n✓ Apple Calendar integration is working correctly!');
    })
    .catch(error => {
      console.error('\\n✗ Error during initialization:', error.message);
      console.error('Stack:', error.stack);
    });
} else {
  console.log('\\nEnvironment variables are not set. Please set them using:');
  console.log('export APPLE_CALENDAR_USERNAME=yourname@icloud.com');
  console.log('export APPLE_CALENDAR_APP_PASSWORD=your-app-specific-password');
  console.log('\\nThen run this script again.');
}