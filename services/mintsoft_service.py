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
        event_data = data["event_data"]
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
        return data["event_data"]["line_items"][0]["storefront_order_number"]

    def fetch_mintsoft_orders(self, data) -> List[Dict]:
        self.logger.info("Starting to fetch Mintsoft orders")

        merchant_name = self._get_merchant_name(data)
        client_id = map_client(merchant_name) # Si no encuentra devuelve None

        if client_id is None:
            print ("Client not in Mintsoft, return cannot be processed")
            return None

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
        merchant_name = self._get_merchant_name(data)
        client_id = map_client(merchant_name) # Si no encuentra devuelve None
        if client_id is None:
                print ("Client not in Mintsoft, return cannot be processed")
                return None, "No Return Created"
        
        orders = self.fetch_mintsoft_orders(data)
        order_id = self.match_rma_order(orders, data)

        try:
            if order_id is None: # Si es un external return
                self.logger.info("Order not found in Mintsoft. Creating EXTERNAL return.")

                event_data = data["event_data"]
                line_items = event_data.get("line_items", [])
                return_identifier = line_items[0].get("tracking_number") # Si hay, es el tracking number

                if return_identifier is None:
                    completed_at = event_data.get("completed_at")
                    customer_email = event_data["customer"].get("email")
                    new_identifier = f"{completed_at}-{customer_email}"
                    return_identifier = new_identifier

                external_return_data= {
                    "Reference": return_identifier,
                    "ClientId": client_id,
                    "WarehouseId": 3, # Inicialmente siempre van a RET o RET-QT
                    "ReturnItems": [],
                }
                for item in line_items:
                    sku = item.get("sku")
                    product_id = self.client.get_product_id(sku)
                    disposition = item.get("disposition")

                    if disposition == "Return to Stock":
                        return_reason = 1
                    else:
                        return_reason = 2,

                    external_return_data["ReturnItems"].append({
                        "SKU": sku,
                        "ProductId": product_id,
                        "Quantity": item.get("quantity"),
                        "Action": "NONE",
                        "ReturnReasonId": return_reason,
                    })

                print(external_return_data)
                response = self.client.create_external_return(data=external_return_data)

                self.logger.info(f"External return created. Response: {response}")
                return None, "External Return Created" # Crea Return Externa (sin Order ID)

            # Si es un Internal Return
            self.logger.info(f"Order found (ID={order_id}). Creating standard return on Warehouse ID = {3}.")
            return_id = self.client.create_return(order_id, warehouse_id = 3)

            self.logger.info(f"Created return with ID: {return_id}")
            return return_id, "Internal Return Created"

        except Exception as e:
            self.logger.error(f"Error creating return: {e}", exc_info=True)
            return None

    def add_return_items(self, return_id: int, data: List[Dict]) -> Optional[Dict[str, Any]]:

        self.logger.info(f"Starting to add items to return {return_id}")
        
        try:
            event_data = data["event_data"]
            line_items = event_data.get("line_items", [])
            returned_product_map = {}
            
            if not line_items:
                self.logger.warning(f"No line items found in return data")
                return None
            
            # Step 1: Add items to the return
            for item in line_items:
                graded_attributes = item.get("graded_attributes") or []
                return_photos = item.get("photo_urls", [])

                disposition = item.get("disposition")

                if disposition == "Return to Stock":
                    return_reason = 1
                    returns_location_id = 4104 # RET
                else:
                    return_reason = 2,
                    returns_location_id = 2363 # RET-QT

                sku = (item.get("sku") or "").strip()
                if not sku:
                    self.logger.warning("Skipping line item with missing or empty SKU")
                    continue
                
                try:
                    product_id = self.client.get_product_id(sku)
                except Exception as e:
                    print(e)

                quantity = item.get("quantity")
                try:
                    quantity = max(1, int(quantity)) if quantity is not None else 1
                except (TypeError, ValueError):
                    quantity = 1

                item_data = {
                    "Quantity": item.get("quantity"),
                    "ReturnReasonId": return_reason, 
                    "ProductId": product_id,
                    "Action": "NONE",
                    "ReturnPhotos": return_photos                   
                }
                
                if graded_attributes:
                    ga = graded_attributes[0] or {}
                    mg = (ga.get("merchant_grading_attribute") or {}).get("grading_attribute") or {}
                    grading_title = (mg.get("title") or "").strip()
                    if grading_title:
                        item_data["Comments"] = grading_title

                response = self.client.add_return_item(return_id, item_data)
                returned_product_map[product_id] = response.get("ID")                

                self.logger.info(item_data)
                self.logger.info(f"Added item {sku} to return {return_id}: {response}")

                if not response.get("Success"):
                    msg = response.get("Message") or "Unknown error"
                    self.logger.error(f"Mintsoft AddItem failed for SKU {sku}: {msg}")
                    raise RuntimeError(f"Mintsoft AddItem failed: {msg}")
            
            # Step 2: Allocate locations for items 
        
            for item in line_items:
                product_id = self.client.get_product_id(sku)

                allocation_data = {
                    "ReturnItemId": returned_product_map.get(product_id),
                    "LocationId": returns_location_id,
                    "Quantity": item.get("quantity"),
                }

                response = self.client.allocate_return_item_location(return_id, allocation_data)
                self.logger.info(f"Allocated location {returns_location_id} for item {product_id}: {response}")
            
            # Step 3: Confirm the return
            self.logger.info(f"Confirming return {return_id}")
            response = self.client.confirm_return(return_id)
            self.logger.info(f"Confirmed return {return_id}: {response}")

            return None
        
        except Exception as e:
            self.logger.error(f"Error adding items to return {return_id}: {e}", exc_info=True)
            return None
    
    def reallocate_return_items(self, data):
        event_data = data.get("event_data")
        line_items = event_data.get("line_items", [])

        for item in line_items:
            sku = item.get("sku")
            product_id = self.client.get_product_id(sku)
            
            merchant = self._get_merchant_name(data)
            warehouse = map_warehouse(merchant)

            disposition = item.get("disposition")
            if disposition == "Return to Stock":
                returns_location_id = 4104 # RET
            else:
                returns_location_id = 2363 # RET-QT

            if returns_location_id == 4104:
                reallocation_data = {
                    "SourceWarehouseId": 3,
                    "SourceNameOrCode": "RET",
                    "DestinationWarehouseId": warehouse,
                    "DestinationNameOrCode": item.get("put_away_bin"),
                    "ProductId": product_id,
                    "Quantity": item.get("quantity"),
                    "Comment": "Return reallocation",
                }

            else:
                reallocation_data = {
                    "SourceWarehouseId": 3,
                    "SourceNameOrCode": "RET-QT",
                    "DestinationWarehouseId": warehouse,
                    "DestinationNameOrCode": item.get("put_away_bin"),
                    "ProductId": item.get("product_id"),
                    "Quantity": item.get("quantity"),
                    "Comment": "Return reallocation",
                } 
            response = self.client.transfer_stock(reallocation_data)
            print(response)
    
        return response
        
