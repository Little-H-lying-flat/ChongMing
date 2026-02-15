import os
from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader

from app.schemas.api_ir import APIIR
from app.schemas.turbo import TurboRunConfig

class LocustCompiler:
    """
    Locust 脚本编译器
    将 API-IR 转换为 locustfile.py
    """
    
    def __init__(self, template_dir: str = None):
        if not template_dir:
            # Default to 'templates' directory in the same package
            current_dir = os.path.dirname(os.path.abspath(__file__))
            template_dir = os.path.join(current_dir, "templates")
            
        self.env = Environment(loader=FileSystemLoader(template_dir))
        
    def compile(self, config: TurboRunConfig, output_path: str = "locustfile.py") -> str:
        """
        编译 API-IR 为 Locust 脚本
        """
        template = self.env.get_template("locustfile.py.j2")
        
        # Prepare context
        steps_context = []
        for step in config.api_ir_chain:
            steps_context.append({
                "name": step.url,  # Better name extraction needed
                "method": step.method,
                "url": step.url,
                "headers": step.headers,
                "body": step.body,
                "weight": step.weight if hasattr(step, 'weight') else 1
            })
            
        context = {
            "target_host": config.target_host,
            "steps": steps_context,
            # Use dynamic path if available, else default
            "data_file_path": getattr(config, "data_file_path", "data.csv").replace("\\", "/") 
        }
        
        script_content = template.render(context)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script_content)
            
        return output_path
