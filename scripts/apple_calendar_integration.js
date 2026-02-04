// apple_calendar_integration.js
// Apple Calendar (CalDAV) integration for the calendar service

const { createAccount, DAV } = require('tsdav'); // CalDAV library
const fs = require('fs').promises;
const path = require('path');

class AppleCalendarIntegration {
  constructor(config = {}) {
    this.config = {
      calendarFile: config.calendarFile || './calendar_data.json',
      username: config.username, // iCloud email address
      password: config.password, // App-specific password
      serverUrl: config.serverUrl || 'https://caldav.icloud.com',
      ...config
    };
    
    this.client = null;
    this.calendars = [];
  }

  // Initialize the CalDAV client
  async initialize() {
    if (!this.config.username || !this.config.password) {
      throw new Error('Username and password (app-specific) required for Apple Calendar integration');
    }

    try {
      // Create CalDAV account
      this.account = await createAccount({
        server: this.config.serverUrl,
        account: {
          type: 'caldav',
          username: this.config.username,
          password: this.config.password,
        },
        props: ['calendar-home-set', 'current-user-principal'],
      });

      // Initialize the client
      this.client = new DAV({ account: this.account });
      
      // Fetch available calendars
      this.calendars = await this.client.fetchCalendars();
      
      console.log(`Connected to Apple Calendar. Found ${this.calendars.length} calendars.`);
      
      return true;
    } catch (error) {
      console.error('Failed to initialize Apple Calendar connection:', error);
      throw error;
    }
  }

  // Get calendar events from Apple Calendar
  async getEvents(startDate, endDate) {
    if (!this.client) {
      throw new Error('Apple Calendar client not initialized. Call initialize() first.');
    }

    try {
      // Format dates for CalDAV query
      const start = new Date(startDate);
      const end = new Date(endDate);

      // Fetch events from all calendars
      let allEvents = [];
      
      for (const calendar of this.calendars) {
        const events = await this.client.fetchCalendarObjects({
          calendar: calendar,
          timeRange: {
            start: start.toISOString(),
            end: end.toISOString(),
          },
        });

        // Process and format events
        const formattedEvents = events.map(event => this.formatAppleEvent(event, calendar));
        allEvents = allEvents.concat(formattedEvents);
      }

      return allEvents;
    } catch (error) {
      console.error('Error fetching Apple Calendar events:', error);
      throw error;
    }
  }

  // Format Apple Calendar event to our standard format
  formatAppleEvent(appleEvent, calendar) {
    // Parse the iCal data to extract event information
    const eventDetails = this.parseICalData(appleEvent.data);
    
    return {
      id: appleEvent.url, // Use the URL as a unique identifier
      title: eventDetails.summary || 'Untitled Event',
      start: eventDetails.startDate,
      end: eventDetails.endDate,
      duration: eventDetails.duration,
      location: eventDetails.location || '',
      description: eventDetails.description || '',
      calendar: calendar.displayName || 'Unknown Calendar',
      raw: appleEvent // Keep raw data for potential future use
    };
  }

  // Parse iCal data to extract event information
  parseICalData(icalData) {
    const result = {
      summary: '',
      startDate: null,
      endDate: null,
      duration: 0,
      location: '',
      description: ''
    };

    // Simple parsing of iCal data
    const lines = icalData.split('\n');
    let dtstart = null;
    let dtend = null;

    for (const line of lines) {
      if (line.startsWith('SUMMARY:')) {
        result.summary = line.substring(8).trim();
      } else if (line.startsWith('DTSTART:')) {
        dtstart = line.substring(8).trim();
        result.startDate = this.parseICalDate(dtstart);
      } else if (line.startsWith('DTEND:')) {
        dtend = line.substring(6).trim();
        result.endDate = this.parseICalDate(dtend);
      } else if (line.startsWith('LOCATION:')) {
        result.location = line.substring(9).trim();
      } else if (line.startsWith('DESCRIPTION:')) {
        result.description = line.substring(12).trim();
      }
    }

    // Calculate duration if both start and end dates are available
    if (result.startDate && result.endDate) {
      const start = new Date(result.startDate);
      const end = new Date(result.endDate);
      result.duration = (end - start) / (1000 * 60 * 60); // Duration in hours
    }

    return result;
  }

