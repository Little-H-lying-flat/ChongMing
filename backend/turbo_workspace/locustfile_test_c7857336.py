from locust import HttpUser, task, between, events
import csv
import random
import os
import json
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TurboLocust")

class TurboUser(HttpUser):
    wait_time = between(1, 3)
    
    host = "https://www.baidu.com"
    
    
    def on_start(self):
        """Initialization: Load data and login if needed"""
        self.data = []
        self.data_index = 0
        self.token = None
        
        # 1. Load Data
        data_path = "data.csv"
        if os.path.exists(data_path):
            with open(data_path, 'r', encoding='utf-8') as f:
                self.data = list(csv.DictReader(f))
            logger.info(f"Loaded {len(self.data)} rows of test data")
        
        # 2. Login / Auth (TODO: Implement Authentication Chain)
        # For now, we assume token is provided or handled in tasks
        
    def get_next_data(self):
        """Get next data row (Round Robin)"""
        if not self.data:
            return {}
        row = self.data[self.data_index % len(self.data)]
        self.data_index += 1
        return row

    
    @task(1)
    def task_1(self):
        """Task for GET https://www.baidu.com/"""
        # 1. Get Data
        data = self.get_next_data()
        
        # 2. Prepare Variables
        # Simple variable substitution for now {var} -> data[var]
        url = "https://www.baidu.com/"
        for key, val in data.items():
            # Avoid Jinja2/f-string conflict with braces
            placeholder = "${" + key + "}"
            url = url.replace(placeholder, str(val))
            
        # 3. Headers
        headers = {"Accept": "application/json"}
        # Inject Auth Token if available
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # 4. Body
        
        body = None
        

        # 5. Execute
        with self.client.request(
            method="GET",
            url=url,
            headers=headers,
            json=body if headers.get("Content-Type") == "application/json" else None,
            data=body if headers.get("Content-Type") != "application/json" else None,
            name="https://www.baidu.com/",
            catch_response=True
        ) as response:
            if response.status_code >= 400:
                response.failure(f"Status {response.status_code}")
            else:
                response.success()
    