import os
import logging
import traceback
import subprocess
import httplib
from collections import defaultdict
from loader import Loader, LoadResult, Timeout, TimeoutError

ENV = '/usr/bin/env'
ZombieJS = 'node'
ZombieLOADER = '/home/b.kyle/github/node-http2/example/pageloader_client.js'

# TODO: when do we return FAILURE_NO_200?
# TODO: enable caching
# TODO: user agent
# TODO: disable network cache

class ZombieJSLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using ZombieJS.
    
    .. note:: The :class:`ZombieJSLoader` currently does not support local caching.
    .. note:: The :class:`ZombieJSLoader` currently does not support disabling network caching.
    .. note:: The :class:`ZombieJSLoader` currently does not support single-object loading (i.e., it always loads the full page).
    '''

    def __init__(self, **kwargs):
        super(ZombieJSLoader, self).__init__(**kwargs)
        if not self._http2:
            raise NotImplementedError('ZombieJSLoader does not support HTTP1.1')
        if not self._disable_local_cache:
            raise NotImplementedError('ZombieJSLoader does not support local caching')
        if not self._full_page:
            raise NotImplementedError('ZombieJSLoader does not support loading only an object')
        if self._disable_network_cache:
            raise NotImplementedError('ZombieJSLoader does not support disabling network caches.')        

    def _load_page(self, url, outdir, trial_num=-1):    
        # load the specified URL
        logging.info('Loading page: %s', url)
        try:	    
	    # Cause a restart of the proxy
	    #if self._proxy:
	    #	conn = httplib.HTTPConnection(self._proxy.split(':')[0]+':5678') # Assume restart always listens on this port for now
	    #	conn.request("GET", "/")
	    #	resp = conn.getresponse() # Don't need to do anything with it. Just want to know that the request was acknowledge

            # Load the page
            Zombie_cmd = [ENV, ZombieJS, ZombieLOADER, url, str(self._timeout)]
	    if self._proxy:
		Zombie_cmd.append('-p')
                Zombie_cmd.append(self._proxy)

            logging.debug('Running ZombieJS: %s', Zombie_cmd)
            #with Timeout(seconds=self._timeout+5): The process should always end
            output = subprocess.check_output(Zombie_cmd)

            return LoadResult(LoadResult.SUCCESS, url, raw=output)

        # problem running ZombieJS
        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s\n%s' % (url, e, e.output, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
