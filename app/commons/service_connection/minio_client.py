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
from common import LoggerFactory
from minio import Minio
from minio.credentials.providers import ClientGrantsProvider
from starlette.concurrency import run_in_threadpool

from app.config import ConfigClass

logger = LoggerFactory(__name__).get_logger()


async def get_minio_client(access_token, refresh_token):
    minio_client = Minio_Client(access_token, refresh_token)
    await minio_client.get_client()
    return minio_client


class Minio_Client:
    def __init__(self, access_token, refresh_token):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client = None

    async def get_client(self):
        # retrieve credential provide with tokens
        c = await run_in_threadpool(self.get_provider)

        self.client = await run_in_threadpool(
            Minio, ConfigClass.MINIO_ENDPOINT, credentials=c, secure=ConfigClass.MINIO_HTTPS
        )
        logger.info('Minio Connection Success')

    # function helps to get new token/refresh the token
    def _get_jwt(self):
        # enable the token exchange with different azp
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        payload = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
            'subject_token': self.access_token.replace('Bearer ', ''),
            'subject_token_type': 'urn:ietf:params:oauth:token-type:access_token',
            'requested_token_type': 'urn:ietf:params:oauth:token-type:refresh_token',
            'client_id': 'minio',
            'client_secret': ConfigClass.KEYCLOAK_MINIO_SECRET,
        }
        with httpx.Client() as client:
            result = client.post(ConfigClass.KEYCLOAK_URL, data=payload, headers=headers)
        if result.status_code != 200:
            raise Exception('Token refresh failed with ' + str(result.json()))
        self.access_token = result.json().get('access_token')
        self.refresh_token = result.json().get('refresh_token')

        jwt_object = result.json()
        return jwt_object

    # use the function above to create a credential object in minio
    # it will use the jwt function to refresh token if token expired
    def get_provider(self):
        minio_http = ('https://' if ConfigClass.MINIO_HTTPS else 'http://') + ConfigClass.MINIO_ENDPOINT
        provider = ClientGrantsProvider(
            self._get_jwt,
            minio_http,
        )

        return provider

    async def fput_object(self, bucket, obj_path, temp_merged_file_full_path):
        try:
            result = await run_in_threadpool(
                self.client.fput_object,
                bucket,
                obj_path,
                temp_merged_file_full_path,
            )
            logger.info('Minio Upload Success')
            return result.version_id
        except Exception as e:
            logger.error('error when uploading: ' + str(e))
