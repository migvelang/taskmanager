"""Historial persistente de tickets generados.

Se guarda en disco (historial.json) para que sobreviva cierres o reinicios
inesperados de la app. Así queda registro de todo lo generado aunque no se
haya alcanzado a descargar el Excel, evitando crear tickets duplicados.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime


class HistoryStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._items: list[dict] = self._load()

    def _load(self) -> list:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    return data if isinstance(data, list) else []
            except Exception:
                return []
        return []

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._items, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # escritura atómica

    def add(self, ost="", f11="", gd="", sn="", ticket="", description="") -> dict:
        with self._lock:
            rec = {
                "id": uuid.uuid4().hex[:12],
                "ost": ost,
                "f11": f11,
                "gd": gd,
                "sn": sn,
                "ticket": ticket,
                "description": description,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            self._items.append(rec)
            self._save()
            return rec

    def delete(self, rec_id: str) -> bool:
        with self._lock:
            antes = len(self._items)
            self._items = [r for r in self._items if r.get("id") != rec_id]
            if len(self._items) != antes:
                self._save()
                return True
            return False

    def list(self, query: str = "") -> list:
        """Devuelve los registros (más reciente primero), filtrando por OST/F11."""
        q = (query or "").strip().lower()
        items = list(reversed(self._items))
        if q:
            items = [
                r for r in items
                if q in str(r.get("ost", "")).lower()
                or q in str(r.get("f11", "")).lower()
            ]
        return items

    def find_by_ost(self, ost: str) -> list:
        """Registros existentes para una OST (para avisar duplicados)."""
        o = (ost or "").strip().lower()
        if not o:
            return []
        return [r for r in self._items if str(r.get("ost", "")).lower() == o]
