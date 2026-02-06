[
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_UI_SEARCH_01",
        "name": "前台商品搜索测试",
        "description": "用户在首页搜索特定商品并验证结果",
        "mode": "UI",
        "priority": "P0",
        "steps": [
            {
                "step_id": 1,
                "action": "open",
                "target": "首页",
                "value": "https://shop.example.com"
            },
            {
                "step_id": 2,
                "action": "input",
                "target": "顶部搜索框",
                "value": "机械键盘"
            },
            {
                "step_id": 3,
                "action": "click",
                "target": "搜索放大镜图标"
            },
            {
                "step_id": 4,
                "action": "verify",
                "target": "商品列表第一项",
                "condition": "contains_text",
                "expected_value": "机械键盘"
            }
        ]
    },
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_API_USER_CREATE_02",
        "name": "后台用户创建接口测试",
        "description": "通过 API 创建新用户并验证数据落库",
        "mode": "API",
        "priority": "P1",
        "steps": [
            {
                "step_id": 1,
                "action": "call_api",
                "target": "创建用户接口",
                "description": "注册名为 'test_user' 的新用户",
                "input_data": {
                    "username": "test_user",
                    "role": "guest"
                }
            },
            {
                "step_id": 2,
                "action": "verify",
                "target": "响应状态码",
                "condition": "equals",
                "expected_value": 201
            },
            {
                "step_id": 3,
                "action": "verify",
                "target": "响应体.user_id",
                "condition": "not_null"
            }
        ]
    },
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_E2E_ORDER_AUDIT_03",
        "name": "订单审核端到端流程",
        "description": "API 造数据 -> UI 审核 (重明混合模式)",
        "mode": "HYBRID",
        "priority": "P0",
        "steps": [
            {
                "step_id": 1,
                "action": "call_api",
                "target": "提交订单接口",
                "description": "前置准备：构造一个待审核状态的订单",
                "output_var": "new_order_id"
            },
            {
                "step_id": 2,
                "action": "login",
                "target": "后台管理系统",
                "value": {
                    "user": "admin",
                    "role": "auditor"
                }
            },
            {
                "step_id": 3,
                "action": "input",
                "target": "订单号搜索框",
                "value": "${new_order_id}",
                "description": "使用第一步生成的订单号进行搜索"
            },
            {
                "step_id": 4,
                "action": "click",
                "target": "审核通过按钮"
            },
            {
                "step_id": 5,
                "action": "verify",
                "target": "订单状态标签",
                "condition": "equals_text",
                "expected_value": "已审核"
            }
        ]
    }
]