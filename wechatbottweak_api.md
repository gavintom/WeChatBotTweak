# WeChatBotTweak HTTP API

适用版本：v1.2.9（2026-11-17）

本文档描述 WeChatBotTweak 对外提供的 HTTP 接口。所有示例中的地址、令牌与 ID 均为占位符，请替换为实际值。

---

## 1. 快速开始

```bash
BASE="http://<DEVICE_IP>:18888"     # 替换为设备实际 IP
TOKEN="<YOUR_TOKEN>"                # 在设置页或配置中查看

# 健康检查（只读，GET）
curl -s -H "X-Token: $TOKEN" "$BASE/api/health"

# 列出会话
curl -s -H "X-Token: $TOKEN" "$BASE/api/chats"

# 发送文本（写操作，POST）
curl -s -X POST "$BASE/api/send/text" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"你好"}'

# 读取最新朋友圈
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/timeline/gethead"
```

---

## 2. 通用约定

| 项 | 说明 |
| --- | --- |
| 基址 | `http://<设备IP>:18888`，默认端口 `18888` |
| 编码 | 请求与响应均为 UTF-8 JSON；`POST` 必须带 `Content-Type: application/json` |
| 鉴权 | 配置了令牌时校验请求头 `X-Token`，也可通过 `?token=` 传递；不匹配返回 `401`。建议只用请求头，避免令牌出现在访问日志中 |
| `chat` 参数 | 会话 ID：群会话通常以 `@chatroom` 结尾，私聊与公众号为对应账号 ID。会话 ID 从 `/api/chats` 或通讯录接口获取 |
| 布尔参数 | 只接受 `0` / `1`（数字）或 `"0"` / `"1"` / `"true"` / `"false"`（字符串）。会产生真实动作的写接口对非法值直接返回 `400`；只读参数（如 `ads` / `media`）非法值回落该参数默认值 |
| 请求体 | 所有 `POST` 的 body 必须是 JSON object，字段类型不符返回 `400` |
| 错误格式 | 统一 `{"ok":false,"error":"..."}`，部分错误附带 `hint` |
| HTTP 状态码 | `200` 成功、`400` 参数错误、`401` 鉴权失败、`403` 权限不足、`404` 资源不存在、`409` 重复请求、`413` 内容过大、`500` 服务异常、`502` 上游资源不可用、`503` 结果不确定 |
| 安全建议 | 本服务仅供受信任的局域网或转发通道内使用，**不要将端口暴露到公网** |

### 2.1 写操作与幂等重试

发送、点赞、评论、删除评论、设置群公告等写接口支持用 `requestId` 标识一次操作，避免网络超时后重试造成重复动作。

| 项 | 规则 |
| --- | --- |
| `requestId` | 可选。放在 POST body 的 `requestId` 字段，或用 `X-Request-Id` 请求头；不传时服务端生成并在响应中返回。请求体较大（base64 媒体）时请使用请求头 |
| `state` | 写操作响应中返回：`done`（已完成）、`canceled`（确定未执行）、`uncertain`（结果不确定） |
| `503` + `state=canceled` | 动作确定没有执行，可携带**同一个** `requestId` 安全重试 |
| `503` + `state=uncertain` | 动作可能已发出。**禁止盲目重试**，应先用读接口核查；确认未生效后换一个新的 `requestId` |
| `409` | 同一 `requestId` 正在执行，或上一次结果不确定；请求被拒绝，不会重复执行动作 |
| `deduped:true` | 同一 `requestId` 已完成，直接回显上次结果，不执行任何动作 |

> 不带 `requestId` 的重复请求不会被去重。「点赞 → 取消赞 → 点赞」和连续发送两条相同内容都是合法操作。需要安全重试时，请保存首次响应中的 `requestId` 并在重试时原样带回。

### 2.2 curl 示例约定

本文所有接口示例写法一致，复制后只需替换 `<...>` 占位符即可运行：

| 项 | 约定 |
| --- | --- |
| 变量 | 只引用第 1 章定义的 `$BASE`（基址）与 `$TOKEN`（令牌），示例中不出现写死的 IP 或令牌 |
| 请求头 | 令牌恒为 `-H "X-Token: $TOKEN"`，并且**排在第一个**；`POST` 再跟 `-H "Content-Type: application/json"` |
| 位置 | `GET` 写成 `curl -s -H "X-Token: $TOKEN" "$BASE/路径"`；`POST` 写成 `curl -s -X POST "$BASE/路径"` 后跟请求头。URL 一律用双引号包住，查询参数直接拼在 URL 上 |
| 请求体 | body 用单引号包住 JSON，`-d` 放在命令**最后**；体积较大时改用 `-d @payload.json` 从文件读取 |
| 下载 | 返回二进制的接口在命令末尾加 `-o <文件名>` |
| 输出 | 统一 `curl -s`（不打印进度，响应体本身即 JSON）；需要格式化输出时可自行在末尾追加 `| jq .` |

---

## 3. 接口总览

共 **30 个接口路径 / 34 个 GET·POST 路由**。

| 分类 | 接口 |
| --- | --- |
| 状态与配置（5 / 7） | `GET /api/health`、`GET\|POST /api/webhook`、`GET\|POST /api/alert`、`GET /api/license`、`POST /api/activate` |
| 通讯录（5 / 6） | `GET\|POST /api/contacts/refresh`、`GET /api/contacts/groups`、`GET /api/contacts/groupmember`、`GET /api/contacts/friends`、`GET /api/contacts/find` |
| 会话与消息（4） | `GET /api/chats`、`GET /api/messages`、`GET /api/media`、`GET /api/file` |
| 发送（6） | `POST /api/send/text`、`/quote`、`/image`、`/voice`、`/video`、`/file` |
| 群公告（1 / 2） | `GET\|POST /api/group/announcement` |
| 朋友圈时间线（2） | `GET /api/moments/timeline/gethead`、`/getnext` |
| 好友朋友圈主页（2） | `GET /api/moments/user/gethead`、`/getnext` |
| 朋友圈媒体（1） | `GET /api/moments/media` |
| 朋友圈写操作（4） | `POST /api/moments/like`、`/unlike`、`/comment`、`/rm_comment` |

