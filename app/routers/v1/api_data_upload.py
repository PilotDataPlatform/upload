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

import asyncio
import json
import os
import shutil
import time
import unicodedata as ud
from typing import Optional

import httpx
from common import GEIDClient, LoggerFactory, ProjectClient, ProjectNotFoundException
from common.object_storage_adaptor.boto3_client import TokenError, get_boto3_client
from fastapi import APIRouter, BackgroundTasks, File, Form, Header, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi_utils import cbv

from app.commons.data_providers import SrvAioRedisSingleton, session_job_get_status
from app.commons.data_providers.redis_project_session_job import (
    EState,
    SessionJob,
    get_fsm_object,
)
from app.commons.kafka_producer import get_kafka_producer
from app.config import ConfigClass
from app.models.base_models import APIResponse, EAPIResponseCode
from app.models.file_data import SrvFileDataMgr
from app.models.folder import FolderMgr
from app.models.models_upload import (
    ChunkUploadResponse,
    EUploadJobType,
    GETJobStatusResponse,
    OnSuccessUploadPOST,
    POSTCombineChunksResponse,
    PreUploadPOST,
    PreUploadResponse,
)
from app.resources.decorator import header_enforcement
from app.resources.error_handler import (
    ECustomizedError,
    catch_internal,
    customized_error_template,
)
from app.resources.helpers import generate_archive_preview
from app.resources.lock import (
    ResourceAlreadyInUsed,
    bulk_lock_operation,
    unlock_resource,
)

router = APIRouter()

_API_TAG = 'V1 Upload'
_API_NAMESPACE = 'api_data_upload'
_JOB_TYPE = 'data_upload'