  // Parse iCal date format to JavaScript Date
  parseICalDate(icalDate) {
    // iCal format: YYYYMMDDTHHmmssZ (UTC) or YYYYMMDDTHHmmss (local)
    if (icalDate.endsWith('Z')) {
      // UTC format
      const dateStr = icalDate.substring(0, 8);
      const timeStr = icalDate.substring(9, 15);
      return new Date(Date.UTC(
        parseInt(dateStr.substring(0, 4)),    // year
        parseInt(dateStr.substring(4, 6)) - 1, // month (0-indexed)
        parseInt(dateStr.substring(6, 8)),    // day
        parseInt(timeStr.substring(0, 2)),    // hour
        parseInt(timeStr.substring(2, 4)),    // minute
        parseInt(timeStr.substring(4, 6))     // second
      ));
    } else {
      // Local time format - assuming it's in the user's local timezone
      const dateStr = icalDate.substring(0, 8);
      const timeStr = icalDate.substring(9, 15);
      return new Date(
        parseInt(dateStr.substring(0, 4)),    // year
        parseInt(dateStr.substring(4, 6)) - 1, // month (0-indexed)
        parseInt(dateStr.substring(6, 8)),    // day
        parseInt(timeStr.substring(0, 2)),    // hour
        parseInt(timeStr.substring(2, 4)),    // minute
        parseInt(timeStr.substring(4, 6))     // second
      );
    }
  }

  // Sync Apple Calendar events to local calendar data
  async syncToLocalStorage() {
    try {
      // Get the next 30 days of events
      const startDate = new Date();
      const endDate = new Date();
      endDate.setDate(startDate.getDate() + 30);

      const appleEvents = await this.getEvents(startDate, endDate);

      // Update the local calendar data file
      const calendarDataPath = this.config.calendarFile;
      let localData = {};

      try {
        const fileContent = await fs.readFile(calendarDataPath, 'utf8');
        localData = JSON.parse(fileContent);
      } catch (error) {
        // If file doesn't exist, create with default structure
        localData = {
          events: [],
          lastSync: null,
          settings: {
            defaultViewRange: 7
          }
        };
      }

      // Replace local events with Apple Calendar events
      localData.events = appleEvents;
      localData.lastSync = new Date().toISOString();

      // Write back to the file
      await fs.writeFile(calendarDataPath, JSON.stringify(localData, null, 2));

      console.log(`Synced ${appleEvents.length} events from Apple Calendar to local storage.`);
      
      return {
        eventsSynced: appleEvents.length,
        lastSync: localData.lastSync,
        calendarsAccessed: this.calendars.map(cal => cal.displayName)
      };
    } catch (error) {
      console.error('Error syncing Apple Calendar to local storage:', error);
      throw error;
    }
  }

  // Get availability summary from Apple Calendar
  async getAvailabilitySummary(dateRange = 7) {
    try {
      const startDate = new Date();
      const endDate = new Date();
      endDate.setDate(startDate.getDate() + dateRange);

      const events = await this.getEvents(startDate, endDate);

      // Calculate availability summary
      const totalDays = dateRange;
      const busyDays = new Set();

      events.forEach(event => {
        const eventDate = new Date(event.start).toDateString();
        busyDays.add(eventDate);
      });

      const busyDayCount = busyDays.size;
      const freeDayCount = totalDays - busyDayCount;

      // Calculate daily breakdown
      const dailyBreakdown = {};
      const currentDate = new Date(startDate);
      while (currentDate <= endDate) {
        dailyBreakdown[currentDate.toISOString().split('T')[0]] = 0;
        currentDate.setDate(currentDate.getDate() + 1);
      }

      events.forEach(event => {
        const eventDay = new Date(event.start).toISOString().split('T')[0];
        if (dailyBreakdown[eventDay] !== undefined) {
          dailyBreakdown[eventDay] += event.duration || 1;
        }
      });

      return {
        summary: {
          period: `${startDate.toDateString()} to ${endDate.toDateString()}`,
          totalDays,
          freeDays: freeDayCount,
          busyDays: busyDayCount,
          availabilityPercentage: Math.round((freeDayCount / totalDays) * 100),
          busiestDay: this.findBusiestDay(dailyBreakdown),
          dailyBreakdown,
          upcomingEvents: events
        },
        events,
        dateRange: {
          start: startDate.toISOString().split('T')[0],
          end: endDate.toISOString().split('T')[0]
        },
        totalEvents: events.length,
        busyDays: busyDayCount
      };
    } catch (error) {
      console.error('Error getting availability summary:', error);
      throw error;
    }
  }

  // Helper to find the busiest day
  findBusiestDay(dailyHours) {
    let busiestDay = null;
    let maxHours = 0;

    for (const [day, hours] of Object.entries(dailyHours)) {
      if (hours > maxHours) {
        maxHours = hours;
        busiestDay = day;
      }
    }

    return busiestDay ? { day: busiestDay, hours: maxHours } : null;
  }

  // Test the connection
  async testConnection() {
    try {
      if (!this.client) {
        await this.initialize();
      }

      // Try to fetch calendars as a basic connectivity test
      const calendars = await this.client.fetchCalendars();
      
      return {
        connected: true,
        calendarCount: calendars.length,
        calendars: calendars.map(cal => ({
          name: cal.displayName,
          url: cal.url
        }))
      };
    } catch (error) {
      return {
        connected: false,
        error: error.message
      };
    }
  }
}

module.exports = AppleCalendarIntegration;