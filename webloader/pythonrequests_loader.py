import os
import logging
import traceback
import subprocess
import requests
from collections import defaultdict
from loader import Loader, LoadResult, Timeout, TimeoutError


class PythonRequestsLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using Python requests.
    
    .. note:: The :class:`PythonRequestLoader` currently does not support HTTP2.
    .. note:: The :class:`PythonRequestLoader` currently does not support caching.
    .. note:: The :class:`PythonRequestsLoader` currently does not support full page loading (i.e., fetching a page's subresources).
    '''

    def __init__(self, **kwargs):
        super(PythonRequestsLoader, self).__init__(**kwargs)
        if self._http2:
            raise NotImplementedError('PythonRequestsLoader does not support HTTP2')
        if not self._disable_cache:
            raise NotImplementedError('PythonRequestsLoader does not support caching')
        if self._full_page:
            raise NotImplementedError('PythonRequestsLoader does not support loading full pages.')


    def _load_page(self, url, outdir):
    
        # load the specified URL
        logging.info('Loading page: %s', url)
        try:
            # Load the page
            with Timeout(seconds=self._timeout+5):
                response = requests.get(url, timeout=self._timeout)
    
            # received response; may not have been successful
            if response.status_code != 200:
                return LoadResult(LoadResultFAILURE_NO_200, url)
            else:
                return LoadResult(LoadResult.SUCCESS,
                    url,
                    final_url=response.url,
                    time=response.elapsed.total_seconds(),
                    size=len(response.content))

        # problem executing request
        except (TimeoutError, requests.exceptions.Timeout):
            logging.exception('Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except Exception as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
