# CRM International RFP (Odoo 20 Community) — v1.1

Tracks international RFPs on the standard CRM lead / opportunity, with a dashboard and automatic reminders.

## 1. How it works on a lead / opportunity

| # | Step | Where |
|---|------|-------|
| 1 | Tick **International RFP** | Lead form, under Tags |
| 2 | Enter **Questionnaire Date** and **Last Submission Date** | **International RFP** tab › Key Dates |
| 3 | Attach the initial RFP documents | Tab › **1. RFP Documents** |
| 4 | Attach the questionnaire, then mark it **Sent** | Tab › **2. Questionnaire** and Status |
| 5 | Attach the proposal, then mark it **Submitted** | Tab › **3. Proposal** and Status |
| 6 | Choose who is responsible and who else to copy | Tab › **Reminders** |

The tab is shown only when the checkbox is ticked. Each document section takes one or more files.

## 2. Reminders

| Who | Field | Default |
|-----|-------|---------|
| Questionnaire Responsible | Gets the reminders while the questionnaire is **Not Sent** | Salesperson of the lead |
| Proposal Responsible | Gets the reminders while the proposal is **Not Submitted** | Salesperson of the lead |
| Also Remind | Copied on every reminder of this RFP (e.g. manager) | Empty |

**When reminders are sent** (checked every morning by the scheduled job *CRM: International RFP reminders*):

| # | Moment | What happens |
|---|--------|--------------|
| 1 | *N* days before the deadline (N set in **CRM › Configuration › Settings › International RFP**, default 3) | To-Do activity created for the responsible, due on the deadline + notification (Odoo inbox and email) |
| 2 | On the deadline day | Second notification |
| 3 | The day after (overdue) | Third notification; the To-Do turns red |

* Each reminder is sent only once; changing a deadline starts the cycle again.
* Changing the responsible moves the open To-Do to the new person; changing the date moves its due date.
* Marking the questionnaire **Sent** / proposal **Submitted** closes the To-Do and stops reminders.
* Lost opportunities and leads without the checkbox are ignored.
* Every reminder is also logged in the lead's chatter.
* Email delivery needs an outgoing mail server in Odoo (Settings › Technical › Outgoing Mail Servers); without it, reminders still appear in the Odoo inbox and activities.

## 3. Dashboard — CRM › RFPs › Dashboard

| Part | Shows | Click |
|------|-------|-------|
| **In Queue (Not Submitted)** | Open RFPs and their total value | List of those RFPs |
| **Questionnaire Not Sent** | Open RFPs whose questionnaire is still pending | List |
| **Due in 7 Days** | Submission deadline within a week | List |
| **Overdue** | Submission date passed, or questionnaire date passed while not sent | List |
| **Submitted** | All submitted RFPs (and how many this month) | List |
| Upcoming Deadlines | Each open RFP's next step (send questionnaire / submit proposal), deadline, days left (red overdue, amber ≤ 7 days, green later), responsible, value | Opens the RFP |
| Pending by Person | Open questionnaires and proposals per responsible | That person's RFPs |
| Recently Submitted | Last 5 submitted RFPs with date | Opens the RFP |

## 4. Built-in rules

| # | Rule |
|---|------|
| 1 | Questionnaire cannot be marked **Sent** without a questionnaire file; proposal cannot be marked **Submitted** without a proposal file |
| 2 | **Sent On** / **Submitted On** dates are filled automatically (cleared if set back) |
| 3 | Yellow notice on the RFP tab when the last submission date is within 7 days or has passed |
| 4 | Warning if the questionnaire date is after the last submission date |
| 5 | All dates, statuses and responsibles are tracked in the chatter |
| 6 | Uploaded files also appear in the lead's attachments (paperclip) |

## 5. Menus and filters

| Place | What you see |
|-------|--------------|
| CRM › RFPs › **Dashboard** | The dashboard above |
| CRM › RFPs › **All RFPs** | List with both dates, both statuses, proposal responsible; overdue unsubmitted RFPs in red. New records here are RFP opportunities by default |
| Pipeline (kanban) | "International RFP" badge, status and due date on the card |
| Search filters | International RFPs · RFP Not Submitted · Questionnaire Not Sent · RFP Submitted · Last Submission Date · Group by RFP Submission Status |

## 6. Install / upgrade

1. Copy `stratos_crm_rfp` into the custom addons path; restart Odoo.
2. New install: Apps › Update Apps List › **CRM International RFP** › Install.
   Upgrade from 1.0: Apps › CRM International RFP › **Upgrade** (existing RFPs and files are kept).
3. Set the reminder days in CRM › Configuration › Settings › International RFP.

## 7. Technical

* Extends `crm.lead`; uses CRM's own access rights.
* Activity types: *RFP Questionnaire*, *RFP Proposal*. Scheduled job: *CRM: International RFP reminders* (daily).
* Dashboard: OWL 3 client action `stratos_crm_rfp.dashboard`, data from `crm.lead.get_rfp_dashboard_data()`.
* Tests: `odoo-bin -d <db> -i stratos_crm_rfp --test-enable --test-tags /stratos_crm_rfp` (14 tests).
