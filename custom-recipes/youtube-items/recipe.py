# -*- coding: utf-8 -*-
import dataiku
from dataiku.customrecipe import get_input_names_for_role, get_recipe_config, get_output_names_for_role
from youtube_client import YoutubeClient
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format='youtube plugin %(levelname)s - %(message)s')

input_A_names = get_input_names_for_role('input_A_role')
id_column_name = get_recipe_config()['id_column_name']
access_type = get_recipe_config()['access_type']
connection_details = get_recipe_config()[access_type]
edge_name = get_recipe_config()['edge_name']
id_type = get_recipe_config().get('id_type', "")
part_name = edge_name + "_part"
part = ",".join(get_recipe_config()[part_name])
access_token = connection_details.get("youtube_credentials")
client = YoutubeClient(connection_details)

id_list = dataiku.Dataset(input_A_names[0])
id_list_df = id_list.get_dataframe()

results = []
args = {
    "edge_name": edge_name,
    part_name: part
}
item_id_equivalent = id_type if id_type != "" else client.get_item_id_equivalent(edge_name)
for index, row in id_list_df.iterrows():
    id = row[id_column_name]
    #if row.isnull().values.any():
    #    continue
    args[item_id_equivalent] = id
    data = client.get_edge(raise_exception=False, **args)
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
