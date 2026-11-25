"""질문 처리 Lambda.

2주차 범위: GET /api/health 하나만 처리한다.
이 Lambda가 문서 버킷, 벡터 저장소, 임베딩 모델, 생성 모델에
각각 접근할 수 있는지 확인하고 결과를 돌려준다.
"""

import json
import os
import platform
import time

import boto3

REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
DOCS_BUCKET = os.environ.get("DOCS_BUCKET", "")
VECTOR_INDEX_ARN = os.environ.get("VECTOR_INDEX_ARN", "")
GENERATION_MODEL_ID = os.environ.get("GENERATION_MODEL_ID", "")
EMBEDDING_MODEL_ID = os.environ.get("EMBEDDING_MODEL_ID", "")
EMBEDDING_DIMENSION = int(os.environ.get("EMBEDDING_DIMENSION", "1024"))

_clients = {}


def client(name):
    """같은 실행 환경에서는 한 번 만든 연결을 다시 쓴다."""
    if name not in _clients:
        _clients[name] = boto3.client(name, region_name=REGION)
    return _clients[name]


def check_runtime():
    return {
        "python": platform.python_version(),
        "boto3": boto3.__version__,
        "region": REGION,
    }


def check_docs_bucket():
    result = client("s3").list_objects_v2(
        Bucket=DOCS_BUCKET, Prefix="processed/", MaxKeys=1
    )
    return {"bucket": DOCS_BUCKET, "files_in_processed": result.get("KeyCount", 0)}


def check_vector_index():
    result = client("s3vectors").get_index(indexArn=VECTOR_INDEX_ARN)
    index = result.get("index", {})
    detail = {
        "index": index.get("indexName"),
        "dimension": index.get("dimension"),
        "distance": index.get("distanceMetric"),
    }
    # 인덱스 방식(ENHANCED/CLASSIC). Lambda에 들어 있는 SDK가 오래되면 값이 없을 수 있다.
    if "indexMode" in index:
        detail["index_mode"] = index["indexMode"]
    return detail


def embed(text):
    body = {"inputText": text, "dimensions": EMBEDDING_DIMENSION, "normalize": True}
    response = client("bedrock-runtime").invoke_model(
        modelId=EMBEDDING_MODEL_ID, body=json.dumps(body)
    )
    return json.loads(response["body"].read())["embedding"]


def check_embedding(state):
    vector = embed("배송이 생각보다 느렸어요")
    state["vector"] = vector
    return {"model": EMBEDDING_MODEL_ID, "vector_length": len(vector)}


def check_vector_query(state):
    if "vector" not in state:
        raise RuntimeError("임베딩 확인이 실패해 검색을 시도하지 못했습니다.")
    result = client("s3vectors").query_vectors(
        indexArn=VECTOR_INDEX_ARN,
        queryVector={"float32": state["vector"]},
        topK=3,
        returnMetadata=True,
        returnDistance=True,
    )
    # 아직 적재 전이므로 0건이 정상이다.
    return {"results": len(result.get("vectors", []))}


def check_generation():
    response = client("bedrock-runtime").converse(
        modelId=GENERATION_MODEL_ID,
        messages=[
            {"role": "user", "content": [{"text": "'연결 확인'이라고만 답해 주세요."}]}
        ],
        inferenceConfig={"maxTokens": 30, "temperature": 0},
    )
    text = response["output"]["message"]["content"][0]["text"]
    return {"model": GENERATION_MODEL_ID, "reply": text.strip()}


def run_check(name, label, func):
    started = time.perf_counter()
    try:
        detail = func()
        ok = True
    except Exception as error:  # 어떤 단계가 막혔는지 그대로 보여주기 위해 모두 잡는다.
        detail = {"error": type(error).__name__, "message": str(error)[:300]}
        ok = False
    return {
        "name": name,
        "label": label,
        "ok": ok,
        "ms": round((time.perf_counter() - started) * 1000),
        "detail": detail,
    }


def health():
    state = {}
    checks = [
        run_check("runtime", "실행 환경", check_runtime),
        run_check("docs_bucket", "문서 버킷 접근", check_docs_bucket),
        run_check("vector_index", "벡터 인덱스 접근", check_vector_index),
        run_check("embedding", "임베딩 모델 호출", lambda: check_embedding(state)),
        run_check("vector_query", "벡터 검색", lambda: check_vector_query(state)),
        run_check("generation", "생성 모델 호출", check_generation),
    ]
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event, context):
    path = event.get("path", "")
    method = event.get("httpMethod", "")
    if method == "GET" and path == "/api/health":
        result = health()
        # 응답 원문은 남기지 않고, 단계별 성공 여부와 걸린 시간만 로그에 남긴다.
        print(json.dumps({
            "event": "health",
            "ok": result["ok"],
            "steps": {c["name"]: {"ok": c["ok"], "ms": c["ms"]} for c in result["checks"]},
        }))
        return respond(200, result)
    return respond(404, {"message": "없는 경로입니다."})
