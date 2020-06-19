import requests
import copy
import json

DEFAULT_DESCRIPTOR = "default"
EDGE_NAME = "edge_name"
RESOURCE = "resource_name"
API_URL = "api"
ON_RETURN = "on_return"
QUERY_STRING = "query_string"
RECIPE_INPUT = "recipe_input"
PARAMS = "query_string"
COLUMN_FORMATING = "column_formating"
COLUMN_CLEANING = "column_cleaning"
COLUMN_EXPANDING = "column_expending"
COLUMN_UNESCAPING = "column_unescaping"
CHANNEL_ID = "{channel_id}"
PART = "{part}"
VIDEO_ID = "{video_id}"
COMMENT_ID = "{comment_id}"
PLAYLIST_ID = "{playlist_id}"
SUBSCRIPTION_ID = "{subscription_id}"

youtube_api = {
    DEFAULT_DESCRIPTOR: {
        RESOURCE: "{edge_name}",
        API_URL: "https://www.googleapis.com/youtube/v3/",  # {edge_name}?channelId={video_id}&key={api_key}&part={parts}
        ON_RETURN: {
            200: "data",
            401: "The user is not logged in",
            500: "Youtube Server Error"
        }
    },
    "edge_name": {
        "playlists": {
            RESOURCE: "{edge_name}",
            QUERY_STRING: {
                "channelId": CHANNEL_ID,
                "id": PLAYLIST_ID,
                "part": PART
            },
            COLUMN_EXPANDING: ["contentDetails", "player", "snippet"]
        },
        "videos": {
            QUERY_STRING: {
                "id": VIDEO_ID,
                "part": PART
            },
            RECIPE_INPUT: "id",
            COLUMN_EXPANDING: ["contentDetails", "player", "snippet", "status"]
        },
        "channels": {
            QUERY_STRING: {
                "categoryId": "{category_id}",
                "id": CHANNEL_ID,
                "part": PART,
                "forUsername": "{for_user_name}"
            },
            COLUMN_EXPANDING: ["brandingSettings", "contentDetails", "status", "topicDetails", "statistics", "contentOwnerDetails", "snippet"]
        },
        "comments": {
            QUERY_STRING: {
                "part": PART,
                "id": COMMENT_ID,
                "parentId": "{parent_id}"
            },
            RECIPE_INPUT: "id",
            COLUMN_EXPANDING: ["snippet"]
        },
        "commentThreads": {
            QUERY_STRING: {
                "part": PART,
                "videoId": VIDEO_ID,
                "channelId": CHANNEL_ID,
                "allThreadsRelatedToChannelId": "{allThreadsRelatedToChannelId}",
                "id": COMMENT_ID
            },
            COLUMN_EXPANDING: ["snippet", "replies"],
            COLUMN_UNESCAPING: ["snippet_topLevelComment_snippet_textDisplay", "snippet_topLevelComment_snippet_textOriginal"]
        },
        "playlistItems": {
            QUERY_STRING: {
                "part": PART,
                "playlistId": PLAYLIST_ID
            },
            COLUMN_EXPANDING: ["contentDetails", "snippet", "status"],
        },
        "subscriptions": {
            QUERY_STRING: {
                "part": PART,  # contentDetails id snippet subscriberSnippet
                "channelId": CHANNEL_ID,
                "id": SUBSCRIPTION_ID,
                "mine": "",
                "myRecentSubscribers": "",
                "mySubscribers": ""
            },
            COLUMN_EXPANDING: ["contentDetails", "snippet", "subscriberSnippet"],
            COLUMN_UNESCAPING: ["snippet_description"]
        },
        "dss_recipe": {
            QUERY_STRING: {
                "part": PART,
                "id": "{id}"
            }
        }
    }
}


