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

import os
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


async def update_file_operation_logs(
    operator: str, download_path: str, project_code: str, operation_type: str = 'data_upload', extra: dict = None
) -> httpx.Response:
    """
    Summary:
        The function will call the api in provenance service to
        create the activity log for file upload. NOTE this function
        will be removed after integrating the Kafka consumer in system
    Parameters:
        - operator(string): the user initiate the download operation
        - download_path(string): the path of object
        - project_code(string): the unique code of project
    Return:
        - httpx response
    """

    # new audit log api
    url_audit_log = ConfigClass.PROVENANCE_SERVICE + 'audit-logs'
    payload_audit_log = {
        'action': operation_type,
        'operator': operator,
        'target': download_path,
        'outcome': download_path,
        'resource': 'file',
        'display_name': os.path.basename(download_path),
        'project_code': project_code,
        'extra': extra if extra else {},
    }
    async with httpx.AsyncClient() as client:
        res_audit_logs = await client.post(url_audit_log, json=payload_audit_log, timeout=3600)
    if res_audit_logs.status_code != 200:
        raise Exception('Error when creating the audit log: ' + str(res_audit_logs.__dict__))
    return res_audit_logs
