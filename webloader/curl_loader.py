import os
import logging
import traceback
import subprocess
import string
from collections import defaultdict
from loader import Loader, LoadResult, Timeout, TimeoutError

CURL = '/usr/bin/env curl'

# TODO: user agent

class CurlLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using curl.
    
    .. note:: The :class:`CurlLoader` currently does not support HTTP2.
    .. note:: The :class:`CurlLoader` currently does not support caching.
    .. note:: The :class:`CurlLoader` currently does not support full page loading (i.e., fetching a page's subresources).
    .. note:: The :class:`CurlLoader` currently does not support custom user agents.
    '''

    def __init__(self, **kwargs):
        super(CurlLoader, self).__init__(**kwargs)
        if self._http2:
            raise NotImplementedError('CurlLoader does not support HTTP2')
        if not self._disable_cache:
            raise NotImplementedError('CurlLoader does not support caching')
        if self._full_page:
            raise NotImplementedError('CurlLoader does not support loading a full page')
        if self._user_agent:
            raise NotImplementedError('CurlLoader does not support custom user agents')
        
        self._image_paths_by_url = defaultdict(list)


    def _load_page(self, url, outdir):
    
        # load the specified URL
        logging.info('Loading page: %s', url)
        try:
            # prepare the curl command
            curl_cmd = CURL
            curl_cmd += ' -s -S'  # don't show progress meter
            curl_cmd += ' -L'  # follow redirects
            curl_cmd += ' -o /dev/null'  # don't print file to stdout
            curl_cmd += ' -w http_code=%{http_code};final_url=%{url_effective};time=%{time_total};size=%{size_download}'   # format for stats at end
            curl_cmd += ' --connect-timeout %i' % self._timeout  # TCP connect timeout
            curl_cmd += ' %s' % url

            # load the page
            logging.debug('Running curl: %s', curl_cmd)
            with Timeout(seconds=self._timeout+5):
                output = subprocess.check_output(curl_cmd.split())
                logging.debug('curl returned: %s', output.strip())

            # curl returned, but may or may not have succeeded
            returnvals = {field.split('=')[0]: field.split('=')[1] for field in output.split('\n')[-1].split(';')}

            if returnvals['http_code'] != '200':
                return LoadResult(LoadResult.FAILURE_NO_200, url)
            else:
                # Report status and time
                return LoadResult(LoadResult.SUCCESS,
                    url,
                    final_url=returnvals['final_url'],
                    time=float(string.replace(returnvals['time'], ',', '.')),
                    size=returnvals['size'])

        # problem running curl
        except TimeoutError:
            logging.exception('Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, e.output))
            if e.returncode == 28:
                return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
            else:
                return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)