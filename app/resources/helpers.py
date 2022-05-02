from zipfile import ZipFile

import httpx

from app.config import ConfigClass


async def generate_archive_preview(file_path: str, file_type: str = 'zip') -> dict:
    """
    Summary:
        The function will walk throught the zip package. And return the
        folder structures.
    Parameters:
        - file_path(string): the path of zip file
        - file_type(string): default is zip type
    Return:
        - (dict) folder structure inside zip
    """

    results = {}
    if file_type == 'zip':
        ArchiveFile = ZipFile

    with ArchiveFile(file_path, 'r') as archive:
        for file in archive.infolist():
            # get filename for file
            filename = file.filename.split('/')[-1]
            if not filename:
                # get filename for folder
                filename = file.filename.split('/')[-2]
            current_path = results
            for path in file.filename.split('/')[:-1]:
                if path:
                    if not current_path.get(path):
                        current_path[path] = {'is_dir': True}
                    current_path = current_path[path]

            if not file.is_dir():
                current_path[filename] = {
                    'filename': filename,
                    'size': file.file_size,
                    'is_dir': False,
                }
    return results


async def get_project(project_code: str) -> dict:
    """
    Summary:
        The function call the neo4j service to check if the
        input project_code exists.
    Parameters:
        - project_code(string): unique code of project
    Return:
        - (dict) the project detail
    """
    data = {'code': project_code}
    async with httpx.AsyncClient() as client:
        response = await client.post(ConfigClass.NEO4J_SERVICE + 'nodes/Container/query', json=data)
    result = response.json()

    return result[0] if len(result) > 0 else None


async def send_to_queue(payload: dict) -> httpx.Response:
    """
    Summary:
        The function call the call to queue service and
        send upload finish message for downstream operation.
        at current case, it will trigger the dcm_id pipeline
    Parameters:
        - payload(dict): the message will send to queue
    Return:
        - (httpx.Response) response from queue service
    """
    url = ConfigClass.QUEUE_SERVICE + 'send_message'
    async with httpx.AsyncClient() as client:
        res = await client.post(
            url=url, json=payload,
            headers={'Content-type': 'application/json; charset=utf-8'},
            timeout=3600
        )
    # if res.status_code != 200:
    #     raise Exception("Fail to send the message to queue: " + str(res.__dict__))
    return res
