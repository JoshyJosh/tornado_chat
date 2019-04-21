#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Simplified chat demo for websockets.

Authentication, error handling, etc are left as an exercise for the reader :)
"""

import aiopg
import logging
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import os.path
import uuid
import psycopg2
import psycopg2.extras

import logging

from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)

define("db_host", default="db", help="chat database host")
define("db_port", default=5432, help="chat database port")
define("db_database", default="tornadodb", help="chat database name")
define("db_user", default="tornadouser", help="chat database user")
define("db_password", default="tornadopass", help="chat database password")

chat = None
cur = None

async def test_query(db):
    with (await db.cursor()) as cur:
        await cur.execute("SELECT * FROM message_log")
        foo = await cur.fetchall()
        logging.info("made it to testquery result: %s", foo)
        print(foo)

class Application(tornado.web.Application):
    def __init__(self, db):
        # conn = psycopg2.connect(
        #     dbname="tornadodb", user="tornadouser", password="tornadopass", host="db", port="5432")
        # cur = conn.cursor()
        #
        # psycopg2.extras.register_uuid()
        self.db = db

        handlers = [(r"/", MainHandler), (r"/chatsocket", ChatSocketHandler)]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        super(Application, self).__init__(handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", messages=ChatSocketHandler.cache)


class ChatSocketHandler(tornado.websocket.WebSocketHandler):
    waiters = set()
    cache = []
    cache_size = 200

    def __init__(self, *args, **kwargs):
        logging.info("Initializing waiters")
        logging.info(self.cache)
        super(ChatSocketHandler, self).__init__(*args, **kwargs)

    def get_compression_options(self):
        # Non-None enables compression with default options.
        return {}

    def open(self):
        logging.info("Opening waiters")
        ChatSocketHandler.waiters.add(self)

    def on_close(self):
        logging.info("Closing waiters")
        ChatSocketHandler.waiters.remove(self)

    @classmethod
    def update_cache(cls, chat):
        logging.info("Updating cache")
        cls.cache.append(chat)
        if len(cls.cache) > cls.cache_size:
            cls.cache = cls.cache[-cls.cache_size :]

    @classmethod
    def send_updates(cls, chat):
        logging.info("sending message to %d waiters", len(cls.waiters))
        for waiter in cls.waiters:
            try:
                waiter.write_message(chat)
            except:
                logging.error("Error sending message", exc_info=True)

    def on_message(self, message):
        logging.info("got message %r", message)
        parsed = tornado.escape.json_decode(message)
        chat = {"id": str(uuid.uuid4()), "body": parsed["body"]}
        chat["html"] = tornado.escape.to_basestring(
            self.render_string("message.html", message=chat)
        )

        ChatSocketHandler.update_cache(chat)
        ChatSocketHandler.send_updates(chat)


async def main():
    tornado.options.parse_command_line()

    # Create the global connection pool.
    async with aiopg.create_pool(
        host=options.db_host,
        port=options.db_port,
        user=options.db_user,
        password=options.db_password,
        dbname=options.db_database,
    ) as db:
        await test_query(db)


        app = Application(db)
        app.listen(options.port)
        await test_query(db)
        # tornado.ioloop.IOLoop.current().start()

        # In this demo the server will simply run until interrupted
        # with Ctrl-C, but if you want to shut down more gracefully,
        # call shutdown_event.set().
        shutdown_event = tornado.locks.Event()
        await shutdown_event.wait()


if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().run_sync(main)
