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

    #db_path = (
    #    settings.get("MUSICA_DB")
    #    or settings.get("DATABASE")
    #    or settings.get("DB_PATH")
    #)

    db_path = os.path.join(
        os.path.expanduser(
            settings.get("DPATH", "")
        ),
        settings.get("DBASE", "")
)

    #if not db_path:
    #
    #    return None, "Musica database path is not configured."

    if not settings.get("DPATH"):
        return None, "DPATH is not configured."

    if not settings.get("DBASE"):
        return None, "DBASE is not configured."

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


# CHANGED: Shared SQLite Add implementation.
#
# The web Add operation performs the same database INSERT as
# musica_db_add_recording_sqlite.py, but directly through SQLite.
# HTTP and CGI execution both use this function.
#
def execute_add(record):

    # CHANGED: Resolve the database exactly as defined by config.dta.
    #
    # DPATH identifies the Musica data directory and DBASE identifies
    # the database file.
    #

    config_file = get_config_path()

    settings = read_settings(
        config_file
    )

    if "ERROR" in settings:

        return None, settings["ERROR"]

    db_path = os.path.join(
        os.path.expanduser(
            settings.get(
                "DPATH",
                ""
            )
        ),
        settings.get(
            "DBASE",
            ""
        )
    )

    if not settings.get("DPATH"):

        return None, "DPATH is not configured."

    if not settings.get("DBASE"):

        return None, "DBASE is not configured."

    if not isinstance(
        record,
        dict
    ):

        return None, "Missing record data."

    required = (
        "artist",
        "title",
        "year",
        "genre",
        "format"
    )

    for field in required:

        value = record.get(
            field
        )

        if value is None or str(value).strip() == "":

            return None, (
                "Missing required field: "
                + field
            )

    try:

        year = int(
            record["year"]
        )

    except (
        TypeError,
        ValueError
    ):

        return None, "Invalid year."

    if year < 1900:

        return None, "Year must be >= 1900."

    def optional_text(value):

        if value is None:

            return None

        value = str(
            value
        ).strip()

        return value if value else None

    artist = str(
        record["artist"]
    ).strip()

    title = str(
        record["title"]
    ).strip()

    genre = str(
        record["genre"]
    ).strip()

    fmt = str(
        record["format"]
    ).strip()

    composer = optional_text(
        record.get("composer")
    )

    orchestra = optional_text(
        record.get("orchestra")
    )

    conductor = optional_text(
        record.get("conductor")
    )

    label = optional_text(
        record.get("label")
    )

    catalog = optional_text(
        record.get("catalog_number")
    )

    # CHANGED: Classical and Symphonic both support
    # Composer, Orchestra, and Conductor.
    if genre not in (
        "Classical",
        "Symphonic"
    ):

        composer = None
        orchestra = None
        conductor = None

    recording_mode = optional_text(
        record.get("recording_mode")
    )

    if recording_mode not in (
        "M",
        "S",
        "B"
    ):

        return None, "Invalid recording mode."

    reissue = (
        "Y"
        if record.get("reissue")
        else None
    )

    dbx_encoded = (
        "Y"
        if record.get("dbx_encoded")
        else None
    )

    sql = """
    INSERT INTO recordings (
        artist, title, year,
        composer, orchestra, conductor,
        genre, format,
        label, catalog_number,
        recording_mode, reissue, dbx_encoded
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    connection = None

    try:

        connection = sqlite3.connect(
            os.path.expanduser(
                db_path
            )
        )

        connection.execute(
            "PRAGMA foreign_keys=ON;"
        )

        connection.execute(
            "PRAGMA busy_timeout=5000;"
        )

        cursor = connection.cursor()

        cursor.execute(
            sql,
            (
                artist,
                title,
                year,
                composer,
                orchestra,
                conductor,
                genre,
                fmt,
                label,
                catalog,
                recording_mode,
                reissue,
                dbx_encoded
            )
        )

        connection.commit()

        record_id = cursor.lastrowid

        connection.close()

        return {
            "id": record_id
        }, None

    except sqlite3.IntegrityError as error:

        if connection is not None:

            connection.close()

        return None, str(error)

    except sqlite3.OperationalError as error:

        if connection is not None:

            connection.close()

        return None, str(error)


class MusicaNotesHandler(
    SimpleHTTPRequestHandler
):

    def do_GET(self):

        #
        # API request:
        #

        #if self.path == "/api/settings":

        #    self.send_settings()

        #    return

        # CHANGED: Add Record request.
        #
        # The browser uses /py/server.py for Add().
        # Route the request to the shared Add implementation.

        if self.path.startswith("/py/server.py"):

            self.send_add()

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


        # CHANGED: Add Record API request.

        if self.path == "/py/server.py":

            self.send_add()

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

    # CHANGED: Handle a structured Add Record request.
    #
    # The browser supplies record data, not SQL. This keeps the
    # database mutation under server-side control.
    #
    def send_add(self):

        content_length = self.headers.get(
            "Content-Length"
        )

        if content_length is None:

            self.send_json_error(
                400,
                "Missing Content-Length"
            )

            return

        try:

            length = int(
                content_length
            )

        except ValueError:

            self.send_json_error(
                400,
                "Invalid Content-Length"
            )

            return

        try:

            body = self.rfile.read(
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

            self.send_json_error(
                400,
                "Invalid JSON"
            )

            return

        if request.get(
            "operation"
        ) != "add":

            self.send_json_error(
                400,
                "Invalid Add operation."
            )

            return

        result, error = execute_add(
            request.get(
                "record"
            )
        )

        if error is not None:

            self.send_json_error(
                400,
                error
            )

            return

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

        #
        # Apache did not supply CONTENT_LENGTH.
        #
        # Read the CGI request body until EOF.
        #

        body = sys.stdin.buffer.read()

    else:

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

        body = sys.stdin.buffer.read(
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
    # CHANGED: CGI Add Record request.
    #

    if request.get(
        "operation"
    ) == "add":

        result, error = execute_add(
            request.get(
                "record"
            )
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

        response = json.dumps(
            result
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
