# Todos
## Important
* API calls inside the same plugin currently still go to the main server. Very inefficient.
* Pyro does not define an async interface. However adding one with some reading up in the [PSL](https://docs.python.org/3/library/asyncio-protocol.html)
should not be that hard. But there are also arguments for simply leaving the threadpoolexecutor. 
* Remote plugin logging to file is currently disabled as safe file access currently isn't implemented
* Add return values for plugin functions for JS client
* retrieving user vars fails for remote plugins
* traceback information for LOG.log_exception is false/missing a lot. Specific scenario where occured:
Called call_plugin_function with non existing method. Doesn't show where error originates from.
## General
* if new settings for plugins are added use them as a fallback when not yet specified
* Add basic plugin for nothing but sending commands to running server
* Plugins need a close method for freeing resources or similar. Currently even remote plugins just "die"
* Remote plugins calling other (remote) plugins go the route through the main server. Thats unnecessary
and adds overhead. Especially since each plugin has all the code needed to communicate with other plugins
* Plugin meta settings currently can't be set via the conf file of the plugin. For most settings this makes sense.
However for the venv_path, allowed_as_standalone, api_only etc it doesn't.
* reload plugins from chat
## Architecture
+ plugin_manager.py and more specificall the _PluginManager are a wild mix of module, instance and singleton pattern.
    
    However since commit `decc6b00` and the restructuring of thread and process local variables that is no
    longer necessary or even smart. It currently prohibits any sort of extension of the plugin system.
