#!/usr/bin/env python3

import getpass
import hmac
import json
import os
import sys
from urllib.parse import parse_qs


def get_config_path():
    script_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    return os.path.join(
        script_dir,
        "..",
        "config",
        "config.dta"
    )


def read_config():

    config_path = get_config_path()
    master_users = []

    try:
        with open(config_path, "r") as config:

            for line in config:

                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                if line.startswith("MASTER_USER="):

                    user = line.split(
                        "=",
                        1
                    )[1].strip()

                    if user:
                        master_users.append(user)

    except OSError as error:

        print(
            f"Unable to read configuration: {error}",
            file=sys.stderr
        )

        return None

    return master_users


def read_security_key():

    security_path = "/etc/security.txt"

    try:
        with open(
            security_path,
            "r"
        ) as security:

            for line in security:

                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                if line.startswith("MASTER_KEY="):

                    return line.split(
                        "=",
                        1
                    )[1].strip()

    except OSError as error:

        print(
            f"Unable to read security file: {error}",
            file=sys.stderr
        )

        return None

    return None


def authenticate(
    master_user,
    master_key
):

    master_users = read_config()

    if master_users is None:
        return False

    configured_key = read_security_key()

    if configured_key is None:
        return False

    user_valid = any(
        hmac.compare_digest(
            master_user,
            user
        )
        for user in master_users
    )

    key_valid = hmac.compare_digest(
        master_key,
        configured_key
    )

    return user_valid and key_valid


def cgi_response(authenticated):

    print(
        "Content-Type: application/json"
    )

    print()

    print(
        json.dumps(
            {
                "authenticated": authenticated
            }
        )
    )


def run_cgi():

    content_length = int(
        os.environ.get(
            "CONTENT_LENGTH",
            "0"
        )
    )

    data = sys.stdin.read(
        content_length
    )

    fields = parse_qs(data)

    master_user = fields.get(
        "master_user",
        [""]
    )[0]

    master_key = fields.get(
        "master_key",
        [""]
    )[0]

    authenticated = authenticate(
        master_user,
        master_key
    )

    cgi_response(
        authenticated
    )


def run_cli():

    print()
    print(
        "Musica-Notes Master Authentication"
    )
    print()

    master_user = input(
        "Master User: "
    ).strip()

    master_key = getpass.getpass(
        "Master Key: "
    )

    if authenticate(
        master_user,
        master_key
    ):

        print()
        print(
            "Authentication successful."
        )
        print()

        return 0

    print()
    print(
        "Authentication failed."
    )
    print()

    return 1


def main():

    if os.environ.get(
        "GATEWAY_INTERFACE"
    ):

        run_cgi()

        return 0

    return run_cli()


if __name__ == "__main__":
    sys.exit(
        main()
    )
