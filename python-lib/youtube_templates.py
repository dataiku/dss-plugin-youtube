# -*- coding: utf-8 -*-
import dataiku
from dataiku.customrecipe import get_input_names_for_role, get_recipe_config, get_output_names_for_role
from youtube_client import YoutubeClient
import pandas as pd
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format='youtube plugin %(levelname)s - %(message)s')


def youtube_recipe_runtime(parameter_id):
    input_A_names = get_input_names_for_role('input_A_role')
    id_column_name = get_recipe_config()['id_column_name']
    access_type = get_recipe_config()['access_type']
    connection_details = get_recipe_config()[access_type]
    endpoint = get_recipe_config()['endpoint']
    part = ",".join(get_recipe_config()['part'])
    client = YoutubeClient(connection_details)

    id_list = dataiku.Dataset(input_A_names[0])
    id_list_df = id_list.get_dataframe()

    results = []
    args = {
        "endpoint": endpoint,
        "part": part
    }

    for index, row in id_list_df.iterrows():
        args[parameter_id] = row[id_column_name]  # Optimize this -> [id,id,id...]
        data = client.get_endpoint(**args)
        while len(data) > 0:
            for result in data:
                result = client.format_data(result)
                results.append(result)
            if client.has_next_page():
                data = client.get_next_page()
            else:
                break
    output_names_stats = get_output_names_for_role('youtube_output')
    odf = pd.DataFrame(results)

    if odf.size > 0:
        jira_output = dataiku.Dataset(output_names_stats[0])
        jira_output.write_with_schema(odf)
