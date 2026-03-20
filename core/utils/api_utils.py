"""
API utilities for the Morphic 3D Scanner system.
"""

import json
import requests
from typing import Dict, Any, Optional, Union
from requests.exceptions import RequestException


class APIError(Exception):
    """Custom exception for API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


def make_api_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Union[Dict, str]] = None,
    files: Optional[Dict] = None,
    timeout: int = 30,
    verify_ssl: bool = True
) -> Dict[str, Any]:
    """
    Make an HTTP API request with error handling.
    
    Args:
        url: API endpoint URL
        method: HTTP method (GET, POST, PUT, DELETE)
        headers: Request headers
        data: Request data (dict for JSON, string for raw)
        files: Files to upload
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates
        
    Returns:
        Parsed JSON response
        
    Raises:
        APIError: If the request fails
    """
    try:
        # Prepare request arguments
        kwargs = {
            'timeout': timeout,
            'verify': verify_ssl
        }
        
        if headers:
            kwargs['headers'] = headers
        
        if method.upper() in ['POST', 'PUT', 'PATCH']:
            if files:
                kwargs['files'] = files
                if data:
                    kwargs['data'] = data
            else:
                kwargs['json'] = data if isinstance(data, dict) else {}
        
        # Make request
        response = requests.request(method.upper(), url, **kwargs)
        
        # Handle response
        if response.status_code >= 400:
            try:
                error_data = response.json()
            except json.JSONDecodeError:
                error_data = {'message': response.text}
            
            raise APIError(
                f"API request failed: {response.status_code}",
                status_code=response.status_code,
                response=error_data
            )
        
        # Parse successful response
        try:
            return response.json()
        except json.JSONDecodeError:
            return {'message': response.text}
            
    except RequestException as e:
        raise APIError(f"Network error: {str(e)}")


def handle_api_error(error: APIError) -> Dict[str, Any]:
    """
    Handle API errors and return user-friendly response.
    
    Args:
        error: APIError exception
        
    Returns:
        Error response dictionary
    """
    response = {
        'error': True,
        'message': str(error),
        'status_code': error.status_code
    }
    
    if error.response:
        response['details'] = error.response
    
    return response


def is_success_response(response: Dict[str, Any]) -> bool:
    """
    Check if API response indicates success.
    
    Args:
        response: API response dictionary
        
    Returns:
        True if successful, False otherwise
    """
    return not response.get('error', False) and response.get('status_code', 200) < 400
