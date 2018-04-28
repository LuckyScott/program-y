import uuid
import datetime

from programy.utils.logging.ylogger import YLogger

from flask import Flask
from flask import jsonify
from flask import request
from flask import make_response
from flask import abort
from flask import current_app

from programy.clients.restful.flask.client import FlaskRestBotClient
from programy.clients.restful.flask.webchat.config import WebChatConfiguration
from programy.clients.render.html import HtmlRenderer
import json


class WebChatBotClient(FlaskRestBotClient):

    def __init__(self, argument_parser=None):
        FlaskRestBotClient.__init__(self, "WebChat", argument_parser)
        # Enter you API keys, here, alternatively store in a db or file and load at startup
        # This is an exmaple, and therefore not suitable for production
        self._api_keys = [
        ]
        self._renderer = HtmlRenderer()

    def get_description(self):
        return 'ProgramY AIML2.0 Webchat Client'

    def get_client_configuration(self):
        return WebChatConfiguration()

    def is_apikey_valid(self, apikey):
        return bool(apikey in self._api_keys)

    def get_api_key(self, request):
        if 'api_key' in request.args:
            return request.args['api_key']
        return None

    def unauthorised_access_response(self, error_code=401):
        return make_response(jsonify({'error': 'Unauthorized access'}), error_code)

    def check_api_key(self, request):
        if self.configuration.client_configuration.use_api_keys is True:
            api_key = self.get_api_key(request)
            if api_key is None:
                YLogger.error(self, "Unauthorised access - api required but missing")
                return self.unauthorised_access_response()

            if self.is_apikey_valid(api_key) is False:
                YLogger.error(self, "'Unauthorised access - invalid api key")
                return self.unauthorised_access_response()

        return None

    def get_question(self, request):
        if 'question' in request.args:
            return request.args['question']
        return None

    def get_userid(self, request):
        userid = request.cookies.get(self.configuration.client_configuration.cookie_id)
        if userid is None:
            userid = str(uuid.uuid4().hex)
            YLogger.debug(self, "Setting userid cookie to :%s" % userid)
        else:
            YLogger.debug(self, "Found userid cookie : %s" % userid)
        return userid

    def get_userid_cookie_expirary_date(self, duration):
        expire_date = datetime.datetime.now()
        expire_date = expire_date + datetime.timedelta(days=duration)
        return expire_date

    def create_success_response_data(self, question, answer):
        return {"question": question, "answer": answer}

    def get_default_response(self, client_context):
        return client_context.bot.default_response

    def create_error_response_data(self, client_context, question, error):
        return {"question": question,
                "answer": self.get_default_response(client_context),
                "error": error
                }

    def create_response(self, response_data, userid, userid_expire_date):
        response = jsonify({'response': response_data})
        response.set_cookie(self.configuration.client_configuration.cookie_id, userid, expires=userid_expire_date)
        return response

    def get_answer(self, client_context, question):
        if question == 'YINITIALQUESTION':
            answer = client_context.bot.get_initial_question(client_context)
        else:
            answer = client_context.bot.ask_question(client_context, question, responselogger=self)
        return answer

    def receive_message(self, request):

        api_key_response = self.check_api_key(request)
        if api_key_response is not None:
            return api_key_response

        question = self.get_question(request)
        if question is None:
            YLogger.error(self, "'question' missing from request")
            abort(400)

        userid = self.get_userid(request)

        userid_expire_date = self.get_userid_cookie_expirary_date(self.configuration.client_configuration.cookie_expires)

        client_context = self.create_client_context(userid)
        try:
            answer = self.get_answer(client_context, question)
            if answer.startswith('#`json`#'):
                try:
                    answer = json.loads(answer[8:])
                    if answer['status'] == 0:
                        answer = json.dumps(answer['data'], ensure_ascii=False)
                    else:
                        answer = answer['message']
                except:
                    answer = answer[8:]
                    YLogger.debug(self, "restsclient load json from answer ERROR, answer: %s" % answer)
            rendered = self._renderer.render(client_context, answer)
            response_data = self.create_success_response_data(question, rendered)

        except Exception as excep:
            YLogger.exception(self, excep)
            response_data = self.create_error_response_data(client_context, question, str(excep))

        return self.create_response(response_data, userid, userid_expire_date)

    def get_rest_question(self, rest_request):
        if 'question' not in rest_request.args or rest_request.args['question'] is None:
            YLogger.error(self, "'question' missing from request")
            abort(400)
        return rest_request.args['question']

    def get_rest_userid(self, rest_request):
        if 'userid' not in rest_request.args or rest_request.args['userid'] is None:
            userid = str(uuid.uuid4().hex)
            YLogger.error(self, "'userid' missing from request")
            # abort(400)
        else:
            userid = rest_request.args['userid']
        return userid

    def dump_request(self, request):
        if request.method == 'POST':
            YLogger.debug(self, str(request))
        elif request.method == 'GET':
            YLogger.debug(self, str(request))
        else:
            YLogger.debug(self, "restsclient.dump_request(), only GET and POST supported!")

    def process_rest_request(self, request):
        question = "Unknown"
        userid = "Unknown"
        try:
            response, status = self.verify_api_key_usage(request)
            if response is not None:
                return response, status

            question = self.get_rest_question(request)
            userid = self.get_rest_userid(request)

            answer = self.ask_question(userid, question)
            response = None
            # if type(answer) is bytes and answer.startswith(b'\xe8json\xe8'):
            # 内部不支持 bytes 类型
            if answer.startswith('#`json`#'):
                try:
                    answer = json.loads(answer[8:])
                    response = self.format_success_response(userid, question, answer)
                    response['data_type'] = 'json'
                except:
                    answer = answer[8:]
                    YLogger.debug(self, "restsclient load json from answer ERROR, answer: %s" % answer)

            if response is None:
                response = self.format_success_response(userid, question, answer)
                response['data_type'] = 'text'

            return response, 200
            # return self.format_success_response(userid, question, answer), 200

        except Exception as excep:

            return self.format_error_response(userid, question, str(excep)), 500

    def response_rest_message(self, request):
        response_data, status = self.process_rest_request(request)
        if self.configuration.client_configuration.debug is True:
            self.dump_request(request)
            YLogger.debug(self, "restclient response data:{}".format({'response': response_data, 'status':status}))

        return make_response(jsonify({'response': response_data, 'status':status}))


if __name__ == '__main__':

    WEB_CLIENT = None

    print("Initiating WebChat Client...")
    APP = Flask(__name__)

    @APP.route('/')
    def index():
        return current_app.send_static_file('webchat.html')

    @APP.route('/api/web/v1.0/ask', methods=['GET'])
    def receive_message():
        try:
            return WEB_CLIENT.receive_message(request)
        except Exception as e:
            print(e)
            YLogger.exception(None, e)
            return "500"

    @APP.route('/api/rest/v1.0/ask', methods=['GET'])
    def api_rest_ask():
        return WEB_CLIENT.response_rest_message(request)

    WEB_CLIENT = WebChatBotClient()
    WEB_CLIENT.run(APP)
