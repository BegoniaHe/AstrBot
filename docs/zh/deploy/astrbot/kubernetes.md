# 使用 Kubernetes 部署 AstrBot

仓库中的 Kubernetes 清单提供单副本部署和故障后自动重建 Pod 的能力，但不是多副本高可用方案。AstrBot 当前使用 SQLite 和本地持久化状态；两套 Deployment 都固定为 `replicas: 1` 并使用 `Recreate` 策略，请勿直接扩展副本数。

> [!WARNING]
> `k8s/**/02-deployment.yaml` 中的 AstrBot 镜像仍是上游占位值 `soulter/astrbot:latest`，而且没有覆盖 WebUI 的默认环回监听。应用清单前，必须先构建并替换为当前 fork 的镜像，同时加入 `ASTRBOT_DASHBOARD_HOST=0.0.0.0`。不要直接原样执行全部清单。

## 前置条件

- `kubectl` 已连接到目标集群。
- 集群节点可以从你的镜像仓库拉取镜像。
- 集群有适合这些 PVC 的 StorageClass；用 `kubectl get storageclass` 检查。
- Sidecar 清单中的 `astrbot-data-shared-pvc` 请求 `ReadWriteMany`（RWX）。如果默认存储不支持 RWX，请先修改 `storageClassName` 或提供合适的 PV。
- 清单将宿主机 `/etc/localtime` 作为 `hostPath` 挂载，因而面向具有该文件的 Linux 节点；其他节点环境需要先调整挂载。

## 部署前必须修改清单

### 1. 构建并推送当前 fork 镜像

在仓库根目录执行：

```bash
docker build -t <your-registry>/astrbot:<tag> .
docker push <your-registry>/astrbot:<tag>
```

使用不可变的版本或提交标签，不要在生产环境依赖会漂移的 `latest`。

在你准备使用的 Deployment 中，将：

```yaml
image: soulter/astrbot:latest
```

替换为：

```yaml
image: <your-registry>/astrbot:<tag>
```

对应文件是：

- 独立部署：`k8s/astrbot/02-deployment.yaml`
- NapCat Sidecar：`k8s/astrbot_with_napcat/02-deployment.yaml` 中名为 `astrbot` 的容器

私有仓库还需要按集群规范配置 `imagePullSecrets`。

### 2. 允许 Service 访问 WebUI

WebUI 默认监听 `127.0.0.1`。在同一个 AstrBot 容器的 `env` 列表中加入：

```yaml
env:
  - name: TZ
    value: 'Asia/Shanghai'
  - name: ASTRBOT_DASHBOARD_HOST
    value: '0.0.0.0'
```

否则 Service 虽然会把流量转发到容器端口 `6185`，AstrBot 仍不会在 Pod 网络接口上接受连接。

> [!CAUTION]
> 对外暴露 WebUI 后，请配合 Ingress/反向代理启用 HTTPS，限制来源地址，并使用强密码和 TOTP。`LoadBalancer` 或 `NodePort` 不应在无访问控制时直接面向公网。

### 3. Sidecar 部署改用 NapCat 正向 WebSocket

`k8s/astrbot_with_napcat/02-deployment.yaml` 当前为 NapCat 设置了 `MODE=astrbot`，该模式会写入目标为 `ws://astrbot:6199/ws` 的反向 WebSocket 客户端。它不适合本页使用独立 `NapCat` 平台的同 Pod 配置。

在 Sidecar Deployment 中将：

```yaml
- name: MODE
  value: 'astrbot'
```

改为：

```yaml
- name: MODE
  value: 'ws'
```

这样 NapCat 会启动监听端口 `3001` 的正向 WebSocket 服务，供同 Pod 的 AstrBot 主动连接。

`MODE` 会在 NapCat 每次启动时重写 `onebot11.json`，模板 token 为空。如果需要自定义 token，可先让 Pod 用 `MODE=ws` 启动并生成 PVC 中的配置，再从 Deployment 删除 `MODE`，随后在 NapCat WebUI 中设置 token；不要把敏感 token 直接提交到清单。

## 方式一：AstrBot + NapCat Sidecar

