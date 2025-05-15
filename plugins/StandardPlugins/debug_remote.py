import threading

import click
import time
import sys
from plugins.api import *
import json

@plugin_init(name="debug_remote", hidden_in_function_dic=True, help="Remote debugging stuff")
def data(ctx, config, meta_config):
    pass


@data.plugin_method()
@argument("to_print")
def print_to_chat(api, to_print):
    api.display_in_chat(to_print)

@data.plugin_method()
@argument("to_print")
def raise_exception(api, to_print):
    raise Exception(to_print)


@data.plugin_method()
def write_to_html(api, html_obj):
    api.display_html(html_obj)


@data.plugin_method()
@argument("tts", type=int)
def halt_server(api, tts):
    api.display_message(f"Waiting for {tts}")
    time.sleep(tts)
    api.display_message(f"Finished waiting")
