# -*- coding: utf-8 -*-

import json
import logging
import pprint
import urllib.request
import requests
import werkzeug
from werkzeug import urls

from odoo import http
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.http import request

from odoo.addons.payment_alipay.models import func

_logger = logging.getLogger(__name__)

class AlipayController(http.Controller):
    _notify_url = '/payment/alipay/ipn/'
    _return_url = '/payment/alipay/dpn/'

    def _get_return_url(self, **post):
        """ Extract the return URL from the data coming from alipay. """
        return_url = post.pop('return_url', '')
        if not return_url:
            custom = json.loads(urls.url_unquote_plus(post.pop('custom', False) or post.pop('cm', False) or '{}'))
            return_url = custom.get('return_url', '/')
        return return_url

    """
     * 获取返回时的签名验证结果
     * @param post 通知返回来的参数数组
     * @返回 签名验证结果
    """
    def getSignVerify(self,**post):
        key_sorted = sorted(post.keys())
        content = ''
        sign_type = post['sign_type']
        sign = post['sign']
        charset = post['charset']

        for key in key_sorted:
            if key not in ["sign","sign_type"]:
                if post[key]:
                    content = content + key + "=" + post[key] + "&"
        content = content[:-1]
        content = content.encode(charset)
        alipay_official_public_key = request.env['payment.acquirer'].sudo().search([]).alipay_official_public_key
        _logger.info(alipay_official_public_key)
        isSign = False
        if sign_type.upper() == "RSA2":
            isSign = func.rsaVerify(content,alipay_official_public_key,sign)
        return isSign
        

    def verify_data(self, **post):
        if not post:
            return False
        else:
            isSign = self.getSignVerify(**post)
            if  isSign:
                res = request.env['payment.transaction'].sudo().form_feedback(post,'alipay')
                return True
            else:
                return False


    @http.route('/payment/alipay/ipn/', type='http', auth="none", methods=['POST'], csrf=False)
    def alipay_ipn(self, **post):
        """ Alipay IPN. """
        _logger.info('Beginning Alipay IPN form_feedback with post data %s', pprint.pformat(post))  # debug
        if self.verify_data(**post):
            return 'success'
        else:
            return 'fail'

    @http.route('/payment/alipay/dpn', type='http', auth="none", methods=['POST', 'GET'], csrf=False)
    def alipay_dpn(self, **post):
        """ Alipay RETURN """
        _logger.info('Beginning Alipay DPN form_feedback with post data %s', pprint.pformat(post))  # debug
        
        if self.verify_data(**post):
            return "验签成功"
        else:
            return "验签失败"
