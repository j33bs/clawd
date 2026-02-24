#!/usr/bin/env osascript
-- Calendar access script for OpenClaw
-- Usage: osascript calendar_events.applescript [today|tomorrow|week]

on run argv
  set queryType to item 1 of argv
  set todayDate to current date
  set nowTime to time of todayDate
  
  tell application "Calendar"
    if queryType is "today" then
      set endDate to (todayDate + 1 * days)
      set today's events to events whose (start date ≥ todayDate) and (start date < endDate)
      
      repeat with evt in today's events
        set evtSummary to summary of evt
        set evtStart to start date of evt
        set evtEnd to end date of evt
        
        set startTime to time of evtStart
        set endTime to time of evtEnd
        
        -- Format times
        set startStr to time string of evtStart
        set endStr to time string of evtEnd
        
        log "• " & evtSummary & " (" & startStr & " - " & endStr & ")"
      end repeat
      
    else if queryType is "tomorrow" then
      set tomorrowDate to (todayDate + 1 * days)
      set endDate to (tomorrowDate + 1 * days)
      set tomorrow's events to events whose (start date ≥ tomorrowDate) and (start date < endDate)
      
      repeat with evt in tomorrow's events
        set evtSummary to summary of evt
        set evtStart to start date of evt
        set startStr to time string of evtStart
        log "• " & evtSummary & " (" & startStr & ")"
      end repeat
      
    else if queryType is "week" then
      set weekEnd to (todayDate + 7 * days)
      set weekEvents to events whose (start date ≥ todayDate) and (start date < weekEnd)
      
      repeat with evt in weekEvents
        set evtSummary to summary of evt
        set evtStart to start date of evt
        set dateStr to date string of evtStart
        set startStr to time string of evtStart
        log dateStr & ": " & evtSummary & " (" & startStr & ")"
      end repeat
      
    else
      log "Usage: osascript calendar.applescript [today|tomorrow|week]"
    end if
  end tell
end run