@cbv.cbv(router)
class APIUpload:
    """
    Summary:
        Upload workflow will involve three api *in a row*. They are following:
            - Pre upload api
            - Chunk upload api
            - Combine chunks api
        The upload process in both frontend/command line tool will follow this
        workflow:
            1. before the upload, call the pre upload api to do the name check
            2. then each file will be chunked up into 2MB(current setting),
                then each chunk will upload to server one by one with chunk
                upload api.
            3. finally, if the client side detect it uploaded ALL chunks, it will
                signal out the combine chunks api to backend. The backend will
                start a background job to process chunks and meta.
        The detail description of EACH api will be shown underneath
    Special Note:
        The file and folder cannot with same name
    """

    def __init__(self):
        self.__logger = LoggerFactory('api_data_upload').get_logger()
        self.geid_client = GEIDClient()
        self.project_client = ProjectClient(ConfigClass.PROJECT_SERVICE, ConfigClass.REDIS_URL)
        self.boto3_client = self._connect_to_object_storage()

    def _connect_to_object_storage(self):
        loop = asyncio.new_event_loop()
        boto3_client = loop.run_until_complete(
            get_boto3_client(
                ConfigClass.MINIO_ENDPOINT,
                access_key=ConfigClass.MINIO_ACCESS_KEY,
                secret_key=ConfigClass.MINIO_SECRET_KEY,
                https=ConfigClass.MINIO_HTTPS,
            )
        )
        loop.close()
        return boto3_client

    @router.post(
        '/files/jobs',
        tags=[_API_TAG],
        response_model=PreUploadResponse,
        summary='Always would be called first when upload, \
                 Init an async upload job, returns list of job identifier.',
    )
    @catch_internal(_API_NAMESPACE)
    @header_enforcement(['session_id'])
    async def upload_pre(
        self,
        request_payload: PreUploadPOST,
        session_id=Header(None),
        Authorization: Optional[str] = Header(None),
    ):
        """
        Summary:
            This is the first api the client side will call before upload
            Its allow to create an async upload job(s) for all upload files.
            It will make following checks for uploaded file(s):
                1. check if project exist
                2. check if the root folder is duplicate
                3. normalize the filename with different client(firefox/chrome)
                4. initialize the job for ALL upload files
                5. lock all file/node will be
        Header:
            - session_id(string): The unique session id from client side
        Payload:
            - project_code(string): the target project will upload to
            - operator(string): the name of operator
            - job_type(str): either can be file upload or folder upload
            - data(SingleFileForm):
                - resumable_filename(string): the name of file
                - resumable_relative_path: the relative path of the file
            - upload_message(string):
            - current_folder_node(string): the root level folder that will be
                uploaded
            - incremental(integer):
        Special Note:
            the folder upload & file upload has different payload structure.
            When the file upload, the current_folder_node will be '' (empty string)
            When the folder uplaod, the current_folder_node will be the root folder
        Return:
            - 200, job list
        """

        _res = APIResponse()
        project_code = request_payload.project_code
        namespace = os.environ.get('namespace')

        # check job type
        self.__logger.info('Upload Job start')
        if not (
            request_payload.job_type == EUploadJobType.AS_FILE.name
            or request_payload.job_type == EUploadJobType.AS_FOLDER.name
        ):
            _res.code = EAPIResponseCode.bad_request
            _res.error_msg = 'Invalid job type: {}'.format(request_payload.job_type)
            return _res.json_response()

        try:
            _ = await self.project_client.get(code=request_payload.project_code)

            conflict_file_paths, conflict_folder_paths = [], []
            # handle filename conflicts
            # also check the folder confilct. Note we might have the situation
            # that folder is same name but with different files
            conflict_folder_start_time = time.time()
            if request_payload.job_type == EUploadJobType.AS_FILE.name:
                conflict_file_paths = await get_conflict_file_paths(request_payload.data, request_payload.project_code)
            elif request_payload.job_type == EUploadJobType.AS_FOLDER.name:
                conflict_folder_paths = await get_conflict_folder_paths(
                    request_payload.project_code,
                    request_payload.current_folder_node,
                )
            self.__logger.warning('Conflict Folder Cal Time: ' + str(time.time() - conflict_folder_start_time))

            if len(conflict_file_paths) > 0 or len(conflict_folder_paths) > 0:
                return response_conflic_folder_file_names(_res, conflict_file_paths, conflict_folder_paths)

            # here I have to update the special character into NFC form
            # since some of the browser will encode them into NFD form
            # for the bug detail. Please check the 2244
            for upload_data in request_payload.data:
                upload_data.resumable_filename = ud.normalize('NFC', upload_data.resumable_filename)

            #######################################################

            # initialize empty job status manager
            status_mgr = await get_fsm_object(
                session_id,
                project_code,
                request_payload.operator,
            )
            task_id = self.geid_client.get_GEID()
            status_mgr.add_payload('task_id', task_id)

            # prepare the presigned upload id
            bucket = ('gr-' if namespace == 'greenroom' else 'core-') + project_code
            file_keys = [x.resumable_relative_path + '/' + x.resumable_filename for x in request_payload.data]
            upload_ids = await self.boto3_client.prepare_multipart_upload(bucket, file_keys)

            # then prepare the job for EACH of the uploading files
            job_list, lock_keys = [], []
            redis_srv = SrvAioRedisSingleton()
            redis_pipeline = await redis_srv.get_pipeline()
            for file_key, upload_id in zip(file_keys, upload_ids):

                await status_mgr.set_job_id(upload_id)
                # file_path = upload_data.resumable_relative_path + '/' + upload_data.resumable_filename
                status_mgr.set_source(file_key)
                status_mgr.add_payload('resumable_identifier', upload_id)

                await status_mgr.set_status(EState.PRE_UPLOADED.name)
                job_key, job_value, job_recorded = status_mgr.get_kv_entity()
                await run_in_threadpool(redis_pipeline.set, job_key, job_value)
                job_list.append(job_recorded)

                # also generate the file lock key for batch lock operation
                lock_key = await run_in_threadpool(os.path.join, bucket, file_key)
                lock_keys.append(lock_key)

            await redis_pipeline.execute()
            # lock all the files to prevent other user uploading same name
            await run_in_threadpool(bulk_lock_operation, lock_keys, 'write')

            _res.result = job_list

        except TokenError as e:
            _res.error_msg = str(e)
            _res.code = EAPIResponseCode.bad_request

        except ProjectNotFoundException as e:
            _res.error_msg = str(e)
            _res.code = EAPIResponseCode.not_found

        except ResourceAlreadyInUsed as e:
            _res.error_msg = str(e)
            _res.code = EAPIResponseCode.conflict

        except Exception as e:
            _res.error_msg = 'Error when pre uploading ' + str(e)
            _res.code = EAPIResponseCode.internal_error

        return _res.json_response()

    @router.get(
        '/upload/status/{job_id}', tags=[_API_TAG], response_model=GETJobStatusResponse, summary='get upload job status'
    )
    @catch_internal(_API_NAMESPACE)
    @header_enforcement(['session_id'])
    async def get_status(self, job_id, session_id: str = Header(None)):
        """
        Summary:
            This method allow to check file upload status.
        Header:
            - session_id(string): The unique session id from client side
        Parameter:
            - job_id(string): The job identifier for each file
        Return:
            - 200, job detail
        """

        _res = APIResponse()

        job_fetched = await session_job_get_status(session_id, job_id, '*', _JOB_TYPE, '*')
        if len(job_fetched) == 0:
            _res.code = EAPIResponseCode.bad_request
            _res.error_msg = 'Job ID %s not found' % job_id
        else:
            _res.code = EAPIResponseCode.success
            _res.result = job_fetched[0]

        return _res.json_response()

    @router.post('/files/chunks', tags=[_API_TAG], response_model=ChunkUploadResponse, summary='upload chunks process.')
    @catch_internal(_API_NAMESPACE)
    @header_enforcement(['session_id'])
    async def upload_chunks(
        self,
        project_code: str = Form(...),
        operator: str = Form(...),
        resumable_identifier: str = Form(...),
        resumable_filename: str = Form(...),
        resumable_relative_path: str = Form(''),
        resumable_chunk_number: int = Form(...),
        resumable_total_chunks: int = Form(...),
        resumable_total_size: int = Form(...),
        tags: list = Form([]),
        session_id: str = Header(None),
        chunk_data: UploadFile = File(...),
    ):
        """
        Summary:
            The second api that the client side will call during the file
             upload. The data is uploaded throught the <Multipart Upload>.
            The api will create the temp folder if it does not exist. Then
             the chunk_data will be saved into the temp folder.
        Header:
            - session_id(string): The unique session id from client side
        Form:
            - project_code(string): the target project will upload to
            - operator(string): the name of operator
            - resumable_filename(string): the name of file
            - resumable_relative_path(string): the relative path of the file
            - resumable_identifier(string): The job identifier for each file
            - resumable_chunk_number(string): The integer id for each chunk
        Return:
            - 200, Succeed
        """

        # init resp
        _res = APIResponse()

        # here I have to update the special character into NFC form
        # since some of the browser will encode them into NFD form
        # for the bug detail. Please check the ticket 2244
        resumable_filename = ud.normalize('NFC', resumable_filename)

        self.__logger.info('Uploading file %s chunk %s', resumable_filename, resumable_chunk_number)
        redis_srv = SrvAioRedisSingleton()
        # using the boto3 to upload chunks directly into minio server
        try:
            bucket = ('gr-' if ConfigClass.namespace == 'greenroom' else 'core-') + project_code
            file_key = resumable_relative_path + '/' + resumable_filename

            # dirctly proxy to the server
            self.__logger.info('Start to read the chunks')
            file_content = await chunk_data.read()
            self.__logger.info('Chunk size is %s', len(file_content))
            etag_info = await self.boto3_client.part_upload(
                bucket, file_key, resumable_identifier, resumable_chunk_number, file_content
            )
            self.__logger.info('finish the chunk upload: %s', json.dumps(etag_info))

            # and then collect the etag for third api
            redis_key = '%s:%s' % (resumable_identifier, resumable_chunk_number)
            await redis_srv.set_by_key(redis_key, json.dumps(etag_info))

            _res.code = EAPIResponseCode.success
            _res.result = {'msg': 'Succeed'}
        except Exception as e:
            error_message = str(e)
            self.__logger.error('Fail to upload chunks: %s', error_message)
            # get the exist status manager that created in
            # pre upload api.And set the job status/return message
            status_mgr = await get_fsm_object(
                session_id,
                project_code,
                operator,
                resumable_identifier,
            )
            status_mgr.add_payload('error_msg', str(e))
            await status_mgr.set_status(EState.TERMINATED.name)

            _res.code = EAPIResponseCode.internal_error
            _res.error_msg = error_message

        return _res.json_response()

    @router.post(
        '/files',
        tags=[_API_TAG],
        response_model=POSTCombineChunksResponse,
        summary='create a background worker to combine chunks, transfer file to the destination namespace',
    )
    @catch_internal(_API_NAMESPACE)
    @header_enforcement(['session_id'])
    async def on_success(
        self,
        request_payload: OnSuccessUploadPOST,
        background_tasks: BackgroundTasks,
        session_id: str = Header(None),
        Authorization: Optional[str] = Header(None),
        refresh_token: Optional[str] = Header(None),
    ):
        """
        Summary:
            The third api will be called by client side. The client send
            the acknoledgement for all chunks uploaded by signaling this
            api. Once the upload service recieve the api calling, it will
            start a background job to combine the chunks and process the
            metadata
        Form:
            - project_code(string): the target project will upload to
            - operator(string): the name of operator
            - resumable_filename(string): the name of file
            - resumable_relative_path(string): the relative path of the file
            - resumable_identifier(string): The job identifier for each file
            - resumable_total_chunks(string): The number of total chunks
            - resumable_total_size(float): the file size
            - process_pipeline(string optional): default is None  # cli
            - from_parents(list optional): default is None  # cli
            - upload_message(string optional): default is ''  # cli
        Return:
            - 200, Succeed
        """

        # init resp
        _res = APIResponse()

        self.__logger.info('resumable_filename: %s' % request_payload.resumable_filename)
        # here I have to update the special character into NFC form
        # since some of the browser will encode them into NFD form
        # for the bug detail. Please check the ticket 2244
        request_payload.resumable_filename = ud.normalize('NFC', request_payload.resumable_filename)

        # init status manager
        status_mgr = await get_fsm_object(
            session_id,
            request_payload.project_code,
            request_payload.operator,
            request_payload.resumable_identifier,
        )

        # add background task to combine all received chunks
        background_tasks.add_task(
            finalize_worker,
            self.__logger,
            request_payload,
            status_mgr,
            self.boto3_client,
            session_id,
        )

        self.__logger.info('finalize_worker started')
        # set merging status
        job_recorded = await status_mgr.set_status(EState.CHUNK_UPLOADED.name)
        _res.code = EAPIResponseCode.success
        _res.result = job_recorded
        return _res.json_response()


