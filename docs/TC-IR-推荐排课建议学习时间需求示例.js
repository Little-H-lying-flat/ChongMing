[
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_UI_SCHEDULE_REC_001",
        "name": "推荐排课列表展示验证",
        "description": "验证推荐排课去掉课程封面图片后的新展示形式",
        "mode": "UI",
        "priority": "P0",
        "source_requirement": "2.1 建议学习时间 - 修改展示形式",
        "steps": [
            {
                "step_id": 1,
                "action": "login",
                "target": "学习平台",
                "value": { "user": "student_01", "role": "student" }
            },
            {
                "step_id": 2,
                "action": "navigate",
                "target": "推荐排课页面"
            },
            {
                "step_id": 3,
                "action": "verify",
                "target": "排课列表区域",
                "condition": "not_contains_element",
                "expected_value": "课程封面图片",
                "description": "验证已去掉课程封面图片"
            },
            {
                "step_id": 4,
                "action": "verify",
                "target": "建议完成时间标签",
                "condition": "visible",
                "expected_value": true,
                "description": "验证展示'建议完成时间：X年X月X号前完成'"
            }
        ]
    },
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_API_SCHEDULE_DATE_002",
        "name": "建议学习时间计算逻辑验证",
        "description": "验证系统正确计算排课生成日期 + 15天的建议完成时间",
        "mode": "API",
        "priority": "P0",
        "source_requirement": "2.1 建议学习时间 - 计算15天之后的日期",
        "steps": [
            {
                "step_id": 1,
                "action": "call_api",
                "target": "获取推荐排课接口",
                "description": "获取系统自动推荐的排课列表",
                "output_var": "schedule_list"
            },
            {
                "step_id": 2,
                "action": "verify",
                "target": "响应体.data[0].suggested_deadline",
                "condition": "equals",
                "expected_value": "${today + 15 days}",
                "description": "验证建议完成时间 = 排课生成日期 + 15天"
            },
            {
                "step_id": 3,
                "action": "verify",
                "target": "响应体.data[0].suggested_deadline",
                "condition": "format_match",
                "expected_value": "^\\d{4}年\\d{1,2}月\\d{1,2}号前完成$",
                "description": "验证日期格式符合'X年X月X号前完成'"
            }
        ]
    },
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_API_SCHEDULE_SORT_003",
        "name": "推荐排课排序规则验证",
        "description": "验证推荐排课按'排课结束正序'排列",
        "mode": "API",
        "priority": "P1",
        "source_requirement": "2.1 建议学习时间 - 排序规则",
        "steps": [
            {
                "step_id": 1,
                "action": "call_api",
                "target": "获取推荐排课接口",
                "output_var": "schedule_list"
            },
            {
                "step_id": 2,
                "action": "verify",
                "target": "响应体.data",
                "condition": "sorted_by",
                "expected_value": { "field": "end_time", "order": "asc" },
                "description": "验证列表按排课结束时间正序排列"
            }
        ]
    },
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_UI_SCHEDULE_E2E_004",
        "name": "推荐排课端到端流程验证",
        "description": "完整验证从推荐生成到前端展示的全流程",
        "mode": "HYBRID",
        "priority": "P0",
        "source_requirement": "2.1 建议学习时间 - 全流程",
        "steps": [
            {
                "step_id": 1,
                "action": "call_api",
                "target": "触发排课推荐生成接口",
                "description": "模拟系统自动生成推荐排课",
                "input_data": { "user_id": "student_01" },
                "output_var": "new_schedule_id"
            },
            {
                "step_id": 2,
                "action": "login",
                "target": "学习平台",
                "value": { "user": "student_01", "role": "student" }
            },
            {
                "step_id": 3,
                "action": "navigate",
                "target": "推荐排课页面"
            },
            {
                "step_id": 4,
                "action": "verify",
                "target": "推荐排课卡片",
                "condition": "contains",
                "expected_value": "${new_schedule_id}",
                "description": "验证新生成的推荐排课已展示"
            },
            {
                "step_id": 5,
                "action": "verify",
                "target": "建议完成时间",
                "condition": "equals_text",
                "expected_value": "${today + 15 days formatted}",
                "description": "验证建议完成时间正确展示"
            },
            {
                "step_id": 6,
                "action": "verify",
                "target": "排课卡片布局",
                "condition": "not_contains_element",
                "expected_value": "img.course-cover",
                "description": "验证无课程封面图片"
            }
        ]
    },
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_EDGE_SCHEDULE_BOUNDARY_005",
        "name": "建议学习时间边界条件验证",
        "description": "验证跨月、跨年时日期计算的正确性",
        "mode": "API",
        "priority": "P1",
        "source_requirement": "2.1 建议学习时间 - 边界条件",
        "coverage_tag": "边界条件",
        "steps": [
            {
                "step_id": 1,
                "action": "mock_system_time",
                "target": "系统时间",
                "value": "2026-01-20T10:00:00Z",
                "description": "设置系统时间为1月20日，+15天后应为2月4日（跨月）"
            },
            {
                "step_id": 2,
                "action": "call_api",
                "target": "生成推荐排课接口"
            },
            {
                "step_id": 3,
                "action": "verify",
                "target": "响应体.suggested_deadline",
                "condition": "equals",
                "expected_value": "2026年2月4号前完成",
                "description": "验证跨月计算正确"
            }
        ]
    },
    {
        "protocol": "TC-IR",
        "version": "1.0",
        "id": "TC_EDGE_SCHEDULE_YEAR_006",
        "name": "建议学习时间跨年边界验证",
        "description": "验证年末时+15天跨年计算的正确性",
        "mode": "API",
        "priority": "P2",
        "source_requirement": "2.1 建议学习时间 - 边界条件（跨年）",
        "coverage_tag": "边界条件",
        "steps": [
            {
                "step_id": 1,
                "action": "mock_system_time",
                "target": "系统时间",
                "value": "2026-12-25T10:00:00Z",
                "description": "设置系统时间为12月25日，+15天后应为2027年1月9日"
            },
            {
                "step_id": 2,
                "action": "call_api",
                "target": "生成推荐排课接口"
            },
            {
                "step_id": 3,
                "action": "verify",
                "target": "响应体.suggested_deadline",
                "condition": "equals",
                "expected_value": "2027年1月9号前完成",
                "description": "验证跨年计算正确"
            }
        ]
    }
]
