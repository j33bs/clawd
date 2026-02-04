// Simple test to check if the modules work together
console.log('Testing module imports...');

try {
  const { createAccount, DAV } = require('tsdav');
  console.log('✓ tsdav imported successfully');
} catch (error) {
  console.error('✗ Error importing tsdav:', error.message);
  process.exit(1);
}

try {
  const AppleCalendarIntegration = require('./apple_calendar_integration.js');
  console.log('✓ AppleCalendarIntegration imported successfully');
} catch (error) {
  console.error('✗ Error importing AppleCalendarIntegration:', error.message);
  process.exit(1);
}

try {
  const CalendarService = require('./calendar_service.js');
  console.log('✓ CalendarService imported successfully');
} catch (error) {
  console.error('✗ Error importing CalendarService:', error.message);
  process.exit(1);
}

console.log('All modules loaded successfully!');