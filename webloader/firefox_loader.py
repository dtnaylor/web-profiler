import os
import sys
import shutil
import subprocess
import logging
import tempfile
from time import sleep
from loader import Loader, LoadResult, Timeout, TimeoutError
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0

FIREFOX = '/usr/bin/env firefox'
XVFB = '/usr/bin/env Xvfb'
DISPLAY = ':99'

TIMINGS_JAVASCRIPT = '''
var performance = window.performance || {};
var timings = performance.timing || {};
return timings;
'''


class FirefoxLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using Firefox.

    .. note:: The :class:`FirefoxLoader` currently does not extract HARs.
    .. note:: The :class:`FirefoxLoader` currently does not save screenshots.
    '''

    def __init__(self, **kwargs):
        super(FirefoxLoader, self).__init__(**kwargs)
        self._xvfb_proc = None
        self._firefox_proc = None
        self._profile_name = 'webloader'
        self._profile_path = os.path.join(tempfile.gettempdir(),\
            'webloader_profile')
        self._selenium_driver = None

    def _load_page(self, url, outdir):
        # path for new HAR file
        safeurl = self._sanitize_url(url)
        filename = '%s.har' % (safeurl)
        harpath = os.path.join(outdir, filename)
        logging.debug('Will save HAR to %s', harpath)
    
    
        # load the specified URL (with selenium)
        logging.info('Fetching page %s', url)
        try:
            # load page
            with Timeout(seconds=self._timeout+5):
                self._selenium_driver.get(url)
                WebDriverWait(self._selenium_driver, self._timeout).until(\
                    lambda d: d.execute_script('return document.readyState') == 'complete')
                logging.debug('Page loaded.')

            # get timing information
            # http://www.w3.org/TR/navigation-timing/#processing-model
            timings = self._selenium_driver.execute_script(TIMINGS_JAVASCRIPT)
            load_time = (timings['loadEventEnd'] - timings['fetchStart']) / 1000.0

            return LoadResult(LoadResult.SUCCESS, url, time=load_time,\
                final_url=self._selenium_driver.current_url)

        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except TimeoutException:
            logging.exception('Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except Exception as e:
            logging.exception('Error loading %s: %s' % (url, e))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
    
        ## load the specified URL (directly)
        #logging.info('Fetching page %s', url)
        #try:
        #    firefox_cmd =  '%s %s' % (FIREFOX, url)
        #    logging.debug('Loading: %s', firefox_cmd)
        #    with Timeout(seconds=self._timeout+5):
        #        subprocess.check_output(firefox_cmd.split())
        #
        #except TimeoutError:
        #    logging.exception('* Timeout fetching %s', url)
        #    return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        #except subprocess.CalledProcessError as e:
        #    logging.exception('Error loading %s: %s\n%s' % (url, e, e.output, ))
        #    return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        #except Exception as e:
        #    logging.exception('Error loading %s: %s' % (url, e))
        #    return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        #logging.debug('Page loaded.')


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
        logging.debug('Started XVFB (DISPLAY=%s)', os.environ['DISPLAY'])

        ## make firefox profile and set preferences
        #try:
        #    # create profile
        #    create_cmd = '%s -CreateProfile "%s %s"'\
        #        % (FIREFOX, self._profile_name, self._profile_path)
        #    logging.debug('Creating Firefox profile: %s' % create_cmd)
        #    subprocess.check_output(create_cmd, shell=True)

        #    # write prefs to user.js
        #    userjs_path = os.path.join(self._profile_path, 'user.js')
        #    logging.debug('Writing user.js: %s' % userjs_path)
        #    with open(userjs_path, 'w') as f:
        #        if self._disable_cache:
        #            f.write('user_pref("browser.cache.disk.enable", false);\n')
        #            f.write('user_pref("browser.cache.memory.enable", false);\n')
        #        # TODO: enable HTTP2
        #    f.closed
        #except Exception as e:
        #    logging.exception("Error creating Firefox profile")
        #    return False
    
        ## launch firefox
        #try:
        #    firefox_command =  '%s -profile %s' % (FIREFOX, self._profile_path)
        #    logging.debug('Starting Firefox: %s', firefox_command)
        #    self._firefox_proc = subprocess.Popen(firefox_command.split())
        #    sleep(5)
        #except Exception as e:
        #    logging.exception("Error starting Firefox")
        #    return False
        #logging.debug('Started Firefox')
        
        # prepare firefox selenium driver
        try:
            profile = webdriver.FirefoxProfile()
            if self._disable_cache:
                profile.set_preference("browser.cache.disk.enable", False)
                profile.set_preference("browser.cache.memory.enable", False)
            # TODO: enable HTTP2
            self._selenium_driver = webdriver.Firefox(firefox_profile=profile)
        except Exception as e:
            logging.exception("Error making selenium driver")
            return False
        return True


    def _teardown(self):
        if self._selenium_driver:
            self._selenium_driver.quit()
        if self._firefox_proc:
            logging.debug('Stopping Firefox')
            self._firefox_proc.kill()
            self._firefox_proc.wait()
        if self._xvfb_proc:
            logging.debug('Stopping XVFB')
            self._xvfb_proc.kill()
            self._xvfb_proc.wait()

        ## remove the firefox profile
        #try:
        #    shutil.rmtree(self._profile_path)
        #except Exception as e:
        #    logging.exception('Error removing firefox profile: %s' % e)
