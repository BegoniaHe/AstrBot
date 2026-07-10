from abc import ABC, abstractmethod


class RenderStrategy(ABC):
    @abstractmethod
    async def render(
        self,
        text: str,
        template_name: str | None = None,
    ) -> str:
        pass

    @abstractmethod
    async def render_custom_template(
        self,
        tmpl_str: str,
        tmpl_data: dict,
        options: dict | None = None,
    ) -> str:
        pass
