# 自行部署文转图服务

AstrBot 可以调用兼容的文转图服务接口。如果你希望完全自行控制服务可用性和网络路径，可以自部署 [AstrBotDevs/astrbot-t2i-service](https://github.com/AstrBotDevs/astrbot-t2i-service)。

部署步骤请以该仓库自己的构建和运行说明为准。完成部署后，你只需要在 AstrBot 中把文转图服务地址指向你自己的实例。

在部署完成后，前往 AstrBot 仪表盘 -> 配置文件 -> 系统，修改 `文本转图像服务 API 地址` 为你部署好的 url（如下图所示）

> 如果你是使用本文档的 Docker教程 部署的 AstrBot ，url应为 `http://文转图服务容器名:8999`。

> 如果部署在与 AstrBot 相同的机器上，url 应为 `http://localhost:8999`。

<img width="591" height="228" alt="image" src="https://github.com/user-attachments/assets/f3564b46-11a4-402a-85e3-5f44a82713fe" />
