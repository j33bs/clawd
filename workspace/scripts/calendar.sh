#!/bin/bash
# Calendar CLI wrapper using icalBuddy

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
  year)
    YEAR=${2:-2025}
    CAL=""
    [ -n "$3" ] && CAL="-ic"
    $ICAL $CAL "$3" "eventsFrom:$YEAR-01-01 to:$YEAR-12-31"
    ;;
  range)
    CAL=""
    [ -n "$4" ] && CAL="-ic"
    $ICAL $CAL "$4" "eventsFrom:$2 to:$3"
    ;;
  month)
    YEAR_MONTH="$2"
    CAL=""
    [ -n "$3" ] && CAL="-ic"
    $ICAL $CAL "$3" "eventsFrom:$YEAR_MONTH-01 to:$YEAR_MONTH-31"
    ;;
  search)
    TERM="$2"
    YEAR=${3:-2025}
    CAL=""
    [ -n "$4" ] && CAL="-ic"
    $ICAL $CAL "$4" "eventsFrom:$YEAR-01-01 to:$YEAR-12-31" | grep -i "$TERM"
    ;;
  *)
    echo "Usage: calendar [command] [options]"
    echo ""
    echo "Commands:"
    echo "  today        - Show today's events"
    echo "  tomorrow     - Show tomorrow's events"
    echo "  week         - Show events for next 7 days"
    echo "  now          - Show current events"
    echo "  tasks        - Show uncompleted tasks"
    echo "  calendars    - List all calendars"
    echo "  year         - Show events for a year: calendar year 2025"
    echo "  month        - Show events for month: calendar month 2025-11"
    echo "  range        - Show events for range: calendar range 2025-01-01 2025-12-31"
    echo "  search       - Search: calendar search \"term\" 2025"
    ;;
esac
