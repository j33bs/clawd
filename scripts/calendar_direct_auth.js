// calendar_direct_auth.js
// Alternative calendar service that accepts credentials directly

const AppleCalendarIntegration = require('./apple_calendar_integration.js');
const CalendarService = require('./calendar_service.js');
const fs = require('fs').promises;

class DirectAuthCalendarService {
  constructor(username, password) {
    this.appleCalendar = new AppleCalendarIntegration({
      username: username,
      password: password,
      serverUrl: 'https://caldav.icloud.com',
      calendarFile: './calendar_data.json'
    });
    
    this.calendarService = new CalendarService({
      calendarFile: './calendar_data.json'
    });
  }

  async initialize() {
    try {
      await this.appleCalendar.initialize();
      console.log('✓ Connected to Apple Calendar successfully!');
      
      // Perform initial sync
      await this.syncCalendar();
      
      return true;
    } catch (error) {
      console.error('Error initializing calendar service:', error);
      throw error;
    }
  }

  async syncCalendar() {
    try {
      const syncResult = await this.appleCalendar.syncToLocalStorage();
      console.log(`✓ Sync completed. ${syncResult.eventsSynced} events synced.`);
      return syncResult;
    } catch (error) {
      console.error('Error during calendar sync:', error);
      throw error;
    }
  }

  async getAvailabilitySummary(dateRange = 7) {
    try {
      // Ensure we have current data
      await this.syncCalendar();
      
      // Then get the summary from the local service
      return await this.calendarService.getAvailabilitySummary(dateRange);
    } catch (error) {
      console.error('Error getting availability summary:', error);
      throw error;
    }
  }
}

// Example usage (replace with your actual credentials):
/*
const service = new DirectAuthCalendarService(
  'your_apple_id@icloud.com',  // Replace with your iCloud email
  'your_app_specific_password'  // Replace with your app-specific password
);

service.initialize()
  .then(() => service.getAvailabilitySummary(7))
  .then(summary => {
    console.log('Availability Summary:', summary);
  })
  .catch(error => {
    console.error('Error:', error);
  });
*/

module.exports = DirectAuthCalendarService;