#!/usr/bin/env python3

#
# Musica-Notes Release alpha-0.1.0
#
# settings.py
#
# Reads and parses the Musica-Notes configuration file.
#

import json
import os
import sys


def get_config_path():

    """
    Return the location of config.dta.

    settings.py resides in:

        ./py/settings.py

    config.dta resides in:

        ./config/config.dta
    """

    script_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    config_path = os.path.join(
        script_dir,
        "..",
        "config",
        "config.dta"
    )

    return os.path.abspath(config_path)


def read_settings(config_file):

    """
    Read config.dta and return active settings.

    Blank lines and comments are ignored.

    Multiple MASTER_USER entries are stored
    in a list.
    """

    settings = {

        "MASTER_IP": None,
        "DATABASE": None,
        "MASTER_USER": []

    }

    try:

        with open(
            config_file,
            "r",
            encoding="utf-8"
        ) as config:

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

                key, value = line.split(
                    "=",
                    1
                )

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

                    settings[
                        "MASTER_USER"
                    ].append(value)

    except FileNotFoundError:

        settings["ERROR"] = (
            "Configuration file not found: "
            + config_file
        )

    except OSError as error:

        settings["ERROR"] = str(error)

    return settings


def determine_setup_type(settings):

    """
    Determine the Musica-Notes installation type
    from the active configuration.
    """

    if not settings["DATABASE"]:

        return "Configuration Incomplete"


    if settings["MASTER_IP"]:

        return "Networked"


    if settings["MASTER_USER"]:

        return "Local / Shared"


    return "Local / Single User"


def print_settings(settings, setup_type):

    """
    Display configuration information
    for CLI use.
    """

    print(
        "Musica-Notes Configuration"
    )

    print()

    if "ERROR" in settings:

        print(
            "ERROR: "
            + settings["ERROR"]
        )

        return


    print(
        "SETUP_TYPE="
        + setup_type
    )


    if settings["MASTER_IP"]:

        print(
            "MASTER_IP="
            + settings["MASTER_IP"]
        )


    if settings["DATABASE"]:

        print(
            "DATABASE="
            + settings["DATABASE"]
        )


    for user in settings["MASTER_USER"]:

        print(
            "MASTER_USER="
            + user
        )


def print_json(settings, setup_type):

    """
    Display configuration information
    in JSON format.
    """

    response = {

        "SETUP_TYPE": setup_type,

        "MASTER_IP":
            settings["MASTER_IP"],

        "DATABASE":
            settings["DATABASE"],

        "MASTER_USER":
            settings["MASTER_USER"]

    }


    if "ERROR" in settings:

        response["ERROR"] = (
            settings["ERROR"]
        )


    print(
        json.dumps(
            response,
            indent=4
        )
    )


def main():

    config_file = get_config_path()

    settings = read_settings(
        config_file
    )


    if "ERROR" in settings:

        setup_type = (
            "Configuration Error"
        )

    else:

        setup_type = determine_setup_type(
            settings
        )


    #
    # JSON output requested.
    #

    if len(sys.argv) > 1 and \
       sys.argv[1] == "--json":

        print_json(
            settings,
            setup_type
        )

        return


    #
    # Default CLI output.
    #

    print_settings(
        settings,
        setup_type
    )


if __name__ == "__main__":

    main()
