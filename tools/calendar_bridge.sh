#!/usr/bin/env bash
set -euo pipefail

# macOS Calendar bridge (read/write/move/delete) returning JSON.
# ISO input format:
#   Dates: YYYY-MM-DD
#   DateTimes: YYYY-MM-DD HH:MM  (optionally HH:MM:SS)

cmd="${1:-}"; shift || true

case "$cmd" in
  list)
    start_date="${1:?start YYYY-MM-DD}"
    end_date="${2:?end YYYY-MM-DD}"
    cal_name="${3:-}"

    osascript -l AppleScript - "$start_date" "$end_date" "$cal_name" <<'APPLESCRIPT' | ~/clawd/tools/cal_lines_to_json.py
on parseISO(s)
  set monthNames to {January, February, March, April, May, June, July, August, September, October, November, December}

  set AppleScript's text item delimiters to {" "}
  set parts to text items of s
  set AppleScript's text item delimiters to {""}

  set datePart to item 1 of parts
  set timePart to "00:00:00"
  if (count of parts) > 1 then set timePart to item 2 of parts

  set AppleScript's text item delimiters to {"-"}
  set dp to text items of datePart
  set AppleScript's text item delimiters to {""}
  set yy to item 1 of dp as integer
  set mm to item 2 of dp as integer
  set dd to item 3 of dp as integer

  set AppleScript's text item delimiters to {":"}
  set tp to text items of timePart
  set AppleScript's text item delimiters to {""}
  set hh to item 1 of tp as integer
  set mi to item 2 of tp as integer
  set ss to 0
  if (count of tp) > 2 then set ss to item 3 of tp as integer

  set d to current date
  set year of d to yy
  set month of d to item mm of monthNames
  set day of d to dd
  set hours of d to hh
  set minutes of d to mi
  set seconds of d to ss
  return d
end parseISO

on run argv
  set startStr to item 1 of argv
  set endStr to item 2 of argv
  set calName to item 3 of argv

  set startDate to parseISO(startStr & " 00:00:00")
  set endDate to parseISO(endStr & " 00:00:00")

  tell application "Calendar"
    set outLines to {}

    if calName is not "" then
      set targetCals to {calendar calName}
    else
      set targetCals to calendars
    end if

    repeat with c in targetCals
      set evList to (every event of c whose start date < endDate and end date > startDate)
      repeat with e in evList
        set eid to uid of e
        set t to summary of e
        if t is missing value then set t to ""
        set caln to name of c
        set sdt to ((start date of e) as string)
        set edt to ((end date of e) as string)
        set loc to location of e
        if loc is missing value then set loc to ""
        set notes to description of e
        if notes is missing value then set notes to ""
        set end of outLines to (eid & tab & t & tab & caln & tab & sdt & tab & edt & tab & loc & tab & notes)
      end repeat
    end repeat

    set AppleScript's text item delimiters to linefeed
    return outLines as string
  end tell
end run
APPLESCRIPT
    ;;
  create)
    ev_title="${1:?title}"
    start_dt="${2:?start 'YYYY-MM-DD HH:MM'}"
    end_dt="${3:?end 'YYYY-MM-DD HH:MM'}"
    cal_name="${4:?calendar name}"
    location="${5:-}"
    notes="${6:-}"

    osascript -l AppleScript - "$ev_title" "$start_dt" "$end_dt" "$cal_name" "$location" "$notes" <<'APPLESCRIPT'
-- Robust ISO parser
on parseISO(s)
  set monthNames to {January, February, March, April, May, June, July, August, September, October, November, December}

  set AppleScript's text item delimiters to {" "}
  set parts to text items of s
  set AppleScript's text item delimiters to {""}

  set datePart to item 1 of parts
  set timePart to "00:00:00"
  if (count of parts) > 1 then set timePart to item 2 of parts

  set AppleScript's text item delimiters to {"-"}
  set dp to text items of datePart
  set AppleScript's text item delimiters to {""}
  set yy to item 1 of dp as integer
  set mm to item 2 of dp as integer
  set dd to item 3 of dp as integer

  set AppleScript's text item delimiters to {":"}
  set tp to text items of timePart
  set AppleScript's text item delimiters to {""}
  set hh to item 1 of tp as integer
  set mi to item 2 of tp as integer
  set ss to 0
  if (count of tp) > 2 then set ss to item 3 of tp as integer

  set d to current date
  set year of d to yy
  set month of d to item mm of monthNames
  set day of d to dd
  set hours of d to hh
  set minutes of d to mi
  set seconds of d to ss
  return d
