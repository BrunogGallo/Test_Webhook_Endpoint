import os
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()


class TwoBoxesClient:
    """
    Client for interacting with the TwoBoxes API.
    Handles authentication and provides methods for all TwoBoxes API operations.
    
    This client is designed to work with the webhook-based workflow where:
    1. TwoBoxes sends webhooks when returns are completed
    2. The webhook payload contains return data
    3. This client can parse webhook data and fetch additional details from the API
    4. The extracted data is then matched with Mintsoft orders
    
    Usage:
        # Initialize client
        client = TwoBoxesClient()
        
        # Parse webhook payload
        webhook_data = [...]  # Received from TwoBoxes webhook
        if client.is_return_complete_event(webhook_data):
            merchant_name = client.extract_merchant_name(webhook_data)
            order_number = client.extract_storefront_order_number(webhook_data)
            return_id = client.extract_return_id(webhook_data)
            
            # Fetch full return details if needed
            return_details = client.get_return(return_id)
    """
    BASE_URL = "https://api.twoboxes.io/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the TwoBoxes API client.
        
        Args:
            api_key: Optional API key. If not provided, will try to load from TWOBOXES_API_KEY env variable.
        
        Raises:
            RuntimeError: If API key is not provided or found in environment variables.
        """
        self.api_key = api_key or os.getenv("TWOBOXES_API_KEY")
        
        if not self.api_key:
            raise RuntimeError(
                "Missing TwoBoxes API key. "
                "Please provide api_key parameter or set TWOBOXES_API_KEY environment variable."
            )

    def headers(self) -> Dict[str, str]:
        """
        Get the headers required for API requests.
        
        Returns:
            Dictionary containing Authorization and Content-Type headers.
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Make a request to the TwoBoxes API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint (e.g., '/returns')
            params: Optional query parameters
            json_data: Optional JSON payload for POST/PUT requests
            timeout: Request timeout in seconds
        
        Returns:
            JSON response from the API
        
        Raises:
            requests.HTTPError: If the API request fails
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        response = requests.request(
            method=method,
            url=url,
            headers=self.headers(),
            params=params,
            json=json_data,
            timeout=timeout
        )
        
        response.raise_for_status()
        return response.json()

    # Returns endpoints
    def get_returns(
        self,
        merchant_id: Optional[str] = None,
        site_id: Optional[str] = None,
        status: Optional[str] = None,
        return_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of returns.
        
        Args:
            merchant_id: Filter by merchant ID
            site_id: Filter by site ID
            status: Filter by status (e.g., 'complete', 'pending')
            return_type: Filter by return type (e.g., 'rma', 'rts')
            limit: Maximum number of results to return
            offset: Number of results to skip
        
        Returns:
            List of return dictionaries
        """
        params = {}
        if merchant_id:
            params["merchant_id"] = merchant_id
        if site_id:
            params["site_id"] = site_id
        if status:
            params["status"] = status
        if return_type:
            params["return_type"] = return_type
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        
        return self._make_request("GET", "/returns", params=params)

    def get_completed_returns(
        self,
        merchant_id: Optional[str] = None,
        site_id: Optional[str] = None,
        return_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of completed returns.
        Convenience method that filters for returns with grading_status='complete'.
        
        Args:
            merchant_id: Filter by merchant ID
            site_id: Filter by site ID
            return_type: Filter by return type (e.g., 'rma', 'rts')
            limit: Maximum number of results to return
            offset: Number of results to skip
        
        Returns:
            List of completed return dictionaries
        """
        returns = self.get_returns(
            merchant_id=merchant_id,
            site_id=site_id,
            return_type=return_type,
            limit=limit,
            offset=offset
        )
        
        # Filter for completed returns
        if isinstance(returns, list):
            return [r for r in returns if r.get("grading_status") == "complete"]
        
        return returns

    def get_return(self, return_id: str) -> Dict[str, Any]:
        """
        Get a specific return by ID.
        
        Args:
            return_id: The return ID
        
        Returns:
            Return dictionary
        """
        return self._make_request("GET", f"/returns/{return_id}")

    def create_return(self, return_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new return.
        
        Args:
            return_data: Dictionary containing return data
        
        Returns:
            Created return dictionary
        """
        return self._make_request("POST", "/returns", json_data=return_data)

    def update_return(self, return_id: str, return_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing return.
        
        Args:
            return_id: The return ID
            return_data: Dictionary containing updated return data
        
        Returns:
            Updated return dictionary
        """
        return self._make_request("PUT", f"/returns/{return_id}", json_data=return_data)

    # Return Line Items endpoints
    def get_return_line_items(
        self,
        return_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of return line items.
        
        Args:
            return_id: Filter by return ID
            limit: Maximum number of results to return
            offset: Number of results to skip
        
        Returns:
            List of return line item dictionaries
        """
        params = {}
        if return_id:
            params["return_id"] = return_id
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        
        return self._make_request("GET", "/return-line-items", params=params)

    def get_return_line_item(self, line_item_id: str) -> Dict[str, Any]:
        """
        Get a specific return line item by ID.
        
        Args:
            line_item_id: The return line item ID
        
        Returns:
            Return line item dictionary
        """
        return self._make_request("GET", f"/return-line-items/{line_item_id}")

    def update_return_line_item(
        self,
        line_item_id: str,
        line_item_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing return line item.
        
        Args:
            line_item_id: The return line item ID
            line_item_data: Dictionary containing updated line item data
        
        Returns:
            Updated return line item dictionary
        """
        return self._make_request(
            "PUT",
            f"/return-line-items/{line_item_id}",
            json_data=line_item_data
        )

    # Merchants endpoints
    def get_merchants(self) -> List[Dict[str, Any]]:
        """
        Get a list of merchants.
        
        Returns:
            List of merchant dictionaries
        """
        return self._make_request("GET", "/merchants")

    def get_merchant(self, merchant_id: str) -> Dict[str, Any]:
        """
        Get a specific merchant by ID.
        
        Args:
            merchant_id: The merchant ID
        
        Returns:
            Merchant dictionary
        """
        return self._make_request("GET", f"/merchants/{merchant_id}")

    # Sites endpoints
    def get_sites(self, merchant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get a list of sites.
        
        Args:
            merchant_id: Filter by merchant ID
        
        Returns:
            List of site dictionaries
        """
        params = {}
        if merchant_id:
            params["merchant_id"] = merchant_id
        
        return self._make_request("GET", "/sites", params=params)

    def get_site(self, site_id: str) -> Dict[str, Any]:
        """
        Get a specific site by ID.
        
        Args:
            site_id: The site ID
        
        Returns:
            Site dictionary
        """
        return self._make_request("GET", f"/sites/{site_id}")

    # Product Variants endpoints
    def get_product_variants(
        self,
        merchant_id: Optional[str] = None,
        site_id: Optional[str] = None,
        sku: Optional[str] = None,
        barcode: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get a list of product variants.
        
        Args:
            merchant_id: Filter by merchant ID
            site_id: Filter by site ID
            sku: Filter by SKU
            barcode: Filter by barcode
            limit: Maximum number of results to return
            offset: Number of results to skip
        
        Returns:
            List of product variant dictionaries
        """
        params = {}
        if merchant_id:
            params["merchant_id"] = merchant_id
        if site_id:
            params["site_id"] = site_id
        if sku:
            params["sku"] = sku
        if barcode:
            params["barcode"] = barcode
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        
        return self._make_request("GET", "/product-variants", params=params)

    def get_product_variant(self, variant_id: str) -> Dict[str, Any]:
        """
        Get a specific product variant by ID.
        
        Args:
            variant_id: The product variant ID
        
        Returns:
            Product variant dictionary
        """
        return self._make_request("GET", f"/product-variants/{variant_id}")

    # Webhooks endpoints (if applicable)
    def get_webhooks(self) -> List[Dict[str, Any]]:
        """
        Get a list of webhooks.
        
        Returns:
            List of webhook dictionaries
        """
        return self._make_request("GET", "/webhooks")

    def create_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new webhook.
        
        Args:
            webhook_data: Dictionary containing webhook configuration
        
        Returns:
            Created webhook dictionary
        """
        return self._make_request("POST", "/webhooks", json_data=webhook_data)

    def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """
        Delete a webhook.
        
        Args:
            webhook_id: The webhook ID
        
        Returns:
            Deletion confirmation
        """
        return self._make_request("DELETE", f"/webhooks/{webhook_id}")

    # Webhook processing utilities
    @staticmethod
    def parse_webhook_payload(webhook_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Parse and validate a webhook payload from TwoBoxes.
        
        Args:
            webhook_data: The webhook payload (list format from TwoBoxes)
        
        Returns:
            Dictionary containing event_type and event_data, or None if invalid
        """
        if not webhook_data or not isinstance(webhook_data, list) or len(webhook_data) == 0:
            return None
        
        event = webhook_data[0]
        if "event_type" not in event or "event_data" not in event:
            return None
        
        return {
            "event_id": event.get("id"),
            "event_type": event.get("event_type"),
            "event_data": event.get("event_data")
        }

    @staticmethod
    def extract_return_id(webhook_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the return ID from webhook data.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            Return ID string or None if not found
        """
        parsed = TwoBoxesClient.parse_webhook_payload(webhook_data)
        if parsed and parsed.get("event_data"):
            return parsed["event_data"].get("id")
        return None

    @staticmethod
    def extract_merchant_name(webhook_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the merchant name from webhook data.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            Merchant name string or None if not found
        """
        parsed = TwoBoxesClient.parse_webhook_payload(webhook_data)
        if parsed and parsed.get("event_data"):
            merchant_integration = parsed["event_data"].get("merchant_integration", {})
            merchant = merchant_integration.get("merchant", {})
            return merchant.get("name")
        return None

    @staticmethod
    def extract_merchant_id(webhook_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the merchant ID from webhook data.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            Merchant ID string or None if not found
        """
        parsed = TwoBoxesClient.parse_webhook_payload(webhook_data)
        if parsed and parsed.get("event_data"):
            merchant_integration = parsed["event_data"].get("merchant_integration", {})
            merchant = merchant_integration.get("merchant", {})
            return merchant.get("id")
        return None

    @staticmethod
    def extract_storefront_order_number(webhook_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the storefront order number from webhook data.
        Looks in the first line item's storefront_order_number field.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            Storefront order number string or None if not found
        """
        parsed = TwoBoxesClient.parse_webhook_payload(webhook_data)
        if parsed and parsed.get("event_data"):
            line_items = parsed["event_data"].get("line_items", [])
            if line_items and len(line_items) > 0:
                return line_items[0].get("storefront_order_number")
        return None

    @staticmethod
    def extract_rma_number(webhook_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the RMA number from webhook data.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            RMA number string or None if not found
        """
        parsed = TwoBoxesClient.parse_webhook_payload(webhook_data)
        if parsed and parsed.get("event_data"):
            return parsed["event_data"].get("rma")
        return None

    @staticmethod
    def extract_tracking_number(webhook_data: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract the tracking number from webhook data.
        Returns the tracking number from the first line item.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            Tracking number string or None if not found
        """
        parsed = TwoBoxesClient.parse_webhook_payload(webhook_data)
        if parsed and parsed.get("event_data"):
            line_items = parsed["event_data"].get("line_items", [])
            if line_items and len(line_items) > 0:
                return line_items[0].get("tracking_number")
        return None

    @staticmethod
    def is_return_complete_event(webhook_data: List[Dict[str, Any]]) -> bool:
        """
        Check if the webhook is a return-complete event.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            True if event_type is 'return-complete', False otherwise
        """
        parsed = TwoBoxesClient.parse_webhook_payload(webhook_data)
        return parsed is not None and parsed.get("event_type") == "return-complete"

    def fetch_return_from_webhook(self, webhook_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Fetch the full return data from TwoBoxes API using the return ID from webhook.
        Useful for getting the latest data or if webhook payload is incomplete.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            Full return dictionary from API, or None if return ID not found
        """
        return_id = self.extract_return_id(webhook_data)
        if not return_id:
            return None
        
        try:
            return self.get_return(return_id)
        except Exception:
            return None

    def get_return_line_items_from_webhook(
        self,
        webhook_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract line items from webhook data, or fetch from API if needed.
        
        Args:
            webhook_data: The webhook payload
        
        Returns:
            List of line item dictionaries
        """
        parsed = TwoBoxesClient.parse_webhook_payload(webhook_data)
        if parsed and parsed.get("event_data"):
            line_items = parsed["event_data"].get("line_items", [])
            if line_items:
                return line_items
        
        # Fallback: try to fetch from API
        return_id = self.extract_return_id(webhook_data)
        if return_id:
            try:
                return_data = self.get_return(return_id)
                return return_data.get("line_items", [])
            except Exception:
                pass
        
        return []
