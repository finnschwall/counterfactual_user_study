# Installation

<h1><img src="https://cdn-icons-png.flaticon.com/512/3261/3261386.png"  width="100" height="100">Ignore this page!</h1>


## Python Version
The primary python version for the server is `3.1.1`. But it *should* run on all python versions > 3. More on that in [pyenv](#pyenv-target)

## Preparing the environment

### Quick way
Likely there is venv on your system. So you can simply install the requirements and then run the server.
That looks something like this

```bash
python3 -m virtualenv venv_django
source venv_django/bin/activate
pip install -r rixawebserver/requirements.txt
```

(pyenv-target)=
### Pyenv (the full solution)
The more robust solution. It can be built from [here](https://github.com/pyenv/pyenv). It does not work under windows but
there are alternatives like [pyenv-win](https://github.com/pyenv-win/pyenv-win).

Then clone the repo and use install.sh

## Prepare the webserver

Choose one of the following cases

### I have a configured database and want to tranfer the prebuilt database content
Start with

```bash
python3 manage.py dumpdata > out.json
```

Then change the db configuration in `RIXAWebserver/settings.py` if you want to use you local MongoDB or MySQL db.
[This](https://docs.djangoproject.com/en/4.2/ref/databases/) will help.
You will then have to rebuild the db scheme, delete all predefined entries and transfer the content.

```bash
python3 manage.py migrate
echo "delete from auth_permission; delete from django_content_type;" | python3 manage.py dbshell
python3 manage.py loaddata out.json
```

### I have a db.sqlite3 file in the root
Do you want to use sqlite? In that case you are golden. If not look at the previous point.

### I have no database (or no idea what that even means)
Check for the before mentioned point. If that does not apply then in the root folder do

```bash
python3 manage.py migrate
```
As the db is now completely empty for full access you need a superuser account. Stop the server should it
be running and enter
	
```bash
python3 manage.py createsuperuser
```

## Starting the server

```bash
python3 manage.py runserver
```

under windows there may be firewall prompts but since there is no "outside" connection it should be fine

> localhost:8000

the account system can be viewed under

> localhost:8000/account_managment