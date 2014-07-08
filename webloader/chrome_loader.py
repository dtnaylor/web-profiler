import os
import sys
import subprocess
import traceback
import logging
from time import sleep
from loader import Loader
from loader import Loader, LoadResult, Timeout, TimeoutError

CHROME = '/usr/bin/env google-chrome'
CHROME_HAR_CAPTURER = '/usr/bin/env chrome-har-capturer'
XVFB = '/usr/bin/env Xvfb'
DISPLAY = ':99'

# TODO: document chrome-har-capturer
# TODO: test if isntalled chrome can support HTTP2
# TODO: pick different display if multiple instances are used at once
# TODO: get load time
# TODO: screenshot?
# TODO: final URL?
# TODO: pass timeout to chrome?

class ChromeLoader(Loader):
    def __init__(self, **kwargs):
        super(ChromeLoader, self).__init__(**kwargs)
        self._xvfb_proc = None
        self._chrome_proc = None

    def _load_page(self, url, outdir):
        # path for new HAR file
        safeurl = self._sanitize_url(url)
        filename = '%s.har' % (safeurl)
        harpath = os.path.join(outdir, filename)
        logging.debug('Will save HAR to %s', harpath)
    
        # load the specified URL
        logging.info('Fetching page %s', url)
        try:
            capturer_cmd = '%s -o %s %s' % (CHROME_HAR_CAPTURER, harpath, url)
            logging.debug('Running capturer: %s', capturer_cmd)
            with Timeout(seconds=self._timeout+5):
                subprocess.check_output(capturer_cmd.split())
        
        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(Loader.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s\n%s' % (url, e, e.output, traceback.format_exc()))
            return LoadResult(Loader.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, traceback.format_exc()))
            return LoadResult(Loader.FAILURE_UNKNOWN, url)
        logging.getLogger(__name__).debug('Page loaded.')
    
        return LoadResult(Loader.SUCCESS, url, har=harpath)


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
    
        # launch chrome with no cache and remote debug on
        chrome_proc = None
        try:
            # TODO: enable HTTP2
            cache_options = '--disable-application-cache --disable-cache'
            har_options = '--remote-debugging-port=9222 --enable-benchmarking --enable-net-benchmarking'
            chrome_command = '%s %s %s' % (CHROME, cache_options, har_options)
            logging.debug('Starting Chrome: %s', chrome_command)
            self._chrome_proc = subprocess.Popen(chrome_command.split())
            sleep(5)
        except Exception as e:
            logging.exception("Error starting Chrome")
            return False
        logging.getLogger(__name__).debug('Started Chrome')
        return True


    def _teardown(self):
        if self._chrome_proc:
            logging.debug('Stopping Chrome')
            self._chrome_proc.kill()
            self._chrome_proc.wait()
        if self._xvfb_proc:
            logging.debug('Stopping XVFB')
            self._xvfb_proc.kill()
            self._xvfb_proc.wait()