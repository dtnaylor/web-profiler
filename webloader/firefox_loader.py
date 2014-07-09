import os
import sys
import subprocess
import traceback
import logging
from time import sleep
from loader import Loader, LoadResult, Timeout, TimeoutError

XVFB = '/usr/bin/env Xvfb'
DISPLAY = ':99'


class FirefoxLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using Firefox.'''

    def __init__(self, **kwargs):
        super(FirefoxLoader, self).__init__(**kwargs)
        self._xvfb_proc = None
        self._firefox_proc = None

    def _load_page(self, url, outdir):
        # path for new HAR file
        safeurl = self._sanitize_url(url)
        filename = '%s.har' % (safeurl)
        harpath = os.path.join(outdir, filename)
        logging.debug('Will save HAR to %s', harpath)
    
        # load the specified URL
        logging.info('Fetching page %s', url)
        try:
            firefox_cmd =  # TODO
            logging.debug('Loading: %s', firefox_cmd)
            with Timeout(seconds=self._timeout+5):
                subprocess.check_output(firefox_cmd.split())
        
        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s\n%s' % (url, e, e.output, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        logging.getLogger(__name__).debug('Page loaded.')
    
        return LoadResult(LoadResult.SUCCESS, url, har=harpath)


    def _setup(self):
        # start a virtual display
        try:
            os.environ['DISPLAY'] = DISPLAY
            xvfb_command = '%s %s -screen 0 1366x768x24 -ac' % (XVFB, DISPLAY)
            logging.debug('Starting XVFB: %s', xvfb_command)
            self._xvfb_proc = subprocess.Popen(xvfb_command.split())
            sleep(2)
        except Exception as e:
            logging.exception("Error starting XFVB")
            return False
        logging.getLogger(__name__).debug('Started XVFB (DISPLAY=%s)', os.environ['DISPLAY'])
    
        # launch firefox with no cache
        try:
            # TODO: enable HTTP2
            firefox_command =  # TODO
            logging.debug('Starting Chrome: %s', firefox_command)
            self._firefox_proc = subprocess.Popen(firefox_command.split())
            sleep(5)
        except Exception as e:
            logging.exception("Error starting Firefox")
            return False
        logging.getLogger(__name__).debug('Started Firefox')
        return True


    def _teardown(self):
        if self._firefox_proc:
            logging.debug('Stopping Firefox')
            self._firefox_proc.kill()
            self._firefox_proc.wait()
        if self._xvfb_proc:
            logging.debug('Stopping XVFB')
            self._xvfb_proc.kill()
            self._xvfb_proc.wait()
