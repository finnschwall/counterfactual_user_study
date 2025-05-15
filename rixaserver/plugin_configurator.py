import click
import subprocess
import os
import sys
import shutil
import rixaserver

def query_yes_no(question, default="no"):
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


@click.group()
def plug_conf():
    pass


@plug_conf.command()
@click.argument('path', required=False)
def initialize_dir(path):
    if not path:
        path = os.getcwd()
    if not os.path.isdir(path):
        raise Exception(f"'{path}' is not a valid directory path!")
    if len(os.listdir(path)) != 0:
        should_continue = query_yes_no("The directory you want to use as a working dir is not empty. Continue anyway?")
        if not should_continue:
            print("Exiting...")
            return

    try:
        import rixawebserver.plugins as pl
        import shutil
        example_path = os.path.join(pl.__path__[0], "example_wd")
        for i in os.listdir(example_path):
            copy_path = os.path.join(example_path, i)
            if os.path.isdir(copy_path):
                os.mkdir(os.path.join(path, i))
            else:
                shutil.copy2(copy_path, path)
        print(f"New working directoy has been set up in {path}.")

    except Exception as e:
        print(e)


@plug_conf.command(help="Dump all available public settings into a file. Format may be incorrect.")
@click.argument("path")
def dump_settings(path):
    rixaserver._change_to_local()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RIXAWebserver.settings')
    from django.conf import settings
    with open(path, "w") as file:
        for i in settings.ALL_SETTINGS:
            file.write(f"{i}={settings.ALL_SETTINGS[i]}\n")


@plug_conf.command(help="Not working as of now!")
def register_plugin():
    pass

# @plug_conf.command()
# def open_config_location():
#     path = ""
#     try:
#         if "win" in sys.platform:
#             os.startfile(path)
#         if os.name == "posix":
#             opener = "open" if sys.platform == "darwin" else "xdg-open"
#             subprocess.call([opener, path])
#     except:
#         print(f"Can't open file browser. The location is: {path}")
