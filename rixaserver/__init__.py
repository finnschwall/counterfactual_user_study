import os
import sys


def _change_to_local():
    parent_dir = os.path.dirname(__path__[0])
    sys.path.insert(0, parent_dir)
    # os.chdir(parent_dir)


def launch():
    _change_to_local()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RIXAWebserver.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


def plugin_conf():
    _change_to_local()
    from .plugin_configurator import plug_conf
    plug_conf(sys.argv[1:])