---

## 4. 状态与配置

### 4.1 `GET /api/health` — 健康检查

无参数。

| 字段 | 说明 |
| --- | --- |
| `ok` | 恒为 `true` |
| `version` | 服务版本 |
| `port` | 当前监听端口 |
| `wechatReady` | 微信环境是否就绪 |
| `self` | 当前登录账号 ID |
| `runtime` | object，运行状态；其中 `listening` 表示 HTTP 服务是否在监听 |
| `webhook` / `alertPushUrl` | 当前配置的两个推送地址 |
| `autoDownloadMedia` / `keepAlive` | 相关功能开关状态 |

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/health"
```

### 4.2 `GET|POST /api/webhook` — 消息推送地址

`GET` 返回当前配置：

```json
{"ok":true,"webhook":"<URL>","alertPushUrl":"<URL>"}
```

`POST` 设置或清除地址：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `url` | string | 接收新消息推送的地址。省略、空串或纯空白表示清除，清除后不再推送 |

```bash
# 查询当前地址
curl -s -H "X-Token: $TOKEN" "$BASE/api/webhook"

# 设置地址
curl -s -X POST "$BASE/api/webhook" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/messages"}'
```

### 4.3 `GET|POST /api/alert` — 告警推送地址

告警与消息推送相互独立；告警只发往此处配置的地址，地址为空时只保留设备本地通知，不会改发到消息推送地址。

`GET` 返回 `ok`、`alertPushUrl`、`networkAlertEnabled`、`webhook`。

`POST` 参数：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `url` 或 `alertPushUrl` | string | 告警接收地址，省略或空串表示清除（两者同时传入时以 `url` 为准） |
| `test` | bool | `1` 时向新地址发送一条测试告警，不阻塞响应 |

```bash
# 查询当前地址
curl -s -H "X-Token: $TOKEN" "$BASE/api/alert"

# 设置地址并发一条测试告警
curl -s -X POST "$BASE/api/alert" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/alerts","test":1}'
```

### 4.4 `GET /api/license` — 授权状态

无参数。

| 字段 | 说明 |
| --- | --- |
| `ok` | 恒为 `true` |
| `state` | `trial` 试用 / `active` 已激活 / `expired` 已过期 / `invalid` 激活码无效 |
| `valid` | 当前是否允许使用服务 |
| `user` | 授权用户 |
| `install` | 首次使用日期 |
| `activated` | 激活日期 |
| `expire` | 有效期截止日 |
| `daysLeft` | 剩余天数，负数表示已过期 |
| `hasCode` | 是否已设置激活码 |
| `machine` | 本机设备标识 |
| `version` | 服务版本 |

> 授权失效时 HTTP 服务会停止，需在设置页重新激活。未激活时可在试用期内使用。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/license"
```

### 4.5 `POST /api/activate` — 设置或清除激活码

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `code` | string | 否 | 激活码；空串或省略表示清除当前激活码 |
| `dryRun` | bool | 否 | `1` 只校验激活码，不写入、不改变当前状态 |

激活码与设备绑定，仅适用于签发时指定的设备。响应为 4.4 的授权状态结构；校验失败返回 `400` 并带错误说明。

```bash
# 只校验激活码，不写入
curl -s -X POST "$BASE/api/activate" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"<CODE>","dryRun":1}'

# 正式写入绑定
curl -s -X POST "$BASE/api/activate" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"<CODE>"}'
```

---

## 5. 事件推送（接收侧）

配置地址后，服务以 `HTTP POST` + `Content-Type: application/json` 推送事件。未配置地址时整条链路跳过。推送失败不重试、不排队；消息本身仍可通过 `/api/messages` 补拉。

| 事件 | 使用的地址 |
| --- | --- |
| 新消息（含本机发出的） | `/api/webhook` 配置的地址 |
| 服务掉线、授权提醒、地址测试 | `/api/alert` 配置的地址 |

消息推送一次只含 **1 条**完整消息；接口发送出去的消息也走同一条链路，不会再额外推送发送确认。

### 5.1 新消息字段

| 字段 | 说明 |
| --- | --- |
| `ts` | 时间戳（秒） |
| `chat` | 会话 ID |
| `sender` / `senderName` | 发送者 ID 与显示名 |
| `chatType` / `chatName` / `isGroup` | 会话类型、名称、是否群聊 |
| `direction` / `outgoing` | `in` 收到 / `out` 发出 |
| `type` / `typeName` | 消息类型码与名称：`1` 文本、`3` 图片、`34` 语音、`43` 视频、`49` 应用消息 |
| `content` | 原始内容（可能是整段 XML） |
| `text` | 清洗后可直接使用的正文 |
| `localID` | 消息本地 ID，用于 `/api/media`、`/api/file` 与引用回复 |
| `mediaApi` | 媒体下载地址（媒体消息） |
| `isAt` / `atList` / `atMe` / `atAll` / `atNames` | 群 @ 结构化字段 |
| `appType` | 应用消息细分：`file`、`link`、`quote`、`music`、`miniapp` 等 |
| `appSubType` / `appId` / `appName` | 应用消息附加标识 |
| `fileName` / `fileSize` / `fileExt` / `fileMd5` | 文件消息元信息 |
| `fileState` / `fileApi` / `fileInfoApi` | 文件状态与下载地址 |
| `title` / `desc` / `url` | 链接与卡片标题、描述、跳转地址 |
| `coverUrl` / `thumbUrl` | 封面与缩略图地址 |

> 只有服务运行期间捕获到的消息会推送，不是微信全量历史。开启自动下载媒体后，新收到的图片、视频与文件会异步下载，随后可用对应接口回读。

### 5.2 告警字段

带 `alert` 字段即为告警，`title` / `body` / `ts` 为通用字段。

