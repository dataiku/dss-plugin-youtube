# -*- coding: utf-8 -*-
import dataiku
from dataiku.customrecipe import get_input_names_for_role, get_recipe_config, get_output_names_for_role
from youtube_client import YoutubeClient
import pandas as pd
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format='youtube plugin %(levelname)s - %(message)s')

input_datasets_name = get_input_names_for_role('input_datasets_name')
id_column_name = get_recipe_config()['id_column_name']
access_type = get_recipe_config()['access_type']
connection_details = get_recipe_config()[access_type]
endpoint = get_recipe_config()['endpoint']
id_type = get_recipe_config().get('id_type', "")
part_name = endpoint + "_part"
part = ",".join(get_recipe_config()[part_name])
access_token = connection_details.get("youtube_credentials")
client = YoutubeClient(connection_details)
maximum_items = get_recipe_config().get('maximum_items', 1000)
client.set_item_number_limit(maximum_items)
id_list = dataiku.Dataset(input_datasets_name[0])
id_list_df = id_list.get_dataframe()

results = []
args = {
    "endpoint": endpoint,
    part_name: part
}
item_id_equivalent = id_type if id_type != "" else client.get_item_id_equivalent(endpoint)
nb_items = 0
for index, row in id_list_df.iterrows():
    args[item_id_equivalent] = row[id_column_name]
    data = client.get_endpoint(raise_exception=False, **args)
    while client.has_remaining_data(nb_items):
        for result in data:
            result = client.format_data(result)
            results.append(result)
            nb_items = nb_items + 1
        data = client.get_next_page()
    if maximum_items > -1 and nb_items >= maximum_items:
        break
output_names_stats = get_output_names_for_role('youtube_output')
odf = pd.DataFrame(results)

if odf.size > 0:
    youtube_output = dataiku.Dataset(output_names_stats[0])
    youtube_output.write_with_schema(odf)
