#!/usr/bin/env bash
# 저장소 내려받기부터 배포, 연결 확인까지 한 번에 실행한다.
# AWS 콘솔의 CloudShell(리전: 서울)에서 실행하는 것을 기준으로 한다.
#
# 사용: bash setup.sh                  (예산 알림 없이)
#       bash setup.sh me@example.com   (월 5달러의 80%를 넘으면 이 메일로 알림)
set -euo pipefail

REPO_URL="https://github.com/suholee9509-coder/jiro-rag.git"
DIR="jiro-rag"
EMAIL="${1:-}"
LOG="$HOME/jiro-rag-deploy.log"

step() { echo; echo "== $1"; }

step "0/4 준비 상태 확인"
for tool in git aws sam python3 curl; do
  command -v "$tool" >/dev/null || { echo "'$tool' 명령이 없습니다. AWS CloudShell에서 실행해 주세요."; exit 1; }
done
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" \
  || { echo "AWS 로그인 정보를 찾지 못했습니다. AWS 콘솔의 CloudShell에서 실행해 주세요."; exit 1; }
echo "AWS 계정: $ACCOUNT / 배포 리전: ap-northeast-2 (서울)"

step "1/4 저장소 내려받기"
if [ -f template.yaml ] && [ -f deploy.sh ]; then
  echo "이미 저장소 폴더 안입니다. 최신 내용으로 맞춥니다."
  git pull --ff-only || true
elif [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
  cd "$DIR"
else
  git clone "$REPO_URL" "$DIR"
  cd "$DIR"
fi

step "2/4 ~ 4/4 배포, 화면 파일 올리기, 연결 확인"
chmod +x deploy.sh
./deploy.sh "$EMAIL" 2>&1 | tee "$LOG"

echo
echo "실행 기록을 $LOG 에 저장했습니다."
