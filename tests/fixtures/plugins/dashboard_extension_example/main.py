from pydantic import BaseModel, ConfigDict

from astrbot.api.dashboard import (
    DashboardActionContext,
    DashboardJsonAction,
)
from astrbot.api.star import Star


class SettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SettingsResult(BaseModel):
    message: str


class DashboardExtensionExample(Star):
    async def initialize(self) -> None:
        registrar = self.context.dashboard_extensions.for_plugin(self)
        registrar.register_json(
            DashboardJsonAction(
                name="settings.read",
                input_model=SettingsRequest,
                output_model=SettingsResult,
                description="Read the example Dashboard settings",
            ),
            self.read_settings,
        )

    async def read_settings(
        self,
        _payload: SettingsRequest,
        _context: DashboardActionContext,
    ) -> SettingsResult:
        return SettingsResult(message="Dashboard Extension Protocol v1 is ready")
