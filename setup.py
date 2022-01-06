#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev

import io
import json
from glob import glob
import os
import socket
import sys
import subprocess
from shutil import rmtree
from pathlib import Path

from setuptools.config import read_configuration
from setuptools import find_packages, setup, Command
from setuptools.command.install import install
setup_cfg = read_configuration("setup.cfg")
metadata = setup_cfg['metadata']

# HACK to ignore wheel building from pip and just to source distribution
if 'bdist_wheel' in sys.argv:
    sys.exit(0)

NAME = metadata['name']

# Package meta-data.
# What packages are required for this module to be executed?
REQUIRED = [
    "simplejson",
    "paho-mqtt", "click>=8.0.3", "croniter", "arrow", "pudb", "pathlib", "pyyaml", "inquirer",
    "click-completion-helper"
]

# What packages are optional?
EXTRAS = {
    # 'fancy feature': ['django'],
}

# The rest you shouldn't have to touch too much :)
# ------------------------------------------------
# Except, perhaps the License and Trove Classifiers!
# If you do change the License, remember to change the Trove Classifier for that!

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = metadata['DESCRIPTION']

# Load the package's __version__.py module as a dictionary.
about = {}
if not metadata['version']:
    project_slug = NAME.lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = metadata['version']


class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def clear_builds(self):
        for path in ['dist', 'build', NAME.replace("-", "_") + ".egg-info"]:
            try:
                self.status(f'Removing previous builds from {path}')
                rmtree(os.path.join(here, path))
            except OSError:
                pass

    def run(self):
        self.clear_builds()

        self.status('Building Source distribution…')
        os.system('{0} setup.py sdist'.format(sys.executable))

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload dist/*')

        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(about['__version__']))
        os.system('git push --tags')

        self.clear_builds()

        sys.exit()

class InstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        conf_file = Path('/etc/sre/sre.conf')
        self.execute(self.setup_click_autocompletion, args=tuple([]), msg="Setup Click Completion")
        self.rename_config_files()
        self.make_default_config(conf_file)
        self.setup_service()
        self.install_executable(conf_file)

    def rename_config_files(self):
        # Rename old config file
        path = Path('/etc/sre/autobot.conf')
        try:
            if path.exists():
                path.rename('/etc/sre/sre.conf')
        except:
            pass

    def make_default_config(self, conf_file):
        if not conf_file.exists():
            conf_file.parent.mkdir(parents=True, exist_ok=True)
            conf_file.write_text(json.dumps({
                "bots-paths": [
                ],
                "broker": {
                    "ip": "127.0.0.1",
                    "port": 1883,
                },
                "name": socket.gethostname(),
                "log_level": "info",
                "log_file": "/var/log/sre/sre.log",
                # used for webhook trigger
                "http_address": "0.0.0.0",
                "http_port": 8520,
            }, indent=4))

    def setup_service(self):
        print("Install bot as a service with 'sre install'")
        print("Pick a name for the bot service if you run several bots.")

    def setup_click_autocompletion(self):
        for console_script in setup_cfg['options']['entry_points']['console_scripts']:
            console_call = console_script.split("=")[0].strip()

            subprocess.run(["pip3", "install", "click-completion-helper", "--no-binary=click-completion-helper"])
            subprocess.run([ "click-completion-helper", "setup", console_call])

    def install_executable(self, conf_file):
        for console_script in setup_cfg['options']['entry_points']['console_scripts']:
            console_call = console_script.split("=")[0].strip()

            orig_file = Path(self.__dict__['install_scripts']) / console_call
            template = orig_file.read_text().split("\n")[1:]
            template = ["#!" + sys.executable] + template
            template = '\n'.join(template)

            bin = Path("/usr/local/bin/sre")
            bin.write_text(template)
            os.chmod(bin, 0o555)

            subprocess.run(["pip3", "install", "click-completion-helper", "--no-binary=click-completion-helper"])
            subprocess.run(['click-completion-helper', 'setup', bin.name])
            break # only one console supported

setup(
    version=about['__version__'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
    # If your package is a single module, use this instead of 'packages':
    #py_modules=['srebot'],
    package_data={
        "": ["datafiles/*"],
    },
    install_requires=REQUIRED,
    extras_require=EXTRAS,
    include_package_data=True,
    cmdclass={
        'upload': UploadCommand,
        'install': InstallCommand,
    },
)
