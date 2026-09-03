"""
Renders Jinja2 prompt templates with project/lore variables. Templates live
as plain files under novelforge/prompts/templates/ -- never as strings
embedded in tool code. This keeps novel-specific prompt language completely
out of the Python source tree.
"""
from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(disabled_extensions=("jinja2",)),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(template_name: str, **kwargs) -> str:
    template = _env.get_template(f"{template_name}.jinja2")
    return template.render(**kwargs)


def render_pair(template_name: str, **kwargs) -> tuple[str, str]:
    system = _env.get_template(f"{template_name}.system.jinja2")
    user = _env.get_template(f"{template_name}.jinja2")
    return system.render(**kwargs).strip(), user.render(**kwargs).strip()
