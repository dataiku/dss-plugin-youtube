import requests
import copy
import json
import logging

API_URL = "api"
CHANNEL_ID = "{channel_id}"
COLUMN_CLEANING = "column_cleaning"
COLUMN_EXPANDING = "column_expending"
COLUMN_FORMATTING = "column_formatting"
COLUMN_UNESCAPING = "column_unescaping"
COMMENT_ID = "{comment_id}"
DEFAULT_DESCRIPTOR = "default"
ENDPOINT = "endpoint"
ITEM_ID_EQUIVALENT = "item_id_equivalent"
ON_RETURN = "on_return"
PARAMS = "query_string"
PART = "{part}"
PLAYLIST_ID = "{playlist_id}"
QUERY_STRING = "query_string"
RECIPE_INPUT = "recipe_input"
RESOURCE = "resource_name"
SUBSCRIPTION_ID = "{subscription_id}"
VIDEO_ID = "{video_id}"

youtube_api = {
    DEFAULT_DESCRIPTOR: {
        RESOURCE: "{endpoint}",
        API_URL: "https://www.googleapis.com/youtube/v3/",  # {endpoint}?channelId={video_id}&key={api_key}&part={parts}
        ON_RETURN: {
            200: "data",
            401: "The user is not logged in",
            500: "Youtube Server Error"
        }
    },
    ENDPOINT: {
        "channels": {
            QUERY_STRING: {
                "categoryId": "{category_id}",
                "id": CHANNEL_ID,
                "part": "{channels_part}",
                "forUsername": "{for_user_name}"
            },
            COLUMN_EXPANDING: ["brandingSettings", "contentDetails", "status", "topicDetails", "statistics", "contentOwnerDetails", "snippet"]
        },
        "comments": {
            QUERY_STRING: {
                "part": "{comments_part}",
                "id": COMMENT_ID,
                "parentId": "{parent_id}"
            },
            ITEM_ID_EQUIVALENT: "playlist_id",
            RECIPE_INPUT: "id",
            COLUMN_EXPANDING: ["snippet"]
        },
        "commentThreads": {
            QUERY_STRING: {
                "part": "{commentThreads_part}",
                "videoId": VIDEO_ID,
                "channelId": CHANNEL_ID,
                "all_threads_related_to_channel_id": "{all_threads_related_to_channel_id}",
                "id": COMMENT_ID
            },
            ITEM_ID_EQUIVALENT: VIDEO_ID,
            COLUMN_EXPANDING: ["snippet", "replies"],
            COLUMN_UNESCAPING: ["snippet_topLevelComment_snippet_textDisplay", "snippet_topLevelComment_snippet_textOriginal"]
        },
        "dss_recipe": {
            QUERY_STRING: {
                "part": "{dss_recipe_part}",
                "id": "{id}"
            }
        },
        "playlistItems": {
            QUERY_STRING: {
                "part": "{playlistItems_part}",
                "playlistId": PLAYLIST_ID
            },
            COLUMN_EXPANDING: ["contentDetails", "snippet", "status"],
        },
        "playlists": {
            RESOURCE: "{endpoint}",
            QUERY_STRING: {
                "channelId": CHANNEL_ID,
                "id": PLAYLIST_ID,
                "part": "{playlists_part}"
            },
            COLUMN_EXPANDING: ["contentDetails", "player", "snippet"]
        },
        "playlists_channelid": {
            RESOURCE: "playlists",
            QUERY_STRING: {
                "channelId": CHANNEL_ID,
                "part": "{playlists_part}"
            },
            COLUMN_EXPANDING: ["contentDetails", "player", "snippet"]
        },
        "subscriptions": {
            QUERY_STRING: {
                "part": "{subscriptions_part}",  # contentDetails id snippet subscriberSnippet
                "channelId": CHANNEL_ID,
                "id": SUBSCRIPTION_ID,
                "mine": "",
                "myRecentSubscribers": "",
                "mySubscribers": ""
            },
            COLUMN_EXPANDING: ["contentDetails", "snippet", "subscriberSnippet"],
            COLUMN_UNESCAPING: ["snippet_description"]
        },
        "videos": {
            QUERY_STRING: {
                "id": VIDEO_ID,
                "part": "{videos_part}"
            },
            RECIPE_INPUT: "id",
            COLUMN_EXPANDING: ["contentDetails", "player", "snippet", "status"]
        }
    }
}

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format='youtube plugin %(levelname)s - %(message)s')


