import yaml
import os
import re
import requests

from plugins import CORE_PLUGINS
from utils import (
    PLUGINS_JSON_FILE,
    THEME_CSS_FILE,
    get_json_from_github,
    get_output_dir,
    get_theme_css
)

settings_regex = r"\/\*\s*@settings[\r\n]+?([\s\S]+?)\*\/"
plugins_regex = r"\/\*\s*@plugins[\r\n]+?([\s\S]+?)\*\/"

DOWNLOAD_COUNT_SHIELDS_URL_PREFIX = 'https://img.shields.io/badge/downloads-'
DOWNLOAD_COUNT_SEARCH = re.compile(DOWNLOAD_COUNT_SHIELDS_URL_PREFIX + r"(\d+)-")

DARK_MODE_THEMES = "[[Dark-mode themes|dark]]"
LIGHT_MODE_THEMES = "[[Light-mode themes|light]]"


def get_theme_settings(theme_css):
    """
    Based on the style settings plugin: https://github.com/mgmeyers/obsidian-style-settings/blob/main/src/main.ts
    
    Example with Yin and Yang settings: https://regex101.com/r/ZAQcf6/1
    """
    match = re.search(settings_regex, theme_css, re.MULTILINE)
    if match:
        settings_str = match[1]
        settings = yaml.load(settings_str.replace("\t", "    "), Loader=yaml.FullLoader)

        start_h = None

        markdown_settings = list()

        tab_level = 0
        last_h = None
        content = True

        for setting in settings.get("settings", list()):
            if setting is None or setting.get("hub") == "ignore":
                continue

            if setting.get("type") == "heading":
                title = setting.get("title")
                description = setting.get("description", "")
                last_h = setting.get("level")
                content = False

                if start_h is None:
                    start_h = setting.get("level")

                if setting.get("level") == start_h:
                    markdown_settings.append(
                        {
                            "header": "**{}**: {}".format(title, description),
                            "type": setting.get("type"),
                        }
                    )
                    tab_level = 0

                else:
                    tab_level = setting.get("level") - start_h - 1

                    markdown_settings.append(
                        {
                            "title": "{}- **{}**: {}".format(
                                "    " * tab_level, title, description,
                            ),
                        }
                    )
            else:
                if last_h is None:
                    tab_level = 0
                elif not content and last_h != start_h:
                    tab_level = tab_level + 1

                if setting.get("description"):
                    description = ": {}".format(setting.get("description"))
                else:
                    description = ""

                markdown_settings.append(
                    {
                        "title": "{}- {}{}".format(
                            "    " * tab_level, setting.get("title"), description
                        ),
                        "type": setting.get("type"),
                    }
                )

                content = True
        return markdown_settings


def get_theme_plugin_support(theme_css, comm_plugins=None):
    match = re.search(plugins_regex, theme_css, re.MULTILINE)
    if match:
        plugin_str = match[1]
        plugins = yaml.load(plugin_str.replace("\t", "    "), Loader=yaml.FullLoader)

        core_plugins = {n.get("id"): n.get("name") for n in CORE_PLUGINS}
        supported_core_plugins = list()
        for p in plugins.get("core", list()):
            plugin_name = core_plugins.get(p)
            supported_core_plugins.append(
                "Obsidian Core Plugins#{}|{}".format(plugin_name, plugin_name)
            )
        plugins["core"] = supported_core_plugins

        if comm_plugins is None:
            plugin_list = get_json_from_github(PLUGINS_JSON_FILE)
            comm_plugins = {n.get("id"): n.get("name") for n in plugin_list}

        supported_comm_plugins = list()
        for p in plugins.get("community", list()):
            plugin_name = comm_plugins.get(p, p)
            supported_comm_plugins.append("{}|{}".format(p, plugin_name))

        plugins["community"] = supported_comm_plugins

        return plugins


