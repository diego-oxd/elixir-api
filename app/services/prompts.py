from .frontend_prompt import frontend_prompt
from .overview_prompt import project_overview_prompt
from .api_prompt import api_prompt
from .data_model_prompt import data_model_prompt

prompts = {
    frontend_prompt["name"]: frontend_prompt,
    project_overview_prompt["name"]: project_overview_prompt,
    api_prompt["name"]: api_prompt,
    data_model_prompt["name"]: data_model_prompt
}