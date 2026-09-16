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
import sqlite3
import sys

from http.server import (
    SimpleHTTPRequestHandler,
    ThreadingHTTPServer
)

from settings import (
    get_config_path,
    read_settings,
    determine_setup_type
)


# CHANGED: Shared SQLite query implementation.
# This contains the database operation previously embedded in
# MusicaNotesHandler.send_query(). Both standalone HTTP and CGI
# execution use this same function.
#
def execute_query(sql):

    #
    # Read application settings.
    #

    config_file = get_config_path()

    settings = read_settings(
        config_file
    )

    if "ERROR" in settings:

        return None, settings["ERROR"]


    #
    # Locate the configured Musica database.
    #

    db_path = (
        settings.get("MUSICA_DB")
        or settings.get("DATABASE")
        or settings.get("DB_PATH")
    )

    if not db_path:

        return None, "Musica database path is not configured."


    #
    # Execute the SQL query.
    #

    connection = None

    try:

        connection = sqlite3.connect(
            os.path.expanduser(
                db_path
            )
        )

        cursor = connection.execute(
            sql
        )

        columns = [
            description[0]
            for description in cursor.description
        ]

        rows = [
            list(row)
            for row in cursor.fetchall()
        ]

        connection.close()

        return {
            "columns": columns,
            "rows": rows
        }, None

    except sqlite3.Error as error:

        if connection is not None:

            connection.close()

        return None, str(error)


class MusicaNotesHandler(
    SimpleHTTPRequestHandler
):

    #def do_GET(self):
    #
    #   #
    #   # API request:
    #   #
    #
    #   if self.path == "/api/settings":

    #       self.send_settings()

    #       return

        #
        # All other requests are normal web files.
        #

    #   super().do_GET()

    def do_GET(self):

        #
        # API request:
        #

        if self.path == "/api/settings":

            self.send_settings()

            return


        #
        # CGI compatibility request:
        #

        if self.path.startswith("/py/settings.py"):

            self.send_settings()

            return


        #
        # All other requests are normal web files.
        #

        super().do_GET()

    def do_POST(self):

        #
        # SQL query API request:
        #

        if self.path == "/api/query":

            self.send_query()
    
            return


        #
        # CGI compatibility request:
        #

        if self.path.startswith("/py/server_query_api.py"):

            self.send_query()

            return


        #
        # All other POST requests are unsupported.
        #

        self.send_error(
            404,
            "Not Found"
        )

    def send_query(self):

        #
        # Read the request body.
        #

        content_length = self.headers.get(
            "Content-Length"
        )

        if content_length is None:

            self.send_error(
                400,
                "Missing Content-Length"
            )

            return


        try:

            length = int(
                content_length
            )

        except ValueError:

            self.send_error(
                400,
                "Invalid Content-Length"
            )

            return


        body = self.rfile.read(
            length
        )


        #
        # Decode the JSON request.
        #

        try:

            request = json.loads(
                body.decode(
                    "utf-8"
                )
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError
        ):

            self.send_error(
                400,
                "Invalid JSON"
            )

            return


        #
        # Extract the SQL command.
        #

        sql = request.get(
            "sql"
        )


        if not isinstance(
            sql,
            str
        ) or not sql.strip():

            self.send_error(
                400,
                "Missing SQL query"
            )

            return


        #
        # Read application settings so the database path
        # comes from the existing Musica configuration.
        #

        config_file = get_config_path()

        settings = read_settings(
            config_file
        )


        if "ERROR" in settings:

            self.send_json_error(
                500,
                settings["ERROR"]
            )

            return


        #
        # Locate the configured Musica database.
        #
        # The existing configuration is authoritative.
        #

        db_path = (
            settings.get("MUSICA_DB")
            or settings.get("DATABASE")
            or settings.get("DB_PATH")
        )


        if not db_path:

            self.send_json_error(
                500,
                "Musica database path is not configured."
            )

            return


        #
        # CHANGED: Execute the SQL through the shared query function.
        # The database operation is now independent of the HTTP transport.
        #

        result, error = execute_query(
            sql
        )

        if error is not None:

            self.send_json_error(
                400,
                error
            )

            return


        #
        # Return columns and rows as JSON.
        #

        response = json.dumps(
		    result
        )

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Content-Length",
            str(
                len(
                    response.encode(
                        "utf-8"
                    )
                )
            )
        )

        self.end_headers()

        self.wfile.write(
            response.encode(
                "utf-8"
            )
        )


    def send_json_error(
        self,
        status,
        message
    ):

        response = json.dumps(
            {
                "error": message
            }
        )

        self.send_response(
            status
        )

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.send_header(
            "Content-Length",
            str(
                len(
                    response.encode(
                        "utf-8"
                    )
                )
            )
        )

        self.end_headers()

        self.wfile.write(
            response.encode(
                "utf-8"
            )
        )


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


# CHANGED: CGI entry point for Apache production use.
# Apache is already the HTTP server when this script is invoked as CGI,
# so CGI mode must not create ThreadingHTTPServer.
#
def run_cgi():

    #
    # Read the POST body supplied by Apache.
    #

    content_length = os.environ.get(
        "CONTENT_LENGTH"
    )

    if content_length is None:

        response = json.dumps(
            {
                "error": "Missing Content-Length"
            }
        )

        print(
            "Status: 400"
        )
        print(
            "Content-Type: application/json"
        )
        print()
        print(
            response
        )

        return


    try:

        length = int(
            content_length
        )

    except ValueError:

        response = json.dumps(
            {
                "error": "Invalid Content-Length"
            }
        )

        print(
            "Status: 400"
        )
        print(
            "Content-Type: application/json"
        )
        print()
        print(
            response
        )

        return


    #
    # Read and decode the JSON request.
    #

    try:

        body = sys.stdin.buffer.read(
            length
        )

        request = json.loads(
            body.decode(
                "utf-8"
            )
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError
    ):

        response = json.dumps(
            {
                "error": "Invalid JSON"
            }
        )

        print(
            "Status: 400"
        )
        print(
            "Content-Type: application/json"
        )
        print()
        print(
            response
        )

        return


    #
    # Extract the SQL command.
    #

    sql = request.get(
        "sql"
    )

    if not isinstance(
        sql,
        str
    ) or not sql.strip():

        response = json.dumps(
            {
                "error": "Missing SQL query"
            }
        )

        print(
            "Status: 400"
        )
        print(
            "Content-Type: application/json"
        )
        print()
        print(
            response
        )

        return


    #
    # CHANGED: Use the same query function as standalone HTTP mode.
    #

    result, error = execute_query(
        sql
    )

    if error is not None:

        response = json.dumps(
            {
                "error": error
            }
        )

        print(
            "Status: 400"
        )
        print(
            "Content-Type: application/json"
        )
        print()
        print(
            response
        )

        return


    #
    # Return the same JSON structure used by /api/query.
    #

    response = json.dumps(
        result
    )

    print(
        "Content-Type: application/json"
    )
    print(
        "Content-Length: {}".format(
            len(
                response.encode(
                    "utf-8"
                )
            )
        )
    )
    print()
    print(
        response
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


# CHANGED: Select execution mode.
# Apache CGI supplies GATEWAY_INTERFACE. Normal command-line execution
# retains the existing standalone development server behavior.
#
if __name__ == "__main__":

    if os.environ.get(
        "GATEWAY_INTERFACE"
    ):

        run_cgi()

    else:

        main()