def save_file(dest: str, my_file: UploadFile) -> None:
    """save file on the disk."""
    with open(dest, 'wb') as buffer:
        shutil.copyfileobj(my_file.file, buffer)


async def folder_creation(project_code: str, operator: str, file_path: str, file_name: str):
    """
    Summary:
        The function will batch create the tree path based on file_path.
        For example, if the file_path is /A/B/C that folder B and C
        do not exist, then function will batch create them
    Parameters:
        - project_code(string): the target project will upload to
        - operator(string): the name of operator
        - file_path(string): the relative path of the file(without ending
            slash)
        - file_name: the name of tile
    Return:
        - The last node in the tree path. In the above example, the function
            will return folder node C
    """

    __logger = LoggerFactory('api_data_upload').get_logger()
    namespace = ConfigClass.namespace
    folder_create_duration = 0

    __logger.info('test')

    # create folder and folder nodes
    folder_create_start_time = time.time()
    folder_mgr = FolderMgr(
        project_code,
        file_path,
    )

    # TODO somehow simplify here
    await folder_mgr.create(operator)
    to_create_folders = folder_mgr.to_create

    # last_folder_node_geid = folder_mgr.last_node.folder_parent_geid if folder_mgr.last_node else None
    folder_create_duration += time.time() - folder_create_start_time

    __logger.info('Save to Cache Folder Time: ' + str(folder_create_duration))

    # batch create folder nodes
    batch_folder_create_start_time = time.time()
    if len(to_create_folders) > 0:
        # also try to lock the those new folder
        try:
            lock_keys = []
            bucket_prefix = 'gr-' if namespace == 'greenroom' else 'core-'
            for nodes in to_create_folders:
                bucket = bucket_prefix + nodes.get('container_code')
                lock_key = '%s/%s/%s' % (bucket, nodes.get('parent_path'), nodes.get('name'))
                lock_keys.append(lock_key)

            await run_in_threadpool(bulk_lock_operation, lock_keys, 'write')
            __logger.info('Folder lock time: ' + str(time.time() - batch_folder_create_start_time))

            url = ConfigClass.METADATA_SERVICE + 'items/batch/'
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={'items': to_create_folders}, timeout=10)
                if response.status_code != 200:
                    raise Exception('Fail to create metadata in postgres: %s' % (response.__dict__))

            __logger.info('New Folders saved: {}'.format(len(to_create_folders)))
            __logger.info('New Node Creation Time: ' + str(time.time() - batch_folder_create_start_time))

            # here we unlock the locked nodes ONLY
            await run_in_threadpool(bulk_lock_operation, lock_keys, 'write', False)

        # for the r/w lock error we just raise to Terminate job
        except ResourceAlreadyInUsed as e:
            raise e
        # for other error we will unlock the folders
        except Exception as e:
            __logger.error('Error when create the folder tree: {}'.format(e))
            await run_in_threadpool(bulk_lock_operation, lock_keys, 'write', False)
            raise e

    __logger.info('[SUCCEED] Done')

    return folder_mgr.last_node


