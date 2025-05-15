read -p "Fraunhofer VPN active? " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]
then
    exit 1
fi



echo "installing stuff required for building python"
sudo apt update; sudo apt install build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

echo "install pyenv"
git clone https://github.com/pyenv/pyenv.git ~/.pyenv
cd ~/.pyenv && src/configure && make -C src

echo "install pyenv venv"
git clone https://github.com/pyenv/pyenv-virtualenv.git $(pyenv root)/plugins/pyenv-virtualenv

echo "bash integration"
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

#load new vars into bash
source ~/.bashrc

echo "installing and setting up server"
pyenv install 3.11
pyenv shell 3.11
pyenv virtualenv rixa_webserver
pyenv virtualenv rixa_plugins

pyenv activate rixa_webserver
git clone https://gitlab.cc-asp.fraunhofer.de/xai-hiwi/rixa/rixawebserver.git
pip3 install -e .[dev]

pyenv deactivate

pyenv activate rixa_plugins
echo "installing requirements for standard plugins"
pip3 install pyro5 sympy sentence_transformers pandas plotly
echo "Use this path + '/bins/python3' for the 'venv_path' attribute for all the standard plugins."
echo pyenv prefix rixa_plugins
pyenv deactivate
echo "finished"
