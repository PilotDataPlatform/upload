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
