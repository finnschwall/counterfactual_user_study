import functools
import functools as _functools
import enum as _enum
import inspect
import os
import threading
import plugins.conf as plugin_conf
import Pyro5
import Pyro5.api
import datetime
import traceback
import plugins.log_helper as log_helper

try:
    import click as _click
    from asgiref.sync import async_to_sync, sync_to_async

    if __name__ == "__main__":
        from django.conf import settings

except:
    pass
import json
import logging
from typing import Optional, Union

logger = logging.getLogger("API")
remote_logger = logging.getLogger("RemoteAPI")
_parsed_methods = {}
_available_functions = {}


def _ignore_self(func):
    def ret_func(*args, **kwargs):
        return func(*(args[1:]), **kwargs)

    return ret_func


def _create_class(class_name, static_methods):
    statics = {}
    for func in static_methods:
        statics[func.__name__] = Pyro5.server.expose(_ignore_self(func))
    created_class = type(class_name, (), statics)
    return created_class


class PluginType(_enum.Enum):
    UNSPECIFIED = 0
    """A plugin without predefined purpose"""
    NL_INFERENCE = 10
    """A plugin for generating natural language from (user) input"""
    DATA = 20
    """A plugin that is related to data and data exploration"""
    ML_MODEL = 30
    """A plugin that provides some form of ML inference"""
    SYSTEM = 40


class MessageLevel(_enum.StrEnum):
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


def plugin_init(namespace=None, name=None, is_local=False, plugin_type=PluginType.UNSPECIFIED, is_extension=False,
                allowed_as_standalone=True, venv_path=None, config=None, config_is_server_managed=False,
                only_api=False, hidden_in_function_dic=False, help=None):
    """
    The definition of any plugin. Despite the functional approach it is recommended to
    keep all true plugin functions (i.e. those that can be called automatically by the server) inside the same file. For
    local plugins this isn't optional.
    The function decorated with @plugin_init has to be the first plugin function in any file!
    The arguments of the 'plugin_init' decorator define how the plugin is handled by the server. After all plugins have
    been discovered the function itself is called to allow the plugins to make initializations.
    Long calculation times are irrelevant here.

    Example:

    .. code-block:: python

        standard_config = {"a_cool_plugin_variable":42}
        @plugin_init(namespace="MyCoolPluginNamespace", config=standard_config)
        def my_cool_plugin(ctx, config, meta_config):
            do_plugin_init_stuff()

    :ivar meta_config: The configuration defined by the plugin_init decorator
    :vartype meta_config: readonly dict
    :ivar config: The configuration defined by the plugin itself
    :vartype config: dict
    :ivar ctx: A context accessible by all plugin functions and those that share the namespace. Not thread safe!
    :vartype ctx: dict
    :ivar plugin_method: The decorator to make a function a plugin function.
    :vartype plugin_method: function


    :param namespace: The name used between all plugins that want to share the same process.
    :param name: The displayed name for the plugin. Also the name used to enter commands.
    :param plugin_type: See :class:`PluginType`
    :param is_extension: This determines load order if your plugin is an extension (or simply lives) in another plugins namespace and this plugin is reliant on it.
    :param allowed_as_standalone: Can be used to make an extension plugin loadable even if it's parent is not currently available.
    :param venv: Either path to venv or name of pyenv venv. Forces plugin to be loaded as separate process.
    :param config: A (template) dictionary that configures your plugin. It will be made available to all plugin methods.
    :param config_is_server_managed: If true then the config will be stored on the server and the here provided config will just be used as template.
    :param help: A description of what this plugin can do.
    """
    plugin_config = vars()

    # del plugin_config["kwargs"]

    def decorate_init(plugin_initializer):
        if not plugin_conf.plugin_system_active:
            return _FakeObj(plugin_initializer.__name__)

        if plugin_conf.parse_mode:
            plugin_initializer.plugin_config = plugin_config

        elif not plugin_conf.is_remote:
            conf = plugin_conf.cur_conf
            _parsed_methods[conf["name"]] = {"original": {}, "init": plugin_initializer, "click": {}}
            _parsed_methods[conf["name"]]["proc_loc"] = "local"
            ctx = _PluginContext()
            _cmd_group = _click.Group(name=conf["name"], hidden=conf["only_api"],
                                      help=conf["help"])  # , add_help_option=False)
            plugin_initializer.meta_config = conf
            plugin_initializer.config = conf["config"]

            plugin_initializer._cmd_group = _cmd_group
            plugin_initializer.ctx = ctx
            plugin_initializer.plugin_method = plugin_func_generator(_cmd_group, conf)
            plugin_initializer.api_init = _api_init_hook

            if conf["plugin_type"] == PluginType.NL_INFERENCE:
                plugin_conf.available_nlp_backends.append(conf["name"])

        elif plugin_conf.is_server:
            conf = plugin_conf.cur_conf
            _parsed_methods["init"] = plugin_initializer
            _parsed_methods["functions"] = {}
            ctx = _PluginContext()
            plugin_initializer.meta_config = conf
            plugin_initializer.config = conf["config"]
            plugin_initializer.ctx = ctx
            plugin_initializer.plugin_method = plugin_func_generator_server(conf)

        elif not plugin_conf.is_server:
            conf = plugin_conf.cur_conf
            _parsed_methods[conf["name"]] = {"original": {}, "init": plugin_initializer, "click": {}}
            _cmd_group = _click.Group(name=conf["name"])  # , add_help_option=False, no_args_is_help=False)
            plugin_initializer._cmd_group = _cmd_group
            plugin_initializer.plugin_method = plugin_func_generator_client(_cmd_group, conf)
            ctx = None

        @_functools.wraps(plugin_initializer)
        def wrapped_init(*args, **kwargs):
            return plugin_initializer(ctx, conf["config"], conf, *args, **kwargs)

        return wrapped_init

    return decorate_init


