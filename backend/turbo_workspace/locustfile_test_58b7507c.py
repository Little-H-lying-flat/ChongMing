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
    host = "http://localhost:8000"
    
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

    