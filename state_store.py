from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("state_store")


class StateStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data: dict[str, Any] = {"used_signals": [], "managed_trades": {}}
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
                    log.info("State loaded | path=%s", self.path)
                    return
        except Exception as exc:
            log.warning("Could not load state file %s: %s", self.path, exc)
        log.warning("No usable state file found at %s; starting empty", self.path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(self.path)

    @property
    def used_signals(self) -> set[str]:
        return set(self.data.get("used_signals", []))

    @property
    def managed_trades(self) -> dict[str, dict]:
        return self.data.setdefault("managed_trades", {})

    def mark_signal_used(self, signal_id: str) -> None:
        used = self.data.setdefault("used_signals", [])
        if signal_id not in used:
            used.append(signal_id)
            self.data["used_signals"] = used[-5000:]
        self.save()

    def set_trade(self, symbol: str, trade: dict) -> None:
        self.managed_trades[symbol] = trade
        self.save()

    def remove_trade(self, symbol: str) -> None:
        self.managed_trades.pop(symbol, None)
        self.save()
