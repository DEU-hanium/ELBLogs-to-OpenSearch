import boto3
import gzip
import re
import requests
from requests_aws4auth import AWS4Auth

region = 'ap-northeast-2'
service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

host = 'https://search-crawling-opensearch-logs-6bvs2mfumuxpdb66cwyaexx3dq.ap-northeast-2.es.amazonaws.com'
index = 'logs'
datatype = '_doc'
url = host + '/' + index + '/' + datatype

headers = { "Content-Type": "application/json" }

s3 = boto3.client('s3')

fields = ['type', 'timestamp', 'elb', 'client_ip', 'clent_port', 'target_ip', 'target_port', 'request_processing_time', 'target_processing_time',
          'response_processing_time', 'elb_status_code', 'target_status_code', 'received_bytes', 'sent_bytes',
          'request_method', 'url', 'http_version', 'user_agent', 'ssl_cipher', 'ssl_protocol', 'target_group_arn', 'trace_id', 'domain_name', 
          'chosen_cert_arn', 'matched_rule_priority', 'request_creation_time', 'actions_executed', 'redirect_url', 'error_reason', 
          'target_port_list', 'target_status_code_list', 'classification', 'classification_reason']

def extract_fields(data, fields):
    extracted_data={}
    temp = 1

    for field in fields:
        regex = re.compile(r'([^ ]*) ([^ ]*) ([^ ]*) ([^ ]*):([0-9]*) ([^ ]*)[:-]([0-9]*) ([-.0-9]*) ([-.0-9]*) ([-.0-9]*) (|[-0-9]*) (-|[-0-9]*) ([-0-9]*) ([-0-9]*) \"([^ ]*) (.*) (- |[^ ]*)\" \"([^\"]*)\" ([A-Z0-9-_]+) ([A-Za-z0-9.-]*) ([^ ]*) \"([^\"]*)\" \"([^\"]*)\" \"([^\"]*)\" ([-.0-9]*) ([^ ]*) \"([^\"]*)\" \"([^\"]*)\" \"([^ ]*)\" \"([^\s]+?)\" \"([^\s]+)\" \"([^ ]*)\" \"([^ ]*)\"')
        match = regex.search(data)

        if match:
            extracted_data[field] = match.group(temp)
            temp += 1

    return extracted_data

def lambda_handler(event, context):
    # TODO implement
    BUCKET_NAME = event['Records'][0]['s3']['bucket']['name']
    KEY = event['Records'][0]['s3']['object']['key'] # 파일명
    
    data = s3.get_object(Bucket = BUCKET_NAME, Key = KEY)
    data = data['Body'].read()
    data = gzip.decompress(data).decode('utf-8') # s3에서 받아온 데이터를 gzip으로 압축해제하고 utf-8로 디코딩
    
    datas = data.splitlines()
    
    logList = []
    for line in datas:
        logList.append(extract_fields(line, fields))
        r = requests.post(url, auth=awsauth, json=extract_fields(line, fields), headers=headers)
        print(r.text)
    
    if len(logList) != 0:
        print(logList)