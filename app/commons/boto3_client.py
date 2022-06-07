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

import aioboto3
import httpx
import xmltodict
from botocore.client import Config

_SIGNATURE_VERSTION = 's3v4'


class TokenExpired(Exception):
    pass


async def get_boto3_client(endpoint: str, token: str = None, temp_credentials: dict = None, https: bool = False):

    mc = Boto3_Client(endpoint, token, temp_credentials, https)
    await mc.init_connection()

    return mc


class Boto3_Client:
    """
    Summary:
        The object client for minio operation. This class is based on
        the keycloak token to make the operations, including:
            - download object
            - presigned-download-url
            - copy object
            - presigned-upload-url
            - part upload
            - combine parts on server side
    """

    def __init__(self, endpoint: str, token: str = None, temp_credentials: dict = None, https: bool = False) -> None:
        """
        Parameter:
            - endpoint(string): the endpoint of minio(no http schema)
            - token(str): the user token from SSO
            - https(bool): the bool to indicate if it is https connection
        """

        self.endpoint = ('https://' if https else 'http://') + endpoint
        self.token = token
        self.temp_credentials = temp_credentials

        self._config = Config(signature_version=_SIGNATURE_VERSTION)
        self._session = None

    async def init_connection(self):
        """
        Summary:
            The async function to setup connection session to minio.

        return:
            - None
        """

        # if we receive token by first time
        # ask minio to give the temperary credentials
        if self.token is not None:
            self.temp_credentials = await self._get_sts(self.token)

        self._session = aioboto3.Session(
            aws_access_key_id=self.temp_credentials.get('AccessKeyId'),
            aws_secret_access_key=self.temp_credentials.get('SecretAccessKey'),
            aws_session_token=self.temp_credentials.get('SessionToken'),
        )

        return

    async def _get_sts(self, access_token: str, duration: int = 86000) -> dict:
        """
        Summary:
            The function will use the token given to minio and
            get a temporary credential:
                - AccessKeyId
                - SecretAccessKey
                - SessionToken

        Parameter:
            - access_token(str): The token get from SSO
            - duration(int): how long the temporary credential
                will expire

        return:
            - dict
        """

        try:
            async with httpx.AsyncClient() as client:
                result = await client.post(
                    self.endpoint,
                    params={
                        'Action': 'AssumeRoleWithWebIdentity',
                        'WebIdentityToken': access_token.replace('Bearer ', ''),
                        'Version': '2011-06-15',
                        'DurationSeconds': duration,
                    },
                )

                if result.status_code == 400:
                    raise TokenExpired('Token expired')

        except Exception as e:
            raise e

        # TODO add the secret
        sts_info = (
            xmltodict.parse(result.text)
            .get('AssumeRoleWithWebIdentityResponse', {})
            .get('AssumeRoleWithWebIdentityResult', {})
            .get('Credentials', {})
        )

        return sts_info

    async def downlaod_object(self, bucket: str, key: str, local_path: str) -> None:
        """
        Summary:
            The function is the boto3 wrapup to download the file from minio

        Parameter:
            - bucket(str): the bucket name
            - key(str): the object path of file
            - local_path(str): the local path to download the file

        return:
            - None
        """

        async with self._session.client('s3', endpoint_url=self.endpoint, config=self._config) as s3:
            await s3.download_file(bucket, key, local_path)

    async def copy_object(self, bucket: str, source: str, destination: str):
        """
        Summary:
            The function is the boto3 wrapup to copy the file on server side.
            Note here the single copy will only allow the upto 5GB

        Parameter:
            - bucket(str): the bucket name
            - key(str): the object path of file
            - local_path(str): the local path to download the file

        return:
            - None
        """

        async with self._session.client('s3', endpoint_url=self.endpoint, config=self._config) as s3:
            await s3.copy_object(Bucket=bucket, CopySource=source, Key=destination)

    async def get_download_presigned_url(self, bucket: str, key: str, duration: int = 3600) -> str:
        """
        Summary:
            The function is the boto3 wrapup to generate a download presigned url.
            The user can directly download the file by open the url

        Parameter:
            - bucket(str): the bucket name
            - key(str): the object path of file
            - duration(int): how long the link will expire

        return:
            - presigned url(str)
        """

        async with self._session.client('s3', endpoint_url=self.endpoint, config=self._config) as s3:
            presigned_url = await s3.generate_presigned_url(
                'get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=duration
            )

        return presigned_url

    async def prepare_multipart_upload(self, bucket: str, keys: str) -> str:
        """
        Summary:
            The function is the boto3 wrapup to generate a multipart upload presigned url.
            This is the first step to do the multipart upload.

            NOTE: The api has been changed to adapot the batch operation. The prepare
            upload api is a batch operation to create all jobs and lock in advance. If
            not, the performance will decrease that every iteration will try to connect
            with endpoints

        Parameter:
            - bucket(str): the bucket name
            - keys(list of str): the object path of file

        return:
            - upload_id(list): list of upload id will be used in later two apis
        """

        upload_id_list = []
        async with self._session.client('s3', endpoint_url=self.endpoint, config=self._config) as s3:
            for key in keys:
                res = await s3.create_multipart_upload(Bucket=bucket, Key=key)
                upload_id_list.append(res.get('UploadId'))

        return upload_id_list

    async def part_upload(self, bucket: str, key: str, upload_id: str, part_number: int, content: str) -> dict:
        """
        Summary:
            The function is the boto3 wrapup to upload a SINGLE part.
            This is the second step to do the multipart upload.

        Parameter:
            - bucket(str): the bucket name
            - key(str): the object path of file
            - upload_id(str): the hash id generate from `prepare_multipart_upload` function
            - part_number(int): the part number of current chunk (which starts from 1)
            - content(str/byte): the file content

        return:
            - dict: will be collected and used in third step
        """

        async with self._session.client('s3', endpoint_url=self.endpoint, config=self._config) as s3:
            signed_url = await s3.generate_presigned_url(
                ClientMethod='upload_part',
                Params={'Bucket': bucket, 'Key': key, 'UploadId': upload_id, 'PartNumber': part_number},
            )

        async with httpx.AsyncClient() as client:
            res = await client.put(signed_url, data=content)

        etag = res.headers.get('ETag').replace("\"", '')

        return {'ETag': etag, 'PartNumber': part_number}

    async def combine_chunks(self, bucket: str, key: str, upload_id: str, parts: list) -> dict:
        """
        Summary:
            The function is the boto3 wrapup to combine parts on server side.
            This is the third step to do the multipart upload.

        Parameter:
            - bucket(str): the bucket name
            - key(str): the object path of file
            - upload_id(str): the hash id generate from `prepare_multipart_upload` function
            - parts(list): the list of {'ETag': <etag>, 'PartNumber': <part_number>} which
                collects from second step.

        return:
            - dict
        """

        async with self._session.client('s3', endpoint_url=self.endpoint, config=self._config) as s3:
            res = await s3.complete_multipart_upload(
                Bucket=bucket, Key=key, MultipartUpload={'Parts': parts}, UploadId=upload_id
            )

        return res