end parseISO

on run argv
  set evTitle to item 1 of argv
  set startStr to item 2 of argv
  set endStr to item 3 of argv
  set calName to item 4 of argv
  set loc to item 5 of argv
  set notesTxt to item 6 of argv

  set sdt to parseISO(startStr)
  set edt to parseISO(endStr)

  tell application "Calendar"
    set c to calendar calName
    set e to make new event at end of events of c with properties {summary:evTitle, start date:sdt, end date:edt, location:loc, description:notesTxt}
    set allday event of e to false
    set eid to uid of e
    return "{\"ok\":true,\"id\":\"" & eid & "\"}"
  end tell
end run
APPLESCRIPT
    ;;

  delete)
    eid="${1:?event id}"
    osascript -l AppleScript - "$eid" <<'APPLESCRIPT'
on run argv
  set eid to item 1 of argv
  tell application "Calendar"
    set deleted to false
    repeat with c in calendars
      set matches to (every event of c whose uid is eid)
      if (count of matches) > 0 then
        repeat with e in matches
          delete e
          set deleted to true
        end repeat
      end if
    end repeat
    if deleted then
      return "{\"ok\":true}"
    else
      return "{\"ok\":false,\"error\":\"not_found\"}"
    end if
  end tell
end run
APPLESCRIPT
    ;;

  move)
    eid="${1:?event id}"
    start_dt="${2:?start 'YYYY-MM-DD HH:MM'}"
    end_dt="${3:?end 'YYYY-MM-DD HH:MM'}"
    osascript -l AppleScript - "$eid" "$start_dt" "$end_dt" <<'APPLESCRIPT'
-- Robust ISO parser
on parseISO(s)
  set monthNames to {January, February, March, April, May, June, July, August, September, October, November, December}

  set AppleScript's text item delimiters to {" "}
  set parts to text items of s
  set AppleScript's text item delimiters to {""}

  set datePart to item 1 of parts
  set timePart to "00:00:00"
  if (count of parts) > 1 then set timePart to item 2 of parts

  set AppleScript's text item delimiters to {"-"}
  set dp to text items of datePart
  set AppleScript's text item delimiters to {""}
  set yy to item 1 of dp as integer
  set mm to item 2 of dp as integer
  set dd to item 3 of dp as integer

  set AppleScript's text item delimiters to {":"}
  set tp to text items of timePart
  set AppleScript's text item delimiters to {""}
  set hh to item 1 of tp as integer
  set mi to item 2 of tp as integer
  set ss to 0
  if (count of tp) > 2 then set ss to item 3 of tp as integer

  set d to current date
  set year of d to yy
  set month of d to item mm of monthNames
  set day of d to dd
  set hours of d to hh
  set minutes of d to mi
  set seconds of d to ss
  return d
end parseISO

on run argv
  set eid to item 1 of argv
  set startStr to item 2 of argv
  set endStr to item 3 of argv

  set sdt to parseISO(startStr)
  set edt to parseISO(endStr)

  tell application "Calendar"
    set updated to false
    repeat with c in calendars
      set matches to (every event of c whose uid is eid)
      if (count of matches) > 0 then
        repeat with e in matches
          set allday event of e to false
          set allday event of e to false
          set properties of e to {start date:sdt, end date:edt}
          set updated to true
        end repeat
      end if
    end repeat
    if updated then
      return "{\"ok\":true}"
    else
      return "{\"ok\":false,\"error\":\"not_found\"}"
    end if
  end tell
end run
APPLESCRIPT
    ;;

  *)
    echo "Usage:"
    echo "  $0 list YYYY-MM-DD YYYY-MM-DD [calendarName]"
    echo "  $0 create \"Title\" \"YYYY-MM-DD HH:MM\" \"YYYY-MM-DD HH:MM\" \"CalendarName\" \"Location\" \"Notes\""
    echo "  $0 delete \"<eventId>\""
    echo "  $0 move \"<eventId>\" \"YYYY-MM-DD HH:MM\" \"YYYY-MM-DD HH:MM\""
    exit 2
    ;;
esac
