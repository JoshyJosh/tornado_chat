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

# define("db_host", default="db", help="chat database host")
define("db_host", default="localhost", help="chat database host")
define("db_port", default=5432, help="chat database port")
define("db_database", default="tornadodb", help="chat database name")
define("db_user", default="tornadouser", help="chat database user")
define("db_password", default="tornadopass", help="chat database password")

INIT_CHAT = []

class Application(tornado.web.Application):
    def __init__(self, db, init_chat):
        self.db = db
        self.init_chat = init_chat

        handlers = [(r"/", MainHandler, dict(init_chat=self.init_chat)), (r"/chatsocket", ChatSocketHandler)]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        super(Application, self).__init__(handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    called_cache = False

    def initialize(self, init_chat):
        logging.info("initializing MainHandler")
        logging.info(init_chat)
        logging.info(self.called_cache)
        if self.__class__.called_cache == False:
            db_cache = []
            for chat_msg in init_chat:
                cache_msg = {"id": chat_msg[0], "body": chat_msg[1]}
                cache_msg["html"] = self.render_string("message.html", message=cache_msg)
                db_cache.append(cache_msg)
            ChatSocketHandler.initialize_cache(db_cache)
            INIT_CHAT = []
            self.application.init_chat = []
            self.__class__.called_cache = True
        super(MainHandler, self).initialize()

    def get(self):
        self.render("index.html", messages=ChatSocketHandler.cache)


class ChatSocketHandler(tornado.websocket.WebSocketHandler):
    waiters = set()
    cache = []
    cache_size = 200

    def initialize(self):
        logging.info("running initialize")
        super(ChatSocketHandler, self).initialize()

    def get_compression_options(self):
        # Non-None enables compression with default options.
        return {}

    async def open(self):
        logging.info("Opening waiters")
        ChatSocketHandler.waiters.add(self)

    def on_close(self):
        logging.info("Closing waiters")
        ChatSocketHandler.waiters.remove(self)

    @classmethod
    def initialize_cache(cls, chat_log):
        logging.info("initializing cache")
        cls.cache = chat_log

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
        logging.info(chat)

        ChatSocketHandler.update_cache(chat)
        ChatSocketHandler.send_updates(chat)
        logging.info(self.cache)


async def main():
    tornado.options.parse_command_line()

    # get data from db before starting loop
    conn = psycopg2.connect("host={} port={} user={} password={} dbname={}".format(options.db_host, options.db_port, options.db_user, options.db_password, options.db_database))
    cur = conn.cursor()

    cur.execute("SELECT id, message, created_at FROM message_log ORDER BY created_at DESC LIMIT 200")
    INIT_CHAT = cur.fetchall()

    cur.close()
    conn.close()

    # Create the global connection pool.
    async with aiopg.create_pool(
        host=options.db_host,
        port=options.db_port,
        user=options.db_user,
        password=options.db_password,
        dbname=options.db_database,
    ) as db:
        app = Application(db, INIT_CHAT)
        app.listen(options.port)

        # In this demo the server will simply run until interrupted
        # with Ctrl-C, but if you want to shut down more gracefully,
        # call shutdown_event.set().
        shutdown_event = tornado.locks.Event()
        await shutdown_event.wait()


if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().run_sync(main)
