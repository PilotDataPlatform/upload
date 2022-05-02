

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
                    raise HeaderMissingException("%s is required" % header)

            return await func(*arg, **kwargs)

        return inner
    return decorator