| `alert` | 触发条件 | 额外字段 |
| --- | --- | --- |
| `background_offline` | 服务监听中断、后台额度被系统拒绝 | `port`、`offlineCount` |
| `alert_config_test` | 配置告警地址时带 `test=1` | 无 |
| `license_expiring` | 授权到期前提醒 | `daysLeft` |
| `license_expired` | 授权已过期或激活码无效，同时停止服务 | `daysLeft` |

---

## 6. 通讯录接口

通讯录数据为一份快照，只有 `refresh` 会重建；其余接口均为只读查询，不产生任何社交动作。

### 6.1 `GET|POST /api/contacts/refresh` — 重建通讯录

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `force` | `0` | `1` 或 `true` 时绕过 60 秒限流立即重建 |

默认 60 秒限流：距上次构建不足 60 秒时不会重扫，返回 `throttled=true`、`reused=true`、`retryAfter=<秒>`，并照常回显当前 `total` / `classes`。**成功只返回数量与分类汇总，不返回联系人明细。**

```json
{
  "ok": true, "throttled": false, "total": 10,
  "classes": {"friend": 5, "group": 3, "officialAccount": 2},
  "elapsedMs": 120
}
```

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/refresh"
curl -s -X POST "$BASE/api/contacts/refresh?force=1" -H "X-Token: $TOKEN"
```

### 6.2 `GET /api/contacts/groups` — 所有群聊

无参数。返回全量中 `uiClass=group` 的条目，每条含 `memberCount`。

```json
{"ok":true,"count":1,"groups":[{"wxid":"<CHAT_ID>","name":"示例群",
 "uiClass":"group","isGroup":true,"memberCount":12}]}
```

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/groups"
```

### 6.3 `GET /api/contacts/groupmember` — 群成员 / 反查成员

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `chat` | 是 | 群会话 ID |
| `wxid` | 否 | 传了进入精确反查模式 |
| `name` | 否 | 传了进入反查模式（先精确后模糊） |

列表模式返回 `ok`、`chat`、`groupName`、`owner`、`self`、`isOwner`、`count`、`memberCount`、`members[]`。`members[]` 每项含 `wxid`、`name`、`nickName`、`remark`、`groupNick`、`displayName`、`isSelf`、`isOwner`、`uiClass`、`avatar`（有值才出现）。`displayName` 优先取群名片，否则取全局显示名。

反查模式返回 6.6 的统一结构，并额外带 `chat` / `groupName` / `owner` / `isOwner` / `memberCount`；此时 `count` 是匹配数，成员总数在 `memberCount`。

错误：缺 `chat` → `400`；非群会话 → `404 not a group chat`；找不到该群 → `404 group not found`。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/groupmember?chat=<CHAT_ID>"
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/groupmember?chat=<CHAT_ID>&name=<NAME>"
```

### 6.4 `GET /api/contacts/friends` — 好友明细 / 反查好友

无参数时返回全部好友（含自己）：`{ok, count, friends[]}`。传 `wxid` 或 `name` 时只在好友范围内反查，返回 6.6 的统一结构。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/friends"
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/friends?name=<NAME>"
```

### 6.5 `GET /api/contacts/find` — 全量反查用户

| 参数 | 说明 |
| --- | --- |
| `wxid` | 精确查一条 |
| `name` | 先精确后模糊（不区分大小写） |

在全量通讯录中查询，可查到群成员、公众号等。两个参数至少传一个，都不传 → `400 need wxid or name`。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/find?wxid=<WXID>"
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/find?name=<NAME>"
```

### 6.6 统一反查结构与联系人字段

`friends`、`groupmember`、`find` 的反查模式一律返回：

```json
{"ok":true,"mode":"byName","query":"<NAME>","exact":true,
 "count":1,"truncated":false,
 "matches":[{"wxid":"<WXID>","name":"示例用户","uiClass":"friend"}]}
```

- `mode` = `byWxid`（精确）或 `byName`；`exact=true` 表示有精确命中。
- 匹配字段：`name` / `nickName` / `remark` / `alias` / `wxid`；群成员反查额外包含 `displayName`。
- 找不到不是错误：`ok=true`、`count=0`、`matches=[]`。
- 模糊结果上限 200 条，超出时 `truncated=true`。

联系人条目字段：

| 字段 | 说明 |
| --- | --- |
| `wxid` | 账号 ID |
| `name` | 显示名（备注 > 昵称 > ID） |
| `nickName` / `remark` | 昵称 / 备注 |
| `uiClass` | 分类：`friend` / `group` / `officialAccount` / `enterpriseContact` / `enterpriseRelated` / `myEnterpriseMember` / `plugin` / `builtinService` / `migrated` / `stranger` |
| `isFriend` / `isGroup` / `isSelf` | 布尔快捷标记 |
| `memberCount` | 仅群：本地缓存的成员数 |
| `alias` / `avatar` / `signature` / `certification` / `sex` | 有值才出现 |

> `uiClass=stranger` 表示缓存中的群成员或陌生人，不等于好友；好友数通常远小于通讯录总数。

### 6.7 典型调用顺序

```bash
# 1) 微信刚启动或通讯录有变动后刷新一次（60 秒内重复调用会被限流）
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/refresh"

# 2) 拿群与好友
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/groups"
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/friends"

# 3) 按名字 / ID 查人，或查群成员
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/find?name=<NAME>"
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/groupmember?chat=<CHAT_ID>"
```

---

## 7. 会话、消息与媒体接口

### 7.1 `GET /api/chats` — 会话列表

无参数。返回 `{"ok":true,"count":N,"chats":[...]}`，按 `lastTs` 降序排列。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `wxid` | string | 会话 ID |
| `name` | string | 显示名 |
| `type` | string | `group` / `private` / `official` / `service` |
| `isGroup` | bool | 是否群聊 |
| `messageCount` | int | 本服务缓存的消息条数，**不是微信历史总数**；仅来自会话列表的条目为 `0` |
| `lastTs` | int | 最后一条消息时间戳（秒），无缓存消息为 `0` |
| `lastType` | int | 最后一条消息类型，无消息为 `0` |
| `lastContent` | string | 原始内容，可能是整段 XML；取正文请用 `/api/messages` 的 `text` |
| `lastOutgoing` | bool | 最后一条是否本机发出 |
| `observed` | bool | 是否观察到过该会话的消息 |
| `inSessionList` | bool | 是否出现在微信会话列表中 |

未知 query 参数会被忽略。需要全量联系人与分类请使用第 6 章接口。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/chats"
```

