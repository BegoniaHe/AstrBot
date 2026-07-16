# Deploy AstrBot with Kubernetes

The repository's Kubernetes manifests provide a single-replica deployment whose Pod can be recreated after a failure. They are not a multi-replica high-availability setup. AstrBot currently uses SQLite and local persistent state; both Deployments specify `replicas: 1` and the `Recreate` strategy, so do not scale them horizontally as-is.

> [!WARNING]
> The AstrBot container in each `k8s/**/02-deployment.yaml` still uses the upstream placeholder image `soulter/astrbot:latest` and does not override the WebUI's loopback-only default. Before applying the manifests, build and select an image from this fork and add `ASTRBOT_DASHBOARD_HOST=0.0.0.0`. Do not apply the unmodified manifest set.

## Prerequisites

- `kubectl` is connected to the target cluster.
- Cluster nodes can pull from your selected image registry.
- The cluster has a StorageClass suitable for the manifests' PVCs; check with `kubectl get storageclass`.
- The Sidecar manifest requests `ReadWriteMany` (RWX) for `astrbot-data-shared-pvc`. Select an RWX-capable StorageClass or provide an appropriate PV before applying it.
- The manifests mount the node's `/etc/localtime` with `hostPath`, so they target Linux nodes that provide that file. Adjust the mount first for other node environments.

## Required Manifest Changes

### 1. Build and Push This Fork's Image

From the repository root, run:

```bash
docker build -t <your-registry>/astrbot:<tag> .
docker push <your-registry>/astrbot:<tag>
```

Use an immutable version or commit tag in production instead of a moving `latest` tag.

In the Deployment you plan to use, replace:

```yaml
image: soulter/astrbot:latest
```

with:

```yaml
image: <your-registry>/astrbot:<tag>
```

The relevant locations are:

- standalone: `k8s/astrbot/02-deployment.yaml`
- NapCat Sidecar: the container named `astrbot` in `k8s/astrbot_with_napcat/02-deployment.yaml`

For a private registry, also configure `imagePullSecrets` according to your cluster policy.

### 2. Make the WebUI Reachable Through a Service

The WebUI listens on `127.0.0.1` by default. Add the following variable to the same AstrBot container's `env` list:

```yaml
env:
  - name: TZ
    value: 'Asia/Shanghai'
  - name: ASTRBOT_DASHBOARD_HOST
    value: '0.0.0.0'
```

Without this override, a Service can forward to container port `6185`, but AstrBot will not accept the connection on the Pod network interface.

> [!CAUTION]
> After exposing the WebUI, use an Ingress or reverse proxy with HTTPS, restrict source addresses, and enable a strong password and TOTP. Do not leave a `LoadBalancer` or `NodePort` admin endpoint open to the internet without access controls.

### 3. Use NapCat Forward WebSocket in the Sidecar

`k8s/astrbot_with_napcat/02-deployment.yaml` currently sets NapCat `MODE=astrbot`, which writes a reverse WebSocket client targeting `ws://astrbot:6199/ws`. That does not match the same-Pod setup below that uses AstrBot's dedicated `NapCat` platform.

In the Sidecar Deployment, replace:

```yaml
- name: MODE
  value: 'astrbot'
```

with:

```yaml
- name: MODE
  value: 'ws'
```

NapCat will then start a forward WebSocket server on port `3001` for AstrBot in the same Pod to connect to.

`MODE` rewrites `onebot11.json` on every NapCat startup, and the template token is empty. To use a custom token, first let the Pod start with `MODE=ws` and create the configuration on the PVC, then remove `MODE` from the Deployment and set the token in NapCat WebUI. Do not commit a sensitive token directly to the manifest.

## Method 1: AstrBot and NapCat Sidecar

This option is under `k8s/astrbot_with_napcat/`; both containers run in one Pod.

After making the required image, listener, and NapCat mode changes, apply:

```bash
kubectl apply -f k8s/astrbot_with_napcat/00-namespace.yaml
kubectl apply -f k8s/astrbot_with_napcat/01-pvc.yaml
kubectl apply -f k8s/astrbot_with_napcat/02-deployment.yaml
```

Confirm that the Pod is ready:

```bash
kubectl get pods -n astrbot-ns
```

### Expose the Services

Choose either NodePort or LoadBalancer.

NodePort:

```bash
kubectl apply -f k8s/astrbot_with_napcat/03-service-nodeport.yaml
kubectl get svc astrbot-service-nodeport -n astrbot-ns
```

The Sidecar NodePort manifest does not set fixed `nodePort` values. Kubernetes assigns ports for internal port `6099` (NapCat WebUI) and `6185` (AstrBot WebUI). Read the actual values from the `PORT(S)` column and use `http://<NodeIP>:<assigned-NodePort>`.

LoadBalancer:

```bash
kubectl apply -f k8s/astrbot_with_napcat/04-service-loadbalancer.yaml
kubectl get svc astrbot-service-lb -n astrbot-ns
```

Wait for `EXTERNAL-IP`, then access AstrBot through port `6185` or the port mapping provided by the external load balancer.

### Configure the NapCat Connection

AstrBot and NapCat share the Pod network namespace. Create a `NapCat` platform in the AstrBot WebUI and set:

- `ws_url`: `ws://localhost:3001`
- `token`: only when NapCat's forward WebSocket enables authentication; use the same value on both sides

This in-Pod connection does not need another Service or NodePort.

## Method 2: AstrBot Only

This option is under `k8s/astrbot/`. After making the required image and listener changes, apply:

```bash
kubectl apply -f k8s/astrbot/00-namespace.yaml
kubectl apply -f k8s/astrbot/01-pvc.yaml
kubectl apply -f k8s/astrbot/02-deployment.yaml
kubectl get pods -n astrbot-standalone-ns
```

### Expose the Services

NodePort:

```bash
kubectl apply -f k8s/astrbot/03-service-nodeport.yaml
kubectl get svc astrbot-standalone-nodeport -n astrbot-standalone-ns
```

The standalone manifest explicitly fixes these NodePorts:

- AstrBot WebUI: internal port `6185` -> NodePort `30185`
- OneBot v11 reverse WebSocket: internal port `6199` -> NodePort `30199`

The WebUI is therefore usually available at `http://<NodeIP>:30185`. Edit the manifest first if cluster policy does not allow these NodePorts.

Port `30199` is only a Service mapping. An external OneBot client can connect only after you create a OneBot v11 platform and explicitly set its `ws_reverse_host` to `0.0.0.0`. Configure a token as well, and do not expose that port to the entire internet.

LoadBalancer:

```bash
kubectl apply -f k8s/astrbot/04-service-loadbalancer.yaml
kubectl get svc astrbot-standalone-lb -n astrbot-standalone-ns
```

This Service exposes internal ports `6185` and `6199`. If you do not need a remote OneBot reverse WebSocket, remove `6199` from the Service manifest.

## View Logs

Sidecar deployment:

```bash
kubectl logs -f -n astrbot-ns deployment/astrbot-stack -c astrbot
kubectl logs -f -n astrbot-ns deployment/astrbot-stack -c napcat
```

Standalone deployment:

```bash
kubectl logs -f -n astrbot-standalone-ns deployment/astrbot-standalone
```

For the first login, use the random password printed in the AstrBot logs. The default username is `astrbot`.

## Agent Sandbox

These manifests do not include a separate in-cluster Agent sandbox runtime. If you need that capability, follow the [Agent Sandbox Environment](/en/use/astrbot-agent-sandbox) guide and deploy and secure the selected runtime separately.