def _api_init_hook():
    def decorate_api_hook(plugin_api_hook):
        plugin_conf.api_init_funcs.append(plugin_api_hook)

        def wrapped_init(*args, **kwargs):
            raise Exception("You can't call a middleware function!")

        return wrapped_init

    return decorate_api_hook


def plugin_func_generator(group, config):
    def plugin_method(help=None, callable_only=False):
        def decorate_command(func_command):
            @_functools.wraps(func_command)
            def wrapped_command(*args, **kwargs):
                return func_command(args[0].obj, *(args[1:]), **kwargs)

            _parsed_methods[config["name"]]["original"][func_command.__name__.lower()] = func_command
            if not callable_only:
                _parsed_methods[config["name"]]["click"][func_command.__name__.lower()] = group.command(help=help)(
                    _click.pass_context(wrapped_command))
            return func_command

        return decorate_command

    plugin_method.config = config
    return plugin_method


def plugin_func_generator_client(group, config):
    """
    :meta private:
    """

    def plugin_method(help=None, callable_only=False):
        def decorate_command(func_command):
            def pyro_call(*args, **kwargs):
                uri = f"PYRO:{config['name']}@localhost:{config['port']}"
                proxy = Pyro5.api.Proxy(uri)
                proxy._pyroBind()
                ret_val = getattr(proxy, func_command.__name__)(args[0], *(args[1:]), **kwargs)
                if type(ret_val) == dict and "exc_type" in ret_val:
                    if plugin_conf.show_all_exceptions:
                        logger.debug(ret_val["full_traceback"])
                return ret_val

            @_functools.wraps(func_command)
            def wrapped_command(*args, **kwargs):
                return args[0].obj.call_plugin_function(config["name"], func_command.__name__, args[1:], kwargs=kwargs)

            def local_call(*args, **kwargs):
                return pyro_call(args[0].uid, *(args[1:]), **kwargs)

            local_call.direct_pyro = pyro_call

            _parsed_methods[config["name"]]["original"][func_command.__name__] = local_call
            if not callable_only:
                _parsed_methods[config["name"]]["click"][func_command.__name__] = group.command(help=help)(
                    _click.pass_context(wrapped_command))
            return wrapped_command

        return decorate_command

    plugin_method.config = config
    return plugin_method


def plugin_func_generator_server(config):
    """
    :meta private:
    """

    def plugin_method(*args, **kwargs):
        def decorate_command(func_command):

            @_functools.wraps(func_command)
            def mod_func(*args, **kwargs):
                uri = f"PYRO:{args[0]}@localhost:{config['remote_port']}"
                proxy_api = Pyro5.api.Proxy(uri)
                try:
                    ret_val = func_command(proxy_api, *(args[1:]), **kwargs)
                    return ret_val
                except Exception as e:
                    remote_logger.log_exception()
                    return
                    # return {"exc_type": type(e).__name__, "exc_message": str(e),
                    #         "full_traceback": log_helper.format_exception(e)}

            _parsed_methods["functions"][func_command.__name__] = mod_func
            return mod_func

        return decorate_command

    plugin_method.config = config
    return plugin_method


class MessageFlags(_enum.StrEnum):
    LONG_CALL_STARTED = "show_bot_loading"


