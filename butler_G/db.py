"""DB Service Module

Single service to handle all database interactions.
Uses Lazy Pirate Pattern

The goal is to minimize `psycopg2.connect` calls (which is expensive).
"""
import logging

import psycopg2
import zmq

logger = logging.getLogger(__name__)


class Server:
    """Single server that interacts with DB"""

    def __init__(self, URL):
        """
        Parameters
        ----------
        URL: str
            address bound to REP server
        """
        self.URL = URL

    def main(self, *args, **kwargs):
        """Main routine

        Parameters
        ----------
        *args, **kwargs
            passed to `psycopg2.connect`
        """
        logger.info("[DBSvc] Creating PG connection...")
        conn = psycopg2.connect(*args, **kwargs)

        logger.info("[DBSvc] Starting zmq.REP socket...")
        ctx = zmq.Context.instance()
        server = ctx.socket(zmq.REP)  # pylint: disable=no-member
        server.bind(self.URL)
        while True:
            try:
                msg = server.recv_pyobj()

                logger.debug("[DBSvc] Request: %s", msg)
                recon_attempt = 0
                while True:
                    try:
                        with conn.cursor() as cursor:
                            # execute stuff
                            cursor.execute(msg["query"], msg["query_data"])
                            result = cursor.fetchall() if msg["fetch"] else None
                            if msg["commit"]:
                                conn.commit()
                            else:
                                conn.rollback()
                        break
                    except psycopg2.OperationalError as err:
                        recon_attempt += 1
                        logger.error(
                            "[DBSvc] Error caught: %s, Restarting (Attempt #%.0f)",
                            repr(err),
                            recon_attempt,
                        )
                        conn = psycopg2.connect(*args, **kwargs)

                logger.debug("[DBSvc] Response: %s", result)
                server.send_pyobj(result)

            except (KeyboardInterrupt, SystemExit):
                logger.info("[DBSvc] Stopping...")
                break

        server.close()
        ctx.term()
        logger.info("[DBSvc] Exited")


class Client:
    """Client to send queries to Server"""

    def __init__(self, URL):
        """
        Parameters
        ----------
        URL: str
            address to connect REQ socket
        """
        self.URL = URL
        self.ctx = zmq.Context.instance()
        self.client = self.ctx.socket(zmq.REQ)  # pylint: disable=no-member
        self.client.connect(self.URL)

    def __del__(self):
        self.close()

    def close(self):
        """Cleanup, close zmq socket and context"""
        self.client.close()
        self.ctx.term()

    def send_query(self, query, query_data=None, commit=False, fetch=False):
        """Send SQL query

        Parameters
        ----------
        query: str
            passed as first argument to `cursor.execute()`
        query_data
            passed as second argument to `cursor.execute()`; defaults to None
        commit: bool
            flag whether to run `conn.commit()`; defaults to `False`
        fetch: bool
            flag whether to run `cursor.fetchall()`; defaults to `False`

        Returns
        ----------
        query result if `fetch` is `True`
        """
        data = {
            "query": query,
            "query_data": query_data,
            "commit": commit,
            "fetch": fetch,
        }
        self.client.send_pyobj(data)
        return self.client.recv_pyobj()
