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


async def test_query(db):
    init_cache = []
    with (await db.cursor()) as cur:
        await cur.execute("SELECT id, message, created_at FROM message_log ORDER BY created_at DESC LIMIT 200")
        initial_cache = await cur.fetchall()
        # logging.info(initial_cache)
        # # import pdb; pdb.set_trace()
        for chat_msg in initial_cache:
            chat = {"id": chat_msg[0], "body": chat_msg[1]}
            init_cache.append(chat)
    logging.info(init_cache)
    return init_cache

class Application(tornado.web.Application):
    def __init__(self, db):
        # conn = psycopg2.connect(
        #     dbname="tornadodb", user="tornadouser", password="tornadopass", host="db", port="5432")
        # cur = conn.cursor()
        #
        # psycopg2.extras.register_uuid()
        self.db = db
        # tornado.ioloop.IOLoop.current().spawn_callback(test_query, self.db)add_callback


        handlers = [(r"/", MainHandler), (r"/chatsocket", ChatSocketHandler)]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        super(Application, self).__init__(handlers, **settings)


class MainHandler(tornado.web.RequestHandler):
    called_cache = False

    def initialize(self):
        logging.info("initing MainHandler")
        if self.__class__.called_cache == False:
            self.init_cache = []
            tornado.ioloop.IOLoop.current().spawn_callback(self.test_query)
            tornado.ioloop.IOLoop.current().time(100)
            logging.info("in initialize post test_query")
            logging.info(self.init_cache)
            # for cache_msg in db_cache:
            #     cache_msg["html"] = self.render_string("message.html", message=cache_msg)
            # ChatSocketHandler.initialize_cache(db_cache)
            self.__class__.called_cache = True
        super(MainHandler, self).initialize()

    async def test_query(self):
        with (await self.application.db.cursor()) as cur:
            await cur.execute("SELECT id, message, created_at FROM message_log ORDER BY created_at DESC LIMIT 200")
            initial_cache = await cur.fetchall()
            # logging.info(initial_cache)
            for chat_msg in initial_cache:
                logging.info(chat_msg[0])
                self.init_cache.append(chat_msg[0])
                # chat = {"id": chat_msg[0], "body": chat_msg[1]}
                # chat["html"] = self.render_string("message.html", message=chat)
                # self.init_cache.append(chat)
        # ChatSocketHandler.initialize_cache(init_cache)
        return

    def get(self):
        self.render("index.html", messages=ChatSocketHandler.cache)


class ChatSocketHandler(tornado.websocket.WebSocketHandler):
    waiters = set()
    cache = []
    cache_size = 200

    def initialize(self):
        logging.info("running initialize")
        super(ChatSocketHandler, self).initialize()

    # async def testing_query(self):
    #     logging.info("in test query")
    #     with (await self.application.db.cursor()) as cur:
    #         await cur.execute("SELECT id, message, created_at FROM message_log ORDER BY created_at DESC LIMIT 200")
    #         initial_cache = await cur.fetchall()
    #         # logging.info(initial_cache)
    #         # import pdb; pdb.set_trace()
    #         full_cache = []
    #         for chat_msg in initial_cache:
    #             chat = {"id": chat_msg[0], "body": chat_msg[1]}
    #             chat["html"] = tornado.escape.to_basestring(
    #                 self.render_string("message.html", message=chat)
    #             )
    #             full_cache.append(chat)
    #         print(full_cache)

    def get_compression_options(self):
        # Non-None enables compression with default options.
        return {}

    async def open(self):
        logging.info("Opening waiters")
        # foo = []
        # for chat_msg in init_cache:
        #     chat_msg["html"] = tornado.escape.to_basestring(
        #         self.render_string("message.html", message=chat_msg)
        #     )
        #     foo.append(chat_msg)
        # ChatSocketHandler.initialize_cache(foo)
        # if len(self.cache) < 1:
        #     await self.testing_query()
        ChatSocketHandler.waiters.add(self)

    def on_close(self):
        logging.info("Closing waiters")
        ChatSocketHandler.waiters.remove(self)

    @classmethod
    def initialize_cache(cls, chat_log):
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

    # Create the global connection pool.
    async with aiopg.create_pool(
        host=options.db_host,
        port=options.db_port,
        user=options.db_user,
        password=options.db_password,
        dbname=options.db_database,
    ) as db:
        app = Application(db)
        app.listen(options.port)

        # In this demo the server will simply run until interrupted
        # with Ctrl-C, but if you want to shut down more gracefully,
        # call shutdown_event.set().
        shutdown_event = tornado.locks.Event()
        await shutdown_event.wait()


if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().run_sync(main)
