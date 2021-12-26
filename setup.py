#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev

import io
import os
import sys
import tempfile
import shutil
import distutils
from shutil import rmtree
from pathlib import Path

from setuptools import find_packages, setup, Command
from setuptools.command.install import install
from subprocess import check_call, check_output

# Package meta-data.
NAME = 'sre-bot'
DESCRIPTION = 'Data collector / executor - Site Reliability Framework'
URL = 'https://github.com/marcwimmer/sre-bot'
EMAIL = 'marc@itewimmer.de'
AUTHOR = 'Marc-Christian Wimmer'
REQUIRES_PYTHON = '>=3.6.0'
VERSION = '0.0.1'

# What packages are required for this module to be executed?
REQUIRED = [
    "wheel", "simplejson",
    "paho-mqtt", "click", "croniter", "arrow", "pudb", "pathlib", "pyyaml", "inquirer"
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
    long_description = DESCRIPTION

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    project_slug = NAME.lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = VERSION


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

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload dist/*')

        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(about['__version__']))
        os.system('git push --tags')

        sys.exit()

class InstallCommand(install):
    """Post-installation for installation mode."""
    def run(self):
        install.run(self)
        self.execute(self.setup_click_autocompletion, args=tuple([]), msg="Setup Click Completion")
        self.rename_config_files()
        self.setup_service()

    def rename_config_files(self):
        path = Path('/etc/sre/autobot.conf')
        if path.exists():
            path.rename('/etc/sre/sre.conf')

    def setup_service(self):
        pass

    def setup_click_autocompletion(self):
        self.announce("Setting up click autocompletion", level=distutils.log.INFO)

        def setup_for_bash():
            path = Path("/etc/bash_completion.d")
            done_bash = False
            if path.exists():
                if os.access(path, os.W_OK):
                    os.system(f"_{NAME.upper()}_COMPLETE=bash_source {NAME} > '{path / NAME}'")
                    done_bash = True
            if not done_bash:
                if not (path / NAME).exists():
                    bashrc = Path(os.path.expanduser("~")) / '.bashrc'
                    complete_file = bashrc.parent / f'.{NAME}-completion.sh'
                    os.system(f"_{NAME.upper()}_COMPLETE=bash_source {NAME} > '{complete_file}'")
                    if complete_file.name not in bashrc.read_text():
                        content = bashrc.read_text()
                        content += '\nsource ' + complete_file.name
                        bashrc.write_text(content)
        setup_for_bash()

class UninstallCommand(install):
    def run(self):
        install.run(self)

setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=["tests", "*.tests", "*.tests.*", "tests.*"]),
    # If your package is a single module, use this instead of 'packages':
    #py_modules=['srebot'],

    entry_points={
        'console_scripts': ['sre=srebot:cli'],
    },
    data_files=[
        "install/sre.conf",
        "install/sre.service",
        "install/bot.template.py",
    ],
    install_requires=REQUIRED,
    extras_require=EXTRAS,
    include_package_data=True,
    license='MIT',
    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
        'install': InstallCommand,
        'uninstall': UninstallCommand,
    },
)
