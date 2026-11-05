{
    'name': 'CRM International RFP',
    'version': '20.0.1.1.0',
    'category': 'Sales/CRM',
    'summary': 'Track international RFPs on CRM leads: deadlines, RFP documents, questionnaire, proposal and submission status',
    'description': """
CRM International RFP
=====================
Adds an "International RFP" checkbox on CRM leads / opportunities. When ticked, an RFP tab appears with:

* Questionnaire date and last submission date
* RFP documents (the initial documents received)
* Questionnaire file(s)
* Proposal file(s)
* Questionnaire status (Sent / Not Sent) and submission status (Submitted / Not Submitted)
* Responsible person for the questionnaire and for the proposal, plus people to copy
* Automatic reminders (To-Do activity + notification) before, on and after each deadline
* RFP Dashboard: queue, due this week, overdue, submitted, deadlines and pending work per person

Also adds filters, list columns, a kanban badge and an "International RFPs" menu in CRM.
""",
    'author': 'Stratos Hub',
    'website': 'https://www.stratos-hub.com',
    'license': 'LGPL-3',
    'depends': ['crm'],
    'data': [
        'data/rfp_data.xml',
        'data/ir_cron_data.xml',
        'views/crm_lead_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'stratos_crm_rfp/static/src/dashboard/rfp_dashboard.js',
            'stratos_crm_rfp/static/src/dashboard/rfp_dashboard.xml',
            'stratos_crm_rfp/static/src/dashboard/rfp_dashboard.scss',
        ],
    },
    'installable': True,
    'application': False,
}
