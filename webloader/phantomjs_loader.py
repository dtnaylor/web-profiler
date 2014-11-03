import os
import logging
import traceback
import subprocess
from collections import defaultdict
from loader import Loader, LoadResult, Timeout, TimeoutError

PHANTOMJS = '/usr/bin/env phantomjs'
PHANTOMLOADER = os.path.join(os.path.dirname(__file__), 'phantomloader.js')

# TODO: when do we return FAILURE_NO_200?
# TODO: enable caching
# TODO: user agent
# TODO: disable network cache

class PhantomJSLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using PhantomJS.
    
    .. note:: The :class:`PhantomJSLoader` currently does not support HTTP2.
    .. note:: The :class:`PhantomJSLoader` currently does not support local caching.
    .. note:: The :class:`PhantomJSLoader` currently does not support disabling network caching.
    .. note:: The :class:`PhantomJSLoader` currently does not support single-object loading (i.e., it always loads the full page).
    '''

    def __init__(self, **kwargs):
        super(PhantomJSLoader, self).__init__(**kwargs)
        if self._http2:
            raise NotImplementedError('PhantomJSLoader does not support HTTP2')
        if not self._disable_local_cache:
            raise NotImplementedError('PhantomJSLoader does not support local caching')
        if not self._full_page:
            raise NotImplementedError('PhantomJSLoader does not support loading only an object')
        if self._disable_network_cache:
            raise NotImplementedError('PhantomJSLoader does not support disabling network caches.')
        
        self._image_paths_by_url = defaultdict(list)


    def _load_page(self, url, outdir, trial_num=-1):
        # path for new HAR file
        safeurl = self._sanitize_url(url)
        filename = '%s_trial%d.har' % (safeurl, trial_num)
        imagename = '%s_trial%d.png' % (safeurl, trial_num)

        harpath = os.path.join(outdir, filename)
        if self._save_har:
            logging.debug('Will save HAR to %s', harpath)

        if self._save_screenshot:
            imagepath = os.path.join(outdir, imagename)
            logging.debug('Will save screenshot to %s', imagepath)
        else:
            imagepath = '/dev/null'

    
        # load the specified URL
        logging.info('Loading page: %s', url)
        try:
            # Load the page
            phantom_cmd = '%s --ssl-protocol=any %s %s %s %d' %\
                (PHANTOMJS, PHANTOMLOADER, url, imagepath, self._timeout)
            phantom_cmd = phantom_cmd.split()
            if self._user_agent:
                phantom_cmd.append(' "%s"' % self._user_agent)

            logging.debug('Running PhantomJS: %s', phantom_cmd)
            with Timeout(seconds=self._timeout+5):
                output = subprocess.check_output(phantom_cmd)
                har, statusline = output.split('*=*=*=*')
                logging.debug('loadspeed.js returned: %s', statusline.strip())

            # PhantomJS returned, but may or may not have succeeded
            fields = statusline.strip().split(':')
            status = fields[0]
            message = ':'.join(fields[1:])

            if status == 'FAILURE':
                if message == 'timeout':
                    logging.error('Timeout fetching %s', url)
                    return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
                else:
                    logging.error('Error fetching %s: %s', url, message)
                    return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
            elif status == 'SUCCESS':
                # Save the HAR
                if self._save_har:
                    with open(harpath, 'w') as f:
                        f.write(har)
                    f.closed

                # Report status and time
                returnvals = {field.split('=')[0]: field.split('=')[1] for field in message.split(';')}
                return LoadResult(LoadResult.SUCCESS,
                    url,
                    final_url=returnvals['final_url'],
                    time=float(returnvals['time'])/1000.0,
                    har=harpath,
                    img=imagepath)
            else:
                logging.error('loadspeed.js returned unexpected output: %s', output)
                return LoadResult(LoadResult.FAILURE_UNKNOWN, url)

        # problem running PhantomJS
        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s\n%s' % (url, e, e.output, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