### 7.2 `GET /api/messages` — 读取消息

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `chat` | string | 否 | 不传则跨会话返回全部消息，按时间升序 |
| `limit` | int | 否 | 默认 `50`；`<=0`、非数字或 `>500` 一律回落到 `50` |

响应 `{"ok":true,"chat":"...","messages":[...]}`；跨会话时 `chat:"*"`、`scope:"all"`。`messages[]` 字段与 5.1 的消息字段一致。

> 只包含服务运行期间捕获到的消息，不是微信全量历史。单会话最多返回最近 500 条；建议显式指定 `chat`，跨会话查询会话很多时开销较大。消息写入为异步，紧跟推送之后的立即查询可能短暂读不到。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/messages?chat=<CHAT_ID>&limit=20"
```

### 7.3 `GET /api/media` — 下载收到的媒体

返回媒体**二进制**（非 JSON），`Content-Type` 按文件内容判定。

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `chat` | string | 是 | 会话 ID |
| `localID` | int | 是 | 消息本地 ID（只在单个会话内唯一） |
| `info` | 0/1 | 否 | `1` 只返回元信息 JSON（不含二进制）：画质档位、分辨率、字节数、内容类型 |

- 只支持图片、语音、视频消息；其它类型 → `404`。
- 缺参数或 `localID=0` → `400 missing chat/localID`。
- **媒体尚未下载到本机时，服务端会先自动触发下载并等待最多数秒**；通常一次请求即可拿到文件，无需在微信中手动点开、也无需重试。仅当确实下载不到时才返回 `404 media not found locally`。这一兜底同样覆盖插件重启前的历史消息与后台期间收到的消息。
- 他人发送的媒体同样可获取。图片按画质逐级返回：发过原图时给无损原图；没有原图时服务端会先自动补齐清晰版本，**不会只剩几乎看不清的缩略图**；再退一步还有较清晰的预览图，最后才是缩略图。**视频不会用封面图冒充**：只找到封面时按失败处理，不会返回 `200` 加一张图片。
- `info=1` 返回 `ok`、`tier`（`original` 原图 / `middle` 清晰图 / `preview` 预览图 / `thumb` 缩略图）、`width` / `height`、`bytes`、`mime`、`ext`。客户端可据此判断画质，无需靠文件大小猜测。
- 请不要并发拉取多个大体积视频。

```bash
# 取二进制
curl -s -H "X-Token: $TOKEN" \
  "$BASE/api/media?chat=<CHAT_ID>&localID=<LOCAL_ID>" -o media.bin

# 只看元信息（JSON）
curl -s -H "X-Token: $TOKEN" \
  "$BASE/api/media?chat=<CHAT_ID>&localID=<LOCAL_ID>&info=1"
```

### 7.4 `GET /api/file` — 下载收到的文件

取回文件消息（应用消息中的文件类型）的原始字节或元信息。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `chat` | 是 | 会话 ID |
| `localID` | 是 | 消息本地 ID |
| `info` | 否 | `1` 时只返回元信息 JSON |

`info=1` 返回 `ok`、`appSubType`、`fileName`、`fileSize`、`fileExt`、`fileMd5`、`fileState`（`ready` / `uploading`）、`fileKey`、`attachId`、`title`、`downloaded`、`downloadApi`。非文件消息返回 `ok:false`。

二进制响应的 `Content-Type` 按扩展名映射，未知回落 `application/octet-stream`。文件尚未下载时返回 `404 file not downloaded locally`，可稍后重试或在微信中打开该文件后再试。

```bash
# 只看元信息（JSON）
curl -s -H "X-Token: $TOKEN" "$BASE/api/file?chat=<CHAT_ID>&localID=<LOCAL_ID>&info=1"

# 取原始字节
curl -s -H "X-Token: $TOKEN" \
  "$BASE/api/file?chat=<CHAT_ID>&localID=<LOCAL_ID>" -o out.bin