class YoutubeClient(object):

    def __init__(self, config):
        self.config = config
        self.access_token = self.config.get("api-key")
        self.oauth_access_token = self.config.get("access_token")
        self.next_page = {}
        self.default_api = youtube_api
        self.formating = None
        self.expanding = None
        self.cleaning = None

    def start_session(self, edge_descriptor):
        self.formating = edge_descriptor.get(COLUMN_FORMATING, [])
        self.expanding = edge_descriptor.get(COLUMN_EXPANDING, [])
        self.unescaping = edge_descriptor.get(COLUMN_UNESCAPING, [])
        self.cleaning = edge_descriptor.get(COLUMN_CLEANING, [])
        if self.formating == [] and self.expanding == [] and self.cleaning == []:
            self.format = self.return_data
        else:
            self.format = self.format_data

    def extract_args(self, **kwargs):
        extracted = {}
        for kwarg in kwargs:
            if isinstance(kwargs[kwarg], list):
                extracted[kwarg] = ",".join(kwargs[kwarg])
            else:
                extracted[kwarg] = kwargs[kwarg]
        return extracted

    def get_edge(self, **kwargs):
        edge_name = kwargs.get("edge_name", None)
        edge_descriptor = self.get_edge_descriptor(edge_name)
        self.start_session(edge_descriptor)
        params = self.get_edge_params(edge_descriptor, **kwargs)
        url = self.get_edge_url(edge_descriptor, **kwargs)
        headers = self.get_headers()
        response = requests.get(url, params=params, headers=headers)
        self.assert_valid_response(response, edge_descriptor, **kwargs)
        json_response = response.json()
        self.store_next_page(url, headers, params, json_response)
        return json_response.get("items", [])

    def start_recipe_session(self, edge_name):
        self.edge_descriptor = self.get_edge_descriptor(edge_name)

    def get_edge_from_recipe(self, **kwargs):
        url = self.get_edge_url(self.edge_descriptor, **kwargs)
        headers = self.get_headers()
        params = self.get_edge_params(self.get_edge_descriptor("dss_recipe"), **kwargs)
        response = requests.get(url, params=params, headers=headers)
        self.assert_valid_response(response, self.edge_descriptor, **kwargs)

    def get_headers(self):
        headers = {}
        if self.oauth_access_token is not None:
            headers["Authorization"] = "Bearer {}".format(self.oauth_access_token)
        return headers

    def get_edge_url(self, edge_descriptor, **kwargs):
        base_url_template = self.extract_from_edge_descriptor(API_URL, edge_descriptor)
        ressource_template = self.extract_from_edge_descriptor(RESOURCE, edge_descriptor)
        base_url = self.format_template(base_url_template, **kwargs)
        ressource = self.format_template(ressource_template, **kwargs)
        return "{base_url}{ressource}".format(base_url=base_url, ressource=ressource)

    def get_edge_params(self, edge_descriptor, **kwargs):
        query_string_dict = self.extract_from_edge_descriptor(QUERY_STRING, edge_descriptor)
        query_string = {}
        for key in query_string_dict:
            query_string_template = query_string_dict[key]
            query_string_value = self.format_template(query_string_template, **kwargs)
            if query_string_value is not None and query_string_value != "" and query_string_value != "[]":
                query_string.update({key: query_string_value})
        if self.access_token is not None:
            query_string.update({"access_token": self.access_token})
        return query_string

    def assert_valid_response(self, response, edge_descriptor, **kwargs):
        if response.status_code >= 400:
            response_error = self.get_error(response)
            error_templates = self.extract_from_edge_descriptor(ON_RETURN, edge_descriptor)
            error_template = error_templates.get(response.status_code, "Error: {}".format(response_error))
            error_message = self.format_template(error_template, **kwargs)
            raise Exception(error_message)
        return True

    def format_data(self, data):
        for key in self.formating:
            path = self.formating[key]
            data[key] = self.extract(data, path)
        for key in self.expanding:
            data = self.expand(data, key)
        for key in self.unescaping:
            if key in data:
                data[key] = amp_unescape(data[key])
        for key in self.cleaning:
            data.pop(key, None)
        return self.escape_json(data)

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
        except Exception:
            return response.text

    def format_template(self, template, **kwargs):
        try:
            template = template.format(**kwargs)
        except KeyError as key:  # This has to go
            template = ""
        return template

    def get_params_dict(self, edge_descriptor):
        query_string_template = edge_descriptor.get(QUERY_STRING, None)
        if query_string_template is None:
            query_string_template = self.default_api[DEFAULT_DESCRIPTOR].get(QUERY_STRING)
        return query_string_template

    def extract_from_edge_descriptor(self, item, edge_descriptor):
        query_string_template = edge_descriptor.get(item, None)
        if query_string_template is None:
            query_string_template = self.default_api[DEFAULT_DESCRIPTOR].get(item)
        return query_string_template

    def get_edge_descriptor(self, edge_name):
        edge_descriptor = copy.deepcopy(self.default_api[DEFAULT_DESCRIPTOR])
        if edge_name in self.default_api[EDGE_NAME]:
            update_dict(edge_descriptor, self.default_api[EDGE_NAME][edge_name])
        return edge_descriptor

    def expand(self, dictionary, key_to_expand):
        if key_to_expand in dictionary:
            self.dig(dictionary, dictionary[key_to_expand], [key_to_expand])
            dictionary.pop(key_to_expand, None)
        return dictionary

    def dig(self, dictionary, element_to_expand, path_to_element):
        if not isinstance(element_to_expand, dict):
            dictionary["_".join(path_to_element)] = element_to_expand
        else:
            for key in element_to_expand:
                new_path = copy.deepcopy(path_to_element)
                new_path.append(key)
                self.dig(dictionary, element_to_expand[key], new_path)

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
            self.next_page["nextPageToken"] = next_page_token
            self.next_page["url"] = url
            self.next_page["headers"] = headers
            self.next_page["params"] = params
        else:
            self.next_page = {}

    def has_next_page(self):
        return self.next_page != {}

    def get_next_page(self):
        params = {}
        params = self.next_page["params"]
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
