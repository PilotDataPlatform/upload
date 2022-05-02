import pytest

from app.config import ConfigClass


@pytest.mark.asyncio
async def test_root_request_should_return_app_status(test_async_client):
    response = await test_async_client.get('/')
    assert response.status_code == 200
    assert response.json() == {
        'status': 'OK',
        'name': ConfigClass.APP_NAME,
        'version': ConfigClass.VERSION,
    }
