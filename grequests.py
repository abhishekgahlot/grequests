# -*- coding: utf-8 -*-

"""
grequests
~~~~~~~~~

This module contains an asynchronous replica of ``requests.api``, powered
by gevent. All API methods return a ``Request`` instance (as opposed to
``Response``). A list of requests can be sent with ``map()``.
"""
from functools import partial

try:
    import gevent
    import greenlet
    from gevent import monkey
    from gevent.pool import Pool
except ImportError:
    raise RuntimeError('Gevent is required for grequests.')

# Monkey-patch.
monkey.patch_all(thread=False, select=False)

from requests import Session


__all__ = (
    'map', 'imap',
    'get', 'options', 'head', 'post', 'put', 'patch', 'delete', 'request'
)


def _greenlet_report_error(self, exc_info):
    import sys
    import traceback

    exception = exc_info[1]
    if isinstance(exception, gevent.greenlet.GreenletExit):
        self._report_result(exception)
        return
    exc_handler = False
    for lnk in self._links:
        if isinstance(lnk, gevent.greenlet.FailureSpawnedLink):
            exc_handler = True
            break
    if not exc_handler:
        try:
            traceback.print_exception(*exc_info)
        except:
            pass
    self._exception = exception
    if self._links and self._notifier is None:
        self._notifier = self.parent.loop.run_callback(self._notify_links)
    ## Only print errors
    if not exc_handler:
        info = str(self) + ' failed with '
        try:
            info += self._exception.__class__.__name__
        except Exception:
            info += str(self._exception) or repr(self._exception)
        sys.stderr.write(info + '\n\n')


## Patch the greenlet error reporting
gevent.greenlet.Greenlet._report_error = _greenlet_report_error


class AsyncRequest(object):
    """ Asynchronous request.

    Accept same parameters as ``Session.request`` and some additional:

    :param session: Session which will do request
    :param callback: Callback called on response.
                     Same as passing ``hooks={'response': callback}``
    """
    def __init__(self, method, url, **kwargs):
        #: Request method
        self.method = method
        #: URL to request
        self.url = url
        #: Associated ``Session``
        self.session = kwargs.pop('session', None)
        if self.session is None:
            self.session = Session()

        callback = kwargs.pop('callback', None)
        if callback:
            kwargs['hooks'] = {'response': callback}

        #: The rest arguments for ``Session.request``
        self.kwargs = kwargs
        #: Resulting ``Response``
        self.response = None

    def send(self, **kwargs):
        """
        Prepares request based on parameter passed to constructor and optional ``kwargs```.
        Then sends request and saves response to :attr:`response`

        :returns: ``Response``
        """
        merged_kwargs = {}
        merged_kwargs.update(self.kwargs)
        merged_kwargs.update(kwargs)
        self.response =  self.session.request(self.method,
                                              self.url, **merged_kwargs)
        return self.response


def send(r, pool=None, stream=False, exception_handler=None):
    """Sends the request object using the specified pool. If a pool isn't
    specified this method blocks. Pools are useful because you can specify size
    and can hence limit concurrency."""
    if pool != None:
        p = pool.spawn
    else:
        p = gevent.spawn

    if exception_handler:
        glet = p(r.send, stream=stream)

        def eh_wrapper(g):
            return exception_handler(r,g.exception)

        glet.link_exception(eh_wrapper)
    else:
        glet = p(r.send, stream=stream)

    return glet

# Shortcuts for creating AsyncRequest with appropriate HTTP method
get = partial(AsyncRequest, 'GET')
options = partial(AsyncRequest, 'OPTIONS')
head = partial(AsyncRequest, 'HEAD')
post = partial(AsyncRequest, 'POST')
put = partial(AsyncRequest, 'PUT')
patch = partial(AsyncRequest, 'PATCH')
delete = partial(AsyncRequest, 'DELETE')

# synonym
def request(method, url, **kwargs):
    return AsyncRequest(method, url, **kwargs)


def map(requests, stream=False, size=None, exception_handler=None):
    """Concurrently converts a list of Requests to Responses.

    :param requests: a collection of Request objects.
    :param stream: If True, the content will not be downloaded immediately.
    :param size: Specifies the number of requests to make at a time. If None, no throttling occurs.
    """

    requests = list(requests)

    pool = Pool(size) if size else None
    jobs = [send(r, pool, stream=stream, exception_handler=exception_handler) for r in requests]
    gevent.joinall(jobs)

    return [r.response for r in requests]


def imap(requests, stream=False, size=2, exception_handler=None):
    """Concurrently converts a generator object of Requests to
    a generator of Responses.

    :param requests: a generator of Request objects.
    :param stream: If True, the content will not be downloaded immediately.
    :param size: Specifies the number of requests to make at a time. default is 2
    """

    pool = Pool(size)

    def send(r):
        return r.send(stream=stream, exception_handler=exception_handler)

    for r in pool.imap_unordered(send, requests):
        yield r

    pool.join()
