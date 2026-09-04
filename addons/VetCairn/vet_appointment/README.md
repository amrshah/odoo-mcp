# VetCairn Appointments

Phase 2 scheduling module for Odoo 19 Community. It provides appointment types,
provider and patient booking, calendar/list/form views, visit status actions,
multi-company isolation, schedule conflict validation, and chatter tracking.

The initial lifecycle is:

`Scheduled → Confirmed → Arrived → In Progress → Completed`

Scheduled/confirmed appointments may be marked No Show. Any active booking may be
cancelled; managers can reset cancelled/no-show bookings to Scheduled.

Known later-phase items include configurable reminders, outbound email/SMS,
room/resource scheduling, recurrence, printable schedules, and clinical encounters.
