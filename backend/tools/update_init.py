import os
import re

filepath = r'd:\project\ChongMing\backend\app\engines\right_pupil\__init__.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if skip:
        if 'Please propose the next action."""' in line:
            skip = False
        continue

    # inject element describer logic
    if 'som_text = "\\n".join(som_text_lines)' in line:
        new_lines.append(line)
        new_lines.append('''
            # --- Right Pupil 3.0: Hybrid Perception & Semantic Description ---
            points = []
            for k, v in id_map.items():
                bbox = v.get('bbox', [0, 0, 0, 0])
                cx = (bbox[0] + bbox[2]) / 2.0
                cy = (bbox[1] + bbox[3]) / 2.0
                points.append({"x": cx, "y": cy})
            
            dom_hints = []
            if points:
                try:
                    dom_hints = await self.dom_service.get_dom_hints_from_points(self.page, points)
                except Exception as e:
                    logger.warning(f"Failed to fetch DOM hints: {e}")
                    dom_hints = [None] * len(points)
            
            describer_input = []
            for j, (k, v) in enumerate(id_map.items()):
                item = {
                    "id": int(k),
                    "bbox": [int(x) for x in v.get("bbox", [0, 0, 0, 0])],
                    "ocr": v.get("content", "")
                }
                if j < len(dom_hints) and dom_hints[j]:
                    item["dom_hint"] = dom_hints[j]
                describer_input.append(item)
                
            semantic_elements_str = "[]"
            autogen_status = get_autogen_runtime_status()
            if autogen_status.available:
                 try:
                     import autogen, json, re
                     from app.engines.right_pupil.agents.element_describer import ElementDescriberAgent
                     from app.services.smart_ops.ai_config_service import AIConfigService
                     from app.core.ai_models import AIModule
                     from app.core.config import settings
                     
                     desc_cfg = await AIConfigService.get_model_config(AIModule.AGENT_RIGHT_VISUAL)
                     desc_llm_config = {
                          "config_list": [{
                              "model": desc_cfg.model_id,
                              "api_key": settings.QWEN_API_KEY,
                              "base_url": settings.QWEN_BASE_URL
                          }],
                          "temperature": 0.1,
                          "max_tokens": desc_cfg.max_tokens,
                     }
                     
                     describer = ElementDescriberAgent("ElementDescriber", desc_llm_config)
                     admin = autogen.UserProxyAgent("Admin", human_input_mode="NEVER", code_execution_config=False, max_consecutive_auto_reply=1)
                     
                     desc_prompt = f"Please translate the following elements into semantic descriptions:\\n{json.dumps(describer_input, ensure_ascii=False)}"
                     await self._initiate_chat_async(admin, describer, desc_prompt)
                     
                     last_msg = self._extract_message_text(describer.last_message())
                     json_match = re.search(r'```(?:json)?\\n(.*)\\n```', last_msg, re.DOTALL)
                     if json_match:
                         semantic_elements_str = json_match.group(1).strip()
                     else:
                         match = re.search(r'(\\[.*\\])', last_msg, re.DOTALL)
                         semantic_elements_str = match.group(1).strip() if match else last_msg
                         
                     logger.info(f"Element Describer output computed successfully: {len(semantic_elements_str)} chars")
                 except Exception as e:
                     logger.error(f"Element Describer Agent failed: {e}. Falling back to RAW JSON.")
                     semantic_elements_str = json.dumps(describer_input, ensure_ascii=False)
            else:
                 semantic_elements_str = json.dumps(describer_input, ensure_ascii=False)
''')
        continue

    # add semantic_elements to state updates
    if '"som_text": som_text' in line:
        new_lines.append(line.replace('"som_text": som_text', '"som_text": som_text,\n                "semantic_elements": semantic_elements_str'))
        continue

    # replace Reason prompt
    if 'prompt = f"""Task: {task_desc}' in line:
        skip = True
        new_lines.append('''            prompt = f"""Task: {task_desc}
            
Recent History: {json.dumps(state.get('history')[-3:] if state.get('history') else [])}

Semantic_Elements (translated from OmniParser & DOM):
{state.get('semantic_elements', '[]')}

Please propose the next action."""
''')
        continue

    new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updated __init__.py")