该方案位于 `k8s/astrbot_with_napcat/`，两个容器位于同一个 Pod。

完成上面的镜像、监听地址和 NapCat 模式修改后执行：

```bash
kubectl apply -f k8s/astrbot_with_napcat/00-namespace.yaml
kubectl apply -f k8s/astrbot_with_napcat/01-pvc.yaml
kubectl apply -f k8s/astrbot_with_napcat/02-deployment.yaml
```

确认 Pod 就绪：

```bash
kubectl get pods -n astrbot-ns
```

### 暴露服务

NodePort 和 LoadBalancer 二选一。

NodePort：

```bash
kubectl apply -f k8s/astrbot_with_napcat/03-service-nodeport.yaml
kubectl get svc astrbot-service-nodeport -n astrbot-ns
```

Sidecar NodePort 清单没有固定 `nodePort`，集群会分别为内部端口 `6099`（NapCat WebUI）和 `6185`（AstrBot WebUI）自动分配端口。以 `kubectl get svc` 输出的 `PORT(S)` 为准，通过 `http://<NodeIP>:<分配到的NodePort>` 访问。

LoadBalancer：

```bash
kubectl apply -f k8s/astrbot_with_napcat/04-service-loadbalancer.yaml
kubectl get svc astrbot-service-lb -n astrbot-ns
```

等待 `EXTERNAL-IP` 分配完成，再使用端口 `6185` 或由外部负载均衡器映射后的端口访问 AstrBot。

### 配置 NapCat 连接

AstrBot 与 NapCat 共享 Pod 网络命名空间。在 AstrBot WebUI 中创建 `NapCat` 平台，并填写：

- `ws_url`：`ws://localhost:3001`
- `token`：仅当 NapCat 正向 WebSocket 开启鉴权时填写，且两端保持一致

无需为这个 Pod 内连接创建额外 Service 或 NodePort。

## 方式二：只部署 AstrBot

该方案位于 `k8s/astrbot/`。完成镜像和监听地址修改后执行：

```bash
kubectl apply -f k8s/astrbot/00-namespace.yaml
kubectl apply -f k8s/astrbot/01-pvc.yaml
kubectl apply -f k8s/astrbot/02-deployment.yaml
kubectl get pods -n astrbot-standalone-ns
```

### 暴露服务

NodePort：

```bash
kubectl apply -f k8s/astrbot/03-service-nodeport.yaml
kubectl get svc astrbot-standalone-nodeport -n astrbot-standalone-ns
```

独立部署的 NodePort 是清单中明确固定的：

- AstrBot WebUI：内部端口 `6185` -> NodePort `30185`
- OneBot v11 反向 WebSocket：内部端口 `6199` -> NodePort `30199`

因此 WebUI 地址通常是 `http://<NodeIP>:30185`。如果集群策略不允许这两个 NodePort，请先修改清单。

端口 `30199` 只是 Service 映射；只有创建 OneBot v11 平台并将 `ws_reverse_host` 显式设为 `0.0.0.0` 后，Pod 外的 OneBot 客户端才能连接。请同时设置 token，并避免向整个公网开放该端口。

LoadBalancer：

```bash
kubectl apply -f k8s/astrbot/04-service-loadbalancer.yaml
kubectl get svc astrbot-standalone-lb -n astrbot-standalone-ns
```

该 Service 暴露内部端口 `6185` 和 `6199`。如果不需要远程 OneBot 反向 WebSocket，建议从 Service 清单删除 `6199`。

## 查看日志

Sidecar 部署：

```bash
kubectl logs -f -n astrbot-ns deployment/astrbot-stack -c astrbot
kubectl logs -f -n astrbot-ns deployment/astrbot-stack -c napcat
```

独立部署：

```bash
kubectl logs -f -n astrbot-standalone-ns deployment/astrbot-standalone
```

首次登录使用 AstrBot 日志中打印的随机密码，默认用户名为 `astrbot`。

## Agent 沙盒

这些清单不包含独立的集群内 Agent 沙盒运行时。如果需要相关能力，请参考 [Agent 沙盒环境](/use/astrbot-agent-sandbox)，并单独部署和保护所选运行时。