class API(object):
    """
    .. warning::
        Do not create or save an API object! Outside the main thread this class has no meaning.
    """

    def __init__(self, uid,  consumer=None):
        self.uid = uid
        self._consumer = consumer
        # check is important to ensure this is server local API
        if consumer:
            self._scope = consumer.scope
            # print(self._scope["session"]["session_key"])
            if not "plugin_memory" in self._scope["session"]:
                self._scope["session"]["plugin_memory"] = {}
            for i in plugin_conf.api_init_funcs:
                try:
                    i(uid, self._scope)
                except Exception as e:
                    logger.log_exception()

    async def display_json(self, json_content):
        await self.send(text_data=json.dumps({"role": "JSON", "content": json_content}))

    async def display_html(self, html, forced_position=None):
        """
        Display HTML code to the user.
        :param html: the html code
        :param forced_position: Has to be "Top", "Bottom" or "Full". Otherwise the server will determine placement.
        """
        await self._consumer.send(text_data=json.dumps(
            {"role": "HTML", "content": html, "forced_position": forced_position}))

    async def display_plot(self, plot_object, auto_place=True, size=3, forced_position=None):
        """
        Display a (plotly) plot. For displaying matplotlib the matplotlib plugin is required.

        :param plot_object: The plot to be shown (Not converted to HTML!)
        :param auto_place: Wether or not the server should determine the position.
        :param size: int between 1 and 10, where 10 is full screen. Helps server determine placement and ensure readability.
        :param forced_position: Has to be "Top", "Bottom" or "Full". Otherwise the server will determine placement.
        """
        html = plot_object.to_html(include_plotlyjs=False, include_mathjax=False, full_html=False)
        await self._consumer.send(
            text_data=json.dumps({"role": "HTML", "content": html, "forced_position": forced_position}))

    async def save(self, key, val, level="user"):
        """
        Store something on the server database. Only meant for user specific info.

        :param key: key
        :param val: val (has to be string or JSON serializable)
        :param level: user, session or cookie. Determines type and location of storage. See django doc for more info.
        """
        self._scope["session"]["plugin_memory"][key] = val

    async def save_session(self):
        await sync_to_async(self._scope["session"].save)()

    async def retrieve(self, key):
        """
        Retrieve user based info.

        :param key: key
        :return: val or None if key is invalid or no longer exists.
        """
        if key in self._scope["session"]["plugin_memory"]:
            return self._scope["session"]["plugin_memory"][key]
        else:
            raise IndexError(f"'{key}' does not exist in the storage for this user")

    async def display_in_chat(self, obj):  # , role="server", contains_html=False, metadata=None):
        """
        :param obj: object to be displayed. Usually text. Can also be image, pdf or table.
        :param contains_html: Only valid for text. If true text will be displayed unescaped.
        """
        await self._consumer.send(text_data=json.dumps(obj))

    async def display_message(self, message: str, timeout: Optional[int] = 3,
                              level: Optional[MessageLevel] = MessageLevel.INFO) -> None:
        await self._consumer.send(
            text_data=json.dumps({"role": "status", "content": message, "timeout": timeout,
                                  "level": level}))

    async def send_flag(self, flag: MessageFlags):
        await self._consumer.send(
            text_data=json.dumps(
                {"role": "flag", "content": flag}))

    async def clear_conversations(self):
        del self._scope["session"]["conversations"]
        for i in plugin_conf.api_init_funcs:
            try:
                i(self.uid, self._scope)
            except Exception as e:
                logger.log_exception()

    async def get_available_conversations(self):
        return [i for i in self._scope["session"]["conversations"]["available"]]

    async def rebuild_conv_tracker(self):
        await self._consumer.send(text_data=json.dumps(
            {"update_conversation": await self.get_conv_tracker(to_openai=False, exlude_key="hidden"), "available_trackers": await self.get_available_conversations()}))

    async def get_conv_tracker(self, conv_id=None, to_openai=True, exlude_key=None):
        if not conv_id:
            conv_id = str(self._scope["session"]["conversations"]["active_id"])
        if conv_id not in self._scope["session"]["conversations"]["available"]:
            raise Exception("Given conv id not found in chat tracker for this user!")


        conv_tracker = self._scope["session"]["conversations"]["available"][conv_id]
        if exlude_key:
            conv_tracker = dict(conv_tracker)
            new_messages = []
            for i in conv_tracker["messages"]:
                if exlude_key not in i:
                    if "metadata" not in i or exlude_key not in i["metadata"]:
                        new_messages.append(i)
            conv_tracker["messages"] = new_messages
        if to_openai:
            converted = [{k: v for k, v in d.items() if k != "metadata"} for d in conv_tracker["messages"]]
            converted = [{k: v for k, v in d.items() if k != "msg_id"} for d in converted]
            return converted
        return conv_tracker

    async def add_to_conv_tracker(self, msg, role, add_metadata=None, add_keys=None):

        conv_tracker = await self.get_conv_tracker(to_openai=False)
        metadata = {"timestamp": datetime.datetime.now().strftime("%a %H:%M:%S")}
        if add_metadata:
            metadata.update(add_metadata)
        msg_entry = {"role": role, "content": msg,
                     "metadata": metadata,
                     "msg_id": conv_tracker["active_msg_id"] + 1}
        if add_keys:
            msg_entry.update(add_keys)
        conv_tracker["messages"].append(msg_entry)
        conv_tracker["active_msg_id"] += 1
        return msg_entry

    async def remove_last_conv_entry(self):
        conv_id = self._scope["session"]["conversations"]["active_id"]
        if conv_id not in self._scope["session"]["conversations"]["available"]:
            raise Exception("This is bad...")
        conv_tracker = self._scope["session"]["conversations"]["available"][conv_id]
        conv_tracker["messages"].pop()
        conv_tracker["active_msg_id"] -= 1

    async def call_plugin_function(self, plugin_name=None, function_name=None, args=(), kwargs={},
                                   user_inited=False, oneway=False):
        """

        :param plugin_name: Plugin in which function resides
        :param function_name: name of function
        :param args: args with which to call function. Has to be tuple e.g. (arg1, arg2,)
        :param kwargs: Keyword arguments for function. Has to be dict.
        :param user_inited: Should this call count against the users sync call limit
        :param oneway: Ignore return value and immediately return execution.
        :return: Function return value if there exists one and oneway is disabled.
        """
        try:
            if plugin_name is None:
                plugin_name, function_name = function_name.split("__")
            plugin_name = plugin_name.lower()
            function_name = function_name.lower()
            if plugin_name not in _parsed_methods:
                raise Exception(f"API call for '{plugin_name}.{function_name}' failed because '{plugin_name}' doesn't exist.")
            if function_name not in _parsed_methods[plugin_name]["original"]:
                raise Exception(f"API call for '{plugin_name}.{plugin_name}' failed because '{plugin_name}' doesn't exist.")
            func_to_call = _parsed_methods[plugin_name]["original"][function_name]

            call_type = 1 if "proc_loc" not in _parsed_methods[plugin_name] else 0
            if call_type == 1:
                func_to_call = func_to_call.direct_pyro
                args = (self.uid,) + args
                if kwargs != {}:
                    with_kwargs = functools.partial(func_to_call, **kwargs)
                    future = await plugin_conf.async_loop.run_in_executor(None, with_kwargs, *args)
                else:
                    future = await plugin_conf.async_loop.run_in_executor(None, func_to_call, *args)
                return future
            else:
                return await func_to_call(self, *args, **kwargs)
        except:
            logger.log_exception()


