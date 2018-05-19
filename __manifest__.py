# -*- coding: utf-8 -*-

{
    'name': 'Alipay Payment Acquirer',
    'category': 'Accounting',
    'summary': 'Payment Acquirer: Alipay Implementation',
    'version': '1.0',
    'description': """
Alipay Payment Acquirer，支付宝支付模块，用于支付宝即时收款功能.
需要安装pycrypto Python库，通过命令`pip install pycrypto`安装.
    """,
    'depends': ['payment'],
    'external_dependencies': {
        'python': ['Crypto'],
        'bin': [],
    },
    'data': [
        'views/payment_views.xml',
        'views/payment_alipay_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'installable': True,
}
