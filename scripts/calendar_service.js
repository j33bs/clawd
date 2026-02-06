// calendar_service.js
// Read-only calendar availability summary service

const fs = require('fs');
const path = require('path');

class CalendarService {
  constructor(config = {}) {
    this.config = {
      calendarFile: config.calendarFile || './calendar_data.json',
      defaultRange: config.defaultRange || 7, // days ahead
      ...config
    };
    
    // Initialize calendar data store
    this.initCalendarStore();
  }

  // Initialize calendar data store
  initCalendarStore() {
    if (!fs.existsSync(this.config.calendarFile)) {
      const initialData = {
        events: [],
        lastSync: null,
        settings: {
          defaultViewRange: this.config.defaultRange
        }
      };
      fs.writeFileSync(this.config.calendarFile, JSON.stringify(initialData, null, 2));
    }
  }

  // Get calendar availability summary
  async getAvailabilitySummary(dateRange = null) {
    try {
      // Load calendar data
      const calendarData = JSON.parse(fs.readFileSync(this.config.calendarFile, 'utf8'));
      
      // Determine date range
      const range = dateRange || this.config.defaultRange;
      const startDate = new Date();
      const endDate = new Date();
      endDate.setDate(startDate.getDate() + range);
      
      // Filter events within date range
      const eventsInRange = this.filterEventsByDate(calendarData.events, startDate, endDate);
      
      // Generate summary
      const summary = this.generateSummary(eventsInRange, startDate, endDate);
      
      return {
        summary,
        events: eventsInRange,
        dateRange: {
          start: startDate.toISOString().split('T')[0],
          end: endDate.toISOString().split('T')[0]
        },
        totalEvents: eventsInRange.length,
        busyDays: this.countBusyDays(eventsInRange, startDate, endDate)
      };
    } catch (error) {
      throw new Error(`Calendar service error: ${error.message}`);
    }
  }

  // Filter events by date range
  filterEventsByDate(events, startDate, endDate) {
    return events.filter(event => {
      const eventDate = new Date(event.start);
      return eventDate >= startDate && eventDate <= endDate;
    });
  }

  // Generate availability summary
  generateSummary(events, startDate, endDate) {
    const totalDays = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24));
    const busyDays = this.countBusyDays(events, startDate, endDate);
    const freeDays = totalDays - busyDays;
    
    // Calculate busy hours per day
    const dailyBusyHours = this.calculateDailyBusyHours(events, startDate, endDate);
    
    return {
      period: `${startDate.toDateString()} to ${endDate.toDateString()}`,
      totalDays,
      freeDays,
      busyDays,
      availabilityPercentage: Math.round((freeDays / totalDays) * 100),
      busiestDay: this.findBusiestDay(dailyBusyHours),
      dailyBreakdown: dailyBusyHours,
      upcomingEvents: events.map(e => ({
        title: e.title,
        start: e.start,
        duration: e.duration,
        location: e.location
      }))
    };
  }

  // Count busy days
  countBusyDays(events, startDate, endDate) {
    const busyDays = new Set();
    
    events.forEach(event => {
      const eventDate = new Date(event.start).toDateString();
      busyDays.add(eventDate);
    });
    
    return busyDays.size;
  }

  // Calculate daily busy hours
  calculateDailyBusyHours(events, startDate, endDate) {
    const dailyHours = {};
    const currentDate = new Date(startDate);
    
    // Initialize all days in range
    while (currentDate <= endDate) {
      dailyHours[currentDate.toISOString().split('T')[0]] = 0;
      currentDate.setDate(currentDate.getDate() + 1);
    }
    
    // Add event durations to respective days
    events.forEach(event => {
      const eventDay = new Date(event.start).toISOString().split('T')[0];
      if (dailyHours[eventDay] !== undefined) {
        dailyHours[eventDay] += event.duration || 1; // default to 1 hour if no duration
      }
    });
    
    return dailyHours;
  }

  // Find the busiest day
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

  // Get events for a specific date
  async getEventsForDate(dateString) {
    const calendarData = JSON.parse(fs.readFileSync(this.config.calendarFile, 'utf8'));
    const targetDate = new Date(dateString);
    
    const eventsForDate = calendarData.events.filter(event => {
      const eventDate = new Date(event.start);
      return (
        eventDate.getFullYear() === targetDate.getFullYear() &&
        eventDate.getMonth() === targetDate.getMonth() &&
        eventDate.getDate() === targetDate.getDate()
      );
    });
    
    return {
      date: dateString,
      events: eventsForDate,
      count: eventsForDate.length
    };
  }

  // Mock sync method (in real implementation, this would connect to actual calendar)
  async mockSync(events) {
    const calendarData = JSON.parse(fs.readFileSync(this.config.calendarFile, 'utf8'));
    calendarData.events = events || [];
    calendarData.lastSync = new Date().toISOString();
    
    fs.writeFileSync(this.config.calendarFile, JSON.stringify(calendarData, null, 2));
  }

  // Validate calendar credentials (placeholder for real auth)
  validateCredentials(credentials) {
    // In a real implementation, this would validate actual calendar credentials
    // For now, we just check if required fields exist
    return !!(credentials && credentials.provider);
  }
}

module.exports = CalendarService;