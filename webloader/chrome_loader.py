import os
import sys
import subprocess
import traceback
import logging
from time import sleep
from loader import Loader, LoadResult, Timeout, TimeoutError

CHROME = '/usr/bin/env google-chrome'
CHROME_HAR_CAPTURER = '/usr/bin/env chrome-har-capturer'
XVFB = '/usr/bin/env Xvfb'
DISPLAY = ':99'
CURL = '/usr/bin/env curl'

# TODO: test if isntalled chrome can support HTTP2
# TODO: pick different display if multiple instances are used at once
# TODO: get load time
# TODO: screenshot?
# TODO: final URL?
# TODO: pass timeout to chrome?
# TODO: FAILURE_NO_200?

class ChromeLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using Chrome.
    
    .. note:: The :class:`ChromeLoader` currently does not time page load.
    .. note:: The :class:`ChromeLoader` currently does not save screenshots.
    .. note:: The :class:`ChromeLoader` currently does not support single-object loading (i.e., it always loads the full page).
    .. note:: The :class:`ChromeLoader` currently does not support saving screenshots.
    '''

    def __init__(self, **kwargs):
        super(ChromeLoader, self).__init__(**kwargs)
        if not self._full_page:
            raise NotImplementedError('ChromeLoader does not support loading only an object')
        if self._save_screenshot:
            raise NotImplementedError('ChromeLoader does not support saving screenshots.')

        self._xvfb_proc = None
        self._chrome_proc = None

    def _load_page(self, url, outdir, trial_num=None, tag=None):
        # path for new HAR file
        if self._save_har:
            harpath = self._outfile_path(url, suffix='.har', trial=trial_num, tag=tag)
        else:
            harpath = '/dev/null'
        logging.debug('Will save HAR to %s', harpath)


        # build chrome-har-capturer arguments
        capturer_args = ''

        onload_delay = self._delay_after_onload
        if self._delay_first_trial_only and trial_num != 0:
            onload_delay = 0
        capturer_args += ' -d %i' % onload_delay

        if self._disable_network_cache:
            capturer_args += ' --no-network-cache'

    
        # load the specified URL
        logging.info('Fetching page %s (%s)', url, tag)
        try:
            capturer_cmd = '%s -o "%s" %s %s' %\
                (CHROME_HAR_CAPTURER, harpath, capturer_args, url)
            logging.debug('Running capturer: %s', capturer_cmd)
            with Timeout(seconds=self._timeout+5):
                subprocess.check_call(capturer_cmd, shell=True,\
                    stdout=self._stdout_file, stderr=subprocess.STDOUT)
        
        except TimeoutError:
            logging.error('Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, e.output))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s' % (url, e))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        logging.debug('Page loaded.')
    
        return LoadResult(LoadResult.SUCCESS, url, har=harpath)


    def _setup(self):
        stdout = self._stdout_file
        stderr = self._stdout_file

        if self._headless:
            # start a virtual display
            try:
                os.environ['DISPLAY'] = DISPLAY
                xvfb_command = '%s %s -screen 0 1366x768x24 -ac' % (XVFB, DISPLAY)
                logging.debug('Starting XVFB: %s', xvfb_command)
                self._xvfb_proc = subprocess.Popen(xvfb_command.split(),\
                    stdout=stdout, stderr=stderr)
                sleep(1)

                # check if Xvfb failed to start and process terminated
                retcode = self._xvfb_proc.poll()
                if retcode != None:
                    raise("Xvfb proc exited with return code: %i" % retcode)
            except Exception as e:
                logging.exception("Error starting XFVB")
                return False
            logging.debug('Started XVFB (DISPLAY=%s)', os.environ['DISPLAY'])

        if self._log_ssl_keys:
            keylog_file = os.path.join(self._outdir, 'ssl_keylog')
            os.environ['SSLKEYLOGFILE'] = keylog_file
            
    
        # launch chrome with no cache and remote debug on
        try:
            # TODO: enable HTTP2
            options = ''
            if self._user_agent:
                options += ' --user-agent="%s"' % self._user_agent
            if self._disable_local_cache:
                options += ' --disable-application-cache --disable-cache'
            if self._disable_quic:
                options += ' --disable-quic'
            if self._disable_spdy:
                options += ' --use-spdy=off'
            if self._ignore_certificate_errors:
                options += ' --ignore-certificate-errors'
            # options for chrome-har-capturer
            options += ' --remote-debugging-port=9222 --enable-benchmarking --enable-net-benchmarking'

            chrome_command = '%s %s' % (CHROME, options)
            logging.debug('Starting Chrome: %s', chrome_command)
            self._chrome_proc = subprocess.Popen(chrome_command.split(),\
                stdout=stdout, stderr=stderr)
                

            # wait until chrome remote debugging is ready
            with Timeout(seconds=5):
                curl_retcode = -1
                while curl_retcode != 0:
                    # try to access chrome remote debug interface
                    curl_cmd = '%s -sS --max-time 1 -o /dev/null localhost:9222/json' % CURL
                    curl_retcode = subprocess.call(curl_cmd.split(),\
                        stdout=self._stdout_file, stderr=subprocess.STDOUT)

                    logging.debug('Checking if Chrome remote debug is ready. Curl return code: %d' % curl_retcode)
                
                    # check to see if chrome exited for some reason
                    # (e.g., if Xvfb failed to start)
                    chrome_retcode = self._chrome_proc.poll()
                    if chrome_retcode != None:
                        raise("Chrome proc exited with return code: %i" % chrome_retcode)

                    sleep(0.5)

        except TimeoutError:
            logging.error('Timeout waiting for Chrome to be ready')
            return False
        except Exception as e:
            logging.exception("Error starting Chrome")
            return False
        logging.debug('Started Chrome')
        return True


    def _teardown(self):
        try:
            if self._chrome_proc:
                logging.debug('Stopping Chrome')
                self._chrome_proc.kill()
                self._chrome_proc.wait()
        except:
            logging.exception('Error closing Chrome')

        # kill any subprocesses chrome might have opened
        try:
            subprocess.check_output('killall -q chrome'.split())
        except Exception as e:
            logging.debug('Problem killing all chrome processes (maybe there were none): %s' % e)

        try:
            if self._xvfb_proc:
                logging.debug('Stopping XVFB')
                self._xvfb_proc.kill()
            self._xvfb_proc.wait()
        except:
            logging.exception('Error closing Xvfb')
