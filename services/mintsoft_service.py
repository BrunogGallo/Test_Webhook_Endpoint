import os
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from loggers.main_logger import get_logger
from clients.mintsoftClient import MintsoftOrderClient
from mappers.main_mapper import map_return
from mappers.mintsoft_mapper import map_client, map_warehouse


class MintsoftReturnService:
    def __init__(self, logger_name: str = "mintsoft_service", log_file: str = "m_service.log"):
        self.logger = get_logger(logger_name, log_file)
        self.client = MintsoftOrderClient()
        self.status_ids = [4, 5, 6]

    def _get_merchant_name(self, data) -> str:
        """Get merchant name from event_data; supports both merchant_integration and line_items[0].merchant."""
        event_data = data[0]["event_data"]
        try:
            return event_data["merchant_integration"]["merchant"]["name"]
        except (KeyError, TypeError):
            pass
        line_items = event_data.get("line_items") or []
        if line_items:
            merchant = (line_items[0] or {}).get("merchant") or {}
            name = merchant.get("name")
            if name:
                return name
        return ""

    def _get_storefront_order_number(self, data) -> str:
        return data[0]["event_data"]["line_items"][0]["storefront_order_number"]

    def fetch_mintsoft_orders(self, data) -> List[Dict]:
        self.logger.info("Starting to fetch Mintsoft orders")

        merchant_name = self._get_merchant_name(data)
        client_id = map_client(merchant_name)

        all_orders: List[Dict] = []
        try:
            for status_id in self.status_ids:
                self.logger.info(f"Fetching orders with status ID: {status_id}")
                orders = self.client.get_orders(client_id=client_id, status_id=status_id)
                self.logger.info(f"Fetched {len(orders)} orders with status ID {status_id} from Mintsoft")
                all_orders.extend(orders)

            self.logger.info(f"Fetched {len(all_orders)} orders from Mintsoft (total)")
            return all_orders

        except Exception as e:
            self.logger.error(f"Error fetching Mintsoft orders: {e}", exc_info=True)
            return []

    def match_rma_order(self, orders: List[Dict], data) -> Optional[int]:
        self.logger.info("Starting to match RMA order with Mintsoft orders")

        rma_order_name = self._get_storefront_order_number(data)

        for order in orders:
            if str(order.get("OrderNumber")) == str(rma_order_name):
                self.logger.info(f"Found matching order in Mintsoft for RMA order name: {rma_order_name}")
                return order.get("ID")

        self.logger.warning(f"No matching order found in Mintsoft for RMA order name: {rma_order_name}")
        return None

    def create_return(self, data) -> Optional[int]:
        orders = self.fetch_mintsoft_orders(data)
        order_id = self.match_rma_order(orders, data)

        m_return = map_return(data)

        try:
            if order_id is None:
                self.logger.info("Order not found in Mintsoft. Creating EXTERNAL return.")
                print(m_return)
                response = self.client.create_external_return(data=m_return)
                self.logger.info(f"External return created. Response: {response}")
                return None

            self.logger.info(f"Order found (ID={order_id}). Creating standard return.")
            return_id = self.client.create_return(
                order_id=order_id,
                warehouse_id=m_return["WarehouseId"],
                client_id=m_return.get("ClientId"),  # safe if key exists
            )
            self.logger.info(f"Created return with ID: {return_id}")
            return return_id

        except Exception as e:
            self.logger.error(f"Error creating return: {e}", exc_info=True)
            return None

    def add_return_items(self, return_id: int, data: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        Add items to a return, allocate their locations, and confirm the return.
        Processes Two Boxes return data and orchestrates the Mintsoft API calls.
        
        Args:
            return_id: The ID of the return to add items to
            data: Two Boxes return data (list with event_data)
        
        Returns:
            Dict containing the confirmation response, or None if error occurred
        """
        self.logger.info(f"Starting to add items to return {return_id}")
        
        try:
            event_data = data[0]["event_data"]
            line_items = event_data.get("line_items", [])
            if not line_items:
                self.logger.warning(f"No line items found in return data")
                return None
            
            # Step 1: Add items to the return
            for item in line_items:
                merchant_name = self._get_merchant_name(data)
                warehouse_id = map_warehouse(merchant_name)
                client_id = map_client(merchant_name)
                
                if warehouse_id is None:
                    warehouse_id = 3  # default when merchant not in mapper list

                sku = (item.get("sku") or "").strip()
                if not sku:
                    self.logger.warning("Skipping line item with missing or empty SKU")
                    continue
                
                try:
                    product_id = self.client.get_product_id(sku, client_id)
                except Exception as e:
                    print(e)

                quantity = item.get("quantity")
                try:
                    quantity = max(1, int(quantity)) if quantity is not None else 1
                except (TypeError, ValueError):
                    quantity = 1

                # Map Two Boxes item to Mintsoft format (only non-null values to avoid API null reference)
                item_data = {
                    "Quantity": 1,
                    "ReturnReasonId": 50,
                    "ProductId": 72,
                    "Action": "RETURN",
                    "Comments": "Major stain",
                    "ReturnPhotos": [
                    ""
                    ]
                }
                
                

                graded_attributes = item.get("graded_attributes") or []
                if graded_attributes:
                    ga = graded_attributes[0] or {}
                    mg = (ga.get("merchant_grading_attribute") or {}).get("grading_attribute") or {}
                    grading_title = (mg.get("title") or "").strip()
                    if grading_title:
                        item_data["Comments"] = grading_title

                response = self.client.add_return_item(50, item_data)
                self.logger.info(item_data)
                self.logger.info(f"Added item {sku} to return {return_id}: {response}")

                if not response.get("Success"):
                    msg = response.get("Message") or "Unknown error"
                    self.logger.error(f"Mintsoft AddItem failed for SKU {sku}: {msg}")
                    raise RuntimeError(f"Mintsoft AddItem failed: {msg}")
            
            # Step 2: Allocate locations for items
            # Get warehouse locations to find appropriate return location
            warehouse_locations = self.client.get_warehouse_locations(warehouse_id)
            
            # Find a returns location (e.g., "Returns Shelf" or location with type for returns)
            returns_location_id = 7
            for location in warehouse_locations:
                location_name = location.get("Name", "").lower()
                if "return" in location_name or location.get("LocationTypeId") == 4:  # LocationTypeId 4 might be Returns
                    returns_location_id = location.get("ID")
                    break
            
            if returns_location_id:
                self.logger.info(f"Found returns location ID: {returns_location_id}")
                for item in line_items:
                    allocation_data = {
                        "SKU": item.get("sku"),
                        "LocationId": returns_location_id,
                        "Quantity": item.get("quantity", 1),
                    }
                    response = self.client.allocate_return_item_location(return_id, allocation_data)
                    self.logger.info(f"Allocated location {returns_location_id} for item {item.get('sku')}: {response}")
            else:
                self.logger.warning(f"No returns location found for warehouse {warehouse_id}")
            
            # Step 3: Confirm the return
            self.logger.info(f"Confirming return {return_id}")
            response = self.client.confirm_return(return_id)
            self.logger.info(f"Confirmed return {return_id}: {response}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error adding items to return {return_id}: {e}", exc_info=True)
            return None


if __name__ == "__main__":
    from pathlib import Path
    import json

    BASE_DIR = Path(__file__).resolve().parent.parent
    MODEL_PATH = BASE_DIR / "models" / "tb_rma_model.json"

    with MODEL_PATH.open("r", encoding="utf-8") as f:
        tb_data = json.load(f)

    service = MintsoftReturnService()
    service.create_return(tb_data)
