#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DoctorHide GUI — локальный сервер для интерфейса пакетной анонимизации.

Запуск:  python gui/server.py [--port 8765]
Открыть: http://127.0.0.1:8765/

Поддерживает до 100 файлов за один прогон: PDF, DOCX, MD/TXT, PNG/JPEG/TIFF/BMP/WEBP.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import threading
import time
import traceback
import urllib.parse
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import doctorhide as D  # noqa: E402

WORK = os.path.join(ROOT, "_gui_work")
IN_DIR = os.path.join(WORK, "in")
OUT_DIR = os.path.join(WORK, "out")
MAX_FILES = 100
IMAGE_EXT = D.IMAGE_EXT

FILES: list[dict] = []
LOCK = threading.Lock()
RUNNING = {"value": False, "started": 0.0, "finished": 0.0}


def log(msg: str) -> None:
    print(msg, flush=True)


def _reset_dirs() -> None:
    for d in (IN_DIR, OUT_DIR):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)


def _convert(src: str, dst_dir: str, name: str) -> str:
    """Конвертирует один файл, возвращает путь результата."""
    ext = os.path.splitext(name)[1].lower()
    base = os.path.splitext(name)[0]
    enabled = set(D.CATEGORIES)

    if ext == ".pdf":
        import pymupdf

        doc = pymupdf.open(src)
        text = "".join(p.get_text() for p in doc)
        doc.close()
        mode = "judicial" if D.is_court_act(text) else "document"
        dst = os.path.join(dst_dir, f"{base}_anon.pdf")
        D.render_pdf(src, dst, mode, enabled, "auto", 300, False, False)
        return dst

    if ext in IMAGE_EXT:
        dst = os.path.join(dst_dir, f"{base}_anon{ext}")
        D.render_image(src, dst, "document", enabled, False)
        return dst

    if ext in (".docx", ".doc"):
        md = D.docx_to_md(src)
        anon, _ = D.anonymize_text(md, "document", enabled, False)
        dst = os.path.join(dst_dir, f"{base}_anon.md")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(anon)
        return dst

    with open(src, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    anon, _ = D.anonymize_text(raw, "document", enabled, False)
    dst = os.path.join(dst_dir, f"{base}_anon{ext}")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(anon)
    return dst


def _worker() -> None:
    RUNNING["started"] = time.time()
    while True:
        with LOCK:
            pending = [f for f in FILES if f["status"] == "queued"]
            if not pending:
                RUNNING["value"] = False
                RUNNING["finished"] = time.time()
                return
            item = pending[0]
            item["status"] = "running"
            item["t0"] = time.time()
        try:
            out = _convert(item["path"], OUT_DIR, item["name"])
            with LOCK:
                item["status"] = "done"
                item["out"] = os.path.basename(out)
                item["duration"] = round(time.time() - item["t0"], 2)
            log(f"OK   {item['name']} -> {os.path.basename(out)}")
        except Exception as err:  # noqa: BLE001
            with LOCK:
                item["status"] = "error"
                item["error"] = f"{type(err).__name__}: {err}"
                item["duration"] = round(time.time() - item["t0"], 2)
            log("FAIL " + item["name"] + " " + item.get("error", ""))
            traceback.print_exc()


class Handler(BaseHTTPRequestHandler):
    server_version = "DoctorHideGUI/1.0"

    def log_message(self, fmt, *args):  # тише в консоли
        pass

    # ---------- утилиты ----------
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: str, name: str) -> None:
        if not os.path.exists(path):
            self.send_error(404, "not found")
            return
        data = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        safe = urllib.parse.quote(name)
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{safe}")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------- GET ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            index = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            data = open(index, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/status":
            with LOCK:
                files = [dict(f) for f in FILES]
            done = sum(1 for f in files if f["status"] in ("done", "error"))
            self._json(200, {
                "files": [{k: f.get(k) for k in ("id", "name", "status", "out", "error",
                                                 "duration", "size", "ext")} for f in files],
                "total": len(files),
                "done": done,
                "running": RUNNING["value"],
                "max": MAX_FILES,
            })
            return

        if path.startswith("/api/download/"):
            fid = path.rsplit("/", 1)[-1]
            with LOCK:
                item = next((f for f in FILES if f["id"] == fid), None)
            if not item or item["status"] != "done":
                self.send_error(404, "no result")
                return
            self._file(os.path.join(OUT_DIR, item["out"]), item["out"])
            return

        if path == "/api/zip":
            buf = io.BytesIO()
            with LOCK:
                ready = [f for f in FILES if f["status"] == "done"]
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in ready:
                    zf.write(os.path.join(OUT_DIR, f["out"]), arcname=f["out"])
            data = buf.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", "attachment; filename=doctorhide_results.zip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(404, "not found")

    # ---------- POST ----------
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length") or 0)

        if path == "/api/add":
            name = (qs.get("name") or ["file"])[0]
            name = os.path.basename(name.replace("\\", "/"))
            with LOCK:
                if len(FILES) >= MAX_FILES:
                    self._json(409, {"error": f"лимит {MAX_FILES} файлов"})
                    return
            data = self.rfile.read(length) if length else b""
            fid = uuid.uuid4().hex[:12]
            dst = os.path.join(IN_DIR, f"{fid}_{name}")
            with open(dst, "wb") as f:
                f.write(data)
            ext = os.path.splitext(name)[1].lower()
            with LOCK:
                FILES.append({"id": fid, "name": name, "path": dst, "size": len(data),
                              "ext": ext, "status": "queued", "out": None, "error": None,
                              "duration": None})
            self._json(200, {"id": fid, "name": name})
            return

        if path == "/api/demo":
            demo_dir = os.path.join(ROOT, "_private", "_selftest")
            added = []
            if os.path.isdir(demo_dir):
                for name in sorted(os.listdir(demo_dir)):
                    ext = os.path.splitext(name)[1].lower()
                    if ext not in ({".pdf", ".docx", ".doc", ".md", ".txt"} | IMAGE_EXT):
                        continue
                    with LOCK:
                        if len(FILES) >= MAX_FILES:
                            break
                    fid = uuid.uuid4().hex[:12]
                    dst = os.path.join(IN_DIR, f"{fid}_{name}")
                    shutil.copy2(os.path.join(demo_dir, name), dst)
                    with LOCK:
                        FILES.append({"id": fid, "name": name, "path": dst,
                                      "size": os.path.getsize(dst), "ext": ext,
                                      "status": "queued", "out": None, "error": None,
                                      "duration": None})
                    added.append(name)
            self._json(200, {"added": added})
            return

        if path == "/api/run":
            with LOCK:
                queued = [f for f in FILES if f["status"] == "queued"]
                if not queued:
                    self._json(400, {"error": "нет файлов в очереди"})
                    return
                for f in FILES:
                    if f["status"] == "error":
                        f["status"] = "queued"
                        f["error"] = None
                RUNNING["value"] = True
            threading.Thread(target=_worker, daemon=True).start()
            log(f"start: {len(queued)} файлов")
            self._json(200, {"started": len(queued)})
            return

        if path == "/api/clear":
            with LOCK:
                FILES.clear()
                RUNNING["value"] = False
            _reset_dirs()
            self._json(200, {"ok": True})
            return

        self.send_error(404, "not found")


def main() -> int:
    ap = argparse.ArgumentParser(description="DoctorHide GUI")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    _reset_dirs()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"DoctorHide GUI: http://{args.host}:{args.port}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
