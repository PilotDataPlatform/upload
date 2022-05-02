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

from enum import Enum
from typing import List

from pydantic import BaseModel, Field

from .base_models import APIResponse


class EUploadJobType(Enum):
    AS_FOLDER = 'AS_FOLDER'
    AS_FILE = 'AS_FILE'


class SingleFileForm(BaseModel):
    resumable_filename: str
    resumable_relative_path: str = ''
    dcm_id: str = 'undefined'


class PreUploadPOST(BaseModel):
    """Pre upload payload model."""

    project_code: str
    operator: str
    job_type: str = 'AS_FOLDER | AS_FILE'
    folder_tags: List[str] = []
    data: List[SingleFileForm]
    upload_message = ''
    current_folder_node = ''
    incremental = False  # TODO remove


class PreUploadResponse(APIResponse):
    """Pre upload response class."""

    result: dict = Field(
        {},
        example=[
            {
                'session_id': 'unique_session_2021',
                'job_id': '1bfe8fd8-8b41-11eb-a8bd-eaff9e667817-1616439732',
                'source': 'file1.png',
                'action': 'data_upload',
                'status': 'PRE_UPLOADED',
                'project_code': 'gregtest',
                'operator': 'zhengyang',
                'progress': 0,
                'payload': {
                    'resumable_identifier': '1bfe8fd8-8b41-11eb-a8bd-eaff9e667817-1616439732',
                    'parent_folder_geid': '1bcbe182-8b41-11eb-bf7a-eaff9e667817-1616439732',
                },
                'update_timestamp': '1616439731',
            },
        ],
    )


class ChunkUploadPOST(BaseModel):
    """chunk upload payload model."""

    project_code: str
    operator: str
    resumable_identifier: str
    resumable_filename: str
    resumable_chunk_number: int
    resumable_total_chunks: int
    resumable_total_size: float
    tags: List[str] = []
    dcm_id: str = 'undefined'
    metadatas: dict = None


class ChunkUploadResponse(APIResponse):
    """Pre upload response class."""

    result: dict = Field({}, example={'msg': 'Succeed'})


class OnSuccessUploadPOST(BaseModel):
    """merge chunks payload model."""

    project_code: str
    operator: str
    resumable_identifier: str
    resumable_filename: str
    resumable_relative_path: str
    resumable_total_chunks: int
    resumable_total_size: float
    tags: List[str] = []  # check here
    dcm_id: str = 'undefined'
    metadatas: dict = None  # manifest
    process_pipeline: str = None  # cli
    from_parents: list = None  # cli
    upload_message = ''  # cli


class GETJobStatusResponse(APIResponse):
    """get Job status response class."""

    result: dict = Field(
        {},
        example=[
            {
                'session_id': 'unique_session',
                'job_id': 'upload-0a572418-7c2b-11eb-8428-be498ca98c54-1614780986',
                'source': '<path>',
                'action': 'data_upload',
                'status': 'PRE_UPLOADED | SUCCEED',
                'project_code': 'em0301',
                'operator': 'zhengyang',
                'progress': 0,
                'payload': {
                    'resumable_identifier': 'upload-0a572418-7c2b-11eb-8428-be498ca98c54-1614780986',
                    'parent_folder_geid': '1e3fa930-8b41-11eb-845f-eaff9e667817-1616439736',
                },
                'update_timestamp': '1614780986',
            }
        ],
    )


class POSTCombineChunksResponse(APIResponse):
    """get Job status response class."""

    result: dict = Field(
        {},
        example={
            'session_id': 'unique_session',
            'job_id': 'upload-0a572418-7c2b-11eb-8428-be498ca98c54-1614780986',
            'source': '<path>',
            'action': 'data_upload',
            'status': 'PRE_UPLOADED | SUCCEED',
            'project_code': 'em0301',
            'operator': 'zhengyang',
            'progress': 0,
            'payload': {
                'resumable_identifier': 'upload-0a572418-7c2b-11eb-8428-be498ca98c54-1614780986',
                'parent_folder_geid': '1e3fa930-8b41-11eb-845f-eaff9e667817-1616439736',
            },
            'update_timestamp': '1614780986',
        },
    )
