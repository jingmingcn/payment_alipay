# coding: utf-8

import json
import logging
import datetime
import time
import os
from urllib.parse import urlparse
from urllib.parse import urljoin
from . import func

import dateutil.parser
import pytz
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.addons.payment_alipay.controllers.main import AlipayController
from odoo.tools.float_utils import float_compare


_logger = logging.getLogger(__name__)


class AcquirerAlipay(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(selection_add=[('alipay', 'Alipay')])
    
    alipay_app_id = fields.Char('Alipay APP ID',groups='base.group_user')
    alipay_private_key = fields.Text('Alipay Private KEY',groups='base.group_user')
    #alipay_public_key = fields.Text('Alipay Public key',groups='base.group_user')
    #alipay_sign_type = fields.Selection([('RSA','RSA'),('RSA2','RSA2')],groups='base.gruop_user')
    alipay_transport = fields.Selection([
        ('https','HTTPS'),
        ('http','HTTP')],groups='base.group_user')
    

    @api.model
    def _get_alipay_urls(self, environment):
        """ Alipay URLS """
        if environment == 'prod':
            return {
                'alipay_form_url': 'https://openapi.alipay.com/gateway.do?',
            }
        else:
            return {
                'alipay_form_url': 'https://openapi.alipaydev.com/gateway.do?',
            }

    @api.multi
    def alipay_compute_fees(self, amount, currency_id, country_id):
        """ Compute Alipay fees.

            :param float amount: the amount to pay
            :param integer country_id: an ID of a res.country, or None. This is
                                       the customer's country, to be compared to
                                       the acquirer company country.
            :return float fees: computed fees
        """
        if not self.fees_active:
            return 0.0
        country = self.env['res.country'].browse(country_id)
        if country and self.company_id.country_id.id == country.id:
            percentage = self.fees_dom_var
            fixed = self.fees_dom_fixed
        else:
            percentage = self.fees_int_var
            fixed = self.fees_int_fixed
        fees = (percentage / 100.0 * amount + fixed) / (1 - percentage / 100.0)
        return fees

    @api.multi
    def alipay_form_generate_values(self, values):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        alipay_tx_values = dict(values)
        alipay_tx_values.update({
            #basic parameters
            'method': 'alipay.trade.page.pay',
            #'partner': self.alipay_partner,
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'return_url': '%s' % urljoin(base_url, AlipayController._return_url),
            'notify_url': '%s' % urljoin(base_url, AlipayController._notify_url),
            #buiness parameters
            #'out_trade_no': values['reference'],
            #'subject': '%s: %s' % (self.company_id.name, values['reference']),
            #'total_amount': values['amount'],
            'app_id': self.alipay_app_id,
            #'seller_email': self.alipay_app_id,
            #'seller_account_name': self.alipay_app_id,
            #'body':'',
            #'product_code':'FAST_INSTANT_TRADE_PAY',
            'version':'1.0',
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'biz_content':''
        })

        _logger.info('timestamp :%s' %(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')) )
        _logger.info('Alipay Private Key : %s'%(self.alipay_private_key))

        biz_content = {}
        biz_content['out_trade_no'] = values['reference']
        biz_content['product_code'] = 'FAST_INSTANT_TRADE_PAY'
        biz_content['total_amount'] = values['amount']
        biz_content['subject'] = '%s: %s' % (self.company_id.name, values['reference'])
        biz_content['body'] = '%s: %s' % (self.company_id.name, values['reference'])

        biz_content_sign = func.rsaSign(json.dumps(biz_content),self.alipay_private_key)

        alipay_tx_values.update({'biz_content':biz_content_sign})
        
        subkey = ['app_id','method','version','charset','sign_type','timestamp','biz_content','return_url','notify_url']
        need_sign = {key:alipay_tx_values[key] for key in subkey}
        params,sign = func.buildRequestMysign(need_sign, self.alipay_private_key)
        alipay_tx_values.update({
            'sign':sign,
            })

        _logger.info('script_dir : %s' %(os.path.dirname(__file__)))

        return alipay_tx_values

    @api.multi
    def alipay_get_form_action_url(self):
        return self._get_alipay_urls(self.environment)['alipay_form_url']


class TxAlipay(models.Model):
    _inherit = 'payment.transaction'

    alipay_txn_type = fields.Char('Transaction type')

    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------

    @api.model
    def _alipay_form_get_tx_from_data(self, data):
        reference, txn_id = data.get('out_trade_no'), data.get('trade_no')
        if not reference or not txn_id:
            error_msg = _('Alipay: received data with missing reference (%s) or txn_id (%s)') % (reference, txn_id)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        txs = self.env['payment.transaction'].search([('reference', '=', reference)])
        if not txs or len(txs) > 1:
            error_msg = 'Alipay: received data for reference %s' % (reference)
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    @api.multi
    def _alipay_form_get_invalid_parameters(self, data):
        invalid_parameters = []
        return invalid_parameters

    @api.multi
    def _alipay_form_validate(self, data):
        status = data.get('trade_status')
        res = {
            'acquirer_reference': data.get('out_trade_no'),
            'alipay_txn_type': data.get('payment_type'),
            'acquirer_reference':data.get('trade_no'),
            'partner_reference':data.get('buyer_id')
        }
        if status in ['TRADE_FINISHED', 'TRADE_SUCCESS']:
            _logger.info('Validated alipay payment for tx %s: set as done' % (self.reference))
            res.update(state='done', date_validate=data.get('gmt_payment', fields.datetime.now()))
            return self.write(res)
        else:
            error = 'Received unrecognized status for Alipay payment %s: %s, set as error' % (self.reference, status)
            _logger.info(error)
            res.update(state='error', state_message=error)
            return self.write(res)
