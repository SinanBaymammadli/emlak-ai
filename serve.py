#!/usr/bin/env python3"""Serve the frontend locally at http://localhost:8000"""
import http.server
import socketserver
import webbrowser

PORT = 8000

handler = http.server.SimpleHTTPRequestHandler
handler.extensions_map.update({".js": "application/javascript"})

with socketserver.TCPServer(("", PORT), handler) as httpd:
    url = f"http://localhost:{PORT}"
    print(f"Serving at {url}  (Ctrl+C to stop)")
    webbrowser.open(url)
    httpd.serve_forever()
