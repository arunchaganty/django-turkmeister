from django.apps import AppConfig


class TurkmeisterConfig(AppConfig):
    name = 'turkmeister'
    # Sandbox
    AMT_ENDPOINT = 'https://mturk-requester-sandbox.us-east-1.amazonaws.com'
    AWS_REGION = 'us-east-1'
    AWS_ACCESS_KEY = ''
    AWS_SECRET_ACCESS_KEY = ''
    # Not-sandbox
    # AMT_ENDPOINT = 'https://mturk-requester.us-east-1.amazonaws.com'
