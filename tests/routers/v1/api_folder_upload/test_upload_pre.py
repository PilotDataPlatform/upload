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

import pytest

from app.commons.project_exceptions import ProjectNotFoundException

pytestmark = pytest.mark.asyncio  # set the mark to all tests in this file.


async def test_files_jobs_return_400_when_session_id_header_is_missing(test_async_client, httpx_mock):
    response = await test_async_client.post(
        '/v1/files/jobs', json={'project_code': 'any', 'operator': 'me', 'data': [{'resumable_filename': 'any'}]}
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


async def test_files_jobs_return_400_when_session_job_type_is_wrong(test_async_client, httpx_mock):
    response = await test_async_client.post(
        '/v1/files/jobs',
        headers={'Session-Id': '1234'},
        json={'project_code': 'any', 'operator': 'me', 'job_type': 'any', 'data': [{'resumable_filename': 'any'}]},
    )
    assert response.status_code == 400
    assert response.json() == {
        'code': 400,
        'error_msg': 'Invalid job type: any',
        'page': 0,
        'total': 1,
        'num_of_pages': 1,
        'result': [],
    }


async def test_files_jobs_return_404_when_project_info_not_found(test_async_client, httpx_mock, mocker):
    # httpx_mock.add_response(
    #     method='POST',
    #     url='http://neo4j_service/v1/neo4j/nodes/Container/query',
    #     json=[],
    #     status_code=200,
    # )

    # REMOVE THIS AFTER NEW PUBLISH OF PROJECT CLIENT
    m = mocker.patch(
        'app.commons.project_client.ProjectClient.get', return_value=[]
    )
    m.side_effect = ProjectNotFoundException

    response = await test_async_client.post(
        '/v1/files/jobs',
        headers={'Session-Id': '1234'},
        json={'project_code': 'any', 'operator': 'me', 'job_type': 'AS_FILE', 'data': [{'resumable_filename': 'any'}]},
    )

    assert response.status_code == 404
    assert response.json() == {
        'code': 404,
        'error_msg': 'Project not found',
        'page': 0,
        'total': 1,
        'num_of_pages': 1,
        'result': [],
    }


async def test_file_with_conflict_path_should_return_409(test_async_client, httpx_mock, mocker):
    # httpx_mock.add_response(
    #     method='POST',
    #     url='http://neo4j_service/v1/neo4j/nodes/Container/query',
    #     json=[{'any': 'any', 'global_entity_id': 'fake_global_entity_id'}],
    #     status_code=200,
    # )

    # REMOVE THIS AFTER NEW PUBLISH OF PROJECT CLIENT
    mocker.patch(
        'app.commons.project_client.ProjectClient.get',
        return_value={'any': 'any', 'global_entity_id': 'fake_global_entity_id'}
    )

    httpx_mock.add_response(
        method='GET',
        url='http://metadata_service/v1/items/search/?parent_path=&name=any&'
            'container_code=any&archived=false&zone=1&recursive=false',
        json={"result": [{
            'resumable_filename': 'any',
            'resumable_relative_path': "any"
        }]},
        status_code=200,
    )

    response = await test_async_client.post(
        '/v1/files/jobs',
        headers={'Session-Id': '1234'},
        json={'project_code': 'any', 'operator': 'me', 'job_type': 'AS_FILE', 'data': [{'resumable_filename': 'any'}]},
    )
    assert response.status_code == 409
    assert response.json() == {
        'code': 409,
        'error_msg': '[Invalid File] File Name has already taken by other resources(file/folder)',
        'page': 0,
        'total': 1,
        'num_of_pages': 1,
        'result': {'failed': [{'name': 'any', 'relative_path': '', 'type': 'File'}]},
    }


async def test_files_jobs_should_return_200_when_success(test_async_client, httpx_mock, create_job_folder, mocker):
    # httpx_mock.add_response(
    #     method='POST',
    #     url='http://neo4j_service/v1/neo4j/nodes/Container/query',
    #     json=[{'any': 'any', 'global_entity_id': 'fake_global_entity_id'}],
    #     status_code=200,
    # )

    # REMOVE THIS AFTER NEW PUBLISH OF PROJECT CLIENT
    mocker.patch(
        'app.commons.project_client.ProjectClient.get',
        return_value={'any': 'any', 'global_entity_id': 'fake_global_entity_id'}
    )

    httpx_mock.add_response(
        method='GET',
        url='http://metadata_service/v1/items/search/?parent_path=&name=any&'
            'container_code=any&archived=false&zone=1&recursive=false',
        json={"result": []},
        status_code=200,
    )
    httpx_mock.add_response(method='POST', url='http://data_ops_util_service/v2/resource/lock/bulk',
                            json={}, status_code=200)

    response = await test_async_client.post(
        '/v1/files/jobs',
        headers={'Session-Id': '1234'},
        json={'project_code': 'any', 'operator': 'me', 'job_type': 'AS_FILE', 'data': [{'resumable_filename': 'any'}]},
    )
    assert response.status_code == 200
    result = response.json()['result'][0]
    assert result['session_id'] == '1234'
    assert result['source'] == '/any'
    assert result['action'] == 'data_upload'
    assert result['status'] == 'PRE_UPLOADED'
    assert result['operator'] == 'me'


async def test_files_jobs_type_AS_FOLDER_should_return_200_when_success(
    test_async_client, httpx_mock, create_job_folder, mocker
):
    # httpx_mock.add_response(
    #     method='POST',
    #     url='http://neo4j_service/v1/neo4j/nodes/Container/query',
    #     json=[{'any': 'any', 'global_entity_id': 'fake_global_entity_id'}],
    #     status_code=200,
    # )

    # REMOVE THIS AFTER NEW PUBLISH OF PROJECT CLIENT
    mocker.patch(
        'app.commons.project_client.ProjectClient.get',
        return_value={'any': 'any', 'global_entity_id': 'fake_global_entity_id'}
    )

    httpx_mock.add_response(
        method='GET',
        url='http://metadata_service/v1/items/search/?parent_path=admin&name=test&'
            'container_code=any&archived=false&zone=1&recursive=false',
        json={"result": []},
        status_code=200,
    )
    httpx_mock.add_response(method='POST', url='http://data_ops_util_service/v2/resource/lock/bulk',
                            json={}, status_code=200)

    response = await test_async_client.post(
        '/v1/files/jobs',
        headers={'Session-Id': '1234'},
        json={
            'project_code': 'any',
            'operator': 'me',
            'job_type': 'AS_FOLDER',
            'data': [{'resumable_filename': 'any'}],
            'current_folder_node': 'admin/test'
        },
    )
    assert response.status_code == 200
    result = response.json()['result'][0]
    assert result['session_id'] == '1234'
    assert result['source'] == '/any'
    assert result['action'] == 'data_upload'
    assert result['status'] == 'PRE_UPLOADED'
    assert result['operator'] == 'me'


async def test_files_jobs_adds_folder_should_return_200_when_success(
    test_async_client,
    httpx_mock,
    create_job_folder,
    mocker
):
    # httpx_mock.add_response(
    #     method='POST',
    #     url='http://neo4j_service/v1/neo4j/nodes/Container/query',
    #     json=[{'any': 'any', 'global_entity_id': 'fake_global_entity_id'}],
    #     status_code=200,
    # )

    # REMOVE THIS AFTER NEW PUBLISH OF PROJECT CLIENT
    mocker.patch(
        'app.commons.project_client.ProjectClient.get',
        return_value={'any': 'any', 'global_entity_id': 'fake_global_entity_id'}
    )

    httpx_mock.add_response(
        method='GET',
        url='http://metadata_service/v1/items/search/?parent_path=admin&name=test&'
            'container_code=any&archived=false&zone=1&recursive=false',
        json={"result": []},
        status_code=200,
    )
    httpx_mock.add_response(method='POST', url='http://data_ops_util_service/v2/resource/lock/bulk',
                            json={}, status_code=200)

    response = await test_async_client.post(
        '/v1/files/jobs',
        headers={'Session-Id': '1234'},
        json={
            'project_code': 'any',
            'operator': 'me',
            'job_type': 'AS_FOLDER',
            'data': [{'resumable_filename': 'any', 'resumable_relative_path': 'tests/tmp'}],
            'current_folder_node': 'admin/test'
        },
    )
    assert response.status_code == 200
    result = response.json()['result'][0]
    assert result['session_id'] == '1234'
    assert result['source'] == 'tests/tmp/any'
    assert result['action'] == 'data_upload'
    assert result['status'] == 'PRE_UPLOADED'
    assert result['operator'] == 'me'
