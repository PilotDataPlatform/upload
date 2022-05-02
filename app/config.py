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
    NEO4J_SERVICE: str
    ENTITYINFO_SERVICE: str
    QUEUE_SERVICE: str
    DATA_OPS_UTIL: str
    KEYCLOAK_MINIO_SECRET: str
    METADATA_SERVICE: str

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
    REDIS_PASSWORD: str

    # Neo4j Setup
    NEO4J_URL: str
    NEO4J_USER: str
    NEO4J_PASS: str

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
        self.NEO4J_SERVICE_V2 = self.NEO4J_SERVICE + '/v2/neo4j/'
        self.NEO4J_SERVICE += '/v1/neo4j/'
        self.ENTITYINFO_SERVICE += '/v1/'

        self.QUEUE_SERVICE += '/v1/'
        self.DATA_OPS_UT_V2 = self.DATA_OPS_UTIL + '/v2/'
        self.DATA_OPS_UTIL += '/v1/'
        self.METADATA_SERVICE = self.METADATA_SERVICE + '/v1/'

        # minio
        self.MINIO_TMP_PATH = self.ROOT_PATH + '/tmp/'

        # temp path mount
        self.TEMP_BASE = self.ROOT_PATH + '/tmp/upload'


ConfigClass = Settings()
