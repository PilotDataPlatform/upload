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

from typing import Any, Dict

from common import VaultClient
from pydantic import BaseSettings, Extra
from starlette.config import Config

config = Config('.env')

SRV_NAMESPACE = config('APP_NAME', cast=str, default='service_upload')
CONFIG_CENTER_ENABLED = config('CONFIG_CENTER_ENABLED', cast=str, default='false')


def load_vault_settings(settings: BaseSettings) -> Dict[str, Any]:
    if CONFIG_CENTER_ENABLED == 'false':
        return {}
    else:
        vc = VaultClient(config('VAULT_URL'), config('VAULT_CRT'), config('VAULT_TOKEN'))
        # print(vc.get_from_vault(SRV_NAMESPACE))
        return vc.get_from_vault(SRV_NAMESPACE)


class Settings(BaseSettings):
    """Store service configuration settings."""

    APP_NAME: str = 'service_upload'
    VERSION: str = '0.2.3'
    port: int = 5079
    host: str = '127.0.0.1'
    env: str = ''
    namespace: str = ''

    # disk mounts
    ROOT_PATH: str
    CORE_ZONE_LABEL: str
    GREEN_ZONE_LABEL: str

    # microservices
    ENTITYINFO_SERVICE: str
    QUEUE_SERVICE: str
    DATA_OPS_UTIL: str
    KEYCLOAK_MINIO_SECRET: str
    METADATA_SERVICE: str
    PROJECT_SERVICE: str

    # minio
    MINIO_OPENID_CLIENT: str
    MINIO_ENDPOINT: str
    MINIO_HTTPS: bool = False
    KEYCLOAK_URL: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str

    # Redis Service
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_USER: str = 'default'
    REDIS_PASSWORD: str

    OPEN_TELEMETRY_ENABLED: bool = False
    OPEN_TELEMETRY_HOST: str = '127.0.0.1'
    OPEN_TELEMETRY_PORT: int = 6831

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        extra = Extra.allow

        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            return env_settings, load_vault_settings, init_settings, file_secret_settings

    def __init__(self) -> None:
        super().__init__()

        self.disk_namespace = self.namespace

        # services
        self.ENTITYINFO_SERVICE += '/v1/'

        self.QUEUE_SERVICE += '/v1/'
        self.DATA_OPS_UT_V2 = self.DATA_OPS_UTIL + '/v2/'
        self.DATA_OPS_UTIL += '/v1/'
        self.METADATA_SERVICE = self.METADATA_SERVICE + '/v1/'

        # minio
        self.MINIO_TMP_PATH = self.ROOT_PATH + '/tmp/'

        # temp path mount
        self.TEMP_BASE = self.ROOT_PATH + '/tmp/upload'

        # redis
        self.REDIS_URL = (
            f'redis://{self.REDIS_USER}:{self.REDIS_PASSWORD}@{self.REDIS_HOST}' + f':{self.REDIS_PORT}/{self.REDIS_DB}'
        )


ConfigClass = Settings()