async def finalize_worker(
    logger,
    request_payload: OnSuccessUploadPOST,
    status_mgr: SessionJob,
    boto3_client,
    session_id,
):
    """
    Summary:
        The function is the background job to combine chunks and process the
        metadata. The metadata process including following:
            - lock the target file node.
            - create the folder tree if the folder structure does not exist.
            - combine chunks and upload to minio.
            - calling the dataops utility api to create postgres/es/atlas record.
            - calling the provenence service to create activity log of file.
            - calling the dataops utiltiy api to add the zip preview if upload
                zip file.
            - update the job status.
            - remove the temperary folder
            - unlock the file node
    Parameter:
        - request_payload(OnSuccessUploadPOST)
            - project_code(string): the target project will upload to
            - operator(string): the name of operator
            - resumable_filename(string): the name of file
            - resumable_relative_path(string): the relative path of the file
            - resumable_identifier(string): The job identifier for each file
            - resumable_total_chunks(string): The number of total chunks
            - resumable_total_size(float): the file size
            - process_pipeline(string optional): default is None  # cli
            - from_parents(list optional): default is None  # cli
            - upload_message(string optional): default is ''  # cli
        - status_mgr(SessionJob): the object manage the job status
        - access_token(str): the token for user to upload into minio
        - refresh_token(str): the token to refresh the access
    Return:
        - None
    """

    namespace = ConfigClass.namespace
    project_code = request_payload.project_code
    file_path = request_payload.resumable_relative_path
    file_name = request_payload.resumable_filename
    operator = request_payload.operator
    resumable_identifier = request_payload.resumable_identifier
    bucket = ('gr-' if namespace == 'greenroom' else 'core-') + project_code
    obj_path = await run_in_threadpool(os.path.join, file_path, file_name)
    lock_key = await run_in_threadpool(os.path.join, bucket, file_path, file_name)

    temp_dir = await run_in_threadpool(os.path.join, ConfigClass.TEMP_BASE, resumable_identifier)
    target_file_full_path = await run_in_threadpool(
        os.path.join,
        ConfigClass.ROOT_PATH,
        request_payload.project_code,
        request_payload.resumable_relative_path,
        request_payload.resumable_filename,
    )

    try:

        # create folder tree if not exist. The function is to check if
        # /a/b/c.txt that b is not exist in database. And will create it
        logger.info('Start to create folder trees')
        last_node = await folder_creation(project_code, operator, file_path, file_name)

        target_head, target_tail = await run_in_threadpool(os.path.split, target_file_full_path)

        redis_srv = SrvAioRedisSingleton()
        # get all chunk info like etag
        logger.info('Start server side chunk combination')
        chunks_info = await redis_srv.mget_by_prefix(resumable_identifier)
        chunks_info = [json.loads(x) for x in chunks_info]
        chunks_info = sorted(chunks_info, key=lambda d: d.get('PartNumber'))

        # send the message to combine the chunks on server side
        result = await boto3_client.combine_chunks(bucket, obj_path, resumable_identifier, chunks_info)
        version_id = result.get('VersionId', '')

        # create entity file data
        logger.info('start to create item in metadata service')
        file_meta_mgr = SrvFileDataMgr(logger)
        res_create_meta = await file_meta_mgr.create(
            operator,
            target_tail,
            target_head,
            request_payload.resumable_total_size,
            'Raw file in {}'.format(namespace),
            namespace,
            project_code,
            request_payload.tags,
            bucket,  # minio attribute
            obj_path,  # minio attribute
            version_id,  # minio attribute
            operator=operator,
            process_pipeline=request_payload.process_pipeline,
            from_parents=request_payload.from_parents,
            parent_folder_geid=last_node.global_entity_id,
        )
        # get created entity
        created_entity = res_create_meta.get('result')

        # Store zip file preview in postgres
        try:
            file_type = await run_in_threadpool(os.path.splitext, file_name)
            if file_type[1] == '.zip':
                # new update and temperory solution here: if the file is zip
                # then we download again to read the structure
                await boto3_client.downlaod_object(bucket, obj_path, temp_dir + '/' + obj_path)

                archive_preview = await generate_archive_preview(temp_dir + '/' + obj_path)
                payload = {
                    'archive_preview': archive_preview,
                    'file_id': created_entity.get('id'),
                }
                async with httpx.AsyncClient() as client:
                    await client.post(ConfigClass.DATA_OPS_UTIL + 'archive', json=payload, timeout=3600)
        except Exception as e:
            geid = created_entity.get('id')
            logger.error(f'Error adding file preview for {geid}: {str(e)}')
            raise e

        # update full path to Greenroom/<display_path> for audit log
        obj_path = (
            (ConfigClass.GREEN_ZONE_LABEL if namespace == 'greenroom' else ConfigClass.CORE_ZONE_LABEL) + '/' + obj_path
        )

        # update full path to Greenroom/<display_path> for audit log
        kp = await get_kafka_producer()
        await kp.create_activity_log(
            created_entity, 'metadata_items_activity.avsc', operator, ConfigClass.KAFKA_ACTIVITY_TOPIC
        )

        await status_mgr.set_status(EState.FINALIZED.name)

        status_mgr.add_payload('source_geid', created_entity.get('id'))
        await status_mgr.set_status(EState.SUCCEED.name)
        logger.info('Upload Job Done.')

    except FileNotFoundError as e:
        error_msg = 'folder {} is already empty: {}'.format(temp_dir, str(e))
        logger.error(error_msg)
        status_mgr.add_payload('error_msg', str(error_msg))
        await status_mgr.set_status(EState.TERMINATED.name)

    except Exception as exce:
        logger.error(str(exce))
        status_mgr.add_payload('error_msg', str(exce))
        await status_mgr.set_status(EState.TERMINATED.name)
        raise exce

    finally:
        await unlock_resource(lock_key, 'write')

        # remove the zip preview if applies
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir)


