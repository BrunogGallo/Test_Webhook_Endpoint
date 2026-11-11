"""Coordinación entre webhooks que tocan el mismo return de Mintsoft.

Two Boxes manda dos webhooks `return-complete` casi al mismo tiempo cuando una
caja trae items inesperados (work capture): uno `rma` y otro `unexpected-item`,
ambos con la misma orden. Procesados en paralelo, `CreateReturn/{order_id}` les
devuelve el mismo return abierto, ambos le agregan items y ambos llaman a
Confirm -> Mintsoft ingresa el stock dos veces (caso Bronze Snake 03/11/2026,
tracking 9434636208192295704156).

Este módulo:
  * serializa el procesamiento por orden con un lock de archivo (fcntl.flock),
    que funciona entre threads y entre los workers de gunicorn del mismo host;
  * registra los returns que ya confirmamos, para no volver a confirmar uno.

El estado vive en RETURN_GUARD_DIR (por defecto un directorio en /tmp). Si el
servicio corre en más de una instancia/host, esto no alcanza y hace falta un
lock compartido (Redis, base de datos, etc.).
"""

import fcntl
import hashlib
import os
import tempfile
from contextlib import contextmanager

GUARD_DIR = os.environ.get(
    "RETURN_GUARD_DIR", os.path.join(tempfile.gettempdir(), "twoboxes_return_guard")
)
_CONFIRMED_FILE = os.path.join(GUARD_DIR, "confirmed_returns.txt")
_CONFIRMED_LOCK = os.path.join(GUARD_DIR, "confirmed_returns.lock")


def _ensure_dir() -> None:
    os.makedirs(GUARD_DIR, exist_ok=True)


def lock_key_for(data) -> str:
    """Clave del lock: la orden de la tienda (es lo que comparte el return de
    Mintsoft); si no hay, el tracking; si tampoco, completed_at-email."""
    event_data = (data or {}).get("event_data") or {}
    line_items = event_data.get("line_items") or []
    first = (line_items[0] or {}) if line_items else {}

    order = str(first.get("storefront_order_number") or "").strip().lstrip("#").strip().upper()
    if order:
        return f"order:{order}"

    tracking = str(first.get("tracking_number") or "").strip()
    if tracking:
        return f"tracking:{tracking}"

    customer_email = (event_data.get("customer") or {}).get("email") or ""
    return f"fallback:{event_data.get('completed_at')}-{customer_email}"


@contextmanager
def order_lock(key: str):
    """Lock exclusivo y bloqueante para `key`. Se libera al salir del bloque
    (o si el proceso muere)."""
    _ensure_dir()
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    path = os.path.join(GUARD_DIR, f"{digest}.lock")
    with open(path, "a") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


@contextmanager
def _confirmed_registry_lock():
    _ensure_dir()
    with open(_CONFIRMED_LOCK, "a") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def is_return_confirmed(return_id) -> bool:
    if return_id is None:
        return False
    with _confirmed_registry_lock():
        try:
            with open(_CONFIRMED_FILE, "r") as fh:
                return any(line.strip() == str(return_id) for line in fh)
        except FileNotFoundError:
            return False


def mark_return_confirmed(return_id) -> None:
    if return_id is None:
        return
    with _confirmed_registry_lock():
        with open(_CONFIRMED_FILE, "a") as fh:
            fh.write(f"{return_id}\n")
