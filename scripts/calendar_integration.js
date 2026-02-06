/**
 * calendar_integration.js
 * 
 * Comprehensive calendar integration for Apple Calendar (CalDAV)
 * Handles authentication, event synchronization, and availability tracking
 */

const { createAccount, DAV } = require('tsdav');
const fs = require('fs').promises;
const path = require('path');

class CalendarIntegration {
  constructor(options = {}) {
    this.options = {
      calendarFile: options.calendarFile || './calendar_data.json',
      serverUrl: options.serverUrl || 'https://caldav.icloud.com',
      syncInterval: options.syncInterval || 30 * 60 * 1000, // 30 minutes
      ...options
    };
    
    this.client = null;
    this.calendars = [];
    this.syncIntervalId = null;
    this.isInitialized = false;
  }

  /**
   * Initialize the calendar integration
   */
  async initialize(credentials) {
    if (!credentials || !credentials.username || !credentials.password) {
      throw new Error('Calendar credentials (username and password) are required for initialization');
    }

    try {
      // Create CalDAV account
      this.account = await createAccount({
        server: this.options.serverUrl,
        account: {
          type: 'caldav',
          username: credentials.username,
          password: credentials.password,
        },
        props: ['calendar-home-set', 'current-user-principal'],
      });

      // Initialize the client
      this.client = new DAV({ account: this.account });
      
      // Fetch available calendars
      this.calendars = await this.client.fetchCalendars();
      
      console.log(`✅ Connected to calendar service. Found ${this.calendars.length} calendars.`);
      
      // Initialize local calendar data file
      await this.ensureLocalCalendarFile();
      
      this.isInitialized = true;
      return true;
    } catch (error) {
      console.error('❌ Failed to initialize calendar connection:', error.message);
      throw error;
    }
  }

  /**
   * Ensure local calendar data file exists
   */
  async ensureLocalCalendarFile() {
    try {
      await fs.access(this.options.calendarFile);
    } catch (error) {
      // File doesn't exist, create with default structure
      const defaultData = {
        events: [],
        lastSync: null,
        settings: {
          defaultViewRange: 7
        }
      };
      
      await fs.writeFile(this.options.calendarFile, JSON.stringify(defaultData, null, 2));
      console.log(`📁 Created new calendar data file: ${this.options.calendarFile}`);
    }
  }

  /**
   * Fetch events from the calendar service
   */
  async fetchEvents(startDate, endDate) {
    if (!this.client) {
      throw new Error('Calendar client not initialized. Call initialize() first.');
    }

    try {
      // Format dates for CalDAV query
      const start = new Date(startDate);
      const end = new Date(endDate);

      let allEvents = [];
      
      for (const calendar of this.calendars) {
        try {
          const calendarEvents = await this.client.fetchCalendarObjects({
            calendar: calendar,
            timeRange: {
              start: start.toISOString(),
              end: end.toISOString(),
            },
          });

          // Process and format events
          const formattedEvents = calendarEvents.map(event => 
            this.formatCalendarEvent(event, calendar)
          );
          allEvents = allEvents.concat(formattedEvents);
        } catch (calError) {
          console.warn(`⚠️  Could not fetch events from calendar: ${calendar.displayName}`, calError.message);
        }
      }

      return allEvents;
    } catch (error) {
      console.error('❌ Error fetching calendar events:', error);
      throw error;
    }
  }

