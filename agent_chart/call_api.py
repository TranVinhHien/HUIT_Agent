import os
import requests
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
load_dotenv()
BASE_URL = os.getenv("URL_API_APP")
ROUTER= {
    "agent_detail": f"{BASE_URL}/agents/detail/",
}
def get_agent_info(agent_name: str) -> Dict[str, Any]:
    """
    Calls the API endpoint to get a list of agent URLs.
    
    Returns:
        List[str]: A list of agent URLs
    
    Raises:
        requests.RequestException: If there's an error with the API request
        ValueError: If the API returns invalid data
    """
    api_url = ROUTER.get("agent_detail")
    try:
        response = requests.get(api_url+agent_name)
        response.raise_for_status()  # Raises an exception for 4XX/5XX responses
        
        data = response.json()
        
        if "url" not in data:
            raise ValueError("API response doesn't contain 'url' key")

        return data
    
    except requests.RequestException as e:
        # Log the error or handle it as needed
        print(f"Error calling agent URL API: {str(e)}")
        raise
    except (json.JSONDecodeError, ValueError) as e:
        # Log the error or handle it as needed
        print(f"Error parsing API response: {str(e)}")
        raise
