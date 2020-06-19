# -*- coding: utf-8 -*-
from youtube_templates import youtube_recipe_runtime
from dataiku.customrecipe import get_recipe_config

search_id_type = get_recipe_config()["search_id_type"]

youtube_recipe_runtime(search_id_type)
