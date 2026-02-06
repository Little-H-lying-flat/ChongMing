{
  "protocol": "AUI-IR",
    "version": "1.0",
      "step_id": "TC_LOGIN_STEP_01",
        "description": "登录操作：尝试 OmniParser 视觉点击，失败则降级为 DOM 属性定位",
          "action": "click",
            "execution_plan": {
    "primary": {
      "strategy": "visual",
        "selector": "som_id:5",
          "confidence_threshold": 0.85,
            "metadata": {
        "visual_label": "登录按钮",
          "description": "OmniParser 识别到的第5号红色标记框"
      }
    },
    "fallback": {
      "strategy": "dom",
        "selector": "button[name='login']",
          "trigger_condition": "visual_element_missing_or_low_confidence",
            "metadata": {
        "method": "playwright_locator",
          "reasoning": "视觉层失效时的结构化兜底方案"
      }
    }
  },
  "verification": {
    "expect_visual_change": true
  }
}