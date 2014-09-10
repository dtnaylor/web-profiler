import os
import sys
import shutil
import subprocess
import logging
import tempfile
import platform
from time import sleep
from loader import Loader, LoadResult, Timeout, TimeoutError
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait # available since 2.4.0

FIREFOX = '/usr/bin/env firefox' if platform.system() != 'Darwin' else\
    '/Applications/Firefox.app/Contents/MacOS/firefox'
XVFB = '/usr/bin/env Xvfb'
DISPLAY = ':99'

TIMINGS_JAVASCRIPT = '''
var performance = window.performance || {};
var timings = performance.timing || {};
return timings;
'''

# TODO: send firefox output to separate log file
# TODO: disable network cache (send header)


class FirefoxLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using Firefox.

    .. note:: The :class:`FirefoxLoader` currently does not extract HARs.
    .. note:: The :class:`FirefoxLoader` currently does not save screenshots.
    .. note:: The :class:`FirefoxLoader` currently does not support single-object loading (i.e., it always loads the full page).
    .. note:: The :class:`FirefoxLoader` currently does not support disabling network caches.
    '''

    def __init__(self, selenium=True, **kwargs):
        super(FirefoxLoader, self).__init__(**kwargs)
        if not self._full_page:
            raise NotImplementedError('FirefoxLoader does not support loading only an object')
        if self._disable_network_cache:
            raise NotImplementedError('FirefoxLoader does not support disabling network caches.')

        self._selenium = selenium
        self._xvfb_proc = None
        self._firefox_proc = None
        self._profile_name = 'webloader'
        self._profile_path = os.path.join(tempfile.gettempdir(),\
            'webloader_profile')
        self._selenium_driver = None

    def _load_page_selenium(self, url, outdir):
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


    def _load_page_native(self, url, outdir):
        # load the specified URL (directly)
        logging.info('Fetching page %s', url)
        try:
            firefox_cmd =  '%s %s' % (FIREFOX, url)
            #firefox_cmd =  '%s -profile %s %s' % (FIREFOX, self._profile_path, url)
            logging.debug('Loading: %s', firefox_cmd)
            with Timeout(seconds=self._timeout+5):
                subprocess.check_output(firefox_cmd.split())

            # TODO: error checking
            # TODO: try to get timing info, final URL, HAR, etc.
            
            logging.debug('Page loaded.')
            return LoadResult(LoadResult.SUCCESS, url)
        
        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, e.output, ))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s' % (url, e))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)



    def _load_page(self, url, outdir):

        if self._selenium:
            return self._load_page_selenium(url, outdir)
        else:
            return self._load_page_native(url, outdir)
    
    
    



    def _setup_selenium(self):
        # prepare firefox selenium driver
        try:
            profile = webdriver.FirefoxProfile()
            if self._disable_local_cache:
                profile.set_preference("browser.cache.disk.enable", False)
                profile.set_preference("browser.cache.memory.enable", False)
            if self._http2:
                # As of v34, this is enabled by default anyway
                profile.set_preference("network.http.spdy.enabled.http2draft", True)
		# Attempt to always negotiate http/2.0
		profile.set_preference("network.http.proxy.version", "2.0")
		profile.set_preference("network.http.version", "2.0")
		# Disable validation when using our testing server (since we don't own a valid cert)
#		profile.set_preference("network.http.spdy.enforce-tls-profile", False)
            if self._user_agent:
                profile.set_preference("general.useragent.override", '"%s"' % self._user_agent)
            self._selenium_driver = webdriver.Firefox(firefox_profile=profile)
        except Exception as e:
            logging.exception("Error making selenium driver")
            return False
        return True



    def _setup_native(self):
        # make firefox profile and set preferences
        try:
            # create profile
            create_cmd = '%s -CreateProfile "%s %s"'\
                % (FIREFOX, self._profile_name, self._profile_path)
            logging.debug('Creating Firefox profile: %s' % create_cmd)
            subprocess.check_output(create_cmd, shell=True)

            # write prefs to user.js
            userjs_path = os.path.join(self._profile_path, 'user.js')
            logging.debug('Writing user.js: %s' % userjs_path)
            with open(userjs_path, 'w') as f:
                if self._disable_local_cache:
                    f.write('user_pref("browser.cache.disk.enable", false);\n')
                    f.write('user_pref("browser.cache.memory.enable", false);\n')
                if self._http2:
                    # As of v34, this is enabled by default anyway
                    f.write('user_pref("network.http.spdy.enabled.http2draft", true);\n')
                if self._user_agent:
                    f.write('user_pref("general.useragent.override", "%s");\n' % self._user_agent)
            f.closed
        except Exception as e:
            logging.exception("Error creating Firefox profile")
            return False
    
        # launch firefox
        try:
            firefox_command =  '%s -profile %s' % (FIREFOX, self._profile_path)
            logging.debug('Starting Firefox: %s', firefox_command)
            self._firefox_proc = subprocess.Popen(firefox_command.split())
            sleep(5)
        except Exception as e:
            logging.exception("Error starting Firefox")
            return False
        logging.debug('Started Firefox')
        return True



    def _setup(self):
        if self._headless:
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

        if self._selenium:
            return self._setup_selenium()
        else:
            return self._setup_native()

        


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
