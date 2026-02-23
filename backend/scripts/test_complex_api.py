import requests
import json
import traceback

def main():
    payload = {
        "base_url": "https://httpbin.org",
        "steps": [
            {
                "id": "step_1",
                "name": "GET with Headers and Params",
                "request": {
                    "method": "GET",
                    "url": "/get",
                    "headers": {
                        "X-Custom-Auth": "Bearer super-secret-token",
                        "Accept": "application/json"
                    },
                    "query_params": {
                        "search": "test_query",
                        "page": "1"
                    },
                    "timeout_ms": 10000
                },
                "extraction": {
                    "request_url": "$.url",
                    "auth_header": "$.headers.X-Custom-Auth"
                },
                "assertion": {
                    "status_code": 200,
                    "json_assertions": {
                        "$.args.search": "test_query"
                    },
                    "contains": "httpbin.org"
                }
            },
            {
                "id": "step_2",
                "name": "POST with Extracted Variables",
                "request": {
                    "method": "POST",
                    "url": "/post",
                    "headers": {
                        "Authorization": "${auth_header}"
                    },
                    "body": {
                        "original_url": "${request_url}",
                        "message": "Hello from step 2"
                    },
                    "query_params": {},
                    "timeout_ms": 10000
                },
                "extraction": {},
                "assertion": {
                    "status_code": 200,
                    "json_assertions": {
                        "$.json.message": "Hello from step 2"
                    }
                }
            }
        ],
        "context": {},
        "default_headers": {},
        "stop_on_failure": True
    }

    try:
        print("Sending complex request sequentially...")
        resp = requests.post("http://localhost:8000/api/v1/left-pupil/execute-chain", json=payload, timeout=30.0)
        print(f"Status Code: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print("Request failed!")
        traceback.print_exc()

if __name__ == "__main__":
    main()
