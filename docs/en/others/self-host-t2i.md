# Self-host the Text-to-Image Service

AstrBot can call a compatible text-to-image service endpoint. If you want full control over availability and network locality, you can self-host [AstrBotDevs/astrbot-t2i-service](https://github.com/AstrBotDevs/astrbot-t2i-service).

Follow that repository's own build and run instructions. After the service is up, point AstrBot to your own endpoint.

After deployment, go to AstrBot Dashboard -> Config -> System, and change `Text-to-Image Service API Endpoint` to the URL you deployed (as shown below).

> If you deployed AstrBot using the Docker tutorial in this documentation, the URL should be `http://<t2i-service-container-name>:8999`.

> If you deployed on the same machine as AstrBot, the URL should be `http://localhost:8999`.

<img width="589" height="255" alt="image" src="https://github.com/user-attachments/assets/5ef09db2-1a33-440c-9986-c7b544325e34" />
