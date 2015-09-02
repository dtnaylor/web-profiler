import os
import logging
import traceback
import subprocess
import requests
from collections import defaultdict
from loader import Loader, LoadResult, Timeout, TimeoutError

#TODO: disable network cache

class PythonRequestsLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using Python requests.
    
    .. note:: The :class:`PythonRequestsLoader` currently does not support HTTP2.
    .. note:: The :class:`PythonRequestsLoader` currently does not support local caching.
    .. note:: The :class:`PythonRequestsLoader` currently does not support disabling network caching.
    .. note:: The :class:`PythonRequestsLoader` currently does not support full page loading (i.e., fetching a page's subresources).
    .. note:: The :class:`PythonRequestsLoader` currently does not support saving HARs.
    .. note:: The :class:`PythonRequestsLoader` currently does not support saving screenshots.
    '''

    def __init__(self, **kwargs):
        super(PythonRequestsLoader, self).__init__(**kwargs)
        if self._http2:
            raise NotImplementedError('PythonRequestsLoader does not support HTTP2')
        if not self._disable_local_cache:
            raise NotImplementedError('PythonRequestsLoader does not support local caching')
        if self._disable_network_cache:
            raise NotImplementedError('PythonRequestsLoader does not support disabling network caching.')
        if self._full_page:
            raise NotImplementedError('PythonRequestsLoader does not support loading full pages.')
        if self._save_har:
            raise NotImplementedError('PythonRequestsLoader does not support saving HARs.')
        if self._save_screenshot:
            raise NotImplementedError('PythonRequestsLoader does not support saving screenshots.')
        if self._delay_after_onload != 0:
            raise NotImplementedError('PyhtonRequestsLoader does not support delay after onload')


    def _load_page(self, url, outdir, trial_num=-1):
    
        # load the specified URL
        logging.info('Loading page: %s', url)
        try:
            # Load the page
            with Timeout(seconds=self._timeout+5):
                headers = {}
                if self._user_agent:
                    headers['User-Agent'] = self._user_agent
                response = requests.get(url, timeout=self._timeout, headers=headers)
    
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
