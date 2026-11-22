"""Web-интерфейс демонстрации симуляции на stdlib http.server."""

from __future__ import annotations

import argparse
import json
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..conflict import list_resolvers
from ..mechanisms import list_mechanisms
from ..scenarios.catalog import list_scenarios
from ..simulation import Simulation

STATIC_DIR = Path(__file__).resolve().parent / "static"


class KitchenServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, simulation: Simulation, interval: float = 0.6) -> None:
        super().__init__(address, partial(KitchenHandler, directory=str(STATIC_DIR)))
        self.sim = simulation
        self.lock = threading.Lock()
        self.auto = False
        self.interval = interval
        self.stop_event = threading.Event()

    def run_auto(self) -> None:
        while not self.stop_event.is_set():
            with self.lock:
                if self.auto and not self.sim.env.finished:
                    self.sim.step()
            time.sleep(self.interval)

    def start_auto(self) -> None:
        thread = threading.Thread(target=self.run_auto, daemon=True)
        thread.start()


class KitchenHandler(SimpleHTTPRequestHandler):
    server: KitchenServer

    def log_message(self, format: str, *args) -> None:
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _state(self) -> dict:
        with self.server.lock:
            data = self.server.sim.snapshot()
            data["auto"] = self.server.auto
            data["interval"] = self.server.interval
        data["scenarios"] = [
            {"name": scenario.name, "title": scenario.title}
            for scenario in list_scenarios()
        ]
        data["mechanisms"] = [
            {"name": mechanism.name, "label": mechanism.label}
            for mechanism in list_mechanisms()
        ]
        data["conflicts"] = [
            {"name": resolver.name, "label": resolver.label}
            for resolver in list_resolvers()
        ]
        return data

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/state":
            self._send_json(self._state())
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        payload = self._read_json()

        if path == "/api/step":
            with self.server.lock:
                self.server.auto = False
                if not self.server.sim.env.finished:
                    self.server.sim.step()
            self._send_json(self._state())
            return

        if path == "/api/auto":
            with self.server.lock:
                self.server.auto = bool(payload.get("enabled", True))
                if "interval" in payload:
                    try:
                        interval = float(payload["interval"])
                    except (TypeError, ValueError):
                        interval = self.server.interval
                    self.server.interval = min(3.0, max(0.1, interval))
            self._send_json(self._state())
            return

        if path == "/api/reset":
            scenario = payload.get("scenario") or self.server.sim.env.scenario.name
            mechanism = payload.get("mechanism") or self.server.sim.mechanism_name
            conflict = payload.get("conflict") or self.server.sim.conflict_name
            try:
                with self.server.lock:
                    self.server.sim.reset(
                        scenario, mechanism=mechanism, conflict=conflict
                    )
                    self.server.auto = False
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(self._state())
            return

        if path == "/api/mechanism":
            mechanism = payload.get("mechanism") or ""
            try:
                with self.server.lock:
                    self.server.sim.set_mechanism(mechanism)
                    self.server.auto = False
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(self._state())
            return

        if path == "/api/conflict":
            conflict = payload.get("conflict") or ""
            try:
                with self.server.lock:
                    self.server.sim.set_conflict(conflict)
                    self.server.auto = False
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(self._state())
            return

        self._send_json({"error": "not found"}, status=404)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m src.ui.web",
        description="Веб-интерфейс многоагентной кухни «Красти Крабс».",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--scenario", default="dinner_rush")
    parser.add_argument(
        "--mechanism",
        default="central",
        help="механизм распределения: central | contract_net | auction",
    )
    parser.add_argument(
        "--conflict",
        default="fcfs",
        help="режим конфликта: fcfs | negotiation | arbitration",
    )
    parser.add_argument("--interval", type=float, default=0.6)
    parser.add_argument(
        "--autostart", action="store_true", help="сразу запустить симуляцию"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        simulation = Simulation(
            args.scenario, mechanism=args.mechanism, conflict=args.conflict
        )
    except ValueError as exc:
        print(f"ошибка: {exc}")
        return 2

    server = KitchenServer(
        (args.host, args.port), simulation, interval=args.interval
    )
    server.auto = args.autostart
    server.start_auto()
    print(f"Кухня доступна: http://{args.host}:{args.port}/")
    print(f"Механизм: {args.mechanism}; конфликт: {args.conflict}; сценарий: {args.scenario}")
    print("Ctrl+C — остановка.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        server.stop_event.set()
        simulation.close()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
