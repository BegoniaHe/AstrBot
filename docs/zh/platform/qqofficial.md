# 接入 QQ 官方机器人平台

QQ 官方机器人平台是腾讯官方提供的一个机器人接入平台，允许开发者通过官方接口将机器人接入 QQ 群聊和个人聊天中。

AstrBot 同时支持 WebSocket 和 Webhook。**新接入优先使用 WebSocket**：它不需要为 QQ 平台准备公网 HTTPS 回调地址，WebUI 还支持扫码一键创建。只有在部署环境或业务要求必须由 QQ 主动回调时，才选择 Webhook。

- [WebSocket 方式（推荐）](/platform/qqofficial/websockets)
- [Webhook 方式](/platform/qqofficial/webhook)
