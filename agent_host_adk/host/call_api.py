import os
import requests
import json
from typing import List, Dict, Any, Optional
BASE_URL = os.getenv("URL_API_APP")
ROUTER= {
    "get_agent_urls": f"{BASE_URL}/agents/list",
    "get_available_agents": f"{BASE_URL}/agent_roles/enable_agent"
}

def get_agent_urls() -> List[str]:
    """
    Calls the API endpoint to get a list of agent URLs.
    
    Returns:
        List[str]: A list of agent URLs
    
    Raises:
        requests.RequestException: If there's an error with the API request
        ValueError: If the API returns invalid data
    """
    api_url = ROUTER.get("get_agent_urls")
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raises an exception for 4XX/5XX responses
        
        data = response.json()
        
        if "agent_urls" not in data:
            raise ValueError("API response doesn't contain 'agent_urls' key")
        
        return data["agent_urls"]
    
    except requests.RequestException as e:
        # Log the error or handle it as needed
        print(f"Error calling agent URL API: {str(e)}")
        raise
    except (json.JSONDecodeError, ValueError) as e:
        # Log the error or handle it as needed
        print(f"Error parsing API response: {str(e)}")
        raise


def get_available_agents(token: str) -> List[str]:
    """
    Calls the API endpoint to get a list of available agents the user can use.
    
    Args:
        token (str): Authentication token to include in the request header
        
    Returns:
        List[str]: A list of available agent names
    
    Raises:
        requests.RequestException: If there's an error with the API request
        ValueError: If the API returns invalid data
    """
    api_url = ROUTER.get("get_available_agents")

    # Set up the request headers with the token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # Raises an exception for 4XX/5XX responses
        
        data = response.json()
        
        if "state" not in data:
            raise ValueError("API response doesn't contain 'agent_use' key")
        
        return data["state"]["agent_use"]
    
    except requests.RequestException as e:
        # Log the error or handle it as needed
        print(f"Error calling available agents API: {str(e)}")
        raise
    except (json.JSONDecodeError, ValueError) as e:
        # Log the error or handle it as needed
        print(f"Error parsing API response: {str(e)}")
        raise


# Example usage:
if __name__ == "__main__":
    try:
        # Get list of agent URLs
        agent_urls = get_agent_urls()
        print("Available agent URLs:", agent_urls)
        
        # Get list of available agents (requires a valid token)
        token = "your_auth_token_here"
        available_agents = get_available_agents(token)
        print("Available agents:", available_agents)
    
    except Exception as e:
        print(f"Error occurred: {str(e)}")
