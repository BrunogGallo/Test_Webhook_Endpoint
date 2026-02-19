import os
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import json
load_dotenv()



class MintsoftOrderClient:
    BASE_URL = "https://api.mintsoft.co.uk"

    def __init__(self):
        self.username = os.getenv("MINTSOFT_USERNAME")
        self.password = os.getenv("MINTSOFT_PASSWORD")
        self.client_id = 3
        self.warehouse_id = 3

        if not all([self.username, self.password, self.client_id]):
            raise RuntimeError(
                "Missing Mintsoft credentials "
                "(MINTSOFT_USERNAME / MINTSOFT_PASSWORD / MINTSOFT_CLIENT_ID)"
            )

        self.api_key = self._authenticate()

    def _authenticate(self) -> str:
        url = f"{self.BASE_URL}/api/Auth"

        payload = {
            "Username": self.username,
            "Password": self.password,
        }

        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        print(r.json())
        return r.json()

    def headers(self) -> Dict[str, str]:
        return {
            "ms-apikey": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_orders(self, client_id: Optional[int] = None, status_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if client_id is None:
            client_id = self.client_id

        url = f"{self.BASE_URL}/api/Order/List?clientId={client_id}"
        if status_id is not None:
            url += f"&statusId={status_id}"
        r = requests.get(
            url,
            headers=self.headers(),
            timeout=30,
        )

        r.raise_for_status()
        return r.json()
    
    def create_return(self, order_id:int, warehouse_id:int, client_id:int):
        return []

    def create_external_return(self, data:Dict[str, Any]):
        url = f"{self.BASE_URL}/api/Return/CreateExternalReturn"

        r = requests.post(
            url, 
            headers=self.headers(),
            json=data
        )

        r.raise_for_status()
        response = r.json()
        print(response)
        return response
    
    def add_return_item(self, return_id: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a single item to a return.
        
        Args:
            return_id: The ID of the return
            item_data: Dictionary containing SKU, Quantity, ReturnReasonId, Action, and optional Comments
        
        Returns:
            Dict containing the API response
        """
        url = f"{self.BASE_URL}/api/Return/{return_id}/AddItem"
        
        r = requests.post(
            url,
            headers=self.headers(),
            json=item_data,
            timeout=30
        )
        r.raise_for_status()
        return r.json()
    
    def allocate_return_item_location(self, return_id: int, allocation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Allocate a location for an item in a return.
        
        Args:
            return_id: The ID of the return
            allocation_data: Dictionary containing SKU, LocationId, and Quantity
        
        Returns:
            Dict containing the API response
        """
        url = f"{self.BASE_URL}/api/Return/{return_id}/Allocate"
        
        r = requests.post(
            url,
            headers=self.headers(),
            json=allocation_data,
            timeout=30
        )
        r.raise_for_status()
        return r.json()
    
    def confirm_return(self, return_id: int) -> Dict[str, Any]:
        """
        Confirm a return.
        
        Args:
            return_id: The ID of the return to confirm
        
        Returns:
            Dict containing the API response
        """
        url = f"{self.BASE_URL}/api/Return/{return_id}/Confirm"
        
        r = requests.post(
            url,
            headers=self.headers(),
            timeout=30
        )
        r.raise_for_status()
        return r.json()
    
    def get_warehouse_locations(self, warehouse_id:int):
        url = f"{self.BASE_URL}/api/Warehouse/{warehouse_id}/Location/All"

        r = requests.get(
            url,
            headers=self.headers(),
            timeout=30,
        )

        r.raise_for_status()
        data = r.json()
        with open('mintsoft_warehouse_locations_model.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return data
    
    def transfer_stock(self, warehouse_id:int, product_id:int, source_location_id:int, quantity:int, destination_location_id):
        url = f"{self.BASE_URL}/api/Warehouse/StockMovement?Action=15"

        post_data ={
        "ProductId": product_id,
        "WarehouseId": warehouse_id,
        "LocationId": source_location_id,
        "Quantity": quantity,
        "DestinationWarehouseId": warehouse_id,
        "Comment": "Stock transfer for return",
        "DestinationLocationId": destination_location_id,
        }

        r = requests.post(
            url, 
            headers=self.headers(),
            json=post_data
        )

        data = r.json()
        print(data)
        return r.json()

    def get_currencies(self):
        url = f"{self.BASE_URL}/api/RefData/Currencies"

        r = requests.get(
            url,
            headers=self.headers(),
            timeout=30,
        )

        r.raise_for_status()
        data = r.json()
        print(data)
        with open('mintsoft_currency_model.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return data
    
    def get_products_in_locations(self, warehouse_id:int, client_id:int):
        url = f"{self.BASE_URL}/api/Reports/ProductsInLocationReport?warehouseId={warehouse_id}&clientId={client_id}"

        r = requests.get(
            url,
            headers=self.headers(),
            timeout=30,
        )

        r.raise_for_status()
        data = r.json()
        print(data)
        with open('mintsoft_products_in_locations_model.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return data
    
    def get_return_reasons(self):
        url = f"{self.BASE_URL}/api/Return/Reasons"

        r = requests.get(
            url,
            headers=self.headers(),
            timeout=30,
        )

        r.raise_for_status()
        data = r.json()
        print(data)
        return data    
    