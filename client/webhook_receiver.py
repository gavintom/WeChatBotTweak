#!/usr/bin/env python3
# webhook_receiver.py - Webhook 接收端示例
# 在插件上执行: curl -X POST http://<手机IP>:18888/api/webhook -d '{"url":"http://<电脑IP>:9000/wx"}'
# 之后每条新消息(文字/语音/图片/视频等全部类型)都会实时 POST 到这里。
# 媒体消息带 mediaApi 字段, 本示例演示收到媒体后回连插件把文件拉下来。

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.request

PHONE = "http://<DEVICE_IP>:18888"     # 手机(插件)地址；<DEVICE_IP> 为占位符，请替换为设备实际 IP
TOKEN = ""                              # 与设置页中的访问令牌一致
SAVE_DIR = "media"                      # 媒体保存目录


def download_media(msg, api_key="mediaApi", file_ext=None):
    import os
    os.makedirs(SAVE_DIR, exist_ok=True)
    url = PHONE + msg[api_key]
    req = urllib.request.Request(url)
    if TOKEN:
        req.add_header("X-Token", TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        ext = file_ext or {"image": "jpg", "voice": "silk", "video": "mp4"}.get(msg["typeName"], "bin")
        path = f"{SAVE_DIR}/{msg['localID']}.{ext}"
        with open(path, "wb") as f:
            f.write(data)
        return path
    except Exception as e:
        return f"(下载失败: {e})"


class Handler(BaseHTTPRequestHandler):
    def _reply_ok(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        # webhook 只收消息; 仅当主动把 alertPushUrl 配成同一地址时才会看到告警
        if body.get("alert"):
            print(f"[alert] {body.get('alert')}: {body.get('body', '')}")
            self._reply_ok()
            return

        name = body.get("senderName") or body.get("sender")
        t = body.get("typeName")

        if t == "text":
            print(f"[{body.get('chat')}] {name}: {body.get('text') or body.get('content')}")
        elif t in ("image", "voice", "video") and body.get("mediaApi"):
            saved = download_media(body)
            print(f"[{body.get('chat')}] {name}: <{t}> -> {saved}")
        elif body.get("fileApi"):
            saved = download_media(body, api_key="fileApi",
                                   file_ext=body.get("fileExt") or "bin")
            print(f"[{body.get('chat')}] {name}: <file> {body.get('content', '')[:60]} -> {saved}")
        else:
            print(f"[{body.get('chat')}] {name}: <{t}> {body.get('content', '')[:120]}")

        self._reply_ok()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("listening on 0.0.0.0:9000, all POST paths accepted")
    HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
