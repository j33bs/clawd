#!/bin/bash
# Calendar CLI wrapper using icalBuddy
# Usage: calendar [today|tomorrow|week] [calendars]

ICAL="/opt/homebrew/bin/icalBuddy"

case "$1" in
  today)
    $ICAL eventsToday
    ;;
  tomorrow)
    $ICAL eventsToday+1
    ;;
  week)
    $ICAL eventsToday+7
    ;;
  now)
    $ICAL eventsNow
    ;;
  calendars)
    $ICAL calendars
    ;;
  tasks)
    $ICAL uncompletedTasks
    ;;
  *)
    echo "Usage: calendar [today|tomorrow|week|now|tasks|calendars]"
    echo ""
    echo "Commands:"
    echo "  today      - Show today's events"
    echo "  tomorrow   - Show tomorrow's events"
    echo "  week       - Show events for next 7 days"
    echo "  now        - Show current events"
    echo "  tasks      - Show uncompleted tasks"
    echo "  calendars  - List all calendars"
    ;;
esac
