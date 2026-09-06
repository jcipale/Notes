#!/usr/bin/env python3

#
# Musica-Notes Release alpha-0.1.0
#
# server.py
#
# Minimal standalone HTTP server for Musica-Notes.
#

import json
import os

from http.server import (
    SimpleHTTPRequestHandler,
    ThreadingHTTPServer
)

from settings import (
    get_config_path,
    read_settings,
    determine_setup_type
)


class MusicaNotesHandler(
    SimpleHTTPRequestHandler
):

    def do_GET(self):

        #
        # API request:
        #

        if self.path == "/api/settings":

            self.send_settings()

            return


        #
        # All other requests are normal web files.
        #

        super().do_GET()


    def send_settings(self):

        config_file = get_config_path()

        settings = read_settings(
            config_file
        )


        #
        # Determine installation type.
        #

        if "ERROR" in settings:

            setup_type = (
                "Configuration Error"
            )

        else:

            setup_type = determine_setup_type(
                settings
            )


        #
        # Add setup type to JSON response.
        #

        settings["SETUP_TYPE"] = (
            setup_type
        )


        #
        # Convert response to JSON.
        #

        response = json.dumps(
            settings,
            indent=4
        )


        #
        # Send HTTP response.
        #

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.end_headers()

        self.wfile.write(
            response.encode(
                "utf-8"
            )
        )


def main():

    #
    # The server must serve the web directory,
    # not the py directory.
    #

    script_dir = os.path.dirname(
        os.path.abspath(
            __file__
        )
    )

    web_root = os.path.abspath(
        os.path.join(
            script_dir,
            ".."
        )
    )

    os.chdir(
        web_root
    )


    #
    # Listen only on the local machine.
    #

    server_address = (
        "127.0.0.1",
        8000
    )


    httpd = ThreadingHTTPServer(
        server_address,
        MusicaNotesHandler
    )


    print(
        "Musica-Notes standalone server"
    )

    print()

    print(
        "Listening on:"
    )

    print(
        "http://127.0.0.1:8000/"
    )

    print()

    print(
        "Press Ctrl-C to stop."
    )


    try:

        httpd.serve_forever()

    except KeyboardInterrupt:

        print()

        print(
            "Musica-Notes server stopped."
        )


if __name__ == "__main__":

    main()
