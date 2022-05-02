import httpx

from app.config import ConfigClass


class ResourceAlreadyInUsed(Exception):
    pass


async def data_ops_request(resource_key: str, operation: str, method: str) -> dict:
    url = ConfigClass.DATA_OPS_UT_V2 + 'resource/lock/'
    post_json = {'resource_key': resource_key, 'operation': operation}
    async with httpx.AsyncClient() as client:
        response = await client.request(
            url=url,
            method=method,
            json=post_json,
            timeout=3600
        )
    if response.status_code != 200:
        raise ResourceAlreadyInUsed('resource %s already in used' % resource_key)

    return response.json()


async def lock_resource(resource_key: str, operation: str) -> dict:
    return await data_ops_request(resource_key, operation, 'POST')


async def unlock_resource(resource_key: str, operation: str) -> dict:
    return await data_ops_request(resource_key, operation, 'DELETE')


def bulk_lock_operation(resource_key: list, operation: str, lock=True) -> dict:
    # base on the flag toggle the http methods
    method = "POST" if lock else "DELETE"

    # operation can be either read or write
    url = ConfigClass.DATA_OPS_UT_V2 + 'resource/lock/bulk'
    post_json = {'resource_keys': resource_key, 'operation': operation}
    with httpx.Client() as client:
        response = client.request(method, url, json=post_json, timeout=3600)
    if response.status_code != 200:
        raise ResourceAlreadyInUsed('resource %s already in used' % resource_key)

    return response.json()
