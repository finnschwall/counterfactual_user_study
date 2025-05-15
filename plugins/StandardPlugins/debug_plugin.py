import click
import time
import sys
from plugins.api import *
import json
from django.conf import settings

@plugin_init(name="debug", is_local=True, hidden_in_function_dic=True, help="General debugging stuff")
def data(ctx, config, meta_config):
    pass

@data.plugin_method()
async def shutdown(api):
    import plugins.plugin_manager
    plugins.plugin_manager._PluginLoader.shutdown_server()


@data.plugin_method()
@argument("to_print")
async def print_to_chat(api, to_print):
    await api.display_in_chat(to_print)


@data.plugin_method()
async def show_json_session(api):
    session = json.dumps(dict(api.scope["session"]))
    await api.display_json(session)


@data.plugin_method()
async def write_to_html(api, html_obj):
    await api.display_html(html_obj)


@data.plugin_method()
@argument("time")
async def halt_server(api, time):
    await api.display_message(f"Waiting for {time}")
    time.sleep(time)
    await api.display_message(f"Finished waiting")

@data.plugin_method()
async def disable_nlp(api):
    settings.NLP_BACKEND = "none"
    await api.display_message("NLP processing disabled")

@data.plugin_method()
async def enable_nlp(api):
    settings.NLP_BACKEND = "chatgpt"
    await api.display_message("NLP processing enabled")