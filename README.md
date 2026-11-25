# Jiro(가칭) 설문 응답 챗봇

설문 주관식 응답에 평소 말투로 질문하면, 해당하는 응답을 찾아 인원수와 원문을 출처와 함께 답하는 RAG 챗봇입니다. 리서치 인텔리전스 플랫폼 Jiro(가칭)의 기능 중 하나이며, <클라우드 아키텍처> 수업 과제로 진행합니다.

## 진행 상황

| 주차 | 내용 | 상태 |
|---|---|---|
| 1주차 | 서비스 기획 및 AWS 아키텍처 설계 | 완료 |
| 2주차 | AWS 환경 및 개발 환경 구성, 연결 확인 API 배포 | 이 저장소 |
| 3주차 이후 | 데이터 적재, 질문 답변 기능 | 예정 |

## 구성

```
브라우저 → CloudFront ─┬→ S3 웹 버킷 (화면 파일)
                       └→ API Gateway → Lambda ─┬→ S3 문서 버킷 (설문 파일)
                                                ├→ S3 Vectors (벡터 인덱스)
                                                └→ Bedrock (Titan 임베딩, Claude Haiku)
```

| AWS 서비스 | 쓰는 곳 |
|---|---|
| Amazon S3 | 화면 파일 버킷, 설문 문서 버킷 (둘 다 비공개) |
| Amazon CloudFront | 화면과 API를 한 주소로 전달. 웹 버킷은 CloudFront만 읽음(OAC) |
| Amazon API Gateway (REST API) | 질문을 받는 창구. 초당 5회 호출 제한 |
| AWS Lambda (Python 3.13) | 질문 처리. 2주차에는 연결 확인만 |
| Amazon S3 Vectors | 벡터 인덱스 `responses` (1,024차원, 코사인 거리) |
| Amazon Bedrock | Titan Text Embeddings V2, Claude Haiku 4.5 |
| AWS IAM | Lambda에 필요한 권한만 부여 (읽기·조회·모델 호출) |
| Amazon CloudWatch | Lambda 로그, 30일 뒤 자동 삭제 |
| AWS Budgets | 월 예산 알림 (선택) |

리전은 서울(ap-northeast-2)입니다. Claude Haiku는 서울 리전에서 글로벌 추론 프로필로 호출합니다.

## 폴더

```
template.yaml      AWS 자원 전체를 정의한 설정 파일 (AWS SAM)
samconfig.toml     배포 기본값 (스택 이름, 리전)
deploy.sh          배포 → 화면 파일 올리기 → 연결 확인까지 한 번에
src/query/app.py   질문 처리 Lambda
web/index.html     연결 확인 화면
tests/             AWS 없이 Lambda 코드 흐름을 확인하는 테스트
```

## 배포

AWS 콘솔의 CloudShell에서 실행하면 따로 설치할 것이 없습니다(AWS CLI, SAM CLI, git이 들어 있습니다). 콘솔 오른쪽 위에서 리전을 **서울**로 바꾼 뒤 CloudShell을 엽니다.

```bash
git clone https://github.com/<계정>/<저장소>.git
cd <저장소>
./deploy.sh                 # 예산 알림 없이
./deploy.sh me@example.com  # 월 5달러의 80%를 넘으면 메일로 알림
```

처음 배포는 CloudFront 때문에 5~10분 걸립니다. 끝나면 화면 주소가 출력됩니다.

### 처음 한 번 필요한 것

Anthropic 모델을 계정에서 처음 쓸 때는 Bedrock 콘솔에서 사용 목적을 적어 내야 할 수 있습니다. 연결 확인에서 "생성 모델 호출"만 실패하면 Bedrock 콘솔의 모델 카탈로그에서 Claude Haiku 4.5를 열어 안내에 따라 제출한 뒤 다시 확인합니다.

## 연결 확인

화면 주소를 열면 아래 여섯 가지를 확인한 결과가 나옵니다. `<화면 주소>/api/health` 를 직접 열면 같은 내용을 JSON으로 볼 수 있습니다.

| 항목 | 확인하는 것 |
|---|---|
| 실행 환경 | Lambda의 Python·SDK 버전, 리전 |
| 문서 버킷 접근 | 정리본 폴더 목록 조회 |
| 벡터 인덱스 접근 | 인덱스의 차원 수, 거리 방식, 인덱스 방식 |
| 임베딩 모델 호출 | 한국어 문장을 1,024차원 벡터로 변환 |
| 벡터 검색 | 그 벡터로 인덱스 검색 (적재 전이라 0건이 정상) |
| 생성 모델 호출 | Claude Haiku가 짧은 답을 돌려주는지 |

## 테스트

```bash
pip install boto3
python3 -m unittest discover tests
```

## 지우기

```bash
aws s3 rm "s3://$(aws cloudformation describe-stacks --stack-name jiro-rag --region ap-northeast-2 --query "Stacks[0].Outputs[?OutputKey=='WebBucketName'].OutputValue" --output text)" --recursive
sam delete --stack-name jiro-rag --region ap-northeast-2
```

문서 버킷에 파일을 올렸다면 지우기 전에 그 버킷도 비워야 합니다(버전 관리가 켜져 있어 콘솔의 "비우기"가 가장 간단합니다).
