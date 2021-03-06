# PILOT
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

import httpx

from app.config import ConfigClass


class SrvFileDataMgr:
    """Service for File Data Entity INFO Manager."""

    base_url = ConfigClass.DATAOPS_SERVICE

    def __init__(self, logger):
        self.logger = logger

    async def create(
        self,
        uploader,
        file_name,
        path,
        file_size,
        desc,
        namespace,
        project_code,
        labels,
        minio_bucket,
        minio_object_path,
        version_id,
        operator=None,
        from_parents=None,
        process_pipeline=None,
        parent_folder_geid=None,
    ):
        """Create File Data Entity V2."""

        url = self.base_url + 'filedata/'
        post_json_form = {
            'uploader': uploader,
            'file_name': file_name,
            'path': path,
            'file_size': file_size,
            'description': desc,
            'namespace': namespace,
            'project_code': project_code,
            'labels': labels,
            'parent_folder_geid': parent_folder_geid if parent_folder_geid else '',
            # minio attribute
            'bucket': minio_bucket,
            'minio_object_path': minio_object_path,
            'version_id': version_id,
        }
        self.logger.debug('SrvFileDataMgr post_json_form' + str(post_json_form))
        if process_pipeline:
            post_json_form['process_pipeline'] = process_pipeline
        if operator:
            post_json_form['operator'] = operator
        if from_parents:
            post_json_form['parent_query'] = from_parents

        async with httpx.AsyncClient() as client:
            res = await client.post(url=url, json=post_json_form, timeout=3600)
        self.logger.debug('SrvFileDataMgr create results: ' + res.text)
        if res.status_code != 200:
            raise Exception('Fail to create data entity: ' + str(res.__dict__))
        return res.json()