```

---

## 8. 朋友圈接口

### 8.1 读接口约定

服务端**不保存动态数据、不维护游标**：`gethead` 重置到最新并返回当前批次，`getnext` 只返回本次新增部分，调用方自行累积 `moments[]`。

| 接口 | 动作 | 返回 |
| --- | --- | --- |
| `GET /api/moments/timeline/gethead` | 重置时间线到最新 | 当前批次 `moments[]` + 数量 |
| `GET /api/moments/timeline/getnext` | 追加时间线一页 | 新增 `moments[]` + 数量 + `atEnd` |
| `GET /api/moments/user/gethead` | 重置指定用户主页到最新 | 当前批次 `moments[]` + 数量 |
| `GET /api/moments/user/getnext` | 追加指定用户主页一页 | 新增 `moments[]` + 数量 + `atEnd` |

通用参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `limit` | `0` | `0` = 返回整批，上限 500 |
| `media` | `1` | `0` 时不展开媒体字段 |
| `ads` | `0` | `0`（默认）跳过信息流广告；`1` 全部返回，见下 |
| `user` | — | 仅 `user/*` 接口，**必填**，取值来自 `moments[].username` |

- 读接口不限流，可连续逐页调用。
- 每条 `moments[]` 都带 `likes[]` / `comments[]`（无数据时为空数组）和 `isAd`，与 `media` 参数无关。
- 响应共有字段：`ok`、`action`、`count`（**过滤后**本次条数）、`total`（当前累计条数，**未过滤**）、`moments[]`、`includeAds`、`adsSkipped`、`waitedMs`、`elapsedMs`；`gethead` 另有 `resetFrom` / `added`，`getnext` 另有 `from` / `added` / `atEnd` / `stopReason`。
- `atEnd=true` 且 `count=0` 表示已到末尾，应停止翻页。`stopReason` 取值 `pageLoaded` / `noMore` / `emptyCache`。
- 想查看最新动态时重新调用 `gethead`。

**跳过信息流广告（默认开启）**

信息流广告不是普通用户动态，其图片 / 视频走专用通道，下载接口通常拿不到可用内容。服务端默认把这类动态直接从 `moments[]` 剔除，也不会为它们预热下载。

| 项 | 说明 |
| --- | --- |
| `ads=0` | 默认值。`adsSkipped` 返回本次跳过的条数 |
| `ads=1` | 全部返回，可用每条的 `isAd` 自行处理 |
| `isAd` | 每条动态恒定返回 `true` / `false` |
| `includeAds` | 响应回显本次开关 |
| `total` / `from` / `added` | 仍是服务端原始条数与区间（**未过滤**），翻页逻辑不变 |
| `limit` | 限制本次扫描的区间长度，**不是**「返回 N 条非广告」 |

- 若某页 `count=0` 但 `atEnd=false`，说明该页全部是广告，应继续翻页，不要提前停止。
- 企业微信 / 公众号营销账号发布的内容属于正常动态，**不在默认过滤范围**；如需按作者过滤，请按 `moments[].username` 自行判断。
- 下文各读接口的响应示例省略了 `includeAds` / `adsSkipped`（示例均为 `false` / `0`）。

**写接口共性（8.7~8.10）**：四个接口都是 `POST` + JSON body，且都是**真实社交动作**（会通知对方），评论与删除评论不可撤回。请务必先用 `dryRun=1` 预演。`tid` 取自 `moments[].tid`，需先用读接口装载；时间线与用户主页的动态都支持，无需额外传 `user`。错误：缺 `tid` → `400`，`tid` 未装载 → `404`，无令牌 → `401`。重试规则见 2.1。

### 8.2 `GET /api/moments/timeline/gethead`

无必填参数。返回时间线最新批次（通常 10 条）。

```json
{
  "ok": true, "action": "timeline/gethead",
  "count": 10, "total": 10, "resetFrom": 0, "added": 10,
  "atEnd": false, "moments": [],
  "waitedMs": 1600, "elapsedMs": 1699
}
```

> 示例中 `moments[]` 的数组内容已省略，元素结构见 8.11。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/timeline/gethead?media=0"
```

### 8.3 `GET /api/moments/timeline/getnext`

无必填参数。只返回新增区间 `[from, total)`。

```json
{
  "ok": true, "action": "timeline/getnext",
  "count": 40, "total": 50, "from": 10, "added": 40,
  "atEnd": false, "stopReason": "pageLoaded", "moments": [],
  "waitedMs": 400, "elapsedMs": 477
}
```

> 示例中 `moments[]` 的数组内容已省略，元素结构见 8.11。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/timeline/getnext?limit=40"
```

### 8.4 `GET /api/moments/user/gethead`

`user` 必填。重置指定用户主页并返回最新批次。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/user/gethead?user=<USER_ID>&media=0"
```

错误：缺 `user` → `400`；服务未就绪 → `500`。

### 8.5 `GET /api/moments/user/getnext`

`user` 必填。追加一页，`atEnd` / `stopReason` 语义与 8.3 一致；从未装载过且本地为空时返回 `stopReason:"emptyCache"`。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/user/getnext?user=<USER_ID>&limit=10"
```

### 8.6 `GET /api/moments/media` — 图片 / 视频下载

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `tid` | 是 | 动态 ID，来自 `moments[].tid` |
| `index` | 否 | 媒体下标，**从 0 起**，默认 `0`；越界返回 `404` |
| `info` | 否 | `1` 返回元信息 JSON，默认返回二进制 |
| `original` | 否 | 默认 `1`，允许触发原图下载；`0` 为纯本地读取，不发网络请求 |

- 二进制响应只含媒体字节；完整探测信息一律用 `info=1` 获取。
- **新发布的动态原图可能尚未就绪**：此时可能只拿到低清预览图，`degraded=true` 会明确提示，稍后重新请求即可。
- **视频**：优先返回可直接播放的标准 mp4，客户端无需在手机上点开、也无需额外准备。极少数新视频首次请求时尚未就绪，`502` 会带 `videoEncrypted` 与明确提示，稍后重新请求即可。`original=0` 为纯本地模式，只读本机已就绪内容，不触发网络获取。

`info=1` 关键字段：

| 字段 | 说明 |
| --- | --- |
| `mediaReady` | `true` = 已拿到可用高清图或视频 |
| `degraded` | `true` = 只拿到低清预览图，不能当作原图使用 |
| `localTier` | `none` / `preview` / `hd` / `sight`（视频已在本机就绪） |
| `source` | 视频取自本机就绪文件时为 `localSight`，取自直链时为 `cdnVideo` |
| `videoEncrypted` | `502` 时为 `true` 表示该视频尚未就绪，稍后重试即可 |
| `sightTrigger` | 本次媒体准备结果；未触发时为 `{}` |
| `placeholderOnly` | 只拿到占位图 |
| `quality` | `original` / `scaled` / `placeholder` |
| `mime` / `bytes` / `width` / `height` | 实际返回内容的类型、字节数与尺寸 |
| `cdnTried` | 本次尝试的下载次数 |
| `mediaType` | 视频时为 `video` |
| `videoDuration` | 视频时长（秒） |

错误：缺 `tid` → `400`；`tid` 未装载或下标越界 → `404`；拿不到可用数据 → `502`（附带明确原因提示）。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/media?tid=<TID>&index=0" -o media.bin
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/media?tid=<TID>&index=0&info=1"
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/media?tid=<TID>&index=0&info=1&original=0"
```

### 8.7 `POST /api/moments/like` — 点赞

**真实社交动作**（会通知对方）。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `tid` | 是 | 动态 ID |
| `dryRun` | 否 | `1` 只返回预演结果，不执行 |

返回 `ok`、`action`、`tid`、`changed`；已赞时 `changed=false` + `reason:"already liked"`（幂等，不会重复点赞）。公共响应字段 `requestId` / `state` 见 2.1。

```bash
curl -s -X POST "$BASE/api/moments/like" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"tid":"<TID>","dryRun":1}'
```

### 8.8 `POST /api/moments/unlike` — 取消点赞

**真实社交动作**。参数与 8.7 相同。返回 `ok`、`action`、`tid`、`changed`；未赞时 `changed=false` + `reason:"not liked yet"`。

```bash
curl -s -X POST "$BASE/api/moments/unlike" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"tid":"<TID>","dryRun":1}'
```

### 8.9 `POST /api/moments/comment` — 发表评论

**真实社交动作，不可撤回**（会通知对方）。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `tid` | 是 | 动态 ID |
| `content` | 是 | 评论正文，去首尾空白后非空、不超过 1000 字 |
| `dryRun` | 否 | `1` 只校验参数，不执行 |

返回 `ok`、`action`、`tid`、`changed`、`confirmed`（`true` 表示已收到网络确认）。重试契约见 2.1；同一 `requestId` 的重复请求不会产生两条相同评论。

错误：缺 / 空 `content` 或超长 → `400`；`tid` 未装载 → `404`；重复 `requestId` → `409`。

```bash
curl -s -X POST "$BASE/api/moments/comment" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"tid":"<TID>","content":"谢谢","dryRun":1}'
```

### 8.10 `POST /api/moments/rm_comment` — 删除本人评论

**真实社交动作，不可撤回**。只删除本人在该动态下的评论，不会误删他人评论。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `tid` | 是 | 动态 ID |
| `commentId` | 否 | 精确匹配评论 ID |
| `content` | 否 | 精确匹配评论正文 |
| `dryRun` | 否 | `1` 回显候选清单，不执行 |

定位优先级 `commentId` > `content` > 不传时删除本人最新一条。建议先 `dryRun=1` 取 `candidates[].commentId`，再带 `commentId` 精确删除。

`dryRun` 返回 `ok`、`dryRun`、`commentCount`、`ownCommentCount`、`candidates[]`、`wouldDelete`、`changed:false`。真实删除返回 `ok`、`action`、`tid`、`changed`、`confirmed`、`deleted`、`commentCountBefore` / `After`。

错误：缺 `tid` → `400`；`tid` 未装载或没有匹配的本人评论 → `404`。

```bash
# 1) 查可删评论（不执行）
curl -s -X POST "$BASE/api/moments/rm_comment" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"tid":"<TID>","dryRun":1}'

# 2) 精确删除
curl -s -X POST "$BASE/api/moments/rm_comment" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"tid":"<TID>","commentId":"<COMMENT_ID>"}'
```

### 8.11 `moments[]` 字段字典

| 分组 | 字段 | 说明 |
| --- | --- | --- |
| 标识 | `tid` | 动态 ID，媒体下载与写操作都用它 |
| 作者 | `username`、`nickname` | `username` 也是 `user/*` 的 `user` 参数 |
| 文字 | `contentDesc` | 正文文字，纯图片动态可能没有 |
| 时间 | `createtime` | 发布时间（Unix 秒） |
| 类型 | `type`、`flag` | 动态类型与标志位 |
| 广告 | `isAd` | **总是返回**：`true` = 信息流广告。默认已从结果中剔除，仅 `ads=1` 时可见 `true`（见 8.1） |
| 互动 | `likeFlag`、`likeCount`、`likeUserCount` | 本人是否已赞、赞数、点赞人数量 |
| 互动 | `commentCount`、`commentUserCount` | 评论数、评论人数量 |
| 互动 | `likes[]`、`comments[]` | 明细数组，**总是返回**，无数据为 `[]` |
| 内容 | `contentType`、`contentTitle`、`contentDescr`、`shareUrl` | 分享类动态的标题、描述与链接 |
| 媒体 | `mediaCount`、`images[]`、`media[]` | 媒体数量、图片直链、完整媒体信息 |

除 `likes[]` / `comments[]` / `isAd` 三个键总是返回外，其余字段**有值才出现**。

`likes[]` / `comments[]` 每项：

| 字段 | 说明 |
| --- | --- |
| `wxid`、`nickname` | 点赞人 / 评论人的 ID 与当时昵称 |
| `createTime` | 时间（Unix 秒） |
| `type` | `1` = 点赞，`2` = 评论 |
| `content`、`commentId` | 仅评论项：正文与评论 ID，`commentId` 可直接用于 8.10 |
| `refWxid` | 仅回复型评论：被回复者 ID |
| `deleted` | `true` 表示该条已被标记删除 |

`media[]` 每项：

| 字段 | 说明 |
| --- | --- |
| `index`、`mid` | 媒体下标与 ID，`index` 是 8.6 的入参（从 0 起） |
| `url`、`thumbUrl`、`previewUrls[]` | 原图直链、缩略图与预览图；外部下载时请勿附加自定义请求头 |
| `mediaApi` | 可直接调用的媒体下载地址 |
| `width` / `height` / `totalSize` | 声明尺寸与大小 |
| `videoDuration`、`type` / `subType` | 视频时长与类型，`type=5` 为视频 |
| `title` / `desc` | 媒体标题与描述 |

---

## 9. 发送接口

所有发送接口的结果都会作为一条消息推送到 webhook（见 5.1），一次发送只有 1 条。`chat` 对应的会话必须能在微信中找到，否则返回 `contact not found`。

### 9.1 `POST /api/send/text` — 文本 / @某人

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `chat` | string | 是 | — | 目标会话 ID |
| `text` | string | 是 | — | 正文（纯正文，**不要**自己写 `@昵称`） |
| `at` | array[string] | 否 | `[]` | 被 @ 的账号 ID 数组 |
| `atNames` | object | 否 | — | `{"<WXID>":"显示名"}`，用于强制覆盖显示名 |
| `atAll` | int | 否 | `0` | `1` 时 @所有人（仅群聊、仅群主/管理员） |
| `dryRun` | int | 否 | `0` | `1` 只回显构造结果，不发送、不通知任何人 |

| `at` | 实际正文 | @ 生效 |
| --- | --- | --- |
| 不传 / 空数组 | 原样 `text` | — |
| 有账号 ID | `@昵称` + 窄空格 + `text` | 是 |
| `atAll=1` | `@所有人` + 窄空格 + `text` | 是（全员提醒） |

- 不传 `atNames` 时会自动取群名片，其次取备注 / 昵称，最后回退到账号 ID。
- `at:["@all"]` 等价于 `atAll=1`。
- `@所有人` 仅群主 / 管理员可用：非群聊 → `400`，非群主 / 管理员 → `403`；**每次都会通知全群**，请先用 `dryRun=1` 预演。
- 响应：`ok`、`atList`、`finalText`、`requestId` / `state`（见 2.1）。

```bash
# 普通文本
curl -s -X POST "$BASE/api/send/text" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"你好"}'

# @ 某人
curl -s -X POST "$BASE/api/send/text" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"请看一下","at":["<WXID>"]}'

# @所有人：先预演，确认后再去掉 dryRun
curl -s -X POST "$BASE/api/send/text" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"今晚 8 点开会","atAll":1,"dryRun":1}'
```

### 9.2 `POST /api/send/quote` — 引用回复

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `chat` | string | 是 | 目标会话 ID |
| `text` | string | 是 | 回复正文（纯正文） |
| `quoteLocalID` | int | 是 | 被引用消息的本地 ID，从 `/api/messages` 取 |
| `at` | array[string] | 否 | 被 @ 的账号 ID 数组，规则同 9.1 |
| `atNames` | object | 否 | 强制覆盖显示名，规则同 9.1 |

响应：`ok`、`quoteLocalID`、`finalText`、`atList`。此接口不支持 `atAll`。错误：缺 `quoteLocalID` → `400`；被引用消息不存在 → `400 quote message not found`。

```bash
curl -s -X POST "$BASE/api/send/quote" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"收到，我看下","quoteLocalID":<LOCAL_ID>,"at":["<WXID>"]}'
```

### 9.3 `POST /api/send/image` — 图片

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `chat` | string | 是 | 目标会话 ID |
| `image` | string(base64) | 二选一 | 图片二进制 base64 |
| `path` | string | 二选一 | 设备上的图片文件路径 |

- 图片上限 **5 MB**（按解码后字节数），超限 → `413`，不落盘、不发送。
- 单个 HTTP 请求体上限 **32 MB**，超限 → `413`。
- 缺两者 → `400`；base64 无法解码或内容为空 → `400`；不是合法图片 → `500 image decode failed`。
- 响应：`ok`、`imageBytes`、`requestId` / `state`。

```bash
# 方式一：设备上的文件路径（推荐，不需要编码，最省请求体）
curl -s -X POST "$BASE/api/send/image" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","path":"/var/mobile/Media/DCIM/photo.jpg"}'

# 方式二：base64 内联（小图）或放进 JSON 文件后用 -d @file 发送（大图）
curl -s -X POST "$BASE/api/send/image" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","image":"<BASE64>"}'

curl -s -X POST "$BASE/api/send/image" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d @image.json
```

### 9.4 `POST /api/send/voice` — 语音

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `chat` | string | 是 | — | 目标会话 ID |
| `voice` | string(base64) | 二选一 | — | 音频二进制 base64（SILK / AMR） |
| `path` | string | 二选一 | — | 设备上的音频文件路径 |
| `format` | int | 否 | 自动识别 | `4` = SILK，`0` = AMR；无法识别时按 SILK 处理 |
| `duration` | int | 否 | `1` | 时长（秒），最长 60 秒；建议按真实时长传，否则气泡显示不准 |

音频上限 **5 MB**。声明格式与真实编码不一致时消息能发出但对方可能无法播放。响应：`ok`、`format`、`voiceTimeMs`、`voiceBytes`。

```bash
# 方式一：设备上的音频文件（path），按真实时长声明
curl -s -X POST "$BASE/api/send/voice" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","path":"/var/mobile/Media/audio.silk","format":4,"duration":5}'

# 方式二：base64 内联
curl -s -X POST "$BASE/api/send/voice" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","voice":"<BASE64>","format":4,"duration":5}'
```

### 9.5 `POST /api/send/video` — 视频

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `chat` | string | 是 | 目标会话 ID |
| `video` | string(base64) | 二选一 | mp4 二进制 base64 |
| `path` | string | 二选一 | 设备上的 mp4 文件路径 |

视频上限 **20 MB**，单个请求体上限 **32 MB**，超限 → `413`。响应：`ok`、`videoBytes`。

```bash
# 方式一：设备上的 mp4 文件（推荐）
curl -s -X POST "$BASE/api/send/video" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","path":"/var/mobile/Media/DCIM/VID_0001.mp4"}'

# 方式二：base64 内联（受 32 MB 请求体上限约束，大视频请改用 path）
curl -s -X POST "$BASE/api/send/video" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","video":"<BASE64>"}'
```

### 9.6 `POST /api/send/file` — 发送文件

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `chat` | string | 是 | 目标会话 ID |
| `file` | string(base64) | 二选一 | 文件内容的 base64 |
| `path` | string | 二选一 | 设备上的本地文件路径 |
| `name` | string | 否 | 文件名（含扩展名）；省略时取 `path` 的文件名，再省略为 `file.bin` |

文件上限 **20 MB**，超限 → `413`。响应：`ok`、`fileName`、`fileBytes`、`ext`。

```bash
# 方式一：设备上的文件（推荐，文件名自动取 path 的最后一段）
curl -s -X POST "$BASE/api/send/file" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","path":"/var/mobile/Media/report.pdf"}'

# 方式二：base64 内联
curl -s -X POST "$BASE/api/send/file" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","file":"<BASE64>","name":"report.pdf"}'
```

### 9.7 `GET /api/group/announcement` — 读取群公告

只读，不触发任何网络请求，不需要管理员权限。

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `chat` | 是 | 群会话 ID；非群聊 → `400` |

```json
{"ok":true,"chat":"<CHAT_ID>","text":"今晚 8 点开会",
 "editor":"<WXID>","time":1700000000,"richText":""}
```

| 字段 | 说明 |
| --- | --- |
| `text` | 当前公告纯文本，无公告时为空串 |
| `editor` | 最后发布者 ID |
| `time` | 发布时间（Unix 秒） |
| `richText` | 富文本内容；纯文本公告该项为空 |

> 服务器同步有延迟，刚发布完立刻读可能仍是旧值，隔几秒复查即可。

```bash
curl -s -H "X-Token: $TOKEN" "$BASE/api/group/announcement?chat=<CHAT_ID>"
```

### 9.8 `POST /api/group/announcement` — 设置群公告

**需要群主或管理员，会通知群成员**。`dryRun` 默认 `1`（只预演、不发布）。

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `chat` | string | 是 | — | 群会话 ID；非群聊 → `400` |
| `text` | string | 是 | — | 新公告纯文本 |
| `dryRun` | int | 否 | `1` | `1` 只回显参数与权限；显式 `0` 才真正发布 |

| 字段 | 说明 |
| --- | --- |
| `ok` | 请求是否成功 |
| `chat` / `text` | 目标群与公告文本 |
| `dryRun` | 是否只是预演 |
| `serverAccepted` | 服务端是否接受，**真正的成功判据** |
| `confirmed` | 综合确认结果 |
| `role` | 当前账号在该群的角色信息 |

> 不要以本地读取到的公告文本判断发布是否成功，本地刷新可能滞后数秒；以 `serverAccepted` 为准，再用 9.7 复查。发布的是纯文本公告，不带图片、富文本或 @ 成员；每次发布都会向群成员推送系统消息，请勿高频调用。

错误：`400` 缺参 / 非群聊、`401` 鉴权失败、`403` 非群主或管理员、`503` 服务尚未就绪（稍后重试）。

```bash
# 1) 预演（默认 dryRun=1）
curl -s -X POST "$BASE/api/group/announcement" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"今晚 8 点开会"}'

# 2) 真正发布（会通知群成员）
curl -s -X POST "$BASE/api/group/announcement" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"今晚 8 点开会","dryRun":0}'
```

---

## 10. 常见错误

| 错误 | 原因 / 处理 |
| --- | --- |
| `401 unauthorized` | 令牌不匹配，补 `X-Token` 请求头 |
| `body must be a JSON object` | POST body 不是 JSON object |
| `503` + `state=canceled` | 动作确定没执行，可用同一 `requestId` 安全重试（见 2.1） |
| `503` + `state=uncertain` | 结果不确定，禁止盲目重试；先用读接口核查，再换新的 `requestId` |
| `409` | 同一 `requestId` 正在执行或结果不确定，请求被拒绝，动作不会重复执行 |
| `missing chat/text (both must be strings)` | `/api/send/text` 缺参数或类型不对 |
| `@all is not supported` | `/api/send/quote` 不支持 @所有人；`/api/send/text` 请改用 `atAll=1` |
| `missing quoteLocalID` / `quote message not found` | 引用回复缺少 `quoteLocalID`，或该 ID 不属于当前会话 |
| `413 image/video too large` | 图片 > 5 MB 或视频 / 文件 > 20 MB；响应含 `maxBytes` / `actualBytes`，请求被拒绝且未发送 |
| `413 request body too large` | 单个请求体 > 32 MB，压缩后重发 |
| `media not found locally` | 媒体尚未下载到本机，且自动触发下载后仍未就绪；可稍后重试 |
| `file not downloaded locally` | 文件本体尚未下载，可在微信里打开该文件后重试 |
| `not a file message` | `/api/file` 指向的不是文件消息 |
| `need wxid or name` | `/api/contacts/find` 两个参数都没传 |
| `missing chat` / `not a group chat` / `group not found` | 群成员或群公告接口的参数问题 |
| `contact not found` | 会话 / 联系人不存在，先在微信里打开一次该会话 |
| `only group owner/admin can @all` | `atAll=1` 但当前账号不是群主 / 管理员 |
| `only group owner/admin can set announcement` | 设置群公告需要群主 / 管理员 |
| `code must be a string` | 激活码字段不是字符串 |
| 激活码无效 / 与设备不匹配 | 激活码损坏、被篡改，或签发给其它设备 |
| HTTP 短暂连不上 | 服务可能正在自动恢复；重试前先用 `/api/messages` 核查是否已落库，避免重复发送 |

---

## 11. 典型调用链

```bash
# 1. 选会话
curl -s -H "X-Token: $TOKEN" "$BASE/api/chats"

# 2. 取群成员与显示名
curl -s -H "X-Token: $TOKEN" "$BASE/api/contacts/groupmember?chat=<CHAT_ID>"

# 3. 读消息，拿 localID 作为引用目标 / 媒体依据
curl -s -H "X-Token: $TOKEN" "$BASE/api/messages?chat=<CHAT_ID>&limit=20"

# 4. 发送（文本 / @ / 引用 / 引用 + @）
curl -s -X POST "$BASE/api/send/text" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"...","at":["<WXID>"]}'
curl -s -X POST "$BASE/api/send/quote" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"chat":"<CHAT_ID>","text":"回复内容","quoteLocalID":<LOCAL_ID>}'

# 5. 下载收到的媒体 / 文件
curl -s -H "X-Token: $TOKEN" \
  "$BASE/api/media?chat=<CHAT_ID>&localID=<LOCAL_ID>" -o out.bin
curl -s -H "X-Token: $TOKEN" \
  "$BASE/api/file?chat=<CHAT_ID>&localID=<LOCAL_ID>" -o out.bin

# 6. 朋友圈：取最新 → 逐页追加 → 下载图片 → 点赞
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/timeline/gethead?media=0"
curl -s -H "X-Token: $TOKEN" "$BASE/api/moments/timeline/getnext?media=0"
curl -s -H "X-Token: $TOKEN" \
  "$BASE/api/moments/media?tid=<TID>&index=0" -o photo.jpg
curl -s -X POST "$BASE/api/moments/like" \
  -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"tid":"<TID>","dryRun":1}'
```
