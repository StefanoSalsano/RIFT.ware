# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#
# Author(s): Max Beckett
# Creation Date: 9/5/2015
# 

import urllib.parse
import base64

def split_url(url):
    is_operation = False
    url_parts = urllib.parse.urlsplit(url)
    whole_url = url_parts[2]
    if whole_url.startswith("/api/operational/"):
        relevant_url = whole_url.split("/api/operational/", 1)[-1]
    elif whole_url.startswith("/api/operations/"):
        is_operation = True
        relevant_url = whole_url.split("/api/operations/", 1)[-1]
    elif whole_url.startswith("/api/running/"):
        relevant_url = whole_url.split("/api/running/", 1)[-1]
    elif whole_url.startswith("/api/running"):
        relevant_url = whole_url.split("/api/running", 1)[-1]
    elif whole_url.startswith("/api/config/"):
        relevant_url = whole_url.split("/api/config/", 1)[-1]
    elif whole_url.startswith("/api/config"):
        relevant_url = whole_url.split("/api/config", 1)[-1]
    elif whole_url.startswith("/api/schema"):
        relevant_url = whole_url.split("/api/schema", 1)[-1]
    else:
        raise ValueError("unknown url component in %s" % whole_url)

    url_pieces = relevant_url.split("/")

    return url_pieces, relevant_url, url_parts[3], is_operation

def split_stream_url(url):
    """Splits the stream URL.

    Arguments:
        url - stream URL received when a stream is opened

    Stream URL has the following parts
        stream protocol - indicates HTTP or Websocket stream
        stream name - name of the stream
        optional filter - filter to be applied on the stream
        optional start-time - start-time for the replay feature
        optional stop-time - stop-time for the replay feature

    Reference: draft-ietf-netconf-restconf-09
    Sample:
      For filter = /event/event-class='fault'
      URL: /streams/NETCONF?filter=%2Fevent%2Fevent-class%3D'fault'

      For start-time = 2014-10-25T10:02:00Z
      URL: /ws_streams/NETCONF?start-time=2014-10-25T10%3A02%3A00Z
    """
    url_parts = urllib.parse.urlsplit(url)
    stream_name = url_parts.path.split('/')[2]
    if stream_name.endswith("-JSON"):
        stream_name = stream_name[:-5]
        encoding = "json"
    else:
        encoding = "xml"

    query = urllib.parse.parse_qs(url_parts.query)
    filt = query["filter"] if "filter" in query else None
    start_time = query["start-time"] if "start-time" in query else None
    stop_time = query["stop-time"] if "stop-time" in query else None

    return stream_name, encoding, filt, start_time, stop_time

def is_config(url):
    url_parts = urllib.parse.urlsplit(url)
    whole_url = url_parts[2]
    return whole_url.startswith("/api/running") or whole_url.startswith("/api/config")

def is_schema_api(url):
    url_parts = urllib.parse.urlsplit(url)
    whole_url = url_parts[2]
    return whole_url.startswith("/api/schema")

def get_username_and_password_from_auth_header(auth_header):
    """Gets the username and password from the auth_header

    Arguments:
    auth_header - Encoded auth_header received for basic auth

    Returns: Decoded username and password.
    """
    if not auth_header.startswith("Basic "):
        raise ValueError("only supoprt for basic authorization")

    encoded = auth_header[6:]
    decoded = base64.decodestring(bytes(encoded, "utf-8")).decode("utf-8")
    username, password = decoded.split(":", 2)
    return username, password

