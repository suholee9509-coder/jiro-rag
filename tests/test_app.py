"""AWS 없이 Lambda 코드의 흐름만 확인한다. 실행: python3 -m unittest discover tests"""

import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "query"))

os.environ.update({
    "DOCS_BUCKET": "docs",
    "VECTOR_INDEX_ARN": "arn:aws:s3vectors:ap-northeast-2:1:bucket/b/index/responses",
    "GENERATION_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    "EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
    "EMBEDDING_DIMENSION": "1024",
})

import app  # noqa: E402


def fake_clients(fail=None):
    s3 = mock.Mock()
    s3.list_objects_v2.return_value = {"KeyCount": 0}
    vectors = mock.Mock()
    vectors.get_index.return_value = {
        "index": {"indexName": "responses", "dimension": 1024, "distanceMetric": "cosine"}
    }
    vectors.query_vectors.return_value = {"vectors": []}
    bedrock = mock.Mock()
    bedrock.invoke_model.side_effect = lambda **_: {
        "body": io.BytesIO(json.dumps({"embedding": [0.1] * 1024}).encode())
    }
    bedrock.converse.return_value = {
        "output": {"message": {"content": [{"text": "연결 확인"}]}}
    }
    if fail == "generation":
        bedrock.converse.side_effect = RuntimeError("AccessDeniedException")
    if fail == "embedding":
        bedrock.invoke_model.side_effect = RuntimeError("AccessDeniedException")
    return {"s3": s3, "s3vectors": vectors, "bedrock-runtime": bedrock}


def call(path="/api/health", method="GET"):
    response = app.handler({"path": path, "httpMethod": method}, None)
    return response["statusCode"], json.loads(response["body"])


class HealthTest(unittest.TestCase):
    def setUp(self):
        app._clients.clear()

    def test_all_ok(self):
        app._clients.update(fake_clients())
        status, body = call()
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(len(body["checks"]), 6)
        by_name = {c["name"]: c for c in body["checks"]}
        self.assertEqual(by_name["embedding"]["detail"]["vector_length"], 1024)
        self.assertEqual(by_name["generation"]["detail"]["reply"], "연결 확인")

    def test_generation_failure_is_reported(self):
        app._clients.update(fake_clients(fail="generation"))
        status, body = call()
        self.assertEqual(status, 200)
        self.assertFalse(body["ok"])
        failed = [c["name"] for c in body["checks"] if not c["ok"]]
        self.assertEqual(failed, ["generation"])

    def test_embedding_failure_also_fails_query(self):
        app._clients.update(fake_clients(fail="embedding"))
        _, body = call()
        failed = [c["name"] for c in body["checks"] if not c["ok"]]
        self.assertEqual(failed, ["embedding", "vector_query"])

    def test_unknown_path(self):
        status, _ = call(path="/api/unknown")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
