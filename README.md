# pixiv-vault

Download images and videos from Japanese art site [pixiv.net](https://pixiv.net) automatically.

## Quick Start

To start, just run `./pixiv-vault setup`. (If you're on something Unix-like. Windows users see "Windows" below.) Note that you'll need python3 and python3-pip to be installed.

This script will install all necessary dependencies, set up a basic config file, and help you log into Pixiv with your personal account using a self-contained Chromium browser instance.

- If you are logged out of Pixiv at any time, or the initial login attempt fails, you can re-authenticate at any time with `./pixiv-vault login`. There are no side effects to logging in multiple times, so this is a good first attempt at fixing any API bugs you may encounter.

Once you're authenticated, simply running `./pixiv-vault download` will begin the archival process. The default directory for your vault is at `./vault/`, but this can be changed in your config. All runtime data is stored in the special directory `vault/.pixiv-vault/`, so moving the vault somewhere else is as simple as moving the directory, then updating the path in your config to match.

## Configuration

All configuration is stored in the file `.env`. The default settings are all contained in `example.env`, and these are automatically copied into a starter `.env` file by the setup command. These settings are simply loaded as environment variables, so these can also be set using actual environment variables at runtime, if preferred.

All settings are self-documented in the `.env` file. The most important of these is the `VAULT_DIR` setting, which can be set to any path on the system. Something more convenient than the default may be "~/Pictures/Pixiv", for example. If a vault exists at the directory provided, the existing vault will be loaded. Otherwise, a new one will be created.

## Windows

Windows is not officially supported at the moment, but it should work without too much issue since this is a Python-based project. There's no Batch/PowerShell setup script, so you'll either have to use bash or perform manual setup as described below. Bash can be installed on Windows using Git for Windows, or a development environment such as Cygwin.

Additionally, the "views" feature, which generates directories containing sorted subsets of your downloaded files, will likely not work on Windows since it was designed around Linux symlinks. Make sure to disable views by setting `GENERATE_VIEWS=false` in your `.env` file.

## Manual Setup

If for whatever reason you're unable or unwilling to use `./pixiv-vault setup` to set up pixiv-vault, you can use these steps to get everything ready manually. Note that this process may be subject to change or breakage over time.

1. First, ensure that you have Python 3 and pip3 available on your system. You can look up how to do this for your OS.
2. You'll have to generate virtual environments to run Python in, and install the required dependencies in them. To do this, navigate to `./pixiv/` and run `python3 -m venv venv`.
3. To install dependencies, run `python3 -m pip install --upgrade pip` and then `python3 -m pip install --upgrade -r ./requirements.txt`. This will install the modules specified in the included `requirements.txt` file.
4. Repeat steps 2 and 3 for the `./auth/` directory, which has a separate venv.
5. Without leaving `./auth/`, install the Chromium browser required for login by running the command `./venv/bin/playwright install chromium`. This is optional if you're planning to use headless login.
6. Navigate back to the root directory. You'll need a `.env` file to keep your preferences in, which I recommend creating with `example.env` as a base. E.g. `cp example.env .env`.

This should encapsulate the basic setup procedure. If you can't run `./pixiv-vault login` to authenticate (e.g. you're on Windows), use this command instead: `auth/venv/bin/python auth/main.py`.

Likewise, if you're unable to run `./pixiv-vault download`, this command is currently equivalent: `pixiv/venv/bin/python pixiv/main.py`.

## Footnotes

- Headless login is currently non-operational, at least in my testing. If you think this is wrong or know how to fix it, don't hesitate to submit an issue or PR.
- If you want any additional settings, views, statistics, or other such things to be added, feel free to submit an issue or PR.

> This project is licensed under the GNU Affero General Public License V3.0 or later. You can find a copy of this license in the COPYING file, or at https://www.gnu.org/licenses/agpl-3.0.en.html. Basically, if you publish or host online any modified version of this program, you need to publish the code as well ;)
