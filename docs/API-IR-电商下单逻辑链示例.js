[
    {
        "protocol": "API-IR",
        "version": "1.0",
        "id": "API_STEP_AUTH_01",
        "description": "场景1：用户登录 (获取 Token)",
        "method": "POST",
        "url": "/api/v1/auth/login",
        "headers": {
            "Content-Type": "application/json"
        },
        "body": {
            "username": "test_user_01",
            "password": "Password123!"
        },
        "extract": {
            "access_token": "$.data.token",
            "user_uid": "$.data.user.id"
        },
        "assertion": {
            "status_code": 200,
            "json_schema_check": true
        }
    },
    {
        "protocol": "API-IR",
        "version": "1.0",
        "id": "API_STEP_ORDER_02",
        "description": "场景2：创建订单 (依赖 Token 和 UserID)",
        "dependencies": ["API_STEP_AUTH_01"],
        "method": "POST",
        "url": "/api/v1/orders",
        "headers": {
            "Authorization": "Bearer ${access_token}",
            "Content-Type": "application/json"
        },
        "body": {
            "buyer_id": "${user_uid}",
            "items": [
                {
                    "product_id": "PROD_9988",
                    "quantity": 2
                }
            ],
            "address_id": 501
        },
        "extract": {
            "new_order_id": "$.data.order_id"
        },
        "assertion": {
            "status_code": 201,
            "body_contains": "Order created successfully"
        }
    },
    {
        "protocol": "API-IR",
        "version": "1.0",
        "id": "API_STEP_QUERY_03",
        "description": "场景3：查询订单详情 (依赖 OrderID)",
        "dependencies": ["API_STEP_ORDER_02"],
        "method": "GET",
        "url": "/api/v1/orders/${new_order_id}",
        "headers": {
            "Authorization": "Bearer ${access_token}"
        },
        "assertion": {
            "status_code": 200,
            "assert_expression": "response.data.status == 'PENDING'"
        }
    }
]