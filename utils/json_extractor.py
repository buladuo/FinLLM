from ast import List
import re
import json
import logging


class JsonExtractor:
    def __init__(self):
        # 正则表达式匹配以 ```json``` 开头和结尾的 JSON 字符串
        self.json_pattern = r'```json\s*(.*?)\s*```'
        # 正则表达式匹配所有的 [xxx] 字符串
        self.fallback_pattern = r'\[.*?\]'
        self.logger = logging.getLogger(self.__class__.__name__)

    def extract_json(self, text: str, model_name: str = None)->list:
        """Extract JSON data from the input text."""
        if not text or not isinstance(text, str):
            self.logger.error("Invalid input: The input text must be a non-empty string.")
            return None

        self.logger.debug(f"Starting to extract JSON data from input text.")

        # Replace newlines with spaces to simplify regex matching
        sanitized_text = text.replace('\n', ' ')

        # Try matching ```json [{xxx}] ``` format
        match = re.search(self.json_pattern, sanitized_text, re.DOTALL)
        if match:
            json_str = match.group(1)
            self.logger.debug(f"Found formatted JSON block, content: \n{json_str}")
            try:
                json_data = json.loads(json_str)
                self.logger.debug(f"Successfully parsed JSON data.:\n{json_data}")
                return list(json_data)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON data: {e}")
                return None

        # Try matching all [xxx] strings as a fallback
        fallback_matches = re.findall(self.fallback_pattern, sanitized_text)
        if fallback_matches:
            self.logger.debug(f"Found fallback JSON data blocks, content: {fallback_matches}")
            for fallback_json_str in fallback_matches:
                # Validate the fallback string isn't empty
                if not fallback_json_str.strip():
                    self.logger.warning("Empty fallback JSON string encountered; skipping.")
                    continue

                try:
                    json_data = json.loads(fallback_json_str)
                    self.logger.debug("Successfully parsed fallback JSON data.")
                    return list(json_data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse fallback JSON data: {fallback_json_str}, error: {e}")
                    continue

        # If no matching JSON is found
        self.logger.warning("No matching JSON data found.")
        return None


# Example of how to use the logger for debugging.
if __name__ == "__main__":
    extractor = JsonExtractor()
    sample_text = """Here is some text with a JSON block:
    ```json
    {"key": "value"}
    ```
    And also some other data like [1, 2, 3]."""
    
    json_output = extractor.extract_json(sample_text)
    print(json_output)
    
