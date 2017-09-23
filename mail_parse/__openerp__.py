# -*- coding: utf-8 -*-
{
    'name': "Mail Parse",
    'summary': "Adds new regex rules to mail aliases.",
    'description': "Adds new regex rules to mail aliases.",
    'author': "Mark Robinson",

    'category': 'Discuss',
    'version': '0.9',
    'depends': ['base', 'fetchmail', 'crm'],
    'installable': True,

    'data': [
        'views/mail_settings.xml',
        'security/ir.model.access.csv'
    ],
}