  /**
   * Format calendar event to standard format
   */
  formatCalendarEvent(calendarEvent, calendar) {
    // Parse the iCal data to extract event information
    const eventDetails = this.parseICalData(calendarEvent.data);
    
    return {
      id: calendarEvent.url || `event_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      title: eventDetails.summary || 'Untitled Event',
      start: eventDetails.startDate,
      end: eventDetails.endDate,
      duration: eventDetails.duration || 1, // Default to 1 hour if not specified
      location: eventDetails.location || '',
      description: eventDetails.description || '',
      calendar: calendar.displayName || 'Unknown Calendar',
      status: eventDetails.status || 'confirmed',
      raw: calendarEvent // Keep raw data for potential future use
    };
  }

  /**
   * Parse iCal data to extract event information
   */
  parseICalData(icalData) {
    const result = {
      summary: '',
      startDate: null,
      endDate: null,
      duration: 0,
      location: '',
      description: '',
      status: 'confirmed'
    };

    // Simple parsing of iCal data
    const lines = icalData.split('\n');

    for (const line of lines) {
      if (line.startsWith('SUMMARY:')) {
        result.summary = line.substring(8).trim();
      } else if (line.startsWith('DTSTART:')) {
        const dateStr = line.substring(8).trim();
        result.startDate = this.parseICalDate(dateStr).toISOString();
      } else if (line.startsWith('DTEND:')) {
        const dateStr = line.substring(6).trim();
        result.endDate = this.parseICalDate(dateStr).toISOString();
      } else if (line.startsWith('LOCATION:')) {
        result.location = line.substring(9).trim();
      } else if (line.startsWith('DESCRIPTION:')) {
        result.description = line.substring(12).trim();
      } else if (line.startsWith('STATUS:')) {
        result.status = line.substring(7).trim().toLowerCase();
      }
    }

    // Calculate duration if both start and end dates are available
    if (result.startDate && result.endDate) {
      const start = new Date(result.startDate);
      const end = new Date(result.endDate);
      const diffHours = (end - start) / (1000 * 60 * 60);
      result.duration = diffHours;
    }

    return result;
  }

  /**
   * Parse iCal date format to JavaScript Date
   */
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

  /**
   * Synchronize calendar events to local storage
   */
  async syncToLocalStorage() {
    if (!this.isInitialized) {
      throw new Error('Calendar integration not initialized. Call initialize() first.');
    }

    try {
      // Get the next 30 days of events
      const startDate = new Date();
      const endDate = new Date();
      endDate.setDate(startDate.getDate() + 30);

      console.log(`🔄 Syncing calendar events from ${startDate.toDateString()} to ${endDate.toDateString()}...`);

      const calendarEvents = await this.fetchEvents(startDate, endDate);

      // Update the local calendar data file
      const calendarDataPath = this.options.calendarFile;
      let localData = {};

      try {
        const fileContent = await fs.readFile(calendarDataPath, 'utf8');
        localData = JSON.parse(fileContent);
      } catch (error) {
        // If file doesn't exist, it should have been created by ensureLocalCalendarFile
        console.error('Error reading calendar data file:', error);
        throw error;
      }

      // Replace local events with calendar events
      localData.events = calendarEvents;
      localData.lastSync = new Date().toISOString();

      // Write back to the file
      await fs.writeFile(calendarDataPath, JSON.stringify(localData, null, 2));

      console.log(`✅ Synced ${calendarEvents.length} events from calendar to local storage.`);
      
      return {
        eventsSynced: calendarEvents.length,
        lastSync: localData.lastSync,
        calendarsAccessed: this.calendars.map(cal => cal.displayName)
      };
    } catch (error) {
      console.error('❌ Error syncing calendar to local storage:', error);
      throw error;
    }
  }

  /**
   * Get availability summary based on calendar events
   */
  async getAvailabilitySummary(dateRange = 7) {
    if (!this.isInitialized) {
      throw new Error('Calendar integration not initialized. Call initialize() first.');
    }

    try {
      const startDate = new Date();
      const endDate = new Date();
      endDate.setDate(startDate.getDate() + dateRange);

      // Ensure we have current data
      await this.syncToLocalStorage();

      // Read the local calendar data
      const calendarData = await fs.readFile(this.options.calendarFile, 'utf8');
      const parsedData = JSON.parse(calendarData);
      
      const events = parsedData.events;
      
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
      console.error('❌ Error getting availability summary:', error);
      throw error;
    }
  }

  /**
   * Find the busiest day from daily breakdown
   */
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

  /**
   * Add a new event to the calendar
   */
  async addEvent(eventData) {
    if (!this.client) {
      throw new Error('Calendar client not initialized. Call initialize() first.');
    }

    try {
      // Select the first calendar (or allow specification)
      const calendar = this.calendars[0]; // Using first calendar by default
      
      // Create iCal data for the event
      const iCalData = this.createICalForEvent(eventData);
      
      // Create a unique filename for the event
      const eventId = `event-${Date.now()}.ics`;

      // Add the event to the calendar
      const result = await this.client.createCalendarObject({
        calendar: calendar,
        filename: eventId,
        iCalString: iCalData,
      });

      console.log(`✅ Event "${eventData.title}" added to calendar.`);
      
      // Sync local storage after adding event
      await this.syncToLocalStorage();
      
      return {
        success: true,
        eventId: eventId,
        calendar: calendar.displayName
      };
    } catch (error) {
      console.error('❌ Error adding event to calendar:', error);
      throw error;
    }
  }

  /**
   * Create iCal data for an event
   */
  createICalForEvent(eventData) {
    const uid = `openclaw-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const now = new Date();
    
    // Format dates
    const start = new Date(eventData.start);
    const end = eventData.end ? new Date(eventData.end) : new Date(start.getTime() + (eventData.duration || 1) * 60 * 60 * 1000);
    
    const formatDateTime = (date) => {
      const year = date.getUTCFullYear();
      const month = String(date.getUTCMonth() + 1).padStart(2, '0');
      const day = String(date.getUTCDate()).padStart(2, '0');
      const hours = String(date.getUTCHours()).padStart(2, '0');
      const minutes = String(date.getUTCMinutes()).padStart(2, '0');
      const seconds = String(date.getUTCSeconds()).padStart(2, '0');
      return `${year}${month}${day}T${hours}${minutes}${seconds}Z`;
    };

    return `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//OpenClaw//Calendar Integration//EN
BEGIN:VEVENT
UID:${uid}@openclaw
DTSTAMP:${formatDateTime(now)}
DTSTART:${formatDateTime(start)}
DTEND:${formatDateTime(end)}
SUMMARY:${eventData.title || 'Untitled Event'}
DESCRIPTION:${eventData.description || 'Event added via OpenClaw'}
LOCATION:${eventData.location || ''}
END:VEVENT
END:VCALENDAR`;
  }

  /**
   * Start automatic synchronization
   */
  startAutoSync() {
    if (!this.isInitialized) {
      throw new Error('Calendar integration not initialized. Call initialize() first.');
    }
    
    if (this.syncIntervalId) {
      clearInterval(this.syncIntervalId);
    }

    this.syncIntervalId = setInterval(async () => {
      try {
        await this.syncToLocalStorage();
      } catch (error) {
        console.error('❌ Auto-sync failed:', error);
      }
    }, this.options.syncInterval);

    console.log(`🔄 Auto-sync started. Interval: ${this.options.syncInterval / 60000} minutes.`);
  }

  /**
   * Stop automatic synchronization
   */
  stopAutoSync() {
    if (this.syncIntervalId) {
      clearInterval(this.syncIntervalId);
      this.syncIntervalId = null;
      console.log('⏹️  Auto-sync stopped.');
    }
  }

  /**
   * Test the calendar connection
   */
  async testConnection() {
    try {
      if (!this.client) {
        throw new Error('Calendar client not initialized');
      }

      // Try to fetch calendars as a basic connectivity test
      const calendars = await this.client.fetchCalendars();
      
      return {
        connected: true,
        calendarCount: calendars.length,
        calendars: calendars.map(cal => ({
          name: cal.displayName,
          url: cal.url
        })),
        lastTest: new Date().toISOString()
      };
    } catch (error) {
      return {
        connected: false,
        error: error.message
      };
    }
  }

  /**
   * Get the current sync status
   */
  getSyncStatus() {
    return {
      initialized: this.isInitialized,
      lastSync: this.getLastSyncTime(),
      autoSyncEnabled: !!this.syncIntervalId,
      syncInterval: this.options.syncInterval,
      calendarCount: this.calendars.length,
      calendars: this.calendars.map(cal => cal.displayName)
    };
  }

  /**
   * Get last sync time from the calendar data file
   */
  async getLastSyncTime() {
    try {
      const data = await fs.readFile(this.options.calendarFile, 'utf8');
      const calendarData = JSON.parse(data);
      return calendarData.lastSync || null;
    } catch (error) {
      return null;
    }
  }

  /**
   * Close the calendar integration and clean up
   */
  async close() {
    this.stopAutoSync();
    this.isInitialized = false;
    console.log('🔒 Calendar integration closed.');
  }
}

module.exports = CalendarIntegration;

// Example usage:
/*
const calendarIntegration = new CalendarIntegration();

async function setupCalendar() {
  try {
    // Initialize with credentials
    await calendarIntegration.initialize({
      username: process.env.CALENDAR_USERNAME,
      password: process.env.CALENDAR_PASSWORD
    });
    
    // Start auto-sync
    calendarIntegration.startAutoSync();
    
    // Get availability summary
    const summary = await calendarIntegration.getAvailabilitySummary(7);
    console.log('Availability:', summary.summary.availabilityPercentage + '% free time');
  } catch (error) {
    console.error('Setup failed:', error);
  }
}
*/