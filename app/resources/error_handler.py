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

import enum
from functools import wraps

from common import LoggerFactory
from fastapi import HTTPException

from app.models.base_models import APIResponse
from app.models.base_models import EAPIResponseCode
from app.resources.decorator import HeaderMissingException

_logger = LoggerFactory('internal_error').get_logger()


def catch_internal(api_namespace: str):

    """
    Summary:
        The decorator is to to catch internal server error.
    Parameter:
        - api_namespace(str): the namespace of api
    Return:
        - decorator function
    """

    def decorator(func):
        @wraps(func)
        async def inner(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException as exce:
                respon = APIResponse()
                respon.code = EAPIResponseCode.internal_error
                err = api_namespace + ' ' + exce.detail
                err_msg = customized_error_template(ECustomizedError.INTERNAL) % err
                _logger.error(err_msg)
                respon.error_msg = err_msg
                return respon.json_response()

            # this error will be raised by header_enforcement decorator
            # currently it will check if the require header contains the
            # `session_id` header
            except HeaderMissingException as e:
                respon = APIResponse()
                respon.code = EAPIResponseCode.bad_request
                err_msg = str(e)
                _logger.error(err_msg)
                respon.error_msg = err_msg
                return respon.json_response()

            except Exception as exce:
                respon = APIResponse()
                respon.code = EAPIResponseCode.internal_error
                err = api_namespace + ' ' + str(exce)
                err_msg = customized_error_template(ECustomizedError.INTERNAL) % err
                _logger.error(err_msg)
                respon.error_msg = err_msg
                return respon.json_response()

        return inner

    return decorator


class ECustomizedError(enum.Enum):
    """Enum of customized errors."""

    FILE_NOT_FOUND = 'FILE_NOT_FOUND'
    INVALID_FILE_AMOUNT = 'INVALID_FILE_AMOUNT'
    JOB_NOT_FOUND = 'JOB_NOT_FOUND'
    FORGED_TOKEN = 'FORGED_TOKEN'
    TOKEN_EXPIRED = 'TOKEN_EXPIRED'
    INVALID_TOKEN = 'INVALID_TOKEN'
    INTERNAL = 'INTERNAL'
    INVALID_DATATYPE = 'INVALID_DATATYPE'
    INVALID_FOLDERNAME = 'INVALID_FOLDERNAME'
    INVALID_FILENAME = 'INVALID_FILENAME'
    INVALID_FOLDER_NAME_TYPE = 'INVALID_FOLDER_NAME_TYPE'


def customized_error_template(customized_error: ECustomizedError):
    """get error template."""
    return {
        'FILE_NOT_FOUND': '[File not found] %s.',
        'INVALID_FILE_AMOUNT': '[Invalid file amount] must greater than 0',
        'JOB_NOT_FOUND': '[Invalid Job ID] Not Found',
        'FORGED_TOKEN': '[Invalid Token] System detected forged token, \
                    a report has been submitted.',
        'TOKEN_EXPIRED': '[Invalid Token] Already expired.',
        'INVALID_TOKEN': '[Invalid Token] %s',
        'INTERNAL': '[Internal] %s',
        'INVALID_DATATYPE': '[Invalid DataType]: %s',
        'INVALID_FOLDERNAME': '[Invalid Folder] Folder Name has already taken by other resources(file/folder)',
        'INVALID_FILENAME': '[Invalid File] File Name has already taken by other resources(file/folder)',
        'INVALID_FOLDER_NAME_TYPE': (
            'Folder name should not contain : ',
            '(\\/:?*<>|”\') and must contain 1 to 20 characters',
        ),
    }.get(customized_error.name, 'Unknown Error')
