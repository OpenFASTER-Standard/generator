from typing import Any, Callable

from jinja2 import Template


def jinja_text_renderer(template_source: str) -> Callable[[list[dict]], str]:
    template = Template(template_source)

    def render(rows: list[dict[str, Any]]) -> str:
        return template.render(rows=rows)

    return render
