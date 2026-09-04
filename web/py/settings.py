#!/usr/bin/env python3

#
# Musica-Notes Release alpha-0.1.0
#
# settings.py
#
# Reads and parses the Musica-Notes config.dta file.
#

import json
import os
import sys


def get_config_path():
    """
    Return the location of config.dta.

    settings.py is expected to reside in the web directory.
    config.dta resides in web/config.
    """

    script_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    return os.path.join(
        script_dir,
		"..",
        "config",
        "config.dta"
    )


def read_settings(config_file):
    """
    Read config.dta and return the active settings.

    Blank lines and lines beginning with '#' are ignored.
    Multiple MASTER_USER entries are stored in a list.
    """

    settings = {
        "MASTER_IP": None,
        "DATABASE": None,
        "MASTER_USER": []
    }

    try:

        with open(config_file, "r",
                  encoding="utf-8") as config:

            for line in config:

                line = line.strip()

                #
                # Ignore blank lines.
                #

                if not line:
                    continue

                #
                # Ignore comments.
                #

                if line.startswith("#"):
                    continue

                #
                # Ignore malformed lines.
                #

                if "=" not in line:
                    continue

                key, value = line.split("=", 1)

                key = key.strip()
                value = value.strip()

                #
                # Ignore empty values.
                #

                if not value:
                    continue

                if key == "MASTER_IP":

                    settings["MASTER_IP"] = value

                elif key == "DATABASE":

                    settings["DATABASE"] = value

                elif key == "MASTER_USER":

                    settings["MASTER_USER"].append(value)

    except FileNotFoundError:

        settings["ERROR"] = (
            f"Configuration file not found: "
            f"{config_file}"
        )

    except OSError as error:

        settings["ERROR"] = str(error)

    return settings


def main():

    config_file = get_config_path()

    settings = read_settings(config_file)

    #
    # When called from the command line,
    # display the parsed settings.
    #

    if "GATEWAY_INTERFACE" not in os.environ:

        print("Musica-Notes Configuration")
        print()

        if "ERROR" in settings:

            print(
                f"ERROR: {settings['ERROR']}"
            )

            return

        if settings["MASTER_IP"]:

            print(
                f"MASTER_IP={settings['MASTER_IP']}"
            )

        if settings["DATABASE"]:

            print(
                f"DATABASE={settings['DATABASE']}"
            )

        for user in settings["MASTER_USER"]:

            print(
                f"MASTER_USER={user}"
            )

        return

    #
    # CGI/Web response.
    #

    print("Content-Type: application/json")
    print()

    print(
        json.dumps(
            settings,
            indent=4
        )
    )


if __name__ == "__main__":

    main()
