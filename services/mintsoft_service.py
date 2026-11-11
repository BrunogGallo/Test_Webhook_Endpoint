import os
import json
import sys
import socket
import smtplib
import traceback
from email.message import EmailMessage
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from loggers.main_logger import get_logger
from clients.mintsoftClient import MintsoftOrderClient
from mappers.main_mapper import map_return
from mappers.mintsoft_mapper import map_client, map_warehouse
from services.return_guard import mark_return_confirmed


def _normalize_order_number(value) -> str:
    """Normaliza un número de orden para poder compararlo.

    Two Boxes suele mandar el storefront_order_number con '#' adelante (ej '#2131WF')
    y en Mintsoft la orden está sin él ('2131WF'), así que sacamos el '#' y los espacios
    y comparamos en mayúsculas.
    """
    return str(value or "").strip().lstrip("#").strip().upper()


class MintsoftReturnService:
    def __init__(self, logger_name: str = "mintsoft_service", log_file: str = "m_service.log"):
        self.logger = get_logger(logger_name, log_file)
        self.client = MintsoftOrderClient()
        self.status_ids = [4, 5, 6]

        # ----- Email notification config (read from environment) -----
        self.smtp_host = os.environ.get("SMTP_HOST")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_password = os.environ.get("SMTP_PASSWORD")
        self.alert_email_to = "bgallo@the5411.com, jcordero@the5411.com, ngurfinkel@the5411.com, mbivort@the5411.com",
        self.alert_email_from = os.environ.get("ALERT_EMAIL_FROM", self.smtp_user or "")

    # -------------------------------------------------------------
    # Internal: send an error notification email. Never raises.
    # order_reference (storefront_order_number / POReference) is highlighted
    # in the subject and body when provided.
    # -------------------------------------------------------------
    def _send_error_email(
        self,
        method: str,
        error: BaseException,
        order_reference: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            if not (self.smtp_host and self.smtp_user and self.smtp_password and self.alert_email_to):
                self.logger.warning(
                    "Email alert NOT sent (SMTP credentials missing). "
                    "Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_TO env vars."
                )
                return

            host = socket.gethostname()
            ts = datetime.utcnow().isoformat() + "Z"
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))

            ref_label = str(order_reference) if order_reference else "UNKNOWN"
            subject = f"[MintsoftReturnService] API error in {method} - POReference: {ref_label}"

            body_lines = [
                f"An error occurred in MintsoftReturnService.{method}",
                "",
                f"POReference: {ref_label}",
                f"Time (UTC):  {ts}",
                f"Host:        {host}",
                f"Error type:  {type(error).__name__}",
                f"Error:       {error}",
                "",
            ]
            if context:
                body_lines.append("Context:")
                try:
                    body_lines.append(json.dumps(context, indent=2, default=str))
                except Exception:
                    body_lines.append(str(context))
                body_lines.append("")
            body_lines.append("Traceback:")
            body_lines.append(tb)

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.alert_email_from
            msg["To"] = self.alert_email_to
            msg.set_content("\n".join(body_lines))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.ehlo()
                try:
                    server.starttls()
                    server.ehlo()
                except Exception:
                    # Server may not support STARTTLS (e.g. local relay) -- continue.
                    pass
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            self.logger.info(
                f"Error alert email sent to {self.alert_email_to} for {method} (POReference={ref_label})"
            )
        except Exception as mail_err:
            # Never let notification failures take down the caller.
            self.logger.error(f"Failed to send error alert email: {mail_err}", exc_info=True)

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
                return name.strip()
        return ""

    def _get_storefront_order_number(self, data) -> str:
        return data["event_data"]["line_items"][0]["storefront_order_number"]

    def _safe_get_storefront_order_number(self, data) -> Optional[str]:
        """Same as _get_storefront_order_number but returns None instead of raising
        when data is malformed -- so it can be used inside error-handling code."""
        try:
            return self._get_storefront_order_number(data)
        except Exception:
            return None

    def alert_unprocessed_linked_items(self, data) -> None:
        """Avisa por mail de los `linked_line_items` que este servicio no sube.

        Solo procesamos `line_items`. Los linked que son work capture llegan en su
        propio webhook `unexpected-item`, pero los que pertenecen a OTRO RMA
        (otra orden u otro tracking, ej. el Nova Top de #A11291523 que se escaneó
        en la caja de #A11277516) no aparecen en ningún `line_items` de este
        evento y pueden quedar sin subir a Mintsoft. No los subimos
        automáticamente porque, si después llega el webhook de su propio RMA, se
        duplicarían; se avisa para revisarlos a mano. Nunca lanza.
        """
        try:
            event_data = data.get("event_data") or {}
            line_items = event_data.get("line_items") or []
            linked = event_data.get("linked_line_items") or []
            if not linked:
                return

            own_ids = {li.get("id") for li in line_items if li}
            own_orders = {
                _normalize_order_number(li.get("storefront_order_number"))
                for li in line_items if li
            }
            own_trackings = {
                (li.get("tracking_number") or "").strip() for li in line_items if li
            }

            foreign = []
            for item in linked:
                if not item or item.get("id") in own_ids or item.get("work_capture"):
                    continue
                order = _normalize_order_number(item.get("storefront_order_number"))
                tracking = (item.get("tracking_number") or "").strip()
                if order not in own_orders or tracking not in own_trackings:
                    foreign.append({
                        "sku": item.get("sku"),
                        "quantity": item.get("quantity"),
                        "disposition": item.get("disposition"),
                        "storefront_order_number": item.get("storefront_order_number"),
                        "tracking_number": item.get("tracking_number"),
                        "put_away_bin": item.get("put_away_bin"),
                        "line_item_id": item.get("id"),
                    })

            if not foreign:
                return

            reference = (line_items[0] or {}).get("tracking_number") if line_items else None
            self.logger.warning(
                f"Return {reference}: {len(foreign)} linked item(s) de otro RMA no se suben a Mintsoft: {foreign}"
            )
            self._send_error_email(
                method="alert_unprocessed_linked_items",
                error=RuntimeError(
                    "La caja trae items vinculados de otro RMA que no se suben "
                    "automáticamente. Verificar si llegaron en el webhook de su "
                    "propio RMA; si no, subirlos a mano."
                ),
                order_reference=reference,
                context={
                    "rma": event_data.get("rma"),
                    "merchant_name": self._get_merchant_name(data),
                    "linked_items": foreign,
                },
            )
        except Exception as e:
            self.logger.error(f"Error revisando linked_line_items: {e}", exc_info=True)

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
            event_data = data["event_data"]
            line_items = event_data.get("line_items", [])
            return_identifier = line_items[0].get("tracking_number") # Si hay, es el tracking number

            if return_identifier is None:
                completed_at = event_data.get("completed_at")
                customer_email = event_data["customer"].get("email")
                new_identifier = f"{completed_at}-{customer_email}"
                return_identifier = new_identifier

            self._send_error_email(
                method="fetch_mintsoft_orders",
                error=e,
                order_reference=return_identifier,
                context={"merchant_name": merchant_name, "client_id": client_id},
            )
            return []

    def match_rma_order(self, orders: List[Dict], data) -> Optional[int]:
        self.logger.info("Starting to match RMA order with Mintsoft orders")

        rma_order_name = self._get_storefront_order_number(data)
        try:
            target = _normalize_order_number(rma_order_name)

            if not target:
                #self.logger.warning("Empty storefront_order_number, cannot match against Mintsoft orders")
                return None

            for order in orders:
                if _normalize_order_number(order.get("OrderNumber")) == target:
                    self.logger.info(f"Found matching order in Mintsoft for RMA order name: {rma_order_name}")

                    return order.get("ID")

            self.logger.warning(f"No matching order found in Mintsoft for RMA order name: {rma_order_name}")
            return None

        except Exception:
            return None

    def create_return(self, data) -> Optional[int]:
        try:
            merchant_name = self._get_merchant_name(data)
            client_id = map_client(merchant_name) # Si no encuentra devuelve None
            warehouse = map_warehouse(merchant_name)

            if client_id is None:
                    print ("Client not in Mintsoft, return cannot be processed")
                    return None, "No Return Created"

            orders = self.fetch_mintsoft_orders(data)
            order_id = self.match_rma_order(orders, data)

    
            if order_id is None: # Si es un external return
                self.logger.info("Order not found in Mintsoft. Creating EXTERNAL return.")

                event_data = data["event_data"]
                line_items = event_data.get("line_items", [])
                return_identifier = line_items[0].get("tracking_number") # Si hay, es el tracking number

                # Guardamos el tracking crudo (sin fallback) para usarlo en los Comments de cada item
                return_tracking_number = (return_identifier or "").strip()

                if return_identifier is None:
                    completed_at = event_data.get("completed_at")
                    customer_email = event_data["customer"].get("email")
                    new_identifier = f"{completed_at}-{customer_email}"
                    return_identifier = new_identifier

                external_return_data = {
                    "Reference": return_identifier[:50],
                    "ClientId": client_id,
                    "WarehouseId": warehouse,
                    "ReturnItems": [],
                }
                for item in line_items:
                    sku = item.get("sku")
                    sku, product_id = self.client.get_product_id(sku, client_id, item.get("barcode"))

                    if product_id == None:
                        # Si el item no existe en Mintsoft con ese SKU

                        new_product_data = {
                            "SKU": sku,
                            "Name": (item.get("product_variant") or {}).get("name") or item.get("sku"),
                            "EAN": item.get("barcode"),
                            "ClientId": client_id,
                        }

                        created_product_id = self.client.create_product(new_product_data)
                        
                        # Usamos el ID del item recien creado
                        product_id = created_product_id

                        # Sleep de 3 segundos para no saturar la API
                        time.sleep(3)
                        
                    disposition = item.get("disposition")

                    if disposition == "Return to Stock":
                        return_reason = 1

                    elif disposition == "Missing":
                        print(f"Item {sku} faltante en el return")
                        continue

                    else:
                        return_reason = 2

                    return_item_data = {
                        "SKU": sku,
                        "ProductId": product_id,
                        "Quantity": item.get("quantity"),
                        "Action": "NONE",
                        "ReturnReasonId": return_reason,
                    }

                    # Tracking del item, y si no tiene usamos el del return
                    tracking_number = (item.get("tracking_number") or "").strip() or return_tracking_number
                    if tracking_number:
                        return_item_data["Comments"] = tracking_number

                    external_return_data["ReturnItems"].append(return_item_data)

                print(external_return_data)
                external_return_id = self.client.create_external_return(data=external_return_data)

                self.logger.info(f"External return created. ID: {external_return_id}")

                return external_return_id, "External Return Created" # Crea Return Externa (con el Order ID)

            # Si es un Internal Return
            self.logger.info(f"Order found (ID={order_id}). Creating standard return on Warehouse ID = {3}.")
            return_id = self.client.create_return(order_id, warehouse_id = 3)

            self.logger.info(f"Created return with ID: {return_id}")
            return return_id, "Internal Return Created"

        except Exception as e:
            self.logger.error(f"Error creating return: {e}", exc_info=True)
            event_data = data["event_data"]
            line_items = event_data.get("line_items", [])
            return_identifier = line_items[0].get("tracking_number") # Si hay, es el tracking number

            if return_identifier is None:
                completed_at = event_data.get("completed_at")
                customer_email = event_data["customer"].get("email")
                new_identifier = f"{completed_at}-{customer_email}"
                return_identifier = new_identifier
                
            self._send_error_email(
                method="create_return",
                error=e,
                order_reference=return_identifier,
                context={
                    "merchant_name": merchant_name,
                    "client_id": client_id,
                    "warehouse": warehouse,
                    "order_id": order_id,
                },
            )
            return None, "No Return Created"

    def allocate_external_return_items(self, data, return_id: int):
        merchant_name = self._get_merchant_name(data)
        warehouse = map_warehouse(merchant_name)

        try:
            return_details = self.client.get_return_details(return_id)
            return_items = return_details.get('ReturnItems')

            for item in return_items:
                return_reason = item.get('ReturnReasonId') # 1 es Good Stock, 2 es Quarantine
                print("return_reason",return_reason)
                if return_reason == 1: # Si esta en buena condicion
                    if warehouse == 3:
                        location_id = 4104 # RET Wholesale
                    else:
                        location_id = 4299 # RET E-Commerce

                else: # Si esta en mala condicion
                    if warehouse == 3:
                        location_id = 9 # RET-TEMP Wholesale
                    else:
                        location_id = 4304 # RET-TEMP E-Commerce

                data = {
                    'ReturnItemId': item.get('ID'),
                    'Quantity': item.get('Quantity'),
                    'LocationId': location_id
                }

                response = self.client.allocate_return_item_location(return_id, data)
                self.logger.info(f"Allocated External Return Items to {location_id}: {response}")


            response = self.client.confirm_return(return_id)
            self.logger.info(f"Confirmed return {return_id}: {response}")

            return None

        except Exception as e:
            self.logger.error(f"Error allocating external return items for return {return_id}: {e}", exc_info=True)
            # `data` may have been overwritten in the loop above, so try to pull a
            # reference from it only if it still looks like the original payload.
            ref = None
            if isinstance(data, dict) and "event_data" in data:
                ref = self._safe_get_storefront_order_number(data)
            self._send_error_email(
                method="allocate_external_return_items",
                error=e,
                order_reference=ref,
                context={
                    "merchant_name": merchant_name,
                    "warehouse": warehouse,
                    "return_id": return_id,
                },
            )
            raise


    def add_return_items(self, return_id: int, data: Dict) -> Optional[Dict[str, Any]]:

        self.logger.info(f"Starting to add items to return {return_id}")

        try:
            merchant_name = self._get_merchant_name(data)
            client_id = map_client(merchant_name) # Si no encuentra devuelve None
            event_data = data.get("event_data", {})
            line_items = event_data.get("line_items", [])

            if not line_items:
                self.logger.warning("No line items found in return data")
                return None

            # Guardaremos el (ReturnItemId, item, location_id) para allocarlos luego
            items_to_allocate = []

            # Step 1: Add items to the return
            for item in line_items:
                disposition = item.get("disposition")

                if disposition == "Missing":
                    sku_log = (item.get("sku") or "").strip()
                    self.logger.info(f"Item {sku_log} faltante en el return. Saltando.")
                    continue

                sku = (item.get("sku") or "").strip()
                if not sku:
                    self.logger.warning("Skipping line item with missing or empty SKU")
                    continue

                product_id = None
                try:
                    sku, product_id = self.client.get_product_id(sku, client_id, item.get("barcode"))
                except Exception as e:
                    self.logger.error(f"Error al obtener product_id para SKU {sku}: {e}")
                    continue

                if disposition == "Return to Stock":
                    return_reason = 1
                else:
                    return_reason = 2

                graded_attributes = item.get("graded_attributes") or []
                return_photos = item.get("photo_urls", [])

                quantity = item.get("quantity")
                try:
                    quantity = max(1, int(quantity)) if quantity is not None else 1
                except (TypeError, ValueError):
                    quantity = 1

                item_data = {
                    "Quantity": quantity,
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
                self.logger.info(f"Added item {sku} to return {return_id}: {response}")

                if not response or not response.get("Success"):
                    msg = response.get("Message") if response else "Unknown error"
                    self.logger.error(f"Mintsoft AddItem failed for SKU {sku}: {msg}")
                    raise RuntimeError(f"Mintsoft AddItem failed: {msg}")

                return_item_id = response.get("ID")

                # Determinar la ubicación de asignación para ESTE ítem específico
                merchant = self._get_merchant_name(data)
                warehouse = map_warehouse(merchant) # 3 si es Wholesale, 5 si es E-Comm

                if disposition == "Return to Stock":
                    returns_location_id = 4104 if warehouse == 3 else 4299
                else:
                    returns_location_id = 9 if warehouse == 3 else 4304

                # Guardamos la referencia directa del ID de la devolución que nos devolvió Mintsoft
                items_to_allocate.append({
                    "ReturnItemId": return_item_id,
                    "LocationId": returns_location_id,
                    "Quantity": quantity,
                    "ProductId": product_id
                })

            # Step 2: Allocate locations for items
            for alloc in items_to_allocate:
                allocation_data = {
                    "ReturnItemId": alloc["ReturnItemId"],
                    "LocationId": alloc["LocationId"],
                    "Quantity": alloc["Quantity"],
                }

                response = self.client.allocate_return_item_location(return_id, allocation_data)
                self.logger.info(f"Allocated location {alloc['LocationId']} for ReturnItemId {alloc['ReturnItemId']}: {response}")

            # Step 3: Confirm the return
            self.logger.info(f"Confirming return {return_id}")
            response = self.client.confirm_return(return_id)
            mark_return_confirmed(return_id)
            self.logger.info(f"Confirmed return {return_id}: {response}")

            return None

        except Exception as e:
            self.logger.error(f"Error adding items to return {return_id}: {e}", exc_info=True)
            event_data = data.get("event_data", {})
            line_items = event_data.get("line_items", [])
            
            return_identifier = None
            if line_items:
                return_identifier = line_items[0].get("tracking_number")

            if not return_identifier:
                completed_at = event_data.get("completed_at", "")
                customer_email = (event_data.get("customer") or {}).get("email", "")
                return_identifier = f"{completed_at}-{customer_email}"

            self._send_error_email(
                method="add_return_items",
                error=e,
                order_reference=return_identifier, # <--- Corregido
                context={"return_id": return_id},
            )
            return None
    
    def _send_reallocation_failures_email(self, data, failures, merchant_name, client_id) -> None:
        """Un solo mail con todos los items que no se pudieron pasar a su caja."""
        event_data = data.get("event_data") or {}
        line_items = event_data.get("line_items") or []
        reference = (line_items[0] or {}).get("tracking_number") if line_items else None
        if not reference:
            customer_email = (event_data.get("customer") or {}).get("email")
            reference = f"{event_data.get('completed_at')}-{customer_email}"

        # Un item "no llegó a la caja" si falló la validación, la creación de la
        # caja o el transfer. Si solo falló la cuarentena, el transfer salió bien.
        not_moved_ids = {
            f.get("line_item_id") for f in failures
            if not f.get("paso_fallido", "").startswith("poner en cuarentena")
        }
        not_moved_skus, quarantine_only_skus = [], []
        for f in failures:
            target = not_moved_skus if f.get("line_item_id") in not_moved_ids else quarantine_only_skus
            if f.get("sku") not in target:
                target.append(f.get("sku"))
            if f.get("line_item_id") not in not_moved_ids:
                f["stock_quedo_en"] = "llegó a la caja; revisar estado de cuarentena"

        parts = []
        if not_moved_skus:
            parts.append(
                f"{len(not_moved_skus)} item(s) NO llegaron a su caja y quedaron en RET / RET-TEMP: "
                f"{', '.join(map(str, not_moved_skus))}. Moverlos a mano."
            )
        if quarantine_only_skus:
            parts.append(
                f"{len(quarantine_only_skus)} item(s) llegaron a la caja pero falló la cuarentena: "
                f"{', '.join(map(str, quarantine_only_skus))}. Revisar que estén en cuarentena."
            )

        self._send_error_email(
            method="reallocate_return_items",
            error=RuntimeError(" ".join(parts)),
            order_reference=reference,
            context={
                "merchant_name": merchant_name,
                "client_id": client_id,
                "rma": event_data.get("rma"),
                "items_fallidos": failures,
            },
        )

    def reallocate_return_items(self, data):
        merchant_name = self._get_merchant_name(data)
        client_id = map_client(merchant_name) # Si no encuentra devuelve None
        event_data = data.get("event_data")
        line_items = event_data.get("line_items", [])

        # Items que no llegaron a su caja: se avisan todos juntos en un solo mail
        # al final, y se sigue con el resto de los items.
        failures = []
        response = None

        def _record_failure(item, step, error, source_location):
            entry = {
                "sku": item.get("sku"),
                "quantity": item.get("quantity"),
                "disposition": item.get("disposition"),
                "put_away_bin": item.get("put_away_bin"),
                "paso_fallido": step,
                "error": str(error),
                "stock_quedo_en": source_location,
                "line_item_id": item.get("id"),
            }
            body = getattr(error, "body", None)
            if body is not None:
                entry["respuesta_mintsoft"] = body
            failures.append(entry)
            self.logger.error(f"Reallocation falló para {entry['sku']} en '{step}': {error}")

        try:
            for item in line_items:
                sku = item.get("sku")
                sku, product_id = self.client.get_product_id(sku, client_id, item.get("barcode"))
                merchant = self._get_merchant_name(data)
                warehouse = map_warehouse(merchant) # 3 si es Wholesale, 5 si es E-Comm
                carton_code = (item.get("put_away_bin") or "").strip()

                disposition = item.get("disposition")
                is_good_stock = disposition == "Return to Stock"
                source_location = "RET" if is_good_stock else "RET-TEMP"

                if not carton_code:
                    _record_failure(
                        item, "validar put_away_bin",
                        "El webhook no trae put_away_bin: no se sabe a qué caja transferir",
                        source_location,
                    )
                    continue

                if is_good_stock: # Stock en buenas condiciones

                    reallocation_data = {
                        "SourceWarehouseId": warehouse,
                        "SourceNameOrCode": "RET",
                        "DestinationWarehouseId": warehouse,
                        "DestinationNameOrCode": carton_code,
                        "ProductId": product_id,
                        "Quantity": item.get("quantity"),
                        "Comment": "Return reallocation",
                    }

                    if self.client.check_carton(carton_code) == False: # Check si existe la caja
                        print(f'Carton {carton_code} not in Mintsoft - creating Carton...')
                        client_id = map_client(merchant)

                        if warehouse == 3:
                            returns_location_id = 4104 # RET Wholesale
                        else:
                            returns_location_id = 4299 # RET Ecom

                        carton_data = {
                            "WarehouseId": warehouse,
                            "StorageMediaName": "Stock",
                            "Code": carton_code,
                            "LocationId": returns_location_id
                        }

                        try:
                            self.client.create_carton(carton_data, client_id)
                        except Exception as e:
                            _record_failure(item, "crear caja", e, source_location)
                            continue

                    try:
                        response = self.client.transfer_stock(reallocation_data)
                        print(response)
                    except Exception as e:
                        _record_failure(item, "transferir a la caja", e, source_location)

                else: # Stock a mandar a cuarentena

                    if warehouse == 3:
                        temporary_location_id = 9 # RET-QT Wholesale
                    else:
                        temporary_location_id = 4304 # RET-TEMP E-Comm

                    reallocation_data = {
                        "SourceWarehouseId": warehouse,
                        "SourceNameOrCode": "RET-TEMP",
                        "DestinationWarehouseId": warehouse,
                        "DestinationNameOrCode": carton_code,
                        "ProductId": product_id,
                        "Quantity": item.get("quantity"),
                        "Type": "Quarantine",
                        "Comment": "Return reallocation",
                    }

                    quarantine_data = {
                        "ProductID": product_id,
                        "WarehouseId": warehouse,
                        "LocationId": temporary_location_id,
                        "Quantity": item.get("quantity"),
                        "Comment": "Returned stock sent to Quarantine"
                    }

                    if self.client.check_carton(carton_code) == False: # Check si existe la caja
                        print(f'Carton {carton_code} not in Mintsoft - creating Carton...')
                        client_id = map_client(merchant)

                        carton_data = {
                            "WarehouseId": warehouse,
                            "StorageMediaName": "Stock",
                            "Code": carton_code,
                            "LocationId": temporary_location_id
                        }

                        try:
                            self.client.create_carton(carton_data, client_id)
                        except Exception as e:
                            _record_failure(item, "crear caja", e, source_location)
                            continue

                    # Si la cuarentena falla igual se intenta el transfer (como antes),
                    # pero queda registrado para el mail.
                    try:
                        self.client.quarantine_stock(quarantine_data)
                        self.logger.info(f"{sku} from Return set to Quarantine at Location: {carton_code}")
                    except Exception as e:
                        _record_failure(item, "poner en cuarentena", e, source_location)

                    try:
                        response = self.client.transfer_stock(reallocation_data)
                        print(response)
                    except Exception as e:
                        _record_failure(item, "transferir a la caja (cuarentena)", e, source_location)

            if failures:
                self._send_reallocation_failures_email(data, failures, merchant_name, client_id)

            return response

        except Exception as e:
            self.logger.error(f"Error reallocating return items: {e}", exc_info=True)
            event_data = data["event_data"]
            line_items = event_data.get("line_items", [])
            return_identifier = line_items[0].get("tracking_number") # Si hay, es el tracking number

            if return_identifier is None:
                completed_at = event_data.get("completed_at")
                customer_email = event_data["customer"].get("email")
                new_identifier = f"{completed_at}-{customer_email}"
                return_identifier = new_identifier

            self._send_error_email(
                method="reallocate_return_items",
                error=e,
                order_reference=return_identifier,
                context={
                    "merchant_name": merchant_name,
                    "client_id": client_id,
                },
            )
            raise



        