# TODO seem like we can merge following two functions
async def get_conflict_folder_paths(project_code: str, current_folder_node: str):
    """
    Summary:
        The function will check and return conflict folder paths for
        folder upload only.
    Parameter:
       project_code(string): The unique code of target project
       current_folder_node(string): the root folder name
    Return:
        list of dict
            - display_path(string): the path of conflict folder
            - type(string): Folder
    """
    namespace = ConfigClass.namespace

    conflict_folder_paths = []
    file_path, file_name = current_folder_node.rsplit('/', 1)
    params = {
        'parent_path': file_path,
        'name': file_name,
        'container_code': project_code,
        'archived': False,
        'zone': 0 if namespace == 'greenroom' else 1,
        'recursive': False,
    }
    # also check if it is in greeroom or core
    node_query_url = ConfigClass.METADATA_SERVICE + 'items/search/'
    async with httpx.AsyncClient() as client:
        response = await client.get(node_query_url, params=params)
    nodes = response.json().get('result', [])

    if len(nodes) > 0:
        conflict_folder_paths.append({'display_path': current_folder_node, 'type': 'Folder'})

    return conflict_folder_paths


async def get_conflict_file_paths(data, project_code):
    """
    Summary:
        The function will check and return conflict file paths for
        file upload only.
    Parameter:
        data(list of dict):
            - resumable_filename(string): the name of file
            - resumable_relative_path: the relative path of the file
        project_code(string): The unique code of target project
    Return:
        list of dict
            - display_path(string): the path of conflict file
            - type(string): File
    """
    namespace = ConfigClass.namespace
    conflict_file_paths = []
    for upload_data in data:
        # now we have to use the postgres to check duplicate
        params = {
            'parent_path': upload_data.resumable_relative_path,
            'name': upload_data.resumable_filename,
            'container_code': project_code,
            'archived': False,
            'zone': 0 if namespace == 'greenroom' else 1,
            'recursive': False,
        }

        # search upto the new metadata service if the input files
        node_query_url = ConfigClass.METADATA_SERVICE + 'items/search/'
        async with httpx.AsyncClient() as client:
            response = await client.get(node_query_url, params=params)
        nodes = response.json().get('result', [])

        if len(nodes) > 0:
            conflict_file_paths.append(
                {
                    'name': upload_data.resumable_filename,
                    'relative_path': upload_data.resumable_relative_path,
                    'type': 'File',
                }
            )

    return conflict_file_paths


def response_conflic_folder_file_names(_res, conflict_file_paths, conflict_folder_paths):
    """set conflict response when filename or folder name conflics."""
    # conflict file names
    if len(conflict_file_paths) > 0:
        _res.code = EAPIResponseCode.conflict
        _res.error_msg = customized_error_template(ECustomizedError.INVALID_FILENAME)
        _res.result = {'failed': conflict_file_paths}
        return _res.json_response()
    # conflict folder names
    if len(conflict_folder_paths) > 0:
        _res.code = EAPIResponseCode.conflict
        _res.error_msg = customized_error_template(ECustomizedError.INVALID_FOLDERNAME)
        _res.result = {'failed': conflict_folder_paths}
        return _res.json_response()
