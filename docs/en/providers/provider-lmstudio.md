# Connect LM Studio

LM Studio can expose a local OpenAI-compatible model service on your machine (hardware requirements must be met).

## Download and Install LM Studio

<https://lmstudio.ai/download>

## Download and Start a Model

<https://lmstudio.ai/models>

Download the model you want in LM Studio and start its local inference server.

## Configure AstrBot

On AstrBot's **Providers** page, add a Provider source and select **OpenAI Chat Completions** or the LM Studio preset.

Set `API Base URL` to `http://localhost:1234/v1`

Set `API Key` to `lm-studio`

> For users deploying AstrBot via Docker Desktop on Mac or Windows, set `API Base URL` to `http://host.docker.internal:1234/v1`.
>
> On Linux Docker, attach the container to a controlled network shared with an LM Studio proxy, or configure an explicit host-gateway alias. Do not expose port 1234 to the public Internet for this purpose.

If LM Studio itself is deployed in Docker, ensure port 1234 is mapped to the host.

Set the model name to the one currently exposed by LM Studio, then save the configuration.

> Run `/provider` to view the models configured in AstrBot.
