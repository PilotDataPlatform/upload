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

import asyncio
import json
import os
import shutil
from io import BytesIO
from zipfile import ZipFile

import pytest
from aioredis import StrictRedis
from async_asgi_testclient import TestClient as TestAsyncClient
from fastapi.testclient import TestClient
from httpx import Response
from starlette.config import environ
from urllib3 import HTTPResponse

environ['namespace'] = 'dev'

environ['CONFIG_CENTER_ENABLED'] = 'false'
environ['CORE_ZONE_LABEL'] = 'Core'
environ['GREEN_ZONE_LABEL'] = 'Greenroom'

environ['METADATA_SERVICE'] = 'http://METADATA_SERVICE'
environ['DATAOPS_SERVICE'] = 'http://dataops_service_SERVICE'
environ['PROJECT_SERVICE'] = 'http://PROJECT_SERVICE'
environ['KAFKA_URL'] = 'http://KAFKA_URL'

environ['MINIO_ENDPOINT'] = 'MINIO_ENDPOINT'
environ['MINIO_HTTPS'] = 'true'
environ['MINIO_ACCESS_KEY'] = 'MINIO_ACCESS_KEY'
environ['MINIO_SECRET_KEY'] = 'MINIO_SECRET_KEY'

environ['REDIS_HOST'] = '127.0.0.1'
environ['REDIS_PORT'] = '6379'
environ['REDIS_DB'] = '0'
environ['REDIS_PASSWORD'] = ''
environ['ROOT_PATH'] = 'tests/'


@pytest.fixture(scope='session')
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
    asyncio.set_event_loop_policy(None)


@pytest.fixture(autouse=True)
async def clean_up_redis():
    cache = StrictRedis(host=environ.get('REDIS_HOST', 'localhost'), port=int(environ.get('REDIS_PORT', '6379')))
    await cache.flushall()


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    from app.config import ConfigClass

    monkeypatch.setattr(ConfigClass, 'TEMP_BASE', './tests/')


@pytest.fixture
def test_client():
    from run import app

    return TestClient(app)


@pytest.fixture
def test_async_client():
    from run import app

    return TestAsyncClient(app)


@pytest.fixture()
def create_job_folder():
    folder_path = 'tests/fake_global_entity_id'
    os.mkdir(folder_path)
    with open(f'{folder_path}/any.zip_part_001', 'x') as f:
        f.write('Create a new text file!')
    with open(f'{folder_path}/any_part_001', 'x') as f:
        f.write('Create a new text file!')
    with ZipFile(f'{folder_path}/any.zip', 'w') as myzip:
        myzip.write(f'{folder_path}/any.zip_part_001')
    yield
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)


@pytest.fixture()
async def create_fake_job(monkeypatch):
    from app.commons.data_providers.redis import SrvAioRedisSingleton

    fake_job = {
        'session_id': '1234',
        'job_id': 'fake_global_entity_id',
        'source': 'any',
        'action': 'data_upload',
        'status': 'PRE_UPLOADED',
        'project_code': 'any',
        'operator': 'me',
        'progress': 0,
        'payload': {
            'task_id': 'fake_global_entity_id',
            'resumable_identifier': 'fake_global_entity_id',
            'parent_folder_geid': None,
        },
        'update_timestamp': '1643041439',
    }

    async def fake_return(x, y):
        return [bytes(json.dumps(fake_job), 'utf-8')]

    monkeypatch.setattr(SrvAioRedisSingleton, 'mget_by_prefix', fake_return)

    # mock the credential
    fake_credentials = {
        'AccessKeyId': 'AccessKeyId',
        'SecretAccessKey': 'SecretAccessKey',
        'SessionToken': 'SessionToken',
    }

    async def fake_return_c(x, y):
        return bytes(json.dumps(fake_credentials), 'utf-8')

    monkeypatch.setattr(SrvAioRedisSingleton, 'get_by_key', fake_return_c)


@pytest.fixture()
def mock_boto3(monkeypatch):
    from common.object_storage_adaptor.boto3_client import Boto3Client

    class FakeObject:
        size = b'a'

    http_response = HTTPResponse()
    response = Response(status_code=200, json={})
    response.raw = http_response
    response.raw._fp = BytesIO(b'File like object')

    async def fake_init_connection():
        pass

    async def fake_prepare_multipart_upload(x, y, z):
        return 'fake_upload_id'

    async def fake_part_upload(x, y, z, z1, z2, z3):
        pass

    async def fake_combine_chunks(x, y, z, z1, z2):
        return {'VersionId': 'fake_version'}

    async def fake_downlaod_object(x, y, z, z1):
        return response

    monkeypatch.setattr(Boto3Client, 'init_connection', lambda x: fake_init_connection())
    monkeypatch.setattr(Boto3Client, 'prepare_multipart_upload', lambda x, y, z: fake_prepare_multipart_upload(x, y, z))
    monkeypatch.setattr(Boto3Client, 'part_upload', lambda x, y, z, z1, z2, z3: fake_part_upload(x, y, z, z1, z2, z3))
    monkeypatch.setattr(Boto3Client, 'combine_chunks', lambda x, y, z, z1, z2: fake_combine_chunks(x, y, z, z1, z2))
    monkeypatch.setattr(Boto3Client, 'downlaod_object', lambda x, y, z, z1: fake_downlaod_object(x, y, z, z1))


@pytest.fixture
def mock_kafka_producer(monkeypatch):
    from app.commons.kafka_producer import KakfaProducer

    async def fake_init_connection():
        pass

    async def fake_send_message(x, y, z):
        pass

    async def fake_validate_message(x, y, z):
        pass

    async def fake_create_activity_log(x, y, z, z1, z2):
        pass

    monkeypatch.setattr(KakfaProducer, 'init_connection', lambda x: fake_init_connection())
    monkeypatch.setattr(KakfaProducer, '_send_message', lambda x, y, z: fake_send_message(x, y, z))
    monkeypatch.setattr(KakfaProducer, '_validate_message', lambda x, y, z: fake_validate_message(x, y, z))
    monkeypatch.setattr(
        KakfaProducer, 'create_activity_log', lambda x, y, z, z1, z2: fake_create_activity_log(x, y, z, z1, z2)
    )
