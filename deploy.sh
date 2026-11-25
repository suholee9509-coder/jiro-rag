#!/usr/bin/env bash
# AWS 자원을 만들고 화면 파일을 올린 뒤, 접속 주소를 출력한다.
# 사용: ./deploy.sh            (예산 알림 없이)
#       ./deploy.sh me@x.com   (월 5달러 예산의 80%를 넘으면 이 메일로 알림)
set -euo pipefail

STACK="jiro-rag"
REGION="ap-northeast-2"
EMAIL="${1:-}"

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

echo "1/3 AWS 자원 만들기 (처음에는 CloudFront 때문에 5~10분 걸립니다)"
sam deploy --parameter-overrides "BudgetEmail=$EMAIL"

echo "2/3 화면 파일 올리기"
aws s3 cp web/index.html "s3://$(output WebBucketName)/index.html" \
  --content-type "text/html; charset=utf-8" --cache-control "no-cache" --region "$REGION"

echo "3/3 연결 확인"
SITE="$(output SiteUrl)"
curl -s "$SITE/api/health" | python3 -m json.tool --no-ensure-ascii || true

echo
echo "화면 주소: $SITE"
