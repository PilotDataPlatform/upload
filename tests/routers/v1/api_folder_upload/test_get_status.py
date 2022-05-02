import pytest

pytestmark = pytest.mark.asyncio  # set the mark to all tests in this file.


async def test_get_files_jobs_return_400_when_session_id_header_is_missing(test_async_client, httpx_mock):
    response = await test_async_client.get('/v1/upload/status/test_id', query_string={})
    assert response.status_code == 400
    assert response.json() == {
        'code': 400,
        'error_msg': 'session_id is required',
        'page': 0,
        'total': 1,
        'num_of_pages': 1,
        'result': [],
    }


async def test_get_files_jobs_return_200_and_job_data_in_results(test_async_client, httpx_mock, create_fake_job):
    response = await test_async_client.get(
        '/v1/upload/status/fake_global_entity_id', headers={'Session-Id': '1234'}, query_string={}
    )
    assert response.status_code == 200
    result = response.json()['result']
    assert result['session_id'] == '1234'
    assert result['job_id'] == 'fake_global_entity_id'
    assert result['source'] == 'any'
    assert result['action'] == 'data_upload'
    assert result['status'] == 'PRE_UPLOADED'
    assert result['operator'] == 'me'
    assert result['payload']['task_id'] == 'fake_global_entity_id'
    assert result['payload']['resumable_identifier'] == 'fake_global_entity_id'
