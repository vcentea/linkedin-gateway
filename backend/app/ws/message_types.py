"""
WebSocket message type definitions.
"""
from enum import Enum
from typing import Dict, Any, Optional, Union, List


class MessageType(str, Enum):
    """Enum of WebSocket message types."""
    # Authentication messages
    AUTH = "auth"
    AUTH_SUCCESS = "auth_success"
    AUTH_ERROR = "auth_error"
    
    # System messages
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    
    # Notification messages
    NOTIFICATION = "notification"
    
    # Status update messages
    STATUS_UPDATE = "status_update"
    
    # LinkedIn activity messages
    LINKEDIN_EVENT = "linkedin_event"
    CONNECTION_UPDATE = "connection_update"
    MESSAGE_UPDATE = "message_update"
    PROFILE_VIEW = "profile_view"
    
    # Action messages
    ACTION_REQUEST = "action_request"
    ACTION_RESPONSE = "action_response"
    
    # Post request messages
    REQUEST_GET_POSTS = "request_get_posts"
    RESPONSE_GET_POSTS = "response_get_posts"

    # Profile data request messages (Added)
    REQUEST_PROFILE_DATA = "request_profile_data"
    RESPONSE_PROFILE_DATA = "response_profile_data"

    # Commenter request messages
    REQUEST_GET_COMMENTERS = "request_get_commenters"
    RESPONSE_GET_COMMENTERS = "response_get_commenters"

    # Profile posts request messages
    REQUEST_GET_PROFILE_POSTS = "request_get_profile_posts"
    RESPONSE_GET_PROFILE_POSTS = "response_get_profile_posts"

    # Generic HTTP proxy messages (for transparent LinkedIn API proxying)
    REQUEST_PROXY_HTTP = "request_proxy_http"
    RESPONSE_PROXY_HTTP = "response_proxy_http"

    # Refresh LinkedIn session (cookies + CSRF)
    REQUEST_REFRESH_LINKEDIN_SESSION = "request_refresh_linkedin_session"
    RESPONSE_REFRESH_LINKEDIN_SESSION = "response_refresh_linkedin_session"


