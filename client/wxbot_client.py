#!/usr/bin/env python3
# wxbot_client.py - WeChatBot 插件的外部客户端示例
# 支持: 群列表 / 拉取消息 / 发送文字、图片、语音、视频 / webhook 设置 / 媒体下载
# 用法示例见文件底部的 demo()

import base64
import json
import time
import uuid
import urllib.request
import urllib.parse


class WeChatBotClient:
    def __init__(self, host="<DEVICE_IP>", port=18888, token=""):
        """host 填手机的局域网 IP（<DEVICE_IP> 为占位符，请替换为实际地址）; token 与设置页中的访问令牌一致(未配置则留空)"""
        self.base = f"http://{host}:{port}"
        self.token = token

    # request_id: 写操作幂等键。重试时把第一次响应里的 requestId 原样带回,
    # 服务端就不会再次投递动作(409 / deduped:true)。放在 header 里, 大 body 也生效。
    def _req(self, method, path, params=None, body=None, raw=False, request_id=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("X-Token", self.token)
        if request_id:
            req.add_header("X-Request-Id", str(request_id))
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            if raw:
                return content, resp.headers.get("Content-Type", "")
            return json.loads(content.decode("utf-8"))

    @staticmethod
    def new_request_id():
        """生成一个幂等键; 写操作前先生成, 超时/失败重试时复用同一个。"""
        return str(uuid.uuid4())

    # ---------- 基础 ----------

    # 健康检查: 插件是否加载、微信是否就绪、各发送接口是否适配
    def health(self):
        return self._req("GET", "/api/health")

    # 获取群列表 [{wxid, name, uiClass, memberCount, ...}, ...]
    def groups(self):
        return self._req("GET", "/api/contacts/groups")["groups"]

    # 全量通讯录相关接口（v2）
    def contacts_refresh(self, force=False):
        path = "/api/contacts/refresh" + ("?force=1" if force else "")
        return self._req("GET", path)

    def friends(self, wxid="", name=""):
        q = "&".join(k + "=" + urllib.parse.quote(v) for k, v in
                     (("wxid", wxid), ("name", name)) if v)
        return self._req("GET", "/api/contacts/friends" + ("?" + q if q else ""))

    def find(self, wxid="", name=""):
        q = "&".join(k + "=" + urllib.parse.quote(v) for k, v in
                     (("wxid", wxid), ("name", name)) if v)
        return self._req("GET", "/api/contacts/find" + ("?" + q if q else ""))

    def group_members(self, chat, wxid="", name=""):
        q = "&".join(k + "=" + urllib.parse.quote(v) for k, v in
                     (("chat", chat), ("wxid", wxid), ("name", name)) if v)
        return self._req("GET", "/api/contacts/groupmember?" + q)

    # 获取某个群(或私聊)最近消息, limit 最大 500
    # 媒体消息的 content 为 XML, 并带有 mediaApi 字段, 用 download_media 拉取二进制
    def messages(self, chat_wxid, limit=50):
        return self._req("GET", "/api/messages",
                         {"chat": chat_wxid, "limit": limit})["messages"]

    # ---------- 发送 ----------

    # 发送文本, at 可选 @某人 的 wxid 列表
    # request_id: 幂等键, 超时/失败重试时复用同一个, 避免重复发消息
    def send(self, chat_wxid, text, at=None, request_id=None):
        body = {"chat": chat_wxid, "text": text}
        if at:
            body["at"] = at
        return self._req("POST", "/api/send/text", body=body,
                         request_id=request_id)

    # 发送图片: file_path 为本机图片路径(jpg/png)
    def send_image(self, chat_wxid, file_path, request_id=None):
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return self._req("POST", "/api/send/image",
                         body={"chat": chat_wxid, "image": b64},
                         request_id=request_id)

    # 发送语音: file_path 为本机 silk/amr 音频路径
    #   fmt/duration 不传时交给服务端自动识别容器与默认 1 秒;
    #   显式传 fmt: 4=silk 0=amr, duration 为时长秒(聊天页气泡显示)
    def send_voice(self, chat_wxid, file_path, fmt=None, duration=None,
                   request_id=None):
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        body = {"chat": chat_wxid, "voice": b64}
        if fmt is not None:
            body["format"] = fmt
        if duration is not None:
            body["duration"] = duration
        return self._req("POST", "/api/send/voice", body=body,
                         request_id=request_id)

    # 发送视频: file_path 为本机 mp4 路径
    def send_video(self, chat_wxid, file_path, request_id=None):
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return self._req("POST", "/api/send/video",
                         body={"chat": chat_wxid, "video": b64},
                         request_id=request_id)

    # ---------- 媒体下载 ----------

    # 下载某条媒体消息的二进制内容, 保存到 save_path
    # msg 为 messages() 返回中带 mediaApi 字段的消息
    def download_media(self, msg, save_path):
        api = msg.get("mediaApi")
        if not api:
            raise ValueError("该消息不是媒体消息(无 mediaApi)")
        content, mime = self._req("GET", api, raw=True)
        with open(save_path, "wb") as f:
            f.write(content)
        return save_path, mime

    # ---------- 朋友圈 (v3: 无状态读) ----------

    # gethead 重置到最新并返回整批; getnext 追加一页并返回新增区间 + atEnd。
    # 插件不缓存数据, 调用方自行累积 moments[]。
    def moments_timeline_gethead(self, limit=0, media=True):
        return self._req("GET", "/api/moments/timeline/gethead",
                         params={"limit": limit, "media": "1" if media else "0"})

    def moments_timeline_getnext(self, limit=0, media=True):
        return self._req("GET", "/api/moments/timeline/getnext",
                         params={"limit": limit, "media": "1" if media else "0"})

    def moments_user_gethead(self, user, limit=0, media=True):
        return self._req("GET", "/api/moments/user/gethead",
                         params={"user": user, "limit": limit,
                                 "media": "1" if media else "0"})

    def moments_user_getnext(self, user, limit=0, media=True):
        return self._req("GET", "/api/moments/user/getnext",
                         params={"user": user, "limit": limit,
                                 "media": "1" if media else "0"})


    # 朋友圈图片/视频: info=True 返回元信息字典, 否则返回 (bytes, mime)
    def moments_media(self, tid, index=0, info=False, original=True, save_path=None):
        params = {"tid": tid, "index": index,
                  "original": "1" if original else "0"}
        if info:
            params["info"] = "1"
            return self._req("GET", "/api/moments/media", params=params)
        content, mime = self._req("GET", "/api/moments/media", params=params, raw=True)
        if save_path:
            with open(save_path, "wb") as f:
                f.write(content)
        return content, mime

    # 四个写接口都是真实社交动作: 传 request_id 后, 超时重试不会重复执行。
    # 用法: rid = c.new_request_id(); c.moments_like(tid, request_id=rid)
    def moments_like(self, tid, dry_run=False, request_id=None):
        return self._req("POST", "/api/moments/like",
                         body={"tid": tid, "dryRun": 1 if dry_run else 0},
                         request_id=request_id)

    def moments_unlike(self, tid, dry_run=False, request_id=None):
        return self._req("POST", "/api/moments/unlike",
                         body={"tid": tid, "dryRun": 1 if dry_run else 0},
                         request_id=request_id)

    def moments_comment(self, tid, content, dry_run=False, request_id=None):
        return self._req("POST", "/api/moments/comment",
                         body={"tid": tid, "content": content,
                               "dryRun": 1 if dry_run else 0},
                         request_id=request_id)

    # 删除本人评论: 先 dry_run=True 拿 candidates[] 里的 commentId, 再精确删。
    # comment_id / content 都不传时删本人最新一条评论。
    def moments_rm_comment(self, tid, comment_id=None, content=None,
                           dry_run=False, request_id=None):
        body = {"tid": tid, "dryRun": 1 if dry_run else 0}
        if comment_id:
            body["commentId"] = comment_id
        if content:
            body["content"] = content
        return self._req("POST", "/api/moments/rm_comment", body=body,
                         request_id=request_id)

    # ---------- webhook ----------

    # 设置 webhook: 新消息(文字/语音/图片/视频等全部类型)实时 POST 到该 url (传空串清除)
    def set_webhook(self, url):
        return self._req("POST", "/api/webhook", body={"url": url})

    # ---------- 轮询 ----------

    # 轮询方式持续获取某个群的增量消息
    def poll_group(self, chat_wxid, on_message, interval=2.0):
        seen = set()
        while True:
            for m in self.messages(chat_wxid, limit=50):
                key = (m.get("localID"), m.get("ts"), m.get("content", "")[:32])
                if key not in seen:
                    seen.add(key)
                    on_message(m)
            time.sleep(interval)


def demo():
    bot = WeChatBotClient(host="<DEVICE_IP>", port=18888, token="")

    print("health:", bot.health())

    groups = bot.groups()
    print("groups:", json.dumps(groups, ensure_ascii=False, indent=2))
    if not groups:
        return

    gid = groups[0]["wxid"]

    print("recent messages of", gid)
    msgs = bot.messages(gid, limit=10)
    print(json.dumps(msgs, ensure_ascii=False, indent=2))

    # 下载最近一条媒体消息
    for m in reversed(msgs):
        if m.get("mediaApi"):
            path = f"media_{m['localID']}"
            print("download:", bot.download_media(m, path))
            break

    print("send text:", bot.send(gid, "你好, 这是外部程序发来的消息"))
    # print("send image:", bot.send_image(gid, "test.jpg"))
    # print("send voice:", bot.send_voice(gid, "test.silk", fmt=4, duration=3))
    # print("send video:", bot.send_video(gid, "test.mp4"))

    # 轮询监听(阻塞):
    # bot.poll_group(gid, lambda m: print("new:", m["sender"], m["typeName"], m["content"][:80]))


if __name__ == "__main__":
    demo()