class YoutubeClient(object):

    def __init__(self, config):
        self.config = config
        self.access_token = self.config.get("api-key")
        self.oauth_access_token = self.config.get("access_token")
        self.next_page = None
        self.default_api = youtube_api
        self.formatting = None
        self.expanding = None
        self.cleaning = None
        self.unescaping = None
        self.format = None
        self.endpoint_descriptor = None
        self.initial_data_process_loop = None

    def start_session(self, endpoint_descriptor):
        self.formatting = endpoint_descriptor.get(COLUMN_FORMATTING, [])
        self.expanding = endpoint_descriptor.get(COLUMN_EXPANDING, [])
        self.unescaping = endpoint_descriptor.get(COLUMN_UNESCAPING, [])
        self.cleaning = endpoint_descriptor.get(COLUMN_CLEANING, [])
        if self.formatting == [] and self.expanding == [] and self.cleaning == []:
            self.format = self.return_data
        else:
            self.format = self.format_data

    @staticmethod
    def extract_args(**kwargs):
        extracted = {}
        for kwarg in kwargs:
            if isinstance(kwargs[kwarg], list):
                extracted[kwarg] = ",".join(kwargs[kwarg])
            else:
                extracted[kwarg] = kwargs[kwarg]
        return extracted

    def get_endpoint(self, raise_exception=True, **kwargs):
        endpoint = kwargs.get("endpoint", None)
        endpoint_descriptor = self.get_endpoint_descriptor(endpoint)
        self.start_session(endpoint_descriptor)
        params = self.get_endpoint_params(endpoint_descriptor, **kwargs)
        url = self.get_endpoint_url(endpoint_descriptor, **kwargs)
        headers = self.get_headers()
        response = requests.get(url, params=params, headers=headers)
        if raise_exception:
            self.assert_valid_response(response, endpoint_descriptor, **kwargs)
            json_response = response.json()
        else:
            if response.status_code < 400:
                json_response = response.json()
            else:
                error_message = self.extract_error_message(response, endpoint_descriptor, **kwargs)
                json_response = {"items": [{"error": error_message}]}
        self.store_next_page(url, headers, params, json_response)
        self.initial_data_process_loop = True
        return json_response.get("items", [])

    def start_recipe_session(self, endpoint):
        self.endpoint_descriptor = self.get_endpoint_descriptor(endpoint)

    def get_endpoint_from_recipe(self, **kwargs):
        url = self.get_endpoint_url(self.endpoint_descriptor, **kwargs)
        headers = self.get_headers()
        params = self.get_endpoint_params(self.get_endpoint_descriptor("dss_recipe"), **kwargs)
        response = requests.get(url, params=params, headers=headers)
        self.assert_valid_response(response, self.endpoint_descriptor, **kwargs)

    def get_headers(self):
        headers = {}
        if self.oauth_access_token is not None:
            headers["Authorization"] = "Bearer {}".format(self.oauth_access_token)
        return headers

    def get_item_id_equivalent(self, endpoint):
        endpoint_descriptor = self.get_endpoint_descriptor(endpoint)
        return endpoint_descriptor.get(ITEM_ID_EQUIVALENT, "item_id")

    def get_endpoint_url(self, endpoint_descriptor, **kwargs):
        base_url_template = self.extract_from_endpoint_descriptor(API_URL, endpoint_descriptor)
        resource_template = self.extract_from_endpoint_descriptor(RESOURCE, endpoint_descriptor)
        base_url = self.format_template(base_url_template, **kwargs)
        ressource = self.format_template(resource_template, **kwargs)
        return "{base_url}{ressource}".format(base_url=base_url, ressource=ressource)

    def get_endpoint_params(self, endpoint_descriptor, **kwargs):
        query_string_dict = self.extract_from_endpoint_descriptor(QUERY_STRING, endpoint_descriptor)
        query_string = {}
        for key in query_string_dict:
            query_string_template = query_string_dict[key]
            query_string_value = self.format_template(query_string_template, **kwargs)
            if query_string_value is not None and query_string_value != "" and query_string_value != "[]":
                query_string.update({key: query_string_value})
        if self.access_token is not None:
            query_string.update({"access_token": self.access_token})
        return query_string

    def assert_valid_response(self, response, endpoint_descriptor, **kwargs):
        if response.status_code >= 400:
            error_message = self.extract_error_message(response, endpoint_descriptor, **kwargs)
            raise Exception(error_message)
        return True

    def extract_error_message(self, response, endpoint_descriptor, **kwargs):
        response_error = self.get_error(response)
        error_templates = self.extract_from_endpoint_descriptor(ON_RETURN, endpoint_descriptor)
        error_template = error_templates.get(response.status_code, "Error: {}".format(response_error))
        error_message = self.format_template(error_template, **kwargs)
        return error_message

    def format_data(self, data):
        for key in self.formatting:
            path = self.formatting[key]
            data[key] = self.extract(data, path)
        for key in self.expanding:
            data = self.expand(data, key)
        for key in self.unescaping:
            if key in data:
                data[key] = amp_unescape(data[key])
        for key in self.cleaning:
            data.pop(key, None)
        return self.escape_json(data)

    def extract(self, main_dict, path):
        pointer = main_dict
        for element in path:
            if element in pointer:
                pointer = pointer.get(element)
            else:
                return None
        return pointer

    def return_data(self, data):
        return self.escape_json(data)

    def escape_json(self, data):
        for key in data:
            if isinstance(data[key], dict) or isinstance(data[key], list):
                data[key] = json.dumps(data[key])
        return data

    def get_error(self, response):
        try:
            json_response = response.json()
            json_response = json_response.get("error", json_response)
            json_response = json_response.get("message", json_response)
            return json_response
        except Exception as err:
            logger.warn("Error while parsing the response's json: {}".format(err))
            return response.text

    def format_template(self, template, **kwargs):
        try:
            template = template.format(**kwargs)
        except KeyError:
            template = ""
        return template

    def get_params_dict(self, endpoint_descriptor):
        query_string_template = endpoint_descriptor.get(QUERY_STRING, None)
        if query_string_template is None:
            query_string_template = self.default_api[DEFAULT_DESCRIPTOR].get(QUERY_STRING)
        return query_string_template

    def extract_from_endpoint_descriptor(self, item, endpoint_descriptor):
        query_string_template = endpoint_descriptor.get(item, None)
        if query_string_template is None:
            query_string_template = self.default_api[DEFAULT_DESCRIPTOR].get(item)
        return query_string_template

    def get_endpoint_descriptor(self, endpoint):
        endpoint_descriptor = copy.deepcopy(self.default_api[DEFAULT_DESCRIPTOR])
        if endpoint in self.default_api[ENDPOINT]:
            update_dict(endpoint_descriptor, self.default_api[ENDPOINT][endpoint])
        return endpoint_descriptor

    def expand(self, dictionary, key_to_expand):
        if key_to_expand in dictionary:
            self.dig(dictionary, dictionary[key_to_expand], [key_to_expand])
            dictionary.pop(key_to_expand, None)
        return dictionary

    def dig(self, dictionary, subkey_to_expand, path_to_subkey):
        """Recurses into dict pointed by path_to_subkey until the key contains something else then a dict."""
        if not isinstance(subkey_to_expand, dict):
            dictionary["_".join(path_to_subkey)] = subkey_to_expand
        else:
            for key in subkey_to_expand:
                new_path = copy.deepcopy(path_to_subkey)
                new_path.append(key)
                self.dig(dictionary, subkey_to_expand[key], new_path)

    def get(self, url, headers=None, json=None, params={}):
        args = {}
        args["url"] = url
        if headers is not None:
            args["headers"] = headers
        if json is not None:
            args["json"] = json
        if params is not None and params != {}:
            args["params"] = params
        response = requests.get(**args)
        if response.status_code >= 400:
            raise Exception("Error {}: {}".format(response.status_code, response.text))
        json_response = response.json()
        self.store_next_page(url, headers, params, json_response)
        return json_response

    def store_next_page(self, url, headers, params, json_response):
        next_page_token = json_response.get("nextPageToken", None)
        if next_page_token is not None:
            self.next_page = {
                "nextPageToken": next_page_token,
                "url": url,
                "headers": headers,
                "params": params
            }
        else:
            self.next_page = {}

    def has_data_to_process(self):
        if self.initial_data_process_loop:
            self.initial_data_process_loop = False
            return True
        else:
            return self.has_next_page()

    def has_next_page(self):
        return self.next_page is None or self.next_page != {}

    def get_next_page(self):
        params = {}
        params = self.next_page.get("params")
        if params is None:
            return []
        params["pageToken"] = self.next_page["nextPageToken"]
        json_response = self.get(self.next_page["url"], headers=self.next_page["headers"], params=params)
        data = json_response.get("items", [])
        return data


def update_dict(base_dict, extended_dict):
    for key, value in extended_dict.items():
        if isinstance(value, dict):
            base_dict[key] = update_dict(base_dict.get(key, {}), value)
        else:
            base_dict[key] = value
    return base_dict


def amp_unescape(to_unescape):
    to_convert = {'&quot;': '"', "&apos;": "'", "&lt;": "<", "&gt;": ">", "&amp;": "&", "&#x2F;": "/", "&#39;": "'"}
    for key in to_convert:
        to_unescape = to_unescape.replace(key, to_convert[key])
    return to_unescape
