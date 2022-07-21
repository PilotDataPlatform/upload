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
from functools import wraps


class HeaderMissingException(Exception):
    pass


def header_enforcement(required_headers: list):
    """
    Summary:
        The decorator is to check if the required headers present in the
        http request. Raise the exception if not exist
    Parameter:
        - required_headers(list): the required header value to be checked
    Return:
        - decorator function
    """

    def decorator(func):
        @wraps(func)
        async def inner(*arg, **kwargs):

            # loop over the header to enforce them
            for header in required_headers:
                if not kwargs.get(header):
                    raise HeaderMissingException('%s is required' % header)

            return await func(*arg, **kwargs)

        return inner

    return decorator
