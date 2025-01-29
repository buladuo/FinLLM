import requests
import yaml
import logging
import os

from paths import CONFIG_PATH

class DBClient:
    def __init__(self, path=CONFIG_PATH):
        self.config = self.load_config(path)
        self.api_url = self.config['database']['api_url']
        self.api_key = self.config['database']['api_key']
        self.timeout = self.config['database']['timeout']

        self.logger = logging.getLogger(self.__class__.__name__)

    def load_config(self, path):
        with open(path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    def query(self, sql_str,limit = 999):
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data={
            "sql": sql_str,
            "limit":limit
        }
        
        try:
            self.logger.info(f"Sending query to database: {data}")
            response = requests.post(self.api_url, headers=headers, json=data, timeout=self.timeout)
            response.raise_for_status()  # Raises an error for 4XX/5XX responses
            self.logger.info("Query successful.")
            self.logger.info(f'{response.json()}')
            return response.json()  # Assuming the API returns JSON data
        
        except requests.exceptions.Timeout:
            self.logger.error("Request timed out")
            return None
        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"HTTP error occurred: {http_err}")
            return None
        except requests.exceptions.RequestException as err:
            self.logger.error(f"An error occurred: {err}")
            return None

# Example usage
if __name__ == "__main__":
    client = DBClient(path="../config.yaml")
    sql = "SELECT * FROM constantdb.secumain LIMIT 10"
    result = client.query(sql)
    print(result)