class JupyterAPI(API):
    """
    :meta private:
    """

    def __init__(self, uuid, h1, h2, *args):
        super(JupyterAPI, self).__init__(uuid, None)
        self.text_disp = h2
        self.gen_disp = h1
        from IPython.display import HTML
        self.HTML = HTML

    async def display_html(self, html, forced_position=None):
        try:
            self.gen_disp.update(self.HTML(html))
        except Exception as e:
            logger.warning("Unable to update IPython display. All API calls will now be printed",
                           extra={"only_once": True})
            print(html)

    async def display_plot(self, plot_object, autoplace=True, minimum_size=(200, 200), forced_position=None):
        try:
            self.gen_disp.update(self.HTML(plot_object.to_html(full_html=False)))
        except Exception as e:
            logger.warning("Unable to update IPython display. All API calls will now be printed",
                           extra={"only_once": True})
            print(plot_object)

    async def display_in_chat(self, obj, contains_html=False):
        obj = obj.replace('\n', '<br/>')
        try:
            self.text_disp.update(self.HTML(obj))
        except Exception as e:
            logger.warning("Unable to update IPython display. All API calls will now be printed",
                           extra={"only_once": True})
            print(obj)

    async def save(self, key, val, level="user"):
        pass

    async def retrieve(self, key):
        pass

    async def display_message(self, message: str, timeout: Optional[int] = 3,
                              level: Optional[MessageLevel] = MessageLevel.INFO) -> None:

        print(f"Message with level {level}:\n{message}")