def get_theme_downloads():
    theme_downloads: dict = requests.get('https://releases.obsidian.md/stats/theme').json()
    return theme_downloads


def get_url_pattern_for_downloads_shield(placeholder_for_download_count):
    old_text = f"{DOWNLOAD_COUNT_SHIELDS_URL_PREFIX}{placeholder_for_download_count}-"
    return old_text


def collect_data_for_theme(theme, theme_downloads, template):
    """
    Take raw theme data from a community theme, and add information to it.

    :param theme: A dict with data about the theme, to be updated by this function
    :param theme_downloads: The download count of all themes
    :param template: The template used for writing themes - needed to obtain the location of existing themes
    :return: The name of the theme
    """
    repo = theme.get("repo")
    user = repo.split("/")[0]
    modes = (
        ", ".join(theme.get("modes"))
            .replace("dark", DARK_MODE_THEMES)
            .replace("light", LIGHT_MODE_THEMES)
    )
    branch = theme.get("branch", "master")
    css_file = get_theme_css(THEME_CSS_FILE.format(repo, branch))
    settings = get_theme_settings(css_file)
    plugin_support = get_theme_plugin_support(css_file)

    current_name = theme.get("name")
    download_count = get_theme_download_count_preferring_previous(template, theme_downloads, current_name)

    theme.update(
        user=user,
        modes=modes,
        branch=branch,
        settings=settings,
        plugins=plugin_support,
        download_count=download_count,
    )
    return current_name


def get_theme_download_count_preferring_previous(template, theme_downloads, current_name):
    previous_download_count = get_theme_previous_download_count_or_none(template, current_name)
    if previous_download_count:
        return previous_download_count

    return get_theme_current_download_count(theme_downloads, current_name)


def get_theme_current_download_count(theme_downloads, current_name):
    return theme_downloads[current_name]["download"]


def get_theme_previous_download_count_or_none(template, current_name):
    """
    Read the theme file from disk, and return the previously-saved download count
    :return: The saved theme download count, or None if this could not be obtained 
    """
    file_name = get_output_dir(template, current_name)
    if not os.path.exists(file_name):
        # This is a new theme, so we don't yet have a previous download count:
        return None

    with open(file_name) as file:
        contents = file.read()
        result = DOWNLOAD_COUNT_SEARCH.search(contents)
        if not result:
            # We could not extract the previous download count.
            # Perhaps the URL in the theme template has been modified?
            return None
        return int(result.group(1))


def set_theme_download_count(template, current_name, new_download_count, verbose):
    file_name = get_output_dir(template, current_name)

    if not os.path.exists(file_name):
        if verbose:
            print("No note for theme            {}".format(file_name))
        return

    previous_download_count = get_theme_previous_download_count_or_none(template, current_name)
    if not previous_download_count:
        if verbose:
            print("Cannot read download count   {}".format(file_name))
        return

    # If the download count has decreased, there is something gone fundamentally wrong:
    assert new_download_count >= previous_download_count

    if new_download_count == previous_download_count:
        if verbose:
            print("Download count unchanged     {}".format(file_name))
        return

    # This is a bit hacky, as the call to get_previous_download_count_or_none()
    # already read the file. However, this code is so very fast to run
    # that, for simplicity, it's easier to just re-read the file for now.
    with open(file_name) as file:
        old_contents = file.read()

    old_text = get_url_pattern_for_downloads_shield(previous_download_count)
    new_text = get_url_pattern_for_downloads_shield(new_download_count)
    new_contents = old_contents.replace(old_text, new_text)
    assert new_contents != old_contents

    with open(file_name, 'w') as file:
        file.write(new_contents)

    if verbose:
        print("Download count updated       {} - {} -> {}".format(file_name, previous_download_count, new_download_count))


def update_theme_download_count(template, theme_downloads, current_name, verbose):
    download_count = get_theme_current_download_count(theme_downloads, current_name)
    set_theme_download_count(template, current_name, download_count, verbose)
