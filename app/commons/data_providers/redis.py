from aioredis import StrictRedis
from logger import LoggerFactory

from app.config import ConfigClass

_logger = LoggerFactory('SrvAioRedisSingleton').get_logger()
REDIS_INSTANCE = {}


class SrvAioRedisSingleton:
    """we should replace StrictRedis with aioredis https://aioredis.readthedocs.io/en/latest/getting-started/"""

    def __init__(self):
        self.host = ConfigClass.REDIS_HOST
        self.port = ConfigClass.REDIS_PORT
        self.db = ConfigClass.REDIS_DB
        self.pwd = ConfigClass.REDIS_PASSWORD
        self.connect()

    def connect(self):
        global REDIS_INSTANCE
        if REDIS_INSTANCE:
            self.__instance = REDIS_INSTANCE
            # _logger.info("[SUCCEED] SrvAioRedisSingleton Connection found, no need for connecting")
            pass
        else:

            REDIS_INSTANCE = StrictRedis(host=self.host, port=self.port, db=self.db, password=self.pwd)
            self.__instance = REDIS_INSTANCE
            _logger.info('[SUCCEED] SrvAioRedisSingleton Connection initialized.')

    async def get_pipeline(self):
        return await self.__instance.pipeline()

    async def get_by_key(self, key: str):
        return await self.__instance.get(key)

    async def set_by_key(self, key: str, content: str):
        return await self.__instance.set(key, content)

    async def mget_by_prefix(self, prefix: str):
        # _logger.debug(prefix)
        query = '{}:*'.format(prefix)
        keys = await self.__instance.keys(query)
        return await self.__instance.mget(keys)

    async def check_by_key(self, key: str):
        return await self.__instance.exists(key)

    async def delete_by_key(self, key: str):
        return await self.__instance.delete(key)

    async def mdelete_by_prefix(self, prefix: str):
        _logger.debug(prefix)
        query = '{}:*'.format(prefix)
        keys = await self.__instance.keys(query)
        for key in keys:
            await self.__instance.delete(key)

    async def get_by_pattern(self, key: str, pattern: str):
        query_string = '{}:*{}*'.format(key, pattern)
        keys = await self.__instance.keys(query_string)
        return await self.__instance.mget(keys)

    async def publish(self, channel, data):
        res = await self.__instance.publish(channel, data)
        return res

    async def subscriber(self, channel):
        p = await self.__instance.pubsub()
        p.subscribe(channel)
        return p
