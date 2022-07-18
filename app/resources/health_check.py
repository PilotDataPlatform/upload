# Copyright (C) 2022 Indoc Research
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import httpx

from app.commons.data_providers.redis import SrvAioRedisSingleton
from app.config import ConfigClass


async def check_redis() -> dict:
    """
    Summary:
        the function is to check if redis is available by `ping()`
        if cannot connect to redis, the function will return error
        otherwise will return online
    Return:
        - {"Redis": status}
    """

    try:
        redis_client = SrvAioRedisSingleton()
        if await redis_client.ping():
            return {'Redis': 'Online'}
        else:
            return {'Redis': 'Fail'}
    except Exception as e:
        return {'Redis': 'Fail with error: %s' % (str(e))}


async def check_minio() -> bool:
    """
    Summary:
        the function is to check if minio is available.
        it uses the minio health check endpoint for cluster.
        For more infomation, check document:
        https://github.com/minio/minio/blob/master/docs/metrics/healthcheck/README.md
    Return:
        - {"Redis": status}
    """

    http_protocal = 'https://' if ConfigClass.MINIO_HTTPS else 'http://'
    url = http_protocal + ConfigClass.MINIO_ENDPOINT + '/minio/health/cluster'

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url)

            if res.status_code != 200:
                return {'Minio': 'Cluster unavailable'}
    except Exception as e:
        return {'Minio': 'Fail with error: %s' % (str(e))}

    return {'Minio': 'Online'}