class JupyterSyncAPI(API):
    """
    :meta private:
    """

    def __init__(self, uuid, h1, h2, *args):
        super(JupyterSyncAPI, self).__init__(uuid, None)
        self.text_disp = h2
        self.gen_disp = h1
        from IPython.display import HTML
        self.HTML = HTML

    @Pyro5.server.expose
    def display_html(self, html, forced_position=None):
        try:
            self.gen_disp.update(self.HTML(html))
        except Exception as e:
            logger.warning("Unable to update IPython display. All API calls will now be printed",
                           extra={"only_once": True})
            print(html)

    @Pyro5.server.expose
    def display_plot(self, plot_object, autoplace=True, minimum_size=(200, 200), forced_position=None):
        try:
            self.gen_disp.update(self.HTML(plot_object.to_html(full_html=False)))
        except Exception as e:
            logger.warning("Unable to update IPython display. All API calls will now be printed",
                           extra={"only_once": True})
            print(plot_object)

    @Pyro5.server.expose
    def display_in_chat(self, obj, contains_html=False):
        obj = obj.replace('\n', '<br/>')
        try:
            self.text_disp.update(self.HTML(obj))
        except Exception as e:
            logger.warning("Unable to update IPython display. All API calls will now be printed",
                           extra={"only_once": True})
            print(obj)

    @Pyro5.server.expose
    def save(self, key, val, level="user"):
        pass

    @Pyro5.server.expose
    def retrieve(self, key):
        pass

    @Pyro5.server.expose
    def display_message(self, message: str, timeout: Optional[int] = 3,
                        level: Optional[MessageLevel] = MessageLevel.INFO) -> None:

        print(f"Message with level {level}:\n{message}")


class NoneAPI(API):
    """
        :meta private:
    """

    def __init__(self, uid):
        super(NoneAPI, self).__init__(uid)

    async def display_html(self, html, forced_position=None):
        logger.debug(f"Failed display_html call. {NoneAPI.args_to_string(locals())}")

    async def display_plot(self, plot_object, auto_place=True, size=3, forced_position=None):
        logger.debug(f"Failed display_plot call. {NoneAPI.args_to_string(locals())}")

    async def save(self, key, val, level="user"):
        logger.debug(f"Failed save call. {NoneAPI.args_to_string(locals())}")

    async def retrieve(self, key):
        logger.debug(f"Failed retrieve call. {NoneAPI.args_to_string(locals())}")

    async def display_in_chat(self, obj, contains_html=False):
        logger.debug(f"Failed display_in_chat call. \"{NoneAPI.args_to_string(locals())}\"")

    async def display_message(self, message: str, timeout: Optional[int] = 3,
                              level: Optional[MessageLevel] = MessageLevel.INFO) -> None:
        logger.debug(f"Failed show_message call. msg: '{message}' level: '{level}'")

    @staticmethod
    def args_to_string(args):
        ret_str = ""
        for i in args:
            ret_str += f"'{i}': '{args[i]}'"
        return ret_str


def is_plugin_available(plugin_name):
    if plugin_name in _parsed_methods:
        return True
    return False


def _nothing():
    pass


class _FakeObj:
    def __init__(self, name=None):
        if not name:
            name = "MISSING"

        self.HIDDEN_NAME_XYZ = name

    def __call__(self, *args, **kwargs):
        logger.warning(
            f"A plugin function is called before the plugin system has been loaded! Likely origin: \"{self.HIDDEN_NAME_XYZ}\" ",
            extra={"only_once": True})
        return lambda *args_, **kwargs_: _nothing()

    def __getattribute__(self, attr):
        if attr == "__dict__" or attr == "HIDDEN_NAME_XYZ":
            return super().__getattribute__(attr)
        return _FakeObj(self.HIDDEN_NAME_XYZ + "." + str(attr))


class _PluginContext:
    def __init__(self):
        pass


option = _click.option
"""
Add optional arguments to a function. They are added with '--ARG VAR'

Example:

.. code-block:: python

    @plugin_init_function.plugin_method()
    @option('--stuff', default=False, help='Do some stuff')
    def a_plugin_function_with_options(api, stuff):
        print(stuff)
"""

argument = _click.argument
"""
Add an arguments to a function. They can't be specified and are not optional

Example:

.. code-block:: python

    @plugin_init_function.plugin_method()
    @argument('stuff')
    def a_plugin_function_with_options(api, stuff):
        #stuff will never be None
        print(stuff)
"""
