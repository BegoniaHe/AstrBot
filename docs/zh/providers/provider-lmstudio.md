# 接入 LM Studio

LM Studio 可以在本机启动兼容 OpenAI 的本地模型服务（需要电脑硬件配置符合要求）。

## 下载并安装 LMStudio

<https://lmstudio.ai/download>

## 下载并启动模型

<https://lmstudio.ai/models>

在 LM Studio 中下载你需要的模型，并启动本地推理服务。

## 配置 AstrBot

在 AstrBot 的 **提供商** 页面新增 Provider 来源，选择 **OpenAI Chat Completions** 或 LM Studio 预设。

API Base URL 填写 `http://localhost:1234/v1`

API Key 填写 `lm-studio`

> 对于 Mac/Windows 使用 Docker Desktop 部署 AstrBot 的用户，API Base URL 请填写为 `http://host.docker.internal:1234/v1`。
> 对于 Linux Docker，可将容器加入与 LM Studio 代理相同的受控网络，或显式配置 host-gateway 后使用宿主机别名。不要为此把 1234 端口直接开放到公网。

如果 LM Studio 使用了 Docker 部署，请确保 1234 端口已经映射到宿主机。

模型名称填写 LM Studio 当前暴露的模型名，保存配置即可。

> 输入 /provider 查看 AstrBot 配置的模型
