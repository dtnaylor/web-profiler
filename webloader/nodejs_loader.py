import os
import logging
import traceback
import shlex
import subprocess
import string
from collections import defaultdict
from loader import Loader, LoadResult, Timeout, TimeoutError

NODE = '/usr/bin/env node'
NODEHTTP2 = 'node-http2/example/objloader_client.js' # Put your path here

class NodeJsLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using NODE.JS.
    
    .. note:: The :class:`NodeJsLoader` currently does not support caching.
    .. note:: The :class:`NodeJsLoader` currently does not support full page loading (i.e., fetching a page's subresources).
    .. note:: The :class:`NodeJsLoader` currently does not support disabling network caches.
    .. note:: The :class:`NodeJsLoader` currently does not support saving HARs.
    .. note:: The :class:`NodeJsLoader` currently does not support saving screenshots.
    '''

    def __init__(self, **kwargs):
        super(NodeJsLoader, self).__init__(**kwargs)
        if not self._http2:
            raise NotImplementedError('NodeJsLoader does not support HTTP1.1')
        if not self._disable_local_cache:
            raise NotImplementedError('NodeJsLoader does not support local caching')
        if self._full_page:
            raise NotImplementedError('NodeJsLoader does not support loading a full page')
        if self._disable_network_cache:
            raise NotImplementedError('NodeJsLoader does not support disabling network caches.')
        if self._save_har:
            raise NotImplementedError('NodeJsLoader does not support saving HARs.')
        if self._save_screenshot:
            raise NotImplementedError('NodeJsLoader does not support saving screenshots.')
        
        self._image_paths_by_url = defaultdict(list)


    def _load_page(self, url, outdir, trial_num=-1):
    
        # load the specified URL
        logging.info('Loading page: %s', url)
        try:
            # prepare the NODE command
            node_cmd = NODE+' '
            node_cmd += NODEHTTP2+' ' # Location of node.js client HTTP2 program
	    node_cmd += url

            # load the page
            logging.debug('Running node.js: %s', node_cmd)
            with Timeout(seconds=self._timeout+5):
                output = subprocess.check_output(shlex.split(node_cmd))
                logging.debug('NODE returned: %s', output.strip())

            # NODE returned, but may or may not have succeeded
            returnvals = {field.split('=')[0]: field.split('=')[1] for field in output.split(';')}

            if returnvals['http_code'] != '200':
                return LoadResult(LoadResult.FAILURE_NO_200, url)
            else:
                # Report status and time
                return LoadResult(LoadResult.SUCCESS,
                    url,
                    final_url=returnvals['final_url'],
                    time=float(string.replace(returnvals['time'], ',', '.')),
                    size=returnvals['size'])

        # problem running NODE
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
