"""
services/storage_service.py

Local-first persistence for canvas state (nodes + edges + client QPS).
Saves are plain JSON under ~/.sysdesign_rio/saves/ so designs survive app
restarts without requiring any backend.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models.node import Edge, Node

SAVE_DIR = Path.home() / ".sysdesign_rio" / "saves"


class StorageService:
    def __init__(self, save_dir: Path = SAVE_DIR):
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def list_saves(self) -> list[str]:
        return sorted(p.stem for p in self.save_dir.glob("*.json"))

    def save_canvas(
        self,
        name: str,
        nodes: list[Node],
        edges: list[Edge],
        client_qps: int = 1000,
    ) -> Path:
        payload: dict[str, Any] = {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "meta": {"client_qps": client_qps},
        }
        path = self.save_dir / f"{self._sanitize(name)}.json"
        path.write_text(json.dumps(payload, indent=2))
        return path

    def load_canvas(self, name: str) -> tuple[list[Node], list[Edge], int]:
        path = self.save_dir / f"{self._sanitize(name)}.json"
        if not path.exists():
            return [], [], 1000
        data = json.loads(path.read_text())
        nodes = [Node.from_dict(n) for n in data.get("nodes", [])]
        edges = [Edge.from_dict(e) for e in data.get("edges", [])]
        qps = int(data.get("meta", {}).get("client_qps", 1000))
        return nodes, edges, qps

    def delete_save(self, name: str) -> None:
        path = self.save_dir / f"{self._sanitize(name)}.json"
        if path.exists():
            path.unlink()

    @staticmethod
    def _sanitize(name: str) -> str:
        cleaned = "".join(c for c in name if c.isalnum() or c in ("-", "_", " "))
        return cleaned.strip().replace(" ", "_") or "autosave"
