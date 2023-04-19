# 주요 코드 설명

- S3 PUT Event에 트리거되는 lambda_handler
- event 객체에 저장된 파일의 메타데이터를 통해 get 요청으로 파일 가져오기
- S3에 저장되는 ELB 로그들은 기본적으로 .gz 파일형식이므로 압축해제
- 데이터는 필드명이 없고 값만 있으므로 정규식을 통해 JSON 형식 변환
- OpenSearch에 POST 요청 (post요청은 _id값이 자동 생성됨)