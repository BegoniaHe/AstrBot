# Connect LM Studio

LM Studio can expose a local OpenAI-compatible model service on your machine (hardware requirements must be met).

## Download and Install LM Studio

<https://lmstudio.ai/download>

## Download and Start a Model

<https://lmstudio.ai/models>

Download the model you want in LM Studio and start its local inference server.

## Configure AstrBot

In AstrBot:

Go to **Configuration → Service Providers → + → OpenAI-Compatible Service**

Set `API Base URL` to `http://localhost:1234/v1`

Set `API Key` to `lm-studio`

> For users deploying AstrBot via Docker Desktop on Mac or Windows, set `API Base URL` to `http://host.docker.internal:1234/v1`.
>
> For users deploying AstrBot via Docker on Linux, set `API Base URL` to `http://172.17.0.1:1234/v1`, or replace `172.17.0.1` with your server's public IP (make sure port 1234 is open on the host).

If LM Studio itself is deployed in Docker, ensure port 1234 is mapped to the host.

Set the model name to the one currently exposed by LM Studio, then save the configuration.

> Run `/provider` to view the models configured in AstrBot.
