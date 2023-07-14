# 1. ALB 로그 수집 활성화

## 1.1 S3에 로그 적재
> 본인이 만든 ALB 클릭 -> 속성 탭 -> Edit

![](https://velog.velcdn.com/images/leemhoon00/post/2875535a-a2b2-4bcb-9052-21c11a9d7062/image.png)

> ALB 로그 수집을 활성화 하면 S3에 로그가 저장된다.

## 1.2 로그 수집되는지 확인

![](https://velog.velcdn.com/images/leemhoon00/post/f561a05a-1d98-4344-a22a-c48b4cae4dcd/image.png)

> - 위에서 명시한 접두사 밑으로 여러 폴더가 생성되면서 로그가 만들어진다.
> - ALB 로그는 트래픽이 있을 때마다 S3에 저장하는 것이 아니라 5분 간격으로 그 사이에 있었던 모든 로그를 하나의 파일에 저장한다.
> - 기본적으로 .gz 파일로 압축되어 저장되며 저장 형식을 바꿀 수 있다는 카더라가 있었지만 전혀 찾을 수가 없었다.
확실하진 않지만 트래픽이 아예 없을 때는 파일을 생성하지 않았다.
> - **파일명 규칙은 공식문서에 있으니 참고**

<br>

# 2. Amazon OpenSearch Service
---
## 2.1 OpenSearch 도메인 생성

![](https://velog.velcdn.com/images/leemhoon00/post/a7cf4d22-901c-47f5-b15f-5caeb5c1cd32/image.png)

![](https://velog.velcdn.com/images/leemhoon00/post/7862104d-0ea1-4583-a54b-3812ab60a8c0/image.png)

> 인스턴스 유형이 기본값으로 r6g.large.search이 선택된다.
테스트 용도 이므로 t3.small.search로 변경

![](https://velog.velcdn.com/images/leemhoon00/post/e3deb09d-1cb5-4342-86c9-3642a58ce2c5/image.png)

![](https://velog.velcdn.com/images/leemhoon00/post/d14166d9-b7db-4d66-bfb9-cf4477e7c647/image.png)

![](https://velog.velcdn.com/images/leemhoon00/post/8de85106-fbe7-4e1d-87b4-ac12e89ce711/image.png)

> - 이 외의 것들은 다 기본값.
> - 고급 클러스터 설정의 최대 절 수가 디폴트로 값이 안 들어가있는데 생성버튼을 누를 시 에러가 뜬다.
> - 최대 절 수에 1024라고 적어주자.
> - 이제 생성버튼을 누르면 도메인이 생성되는데 10~15분 정도 걸린다고 한다.


## 2.2 OpenSearch 액세스 정책

> 생성한 도메인 클릭 후 보안 구성 탭 -> 편집

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": "es:*",
      "Resource": "OpenSearch-도메인-arn복붙/*"
    }
  ]
}
```

> 사실 저렇게 하면 안되는데 이 뒤에 있을 Lambda 코드와 OpenSearch 대시보드 접근 등 권한이슈가 해결이 안되서 보안성이고 뭐고 걍 다 열어버렸다.

## 2.3 OpenSearch 대쉬보드

> 도메인을 선택하면 OpenSearch 대시보드 URL을 볼 수 있다. -> 클릭

![](https://velog.velcdn.com/images/leemhoon00/post/599c396b-5595-4b25-b79d-32b85e8b8622/image.png)

> 도메인 생성때 만들었던 마스터유저의 아이디 패스워드를 적는다.
접속 되면 성공

<br>

# 3. Lambda
---

## 3.1 Lambda 코드

> 폴더 하나 생성 후 lambda_function.py 작성

```python
import boto3
import gzip
import re
import requests
from requests_aws4auth import AWS4Auth

region = 'ap-northeast-2'
service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

host = '' # opensearch 엔드포인트 url
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
```

> 해당 lambda 코드는 S3의 Put 이벤트에 의해 트리거되어 실행된다.
간단하게 코드 설명을 하자면
- event 객체에 담긴 메타데이터로 S3에 업로드된 파일정보를 얻어서 s3.get_object로 데이터를 받아온다.
- S3에 저장된 로그 파일은 .gz 파일 형식으로 압축되어 있으므로 gzip 라이브러리를 import 해서 decompress 해준다.
- 압축을 해제 하더라도 로그를 읽어보면 필드명이 없고 데이터값만 나열되어 있다.
- 이걸 정규식으로 추출해 정의해 둔 필드에 매칭시켜 json 형식으로 변환해주는 extract_fields함수
- requests 라이브러리로 post 요청을 하는데 put요청을 하지 않는 이유는 데이터 하나를 넣을 때 마다 put 요청은 _id값을 명시해줘야 한다. 공식문서의 예제는 _docs/1, _docs/2 이런식으로 수를 하나씩 늘려가며 데이터를 넣어주는데 본인은 그걸 자동으로 auto_increase를 해줄 능력이 없기 때문에 찾아보니 post 요청과 동시에 _id값을 명시하지 않을 경우 OpenSearch에서 id값을 알아서 생성해 넣어준다.

> **추가로 나는 Lambda에 관리자 Role을 주어서 권한이슈는 생각하지 않았다.**

## 3.2 Lambda 코드 업로드

> - 위 코드에서 Lambda Python 기본 내장 모듈은 boto3, gzip, re 이고 나머지 **requests, requests_aws4auth 모듈은 내장모듈이 아니므로 직접 pip install 하여 압축해서 올려야된다.**
> - lambda 코드가 있는 폴더로 이동

```bash
cd s3-to-opensearch

pip install --target ./package requests
pip install --target ./package requests_aws4auth

cd package
zip -r ../lambda.zip .

cd ..
zip -g lambda.zip lambda_function.py
```

> 생성된 zip파일과 함께 람다 함수를 생성한다.


<br>

# 4. S3 이벤트 트리거
---

![](https://velog.velcdn.com/images/leemhoon00/post/97731871-ad58-4e02-8643-ccd84d470704/image.png)

![](https://velog.velcdn.com/images/leemhoon00/post/e4b163c7-2a4a-423e-a1d3-c9197b47bfa4/image.png)

![](https://velog.velcdn.com/images/leemhoon00/post/4d9a1b35-afa6-4c45-a92c-d691fff05575/image.png)



<br>

# 5. CloudWatch 로그 그룹
---

> - 시스템은 다 만들었으니 잘 실행되는지 확인만 하면 된다.
> - Lambda가 실행될 경우 자동적으로 CloudWatch에 함수의 로그가 기록된다.
> - 검색창에 CloudWatch -> 로그 -> 로그그룹 -> lambda 함수명 클릭
> - 트래픽이 지속적으로 있을 경우 이론상 5분에 하나씩 로그가 쌓이게 된다. 아무거나 열어보자

![](https://velog.velcdn.com/images/leemhoon00/post/c2e4b89b-fc6d-4fab-a445-26f2487a6214/image.png)

> - Lambda에서 print함수를 썼다면 그 내용이 여기에 출력된다.
> - 다른 건 모르겠고 중간에 _index로 실행하는 로그와 type 으로 실행하는 두 로그를 잘 보면된다.
> - _index로 시작하는 행은 print(r.text)의 결과값으로 post요청에 대한 응답값이다. 오류가 있다면 오류 메시지를 띄워줄거다.
> - type으로 시작하는 행은 print(logList)의 결과다.

<br>

# 6. OpenSearch 대쉬보드 확인
---
확인 전에 opensearch에서 권한 설정을 해줘야 한다.

- [아마존 공식 문서](https://docs.aws.amazon.com/ko_kr/opensearch-service/latest/developerguide/fgac.html#fgac-mapping)

좌측 메뉴에서 OpenSearch Plugins에서 Security를 들어가면 된다.

Internal users에서 Create internal user로 들어가서 user 등록을 해준다. 

본 프로젝트에서는 username과 password를 기입 후 진행한다. 후에 Backend roles - optional에서 aws의 IAM 역할로 만들었던 lambda의 관리자 arn을 복사하여 붙혀넣기 해준 후에 create 해주면 된다.

![image](https://drive.google.com/uc?id=15M48WkrkGPUJb0p19yr3fO9G8RQFroie)


그 후에 Security에 있는 Roles의 all_access를 선택하여 방금 만든 user를 Mapped users에서 Manage mapping을 선택 후 Users에 추가시킨 후에 마찬가지로 Backend roles에 IAM를 복사 - 붙혀넣기하여 Map을 누르면 권한 설정이 완료된다.

테스트로 설정해놓은 ALB의 DNS를 크롤링 기준에 맞춰서 접속을 해준다. 그 후에 Opensearch에 접속해준다.

> 아까 접속했던 OpenSearch 대쉬보드 접속 -> 좌측 메뉴바 -> 아래쪽 Dev Tools 클릭

```graphql
GET _search
{
  "query": {
    "match_all": {}
  }
  ```

을 해준다면 이미지와 같은 화면이 뜨면서 정보들을 확인할 수 있다.

![image](https://drive.google.com/uc?id=1JQLEkuuWD6OTvIbsqTepvsVxjRgMkev5)

> - OpenSearch 쿼리를 어떻게 하는지를 모르지만 이거는 걍 전체 다 검색인거같다.
> - 우측 화면에 결과가 잘 뜬다면 성공