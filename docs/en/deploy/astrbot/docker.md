# Deploy AstrBot with Docker

> [!WARNING]
> This fork does not publish a prebuilt Docker image. Clone this repository and build from its root `Dockerfile` and Compose files.

## Choose a Compose File

The repository provides two locally built deployment paths:

- `compose.yml`: runs AstrBot only. Use it for QQ Official Bot, Telegram, Discord, and other platforms, or when you manage the bot protocol implementation separately.
- `compose-with-napcat.yml`: runs AstrBot and NapCat together for personal QQ accounts. AstrBot is still built from the local checkout; NapCat uses its official container image.

Clone the repository first:

```bash
git clone https://github.com/Xero-Team/AstrBot.git
cd AstrBot
```

## Allow Access to the WebUI from Outside the Container

The AstrBot WebUI listens on `127.0.0.1` by default. Inside a container, this means that publishing port `6185` alone does not make the WebUI reachable from the host.

Before starting, add the following entry under `astrbot.environment` in the Compose file you selected:

```yaml
environment:
  - TZ=Asia/Shanghai
  - ASTRBOT_DASHBOARD_HOST=0.0.0.0
```

`ASTRBOT_DASHBOARD_HOST` takes precedence over `dashboard.host` in `data/cmd_config.json`. If external access is no longer needed, remove the environment variable and restore the configured host to a loopback address.

> [!CAUTION]
> `0.0.0.0` makes the WebUI listen on every container interface. Do not expose the admin panel directly to the public internet. Restrict firewall access and use a reverse proxy, HTTPS, a strong password, and TOTP.

## Start AstrBot Only

The root `compose.yml` builds the current checkout as the local image `astrbot:local`:

```bash
docker compose up -d --build
docker compose logs -f astrbot
```

Its default mount and published ports are:

- `./data` -> `/AstrBot/data`: configuration, database, plugins, and other runtime data.
- `6185:6185`: AstrBot WebUI.
- `6199:6199`: optional OneBot v11 reverse WebSocket endpoint.

Publishing `6199` does not change the OneBot listener address. Only set that platform's `ws_reverse_host` to `0.0.0.0` when its OneBot client runs outside the AstrBot container. Also configure `ws_reverse_token` and restrict network access to the port.

## Start AstrBot and NapCat Together

First add `ASTRBOT_DASHBOARD_HOST=0.0.0.0` to `compose-with-napcat.yml` as described above.

The file currently also sets NapCat `MODE=astrbot`. On every NapCat startup, that mode writes a **reverse** WebSocket client targeting `ws://astrbot:6199/ws`. To use AstrBot's currently recommended dedicated `NapCat` platform, change it first to:

```yaml
- MODE=ws
```

`MODE=ws` starts a OneBot v11 forward WebSocket server on `0.0.0.0:3001`. Then start the stack:

```bash
docker compose -f compose-with-napcat.yml up -d --build
docker compose -f compose-with-napcat.yml logs -f astrbot napcat
```

On Linux, you can run NapCat with your host user's UID/GID to reduce bind-mount permission issues:

```bash
NAPCAT_UID=$(id -u) NAPCAT_GID=$(id -g) \
  docker compose -f compose-with-napcat.yml up -d --build
```

This Compose file publishes:

- `6185`: AstrBot WebUI.
- `6099`: NapCat WebUI.

It persists:

- `./data`
- `./napcat/config`
- `./ntqq`

AstrBot and NapCat share an internal Docker network. With `MODE=ws`, create the dedicated `NapCat` platform in AstrBot and set `ws_url` to `ws://napcat:3001`. If NapCat's forward WebSocket uses a token, configure the same token on both sides. This path does not require publishing a QQ WebSocket port to the host.

> [!NOTE]
> NapCat `MODE` selects a startup template and rewrites `onebot11.json` on every start; the template token is empty. To persist a custom token, start once with `MODE=ws`, remove `MODE` from the Compose file, and then set the token in NapCat WebUI. The resulting configuration remains under `./napcat/config`.

If you retain the Compose file's original `MODE=astrbot`, do not create the dedicated `NapCat` platform. Create `OneBot v11`, set `ws_reverse_host` to `0.0.0.0`, and keep port `6199`. It only needs to be reachable on the internal Docker network and does not need to be published to the host. For authentication, likewise remove `MODE` after the initial configuration is generated, then set the same token in NapCat and AstrBot.

## First Login and Updates

On first startup, AstrBot prints the WebUI address and a random initial password in its logs. The default username is `astrbot`. Change the password immediately after logging in.

To update, back up `data/`, pull the latest code, and rebuild the selected service:

```bash
git pull --ff-only
docker compose up -d --build
```

For the NapCat stack, use:

```bash
git pull --ff-only
docker compose -f compose-with-napcat.yml up -d --build
```
