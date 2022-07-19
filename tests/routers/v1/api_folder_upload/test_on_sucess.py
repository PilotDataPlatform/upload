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

from unittest import mock

import pytest

pytestmark = pytest.mark.asyncio  # set the mark to all tests in this file.


@pytest.fixture
async def on_success_external_requests(httpx_mock):
    httpx_mock.add_response(
        method='POST',
        url='http://dataops_service_service/v1/filedata/',
        json={'result': {'global_entity_id': 'fake_global_entity_id'}},
        status_code=200,
    )
    httpx_mock.add_response(
        method='DELETE',
        url='http://dataops_service_service/v2/resource/lock/',
        json={},
        status_code=200,
    )


async def test_on_success_return_400_when_session_id_header_is_missing(test_async_client, httpx_mock):
    response = await test_async_client.post(
        '/v1/files',
        json={
            'project_code': 'any',
            'operator': 'me',
            'resumable_identifier': 'fake_global_entity_id',
            'resumable_filename': 'any',
            'resumable_relative_path': './',
            'resumable_total_chunks': 1,
            'resumable_total_size': 10,
        },
    )
    assert response.status_code == 400
    assert response.json() == {
        'code': 400,
        'error_msg': 'session_id is required',
        'page': 0,
        'total': 1,
        'num_of_pages': 1,
        'result': [],
    }


@mock.patch('minio.credentials.providers._urlopen')
@mock.patch('os.remove')
async def test_upload_zip_should_allow_zip_preview(
    fake_remove,
    fake_providers_urlopen,
    test_async_client,
    httpx_mock,
    create_job_folder,
    create_fake_job,
    mock_boto3,
    mock_kafka_producer,
    on_success_external_requests,
    mocker,
):
    class FakeLastNode:
        global_entity_id = 'fake_geid'

    mocker.patch('app.routers.v1.api_data_upload.folder_creation', return_value=FakeLastNode())
    httpx_mock.add_response(method='POST', url='http://dataops_service_service/v1/archive', json={}, status_code=200)

    response = await test_async_client.post(
        '/v1/files',
        headers={'Session-Id': '1234', 'Authorization': 'token', 'Refresh-Token': 'refresh_token'},
        json={
            'project_code': 'any',
            'operator': 'me',
            'resumable_identifier': 'fake_global_entity_id',
            'resumable_filename': 'any.zip',
            'resumable_relative_path': './',
            'resumable_total_chunks': 1,
            'resumable_total_size': 10,
        },
    )
    # assert fake_providers_urlopen.call_args[0][2].startswith('https://MINIO_ENDPOINT')

    assert response.status_code == 200
    result = response.json()['result']
    assert result['session_id'] == '1234'
    assert result['job_id'] == 'fake_global_entity_id'
    assert result['source'] == 'any'
    assert result['action'] == 'data_upload'
    assert result['status'] == 'CHUNK_UPLOADED'
    assert result['operator'] == 'me'
    assert result['payload']['task_id'] == 'fake_global_entity_id'
    assert result['payload']['resumable_identifier'] == 'fake_global_entity_id'


@mock.patch('minio.credentials.providers._urlopen')
@mock.patch('os.remove')
async def test_upload_any_file_should_return_200(
    fake_remove,
    fake_providers_urlopen,
    test_async_client,
    httpx_mock,
    create_job_folder,
    create_fake_job,
    mock_boto3,
    mock_kafka_producer,
    on_success_external_requests,
    mocker,
):
    class FakeLastNode:
        global_entity_id = 'fake_geid'

    mocker.patch('app.routers.v1.api_data_upload.folder_creation', return_value=FakeLastNode())

    response = await test_async_client.post(
        '/v1/files',
        headers={'Session-Id': '1234', 'Authorization': 'token', 'Refresh-Token': 'refresh_token'},
        json={
            'project_code': 'any',
            'operator': 'me',
            'resumable_identifier': 'fake_global_entity_id',
            'resumable_filename': 'any',
            'resumable_relative_path': './',
            'resumable_total_chunks': 1,
            'resumable_total_size': 10,
        },
    )
    # assert fake_providers_urlopen.call_args[0][2].startswith('https://MINIO_ENDPOINT')

    assert response.status_code == 200
    result = response.json()['result']
    assert result['session_id'] == '1234'
    assert result['job_id'] == 'fake_global_entity_id'
    assert result['source'] == 'any'
    assert result['action'] == 'data_upload'
    assert result['status'] == 'CHUNK_UPLOADED'
    assert result['operator'] == 'me'
    assert result['payload']['task_id'] == 'fake_global_entity_id'
    assert result['payload']['resumable_identifier'] == 'fake_global_entity_id'
