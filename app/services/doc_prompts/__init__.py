"""Registry of documentation generation prompts."""

from .api import api_prompt
from .data_model import data_model_prompt
from .frontend import frontend_prompt
from .overview import project_overview_prompt

registry = {
    frontend_prompt["name"]: frontend_prompt,
    project_overview_prompt["name"]: project_overview_prompt,
    api_prompt["name"]: api_prompt,
    data_model_prompt["name"]: data_model_prompt,
}