class MessageSchema:
    """Message schema definitions for different message types."""
    
    @staticmethod
    def auth_message(token: str) -> Dict[str, Any]:
        """
        Create an authentication message.
        
        Args:
            token: JWT token for authentication
            
        Returns:
            Dict: Formatted auth message
        """
        return {
            "type": MessageType.AUTH,
            "token": token
        }
    
    @staticmethod
    def auth_success_message(user_id: str) -> Dict[str, Any]:
        """
        Create an authentication success message.
        
        Args:
            user_id: ID of the authenticated user
            
        Returns:
            Dict: Formatted auth success message
        """
        return {
            "type": MessageType.AUTH_SUCCESS,
            "user_id": user_id
        }
    
    @staticmethod
    def error_message(message: str, code: Optional[int] = None) -> Dict[str, Any]:
        """
        Create an error message.
        
        Args:
            message: Error message text
            code: Optional error code
            
        Returns:
            Dict: Formatted error message
        """
        result = {
            "type": MessageType.ERROR,
            "message": message
        }
        
        if code is not None:
            result["code"] = code
            
        return result
    
    @staticmethod
    def ping_message() -> Dict[str, str]:
        """
        Create a ping message for keep-alive.
        
        Returns:
            Dict: Ping message
        """
        return {"type": MessageType.PING}
    
    @staticmethod
    def pong_message() -> Dict[str, str]:
        """
        Create a pong message response.
        
        Returns:
            Dict: Pong message
        """
        return {"type": MessageType.PONG}
    
    @staticmethod
    def notification_message(
        title: str, 
        message: str, 
        level: str = "info", 
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a notification message.
        
        Args:
            title: Notification title
            message: Notification text
            level: Severity level (info, warning, error, success)
            data: Optional additional data
            
        Returns:
            Dict: Formatted notification message
        """
        result = {
            "type": MessageType.NOTIFICATION,
            "title": title,
            "message": message,
            "level": level
        }
        
        if data:
            result["data"] = data
            
        return result
    
    @staticmethod
    def status_update_message(
        status: str, 
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a status update message.
        
        Args:
            status: The new status
            details: Optional status details
            
        Returns:
            Dict: Formatted status update message
        """
        result = {
            "type": MessageType.STATUS_UPDATE,
            "status": status
        }
        
        if details:
            result["details"] = details
            
        return result
    
    @staticmethod
    def linkedin_event_message(
        event_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a LinkedIn event message.
        
        Args:
            event_type: Type of LinkedIn event
            data: Event data
            
        Returns:
            Dict: Formatted LinkedIn event message
        """
        return {
            "type": MessageType.LINKEDIN_EVENT,
            "event_type": event_type,
            "data": data
        }

    @staticmethod
    def request_get_posts_message(
        start_index: int,
        count: int = 10,
        request_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a request to get LinkedIn posts.
        
        Args:
            start_index: Starting index for posts
            count: Number of posts to fetch (default 10)
            request_id: Unique identifier for the request
            
        Returns:
            Dict: Formatted request message
        """
        return {
            "type": MessageType.REQUEST_GET_POSTS,
            "start_index": start_index,
            "count": count,
            "request_id": request_id
        }

    @staticmethod
    def response_get_posts_message(
        request_id: str,
        status: str,
        data: Optional[List[Dict[str, Any]]] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a response for a get posts request.
        
        Args:
            request_id: The ID of the original request
            status: 'success' or 'error'
            data: List of post data (for success)
            error_message: Error description (for error)
            
        Returns:
            Dict: Formatted response message
        """
        response = {
            "type": MessageType.RESPONSE_GET_POSTS,
            "request_id": request_id,
            "status": status
        }
        
        if status == "success" and data is not None:
            response["data"] = data
        elif status == "error" and error_message is not None:
            response["error_message"] = error_message
            
        return response

    # Add schema methods for profile data requests (Added)
    @staticmethod
    def request_profile_data_message(
        profile_id: str,
        request_type: str = "basic_info",
        request_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a request to get LinkedIn profile data.
        
        Args:
            profile_id: LinkedIn profile ID or URL
            request_type: Type of profile data to fetch (basic_info, vanity_name, etc.)
            request_id: Unique identifier for the request
            
        Returns:
            Dict: Formatted profile data request message
        """
        return {
            "type": MessageType.REQUEST_PROFILE_DATA,
            "profile_id": profile_id,
            "request_type": request_type,
            "request_id": request_id
        }

    @staticmethod
    def response_profile_data_message(
        request_id: str,
        status: str,
        data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a response for a profile data request.
        
        Args:
            request_id: The ID of the original request
            status: 'success' or 'error'
            data: Profile data (for success)
            error_message: Error description (for error)
            
        Returns:
            Dict: Formatted profile data response message
        """
        response = {
            "type": MessageType.RESPONSE_PROFILE_DATA,
            "request_id": request_id,
            "status": status
        }
        
        if status == "success" and data is not None:
            response["data"] = data
        elif status == "error" and error_message is not None:
            response["error_message"] = error_message
            
        return response

    @staticmethod
    def request_get_commenters_message(
        post_url: str,
        start: int = 0,
        count: int = 10,
        num_replies: int = 1,
        request_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a request to get commenters for a LinkedIn post.
        
        Args:
            post_url: The full URL of the LinkedIn post.
            start: Starting index for comments pagination (default 0).
            count: Number of comments to fetch per batch (default 10).
            num_replies: Number of replies to fetch per comment (default 1).
            request_id: Unique identifier for the request.
            
        Returns:
            Dict: Formatted request message.
        """
        return {
            "type": MessageType.REQUEST_GET_COMMENTERS,
            "post_url": post_url,
            "start": start,
            "count": count,
            "num_replies": num_replies,
            "request_id": request_id
        }

    @staticmethod
    def response_get_commenters_message(
        request_id: str,
        status: str,
        data: Optional[List[Dict[str, Any]]] = None, # Should match CommenterDetail schema structure
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a response for a get commenters request.
        
        Args:
            request_id: The ID of the original request.
            status: 'success' or 'error'.
            data: List of commenter data (for success).
            error_message: Error description (for error).
            
        Returns:
            Dict: Formatted response message.
        """
        response = {
            "type": MessageType.RESPONSE_GET_COMMENTERS,
            "request_id": request_id,
            "status": status
        }
        
        if status == "success" and data is not None:
            response["data"] = data
        elif status == "error" and error_message is not None:
            response["error_message"] = error_message
            
        return response

    @staticmethod
    def request_get_profile_posts_message(
        profile_id: str,
        count: int = 10,
        request_id: str = None
    ) -> Dict[str, Any]:
        """
        Create a request to get posts from a LinkedIn profile.
        
        Pagination is handled automatically on the client side in chunks of 20.
        
        Args:
            profile_id: The LinkedIn profile ID or URL.
            count: Total number of posts to fetch (will paginate automatically).
            request_id: Unique identifier for the request.
            
        Returns:
            Dict: Formatted request message.
        """
        return {
            "type": MessageType.REQUEST_GET_PROFILE_POSTS,
            "profile_id": profile_id,
            "count": count,
            "request_id": request_id
        }

    @staticmethod
    def response_get_profile_posts_message(
        request_id: str,
        status: str,
        posts: Optional[List[Dict[str, Any]]] = None,
        has_more: Optional[bool] = None,
        pagination_token: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a response for a get profile posts request.
        
        Args:
            request_id: The ID of the original request.
            status: 'success' or 'error'.
            posts: List of post data (for success).
            has_more: Whether more posts are available (for success).
            pagination_token: Token for next page (for success).
            error_message: Error description (for error).
            
        Returns:
            Dict: Formatted response message.
        """
        response = {
            "type": MessageType.RESPONSE_GET_PROFILE_POSTS,
            "request_id": request_id,
            "status": status
        }
        
        if status == "success":
            if posts is not None:
                response["posts"] = posts
            if has_more is not None:
                response["hasMore"] = has_more
            if pagination_token:
                response["paginationToken"] = pagination_token
        elif status == "error" and error_message is not None:
            response["error_message"] = error_message
            
        return response

    @staticmethod
    def request_proxy_http_message(
        request_id: str,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        response_type: str = "json",
        include_credentials: bool = True
    ) -> Dict[str, Any]:
        """
        Create a generic HTTP proxy request message.
        
        This allows the backend to request the extension to execute an HTTP call
        in the browser context with credentials, acting as a transparent proxy.
        
        Args:
            request_id: Unique identifier for the request.
            url: Target URL (absolute or LinkedIn path starting with /).
            method: HTTP method (GET, POST, etc.).
            headers: Request headers to send (extension will filter forbidden headers).
            body: Request body (string, or None for GET).
            response_type: Expected response type ('json', 'text', 'bytes').
            include_credentials: Whether to include cookies (credentials: 'include').
            
        Returns:
            Dict: Formatted proxy HTTP request message.
        """
        message = {
            "type": MessageType.REQUEST_PROXY_HTTP,
            "request_id": request_id,
            "url": url,
            "method": method,
            "response_type": response_type,
            "include_credentials": include_credentials
        }
        
        if headers:
            message["headers"] = headers
        if body is not None:
            message["body"] = body
            
        return message

    @staticmethod
    def request_refresh_linkedin_session_message(
        request_id: str
    ) -> Dict[str, Any]:
        """
        Create a request asking the extension to refresh and return the latest
        LinkedIn cookies and CSRF token (from JSESSIONID).
        """
        return {
            "type": MessageType.REQUEST_REFRESH_LINKEDIN_SESSION,
            "request_id": request_id,
        }

    @staticmethod
    def response_refresh_linkedin_session_message(
        request_id: str,
        status: str,
        csrf_token: Optional[str] = None,
        cookies: Optional[Dict[str, str]] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Response carrying refreshed LinkedIn cookies and CSRF token.
        """
        response: Dict[str, Any] = {
            "type": MessageType.RESPONSE_REFRESH_LINKEDIN_SESSION,
            "request_id": request_id,
            "status": status,
        }
        if status == "success":
            if csrf_token is not None:
                response["csrf_token"] = csrf_token
            if cookies is not None:
                response["cookies"] = cookies
        elif status == "error" and error_message is not None:
            response["error_message"] = error_message
        return response

    @staticmethod
    def response_proxy_http_message(
        request_id: str,
        status: str,
        status_code: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a response for a proxy HTTP request.
        
        Args:
            request_id: The ID of the original request.
            status: 'success' or 'error'.
            status_code: HTTP status code (for success).
            headers: Response headers subset (for success).
            body: Response body as string (for success).
            error_message: Error description (for error).
            
        Returns:
            Dict: Formatted proxy HTTP response message.
        """
        response = {
            "type": MessageType.RESPONSE_PROXY_HTTP,
            "request_id": request_id,
            "status": status
        }
        
        if status == "success":
            if status_code is not None:
                response["status_code"] = status_code
            if headers:
                response["headers"] = headers
            if body is not None:
                response["body"] = body
        elif status == "error" and error_message is not None:
            response["error_message"] = error_message
            
        return response