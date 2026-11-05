{
    'name': 'Stratos Social Marketing',
    'version': '20.0.1.2.0',
    'category': 'Marketing/Social Marketing',
    'summary': 'Compose, schedule and publish posts to Facebook Pages, Instagram, YouTube and TikTok from Odoo',
    'description': """
Stratos Social Marketing (Phase 1)
==================================
* Connect Facebook Pages and Instagram Business accounts (Meta login or access token)
* Connect YouTube channels (Google login) and upload videos with title, visibility and category
* Connect TikTok accounts (TikTok login) and Direct Post videos following TikTok's sharing guidelines
* Compose one post for several accounts, with images and a link
* Publish now or schedule for later (automatic publishing every 5 minutes)
* Content calendar, approval-ready statuses and per-account results
* Multi-company: each company keeps its own accounts and posts
""",
    'author': 'Stratos Hub',
    'website': 'https://www.stratos-hub.com',
    'license': 'LGPL-3',
    'depends': ['base_setup', 'mail', 'utm'],
    'data': [
        'security/stratos_social_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'wizard/social_token_wizard_views.xml',
        'views/social_account_views.xml',
        'views/social_post_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'external_dependencies': {'python': ['requests']},
    'application': True,
    'installable': True,
}
