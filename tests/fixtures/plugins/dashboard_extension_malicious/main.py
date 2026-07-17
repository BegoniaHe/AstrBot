from astrbot.api.dashboard import DashboardJsonAction
from astrbot.api.star import Star


class MaliciousDashboardExtension(Star):
    async def initialize(self) -> None:
        registrar = self.context.dashboard_extensions.for_plugin(self)
        registrar.register_json(DashboardJsonAction, self.initialize)  # type: ignore[arg-type]
