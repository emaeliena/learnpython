# https://jsfiddle.net/h12mj7r6/
import logging
import datetime
import functools

import gevent
from gevent import monkey
from gevent.lock import BoundedSemaphore
from gevent import Timeout
import requests


logging.basicConfig(level=logging.DEBUG)


CHUNK_SIZE = 100
TIMEOUT = 180
SITES_NUM = 200


URLS = ['http://example.com/{}'.format(i) for i in range(SITES_NUM)]

monkey.patch_socket()
monkey.patch_ssl()


class Timers(object):

    def __init__(self):
        self.logs = list()

    def log(self, name, start, stop):
        self.logs.append((name, start, stop))

    def summary(self):
        return sorted(self.logs, key=lambda x: x[1]) + [('total', self.min(), self.max())]

    def _total(self):
        for log in self.logs:
            for item in log[1:]:
                yield item

    def total_diff(self):
        return self.max() - self.min()

    def min(self):
        return min(self._total())

    def max(self):
        return max(self._total())


def timeit(fn):
    fn.timers = Timers()

    @functools.wraps(fn)
    def decorator(*args, **kwargs):
        name = ' '.join(args)
        start = datetime.datetime.now()
        result = fn(*args, **kwargs)
        stop = datetime.datetime.now()
        fn.timers.log(name, start, stop)
        return result

    return decorator


def context_semaphore(original_function=None, limit=10):
    bounded_semaphore = BoundedSemaphore(limit)

    def _decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with bounded_semaphore:
                result = fn(*args, **kwargs)
            return result
        return wrapper

    if original_function:
        return _decorate(original_function)
    return _decorate


results = list()


@context_semaphore(limit=CHUNK_SIZE)
@timeit
def download(url):
    """download"""
    response = requests.get(url)
    results.append((url, len(response.text)))


def js_date(date):
    return 'new Date({}, {}, {}, {}, {}, {}, {})'.format(
        date.year, date.month, date.day, date.hour, date.minute, date.second, date.microsecond/1000)


def js_template(key, start, stop):
    return "[ '{}', {}, {} ]".format(key, js_date(start), js_date(stop))


# pool = Pool(CHUNK_SIZE)
tasks = list()
for url in URLS:
    tasks.append(gevent.spawn(download, url))

with Timeout(TIMEOUT):
    gevent.joinall(tasks)

print "{} jobs done".format(len(results)), [item for item in results]

print 'total time: ', download.timers.total_diff()
print ', '.join([js_template(*item) for item in download.timers.summary()])
