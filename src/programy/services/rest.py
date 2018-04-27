"""
Copyright (c) 2016-2018 Keith Sterling http://www.keithsterling.com

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
from programy.utils.logging.ylogger import YLogger
import requests

from programy.services.service import Service
from programy.config.brain.service import BrainServiceConfiguration
import datetime
from dateutil.parser import parse as date_parse


class RestAPI(object):

    def get(self, url):
        return requests.get(url)

    def post(self, url, data):
        return requests.post(url, data=data)


class GenericRESTService(Service):

    def __init__(self, config: BrainServiceConfiguration, api=None):
        Service.__init__(self, config)

        if api is None:
            self.api = RestAPI()
        else:
            self.api = api

        if config.method is None:
            self.method = "GET"
        else:
            self.method = config.method

        if config.host is None:
            raise Exception("Undefined host parameter")
        self.host = config.host

        self.port = None
        if config.port is not None:
           self.port = config.port

        self.url = None
        if config.url is not None:
           self.url = config.url

    def _format_url(self):
        if self.port is not None:
            host_port = "http://%s:%s"%(self.host, self.port)
        else:
            host_port = "http://%s"%self.host

        if self.url is not None:
            return "%s%s"%(host_port, self.url)
        else:
            return host_port

    def _format_payload(self, client_context, question):
        return {}

    def _format_get_url(self, url, client_context, question):
        splits = question.split()
        api = splits[0].upper()
        if api == 'STOCK_VALUATION':
            code = ''.join(splits[1:])
            dt = datetime.datetime.now()
            if dt.hour <= 8:
                dt = datetime.date.today() - datetime.timedelta(days=1)
            url = '{}/api/stock/valuation/{:%Y-%m-%d}/{}'.format(url, dt, code)
        elif api == 'STOCK_NEWS':
            code = ''.join(splits[1:])
            url = '{}/api/news/ycj/{}'.format(url, code)
        elif api == 'STOCK_NEWS2':
            code = ''.join(splits[1:])
            url = '{}/api/news/cailian/{}'.format(url, code)
        elif api == 'STOCK_MORNING_SELECT':
            if len(splits) < 2:
                date = datetime.date.today()
            if splits[1].upper() == "TODAY":
                date = datetime.date.today()
            elif splits[1].upper() == "YESTERDAY":
                date = datetime.date.today() - datetime.timedelta(days=1)
            else:
                date = date_parse(splits[1:])
            url = '{}/api/stock/morning_select/{:%Y-%m-%d}'.format(url, date)
        elif api == 'STOCK_FOCUS':
            code = ''.join(splits[1:])
            url = '{}/api/stock/ths_focus/{}'.format(url, code)
        elif api == 'STOCK_INFO':
            code = ''.join(splits[1:-1])
            content = splits[-1]
            if content == 'NETPROFIT':
                url = '{}/api/stock/basic_info/fundamental/{}/{:%Y-%m-%d}'.format(url, code, datetime.datetime.now())
            else:
                url = '{}/api/stock/basic_info/{}'.format(url, code)
        return url

    def _parse_response(self, text):
        return text

    def ask_question(self, client_context, question: str):

        try:
            url = self._format_url()

            if self.method == 'GET':
                full_url = self._format_get_url(url, client_context, question)
                response = self.api.get(full_url)
                splits = question.split()
                if splits[0].upper() == 'STOCK_INFO':
                    response = response.json()
                    if response['status'] != 0:
                        response = response['message']
                    elif splits[-1] == 'START_DATE':
                        response = date_parse(response['data']['marketed_date']).strftime('%Y-%m-%d')
                    elif splits[-2] == 'INDUSTRY':
                        response = response['data']['concepts']
                    elif splits[-1] == 'CONCEPT':
                        response = response['data']['wind_concepts']
                    elif splits[-1] == 'CAPITAL':
                        response = response['data']['totle_share_count']
                    elif splits[-1] == 'NETPROFIT':
                        response = "{} 报表公布的净利润为：{}".format(response['data']['stat_date'],response['data']['net_profit'])
                    else:
                        response = "Unknown"
                    return self._parse_response(str(response))
            elif self.method == 'POST':
                payload = self._format_payload(client_context, question)
                response = self.api.post(url, data=payload)
            else:
                raise Exception("Unsupported REST method [%s]"%self.method)

            if response.status_code != 200:
                YLogger.error(client_context, "[%s] return status code [%d]", self.host, response.status_code)
            else:
                return self._parse_response(response.text)

        except Exception as excep:
            YLogger.exception(client_context, excep)

        return ""
