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

import json
import time
from enum import Enum

from .redis import SrvAioRedisSingleton

_JOB_TYPE = 'data_upload'


class EState(Enum):
    """Upload state."""

    INIT = (0,)
    PRE_UPLOADED = (1,)
    CHUNK_UPLOADED = (2,)
    FINALIZED = (3,)
    SUCCEED = (4,)
    TERMINATED = 5


class SessionJob:
    """Session Job ORM."""

    def __init__(self, session_id, project_code, operator, job_id=None):
        """Init function, if provide job_id, will read from redis.

        If not provide, create a new job, and need to call set_job_id to set a new geid
        """
        self.session_id = session_id
        self.job_id = job_id
        self.project_code = project_code
        self.action = _JOB_TYPE
        self.operator = operator
        self.source = None
        self.status = EState.INIT.name
        self.progress = 0
        self.payload = {}

    async def set_job_id(self, job_id):
        """set job id."""
        self.job_id = job_id

    def set_source(self, source: str):
        """set job source."""
        self.source = source

    def add_payload(self, key: str, value):
        """will update if exists the same key."""
        self.payload[key] = value

    async def set_status(self, status: str):
        """set job status."""
        self.status = status
        return await self.save()

    def set_progress(self, progress: int):
        """set job status."""
        self.progress = progress

    async def save(self):
        """save in redis."""
        if not self.job_id:
            raise (Exception('[SessionJob] job_id not provided'))
        if not self.source:
            raise (Exception('[SessionJob] source not provided'))
        if not self.status:
            raise (Exception('[SessionJob] status not provided'))
        return await session_job_set_status(
            self.session_id,
            self.job_id,
            self.source,
            self.action,
            self.status,
            self.project_code,
            self.operator,
            self.payload,
            self.progress,
        )

    async def read(self):
        """read from redis."""
        fetched = await session_job_get_status(
            self.session_id, self.job_id, self.project_code, self.action, self.operator
        )
        if not fetched:
            raise Exception('[SessionJob] Not found job: {}'.format(self.job_id))
        job_read = fetched[0]
        self.source = job_read['source']
        self.status = job_read['status']
        self.progress = job_read['progress']
        self.payload = job_read['payload']

    def get_kv_entity(self):
        """get redis key value pair return key, value, job_dict."""
        my_key = 'dataaction:{}:Container:{}:{}:{}:{}:{}'.format(
            self.session_id, self.job_id, self.action, self.project_code, self.operator, self.source
        )
        # print('mykey:' + my_key)
        record = {
            'session_id': self.session_id,
            'job_id': self.job_id,
            'source': self.source,
            'action': self.action,
            'status': self.status,
            'project_code': self.project_code,
            'operator': self.operator,
            'progress': self.progress,
            'payload': {
                'task_id': self.payload.get('task_id'),
                'resumable_identifier': self.payload.get('resumable_identifier'),
            },
            'update_timestamp': str(round(time.time())),
        }
        my_value = json.dumps(record)
        return my_key, my_value, record


async def get_fsm_object(session_id: str, project_code: str, operator: str, job_id: str = None) -> SessionJob:

    fms_object = SessionJob(session_id, project_code, operator, job_id)
    if job_id:
        await fms_object.read()
    return fms_object


async def session_job_set_status(
    session_id: str,
    job_id: str,
    source: str,
    action: str,
    target_status: str,
    project_code: str,
    operator: str,
    payload: str = None,
    progress: int = 0,
) -> dict:

    srv_redis = SrvAioRedisSingleton()
    my_key = 'dataaction:{}:Container:{}:{}:{}:{}:{}'.format(session_id, job_id, action, project_code, operator, source)

    record = {
        'session_id': session_id,
        'job_id': job_id,
        'source': source,
        'action': action,
        'status': target_status,
        'project_code': project_code,
        'operator': operator,
        'progress': progress,
        'payload': payload,
        'update_timestamp': str(round(time.time())),
    }
    my_value = json.dumps(record)
    await srv_redis.set_by_key(my_key, my_value)
    return record


async def session_job_get_status(
    session_id: str, job_id: str, project_code: str, action: str, operator: str = None
) -> list:

    srv_redis = SrvAioRedisSingleton()
    my_key = 'dataaction:{}:Container:{}:{}:{}'.format(session_id, job_id, action, project_code)
    if operator:
        my_key = 'dataaction:{}:Container:{}:{}:{}:{}'.format(session_id, job_id, action, project_code, operator)

    res_binary = await srv_redis.mget_by_prefix(my_key)
    return [json.loads(record.decode('utf-8')) for record in res_binary] if res_binary else []
