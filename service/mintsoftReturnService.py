import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from loggers.main_logger import get_logger
from clients.mintsoftClient import MintsoftOrderClient
from mappers.main_mapper import map_return
from mappers.mintsoft_mapper import map_client, map_warehouse


class MintsoftReturnService:
    def create_return(self, data) -> Optional[int]:
        data = {
            "ClientId": 3,
            "WarehouseId": 3,
            "Reference": "1ZY287C40333149987"
        }
        try:
                self.logger.info("Order not found in Mintsoft. Creating EXTERNAL return.")
                print(m_return)
                response = self.client.create_external_return(data=m_return)
                self.logger.info(f"External return created. Response: {response}")
                return None

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
            merchant_name = self._get_merchant_name(data)
            warehouse_id = map_warehouse(merchant_name)
            
            if not line_items:
                self.logger.warning(f"No line items found in return data")
                return None
            
            # Step 1: Add items to the return
            for item in line_items:
                self.logger.info(f"Adding item {item.get('sku')} to return {return_id}")
                
                # Map Two Boxes item to Mintsoft format
                item_data = {
                    "SKU": item.get("sku"),
                    "Quantity": item.get("quantity", 1),
                    "ReturnReasonId": 1,  # Default return reason
                    "Action": "DoNothing",  # Default action
                }
                
                # Add comments from graded attributes if available
                graded_attributes = item.get("graded_attributes", [])
                if graded_attributes and len(graded_attributes) > 0:
                    grading_title = graded_attributes[0].get("merchant_grading_attribute", {}).get("grading_attribute", {}).get("title")
                    if grading_title:
                        item_data["Comments"] = grading_title
                
                response = self.client.add_return_item(return_id, item_data)
                self.logger.info(f"Added item {item.get('sku')} to return {return_id}: {response}")
            
            # Step 2: Allocate locations for items
            # Get warehouse locations to find appropriate return location
            warehouse_locations = self.client.get_warehouse_locations(warehouse_id)
            
            # Find a returns location (e.g., "Returns Shelf" or location with type for returns)
            returns_location_id = None
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