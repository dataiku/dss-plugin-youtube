from dataiku.connector import Connector
from youtube_client import YoutubeClient


class MyConnector(Connector):

    def __init__(self, config, plugin_config):

        Connector.__init__(self, config, plugin_config)  # pass the parameters to the base class
        self.config = config
        self.access_type = self.config.get("access_type", "token_access")
        self.channel_id = self.config.get("channel_id", None)
        self.connection_details = self.config.get(self.access_type)
        self.api_key = self.connection_details.get("api-key", None)
        self.access_token = self.connection_details.get("access_token", None)
        self.client = YoutubeClient(self.connection_details)
        self.part = ",".join(self.config.get("part", []))
        self.edge_name = "comments"
        config["edge_name"] = "comments"
        self.args = self.client.extract_args(**config)

    def get_read_schema(self):
        # In this example, we don't specify a schema here, so DSS will infer the schema
        # from the columns actually returned by the generate_rows method
        return None

    def generate_rows(self, dataset_schema=None, dataset_partitioning=None,
                      partition_id=None, records_limit=-1):
        json_response = self.client.get_edge(**self.args)
        while True:
            for item in json_response:
                yield self.client.format_data(item)
            if self.client.has_next_page():
                json_response = self.client.get_next_page()
            else:
                break

    def get_writer(self, dataset_schema=None, dataset_partitioning=None,
                   partition_id=None):
        """
        Returns a writer object to write in the dataset (or in a partition).

        The dataset_schema given here will match the the rows given to the writer below.

        Note: the writer is responsible for clearing the partition, if relevant.
        """
        raise Exception("Unimplemented")

    def get_partitioning(self):
        """
        Return the partitioning schema that the connector defines.
        """
        raise Exception("Unimplemented")

    def list_partitions(self, partitioning):
        """Return the list of partitions for the partitioning scheme
        passed as parameter"""
        return []

    def partition_exists(self, partitioning, partition_id):
        """Return whether the partition passed as parameter exists

        Implementation is only required if the corresponding flag is set to True
        in the connector definition
        """
        raise Exception("Unimplemented")

    def get_records_count(self, partitioning=None, partition_id=None):
        """
        Returns the count of records for the dataset (or a partition).

        Implementation is only required if the corresponding flag is set to True
        in the connector definition
        """
        raise Exception("Unimplemented")
