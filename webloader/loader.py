import os
import subprocess
import re
import logging
import urlparse
import requests
import signal
import pprint
import traceback
import numpy
import time
from collections import defaultdict


TCPDUMP = '/usr/sbin/tcpdump'


################################################################################
#                                                                              #
#   UTILITIES                                                                  #
#                                                                              #
################################################################################

class TimeoutError(Exception):
    pass

class Timeout:
    '''Can be used w/ 'with' to make arbitrary function calls with timeouts'''
    def __init__(self, seconds=10, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)


################################################################################
#                                                                              #
#   RESULTS                                                                    #
#                                                                              #
################################################################################

class LoadResult(object):
    '''Status and stats for a single URL load (i.e., one trial).
    
    :param status: The status of the page load.
    :param url: The original URL.
    :param final_url: The final URL (maybe be different if we were redirected).
    :param time: The page load time (in seconds).
    :param size: Size of object if loading a single object; total size if loading
        a full page.
    :param har: Path to the HAR file.
    :param img: Path to a screenshot of the loaded page.
    :param tcp_fast_open_supported: True if TCP fast open was used successfully;
        False otherwise or unknown
    '''
    
    # Status constants
    SUCCESS = 'SUCCESS' #: Page load was successful
    FAILURE_TIMEOUT = 'FAILURE_TIMEOUT' #: Page load timed out
    FAILURE_UNKNOWN = 'FAILURE_UNKNOWN' #: Unkown failure occurred
    FAILURE_NO_200 = 'FAILURE_NO_200'  #: HTTP status code was not 200
    FAILURE_UNSET = 'FAILURE_UNSET' #: Status has not been set

    def __init__(self, status, url, final_url=None, time=None, size=None,\
        har=None, img=None, raw=None, server=None,\
        tcp_fast_open_supported=False, tls_false_start_supported=False,\
        tls_session_resumption_supported=False):

        self._status = status
        self._url = url  # the initial URL we requested
        self._final_url = final_url  # we may have been redirected
        self._time = time  # load time in seconds
        self._size = size
        self._har_path = har
        self._image_path = img
        self._raw = raw
        self._server = server
        self._tcp_fast_open_supported = tcp_fast_open_supported
        self._tls_false_start_supported = tls_false_start_supported
        self._tls_session_resumption_supported = tls_session_resumption_supported

    @property
    def status(self):
        '''The status of this page load.'''
        return self._status

    @property
    def url(self):
        '''The original URL requested.'''
        return self._url

    @property
    def final_url(self):
        '''The final URL (could be different if we were redirected).'''
        return self._final_url

    @property
    def time(self):
        '''The page load time in seconds.'''
        return self._time

    @property
    def size(self):
        '''???'''
        return self._size

    @property
    def har_path(self):
        '''Path to the HAR captured during this page load.'''
        return self._har_path

    @property
    def image_path(self):
        '''Path to a screenshot of the loaded page.'''
        return self._image_path

    @property
    def raw(self):
        '''Raw output from the underlying command.'''
        return self._raw

    @property
    def server(self):
        '''Web server software name.'''
        return self._server

    @property
    def tcp_fast_open_supported(self):
        '''Bool indicating whether or not TCP fast open succeeded for this
            connection.'''
        return self._tcp_fast_open_supported

    @property
    def tls_false_start_supported(self):
        '''Bool indicating whether or not TLS false start succeeded for this
            connection.'''
        return self._tls_false_start_supported
    
    @property
    def tls_session_resumption_supported(self):
        '''Bool indicating whether or not TLS session resumption succeeded for this
            connection.'''
        return self._tls_session_resumption_supported

    def __str__(self):
        return 'LoadResult (%s): %s' % (self._status,  pprint.saferepr(self.__dict__))

    def __repr__(self):
        return self.__str__()


class PageResult(object):
    '''Status and stats for one URL (all trials).
    
    :param url: The original URL.
    :param status: The overall status of all trials.
    :param load_results: List of individual :class:`LoadResult` objects
    '''
    
    # Status constants
    SUCCESS = 'SUCCESS' #: All trials were successful
    PARTIAL_SUCCESS = 'PARTIAL_SUCCESS' #: some trials were successful
    FAILURE_NOT_ACCESSIBLE = 'FAILURE_NOT_ACCESSIBLE' #: The page could not be loaded with the specified protocol
    FAILURE_UNKNOWN = 'FAILURE_UNKNOWN' #: An unknown failure occurred
    FAILURE_UNSET = 'FAILURE_UNSET' #: Status has not been set

    def __init__(self, url, status=None, load_results=None):
        self._status = PageResult.FAILURE_UNSET
        self._url = url
        self._load_statuses = []
        self._times = []
        self._sizes = []
        self._server = 'UNKNOWN'
        self._tcp_fast_open_support_statuses = []
        self._tls_false_start_support_statuses = []
        self._tls_session_resumption_support_statuses = []

        if load_results:
            was_a_failure = False
            was_a_success = False
            for result in load_results:
                self._load_statuses.append(result.status)
                if result.server:
                    self._server = result.server
                if result.status == PageResult.SUCCESS:
                    was_a_success = True
                    if result.time: self.times.append(result.time)
                    if result.size: self.sizes.append(result.size)
                    self._tcp_fast_open_support_statuses.append(
                        result.tcp_fast_open_supported)
                    self._tls_false_start_support_statuses.append(
                        result.tls_false_start_supported)
                    self._tls_session_resumption_support_statuses.append(
                        result.tls_session_resumption_supported)
                else:
                    was_a_failure = True
            if was_a_failure and was_a_success:
                self._status = PageResult.PARTIAL_SUCCESS
            elif was_a_success:
                self._status = PageResult.SUCCESS
            else:
                self._status = PageResult.FAILURE_UNKNOWN

        if status:
            self._status = status

    @property
    def status(self):
        '''The overall status across all trials.'''
        return self._status

    @property
    def url(self):
        '''The URL.'''
        return self._url

    @property
    def load_statuses(self):
        '''A list of statuses from individual trials.'''
        return self._load_statuses

    @property
    def times(self):
        '''A list of the load times from individual trials.'''
        return self._times

    @property
    def sizes(self):
        '''A list of the page sizes from individual trials.'''
        return self._sizes

    @property
    def server(self):
        '''Web server software name.'''
        return self._server

    @property
    def tcp_fast_open_support_statuses(self):
        '''A list of bools indicating whether or not TCP fast open succeeded
            for each load.'''
        return self._tcp_fast_open_support_statuses
    
    @property
    def tls_false_start_support_statuses(self):
        '''A list of bools indicating whether or not TLS false start succeeded
            for each load.'''
        return self._tls_false_start_support_statuses
    
    @property
    def tls_session_resumption_support_statuses(self):
        '''A list of bools indicating whether or not TLS session resumption 
            succeeded for each load.'''
        return self._tls_session_resumption_support_statuses
    
    @property
    def mean_time(self):
        '''Mean load time across all trials.'''
        return numpy.mean(self.times)
    
    @property
    def median_time(self):
        '''Median load time across all trials.'''
        return numpy.median(self.times)
    
    @property
    def stddev_time(self):
        '''Standard deviation of load time across all trials.'''
        return numpy.std(self.times)
    
    def __str__(self):
        return 'PageResult (%s): %s' % (self._status,  pprint.saferepr(self.__dict__))

    def __repr__(self):
        return self.__str__()



################################################################################
#                                                                              #
#   LOADER                                                                     #
#                                                                              #
################################################################################

class Loader(object):
    '''Superclass for URL loader. Subclasses implement actual page load
    functionality (e.g., using Chrome, PhantomJS, etc.).

    :param outdir: directory for HAR files, screenshots, etc.
    :param num_trials:  number of times to load each URL
    :param http2: use HTTP 2 (not all subclasses support this)
    :param timeout: timeout in seconds
    :param disable_local_cache: disable the local browser cache (RAM and disk)
    :param disable_network_cache: send "Cache-Control: max-age=0" header
    :param full_page: load page's subresources and render; if False, only the
        object is fetched
    :param user_agent: use custom user agent; if None, use browser's default
    :param headless: don't use GUI (if there normally is one -- e.g., browsers)
    :param restart_on_fail: if a load fails, set up the loader again (e.g.,
        reboot chrome)
    :param restart_each_time: tear down and set up the loader before each page
        load (e.g., reboot chrome to close open connections)
    :param save_har: save a HAR file to the output directory
    :param save_screenshot: save a screenshot to the output directory
    :param save_content: save HTTP message bodies (options: 'always', 'first', 'never')
    :param retries_per_trial: if a trial fails, retry this many times (beyond
        first)
    :param stdout_filename: if the loader launches other procs (e.g., browser),
        send their stdout and stderr to this file. If None, use parent proc's
        stdout and stderr.
    :param check_protocol_availability: before loading the page, check to see
        if the specified protocol (HTTP or HTTPS) is supported. (otherwise, the
        loader might silently fall back to a different protocol.)
    :param save_packet_capture: save a pcap trace for each load (separate files)
    :param disable_quic: disable use of the QUIC transport protocol
    :param disable_spdy: disable use of SPDY/HTTP2
    :param log_ssl_keys: instruct browser to save SSL session keys (by setting
        SSLKEYLOGFILE environment variable)
    :param ignore_certificate_errors: continue loading page even if
        certificate check fails
    :param delay_after_onload: continue recording objects after onLoad fires (ms)
    :param delay_first_trial_only: if fetching a URL multiple times, only delay
        after onLoad on the first trial. (The delay is useful to count how many
        objects are loaded after onLoad, and this is less likely to change from
        trial to trial than load time.)
    :param primer_load_first: load the page once before beginning normal trials
        (e.g., to prime DNS caches)
    :param configs: TODO: document
    '''

    def __init__(self, outdir='.', num_trials=1, http2=False, timeout=30,\
        disable_local_cache=True, disable_network_cache=False, full_page=True,\
        user_agent=None, headless=True, restart_on_fail=False,\
        restart_each_time=False, proxy=None, save_har=False,\
        save_screenshot=False, save_content='never', retries_per_trial=0,\
        stdout_filename=None, check_protocol_availability=True,\
        save_packet_capture=False, disable_quic=False, disable_spdy=False,\
        log_ssl_keys=False, ignore_certificate_errors=False,\
        delay_after_onload=0, delay_first_trial_only=False,\
        primer_load_first=False,\
        configs=[{'tag':'default', 'settings':{}}]):
        '''Initialize a Loader object.'''

        # options
        self._outdir = outdir
        self._num_trials = num_trials
        self._http2 = http2
        self._timeout = timeout
        self._disable_local_cache = disable_local_cache
        self._disable_network_cache = disable_network_cache
        self._full_page = full_page
        self._user_agent = user_agent
        self._headless = headless
        self._restart_on_fail = restart_on_fail
        self._restart_each_time = restart_each_time
        self._save_har = save_har
        self._save_screenshot = save_screenshot
        self._save_content = save_content
        self._retries_per_trial = retries_per_trial
        self._stdout_filename = stdout_filename
        self._proxy = proxy
        self._check_protocol_availability = check_protocol_availability
        self._save_packet_capture = save_packet_capture
        self._disable_quic = disable_quic
        self._disable_spdy = disable_spdy
        self._log_ssl_keys = log_ssl_keys
        self._ignore_certificate_errors = ignore_certificate_errors
        self._delay_after_onload = delay_after_onload
        self._delay_first_trial_only = delay_first_trial_only
        self._primer_load_first = primer_load_first
        self._configs = configs
        
        # cummulative list of all URLs (one per trial)
        self._urls = []

        # Map URLs to lists of LoadResults (there will be multiple results per
        # URL if there are multiple trials)
        self._load_results = defaultdict(list)
        
        # Map URLs to PageResults (there is only one PageResult per URL; it
        # summarizes the LoadResults for the individual trials)
        self._page_results = {}

        # count how many times we restarted the loader due to failure
        self._num_restarts = 0

        # count how many consecutive timeouts we've seen; restart if too many
        self._consecutive_timeouts = 0

        # if self._stdout_filename is set, this var will hold the file object
        self._stdout_file = None

    


    ##
    ## Internal helper methods
    ##
    def _sanitize_url(self, url):
        '''Returns a version of the URL suitable for use in a file name.'''
        return re.sub(r'[/\;,><&*:%=+@!#^()|?^]', '-', url)

    def _outfile_path(self, url, suffix=None, trial=None, tag=None):
        '''Returns a path for an output file (e.g., HAR, screenshot, pcap)'''
        filename = self._sanitize_url(url)
        if tag:
            filename += '<%s>' % tag
        if trial != None:
            filename += '_trial%d' % trial
        if suffix:
            filename += suffix
        return os.path.join(self._outdir, filename)


    def _check_url(self, url):
        '''Make sure URL is well-formed'''

        if '://' not in url:
            logging.warn('URL %s has no protocol; using http.' % url)
            url = 'http://%s' % url

        return url

    # TODO: handle sites that sometimes return HTTP and sometimes HTTPS (YouTube)
    def _check_protocol_available(self, url):
        '''Check if the URL can be loaded over the specified protocol.

        For example, an HTTPS might not respond or an HTTP URL might be
        redirected to an HTTPS one.
        '''

        orig_protocol = urlparse.urlparse(url).scheme
        logging.debug('Checking if %s can be accessed using %s'\
            % (url, orig_protocol))
    
        # try to fetch the page with the specified protocol
        response = None
        try:
            with Timeout(seconds = self._timeout+5):
                headers = {}
                if self._user_agent:
                    headers['User-Agent'] = self._user_agent
                response = requests.get(url, timeout=self._timeout,\
                    headers=headers, verify=False) 
        except requests.exceptions.ConnectionError as e:
            logging.debug('Could not connect to %s: %s', url, e)
            return False
        except requests.exceptions.Timeout as e:
            logging.debug('Timed out connecting to %s: %s', url, e)
            return False
        except TimeoutError:
            logging.debug('* Timed out connecting to %s', url)
            return False
        except Exception as e:
            logging.exception('Error requesting %s: %s', url, e)
            return False
    
        # if we got a response, check if we changed protocols
        final_protocol = urlparse.urlparse(response.url).scheme
        if orig_protocol == final_protocol:
            return True
        else:
            return False

    def _setup(self):
        '''Subclasses can override to prepare (e.g., launch Xvfb)'''
        return True
    
    def __setup(self):
        '''Private setup method for Loader superclass'''
        if self._stdout_filename:
            try:
                self._stdout_file = open(self._stdout_filename, 'a')
            except:
                logging.exception('Error opening stdout file: %s. Using parent\'s stdout.',\
                    self._stdout_filename)
                self._stdout_file = None

        # if the loader fails to set itself up, try a few more times with
        # longer timeouts in between
        tries = 10
        tries_so_far = 0
        setup_succeeded = False
        while (not setup_succeeded) and (tries_so_far < tries):
            logging.debug('Setup attempt #%d' % tries_so_far)
            setup_succeeded = self._setup()

            if not setup_succeeded:
                tries_so_far += 1
                logging.warn('Error setting up loader. Will try %d more times' % (tries-tries_so_far))
                self._teardown()
                time.sleep(tries_so_far)

        return setup_succeeded


    def _teardown(self):
        '''Subclasses can override to clean up (e.g., kill Xvfb)'''
        return True
    
    def __teardown(self):
        '''Private teardown method for Loader superclass'''
        child_ret = self._teardown()

        if self._stdout_file:
            self._stdout_file.close()

        return child_ret

    def __restart(self):
        '''Tear down and set up the loader'''
        logging.debug('Restarting loader')
        self.__teardown()
        time.sleep(1)
        setup_succeeded = self.__setup()
        self._num_restarts += 1

        if not setup_succeeded:
            raise('Failed to restart loader')


    def __getstate__(self):
        '''override getstate so we don't try to pickle the stdout file object'''
        state = dict(self.__dict__)
        del state['_stdout_file']
        return state




    ##
    ## Properties
    ##
    @property
    def urls(self):
        '''A cummulative list of the URLs this instance has loaded
        in the order they were loaded. Each trial is listed separately.'''
        return self._urls

    @property
    def load_results(self):
        '''A dict mapping URLs to a list of :class:`LoadResult`.'''
        return self._load_results
    
    @property
    def page_results(self):
        '''A dict mapping URLs to a :class:`PageResult`.'''
        return self._page_results

    @property
    def num_restarts(self):
        '''Number of times the loader was restarted (e.g., rebooted browser
        process) due to failures if restart_on_fail is True.'''
        return self._num_restarts
    
    

    ##
    ## Public methods
    ##
    def load_pages(self, urls):
        '''Load each URL in `urls` `num_trials` times and collect stats.
        
        :param urls: list of URLs to load
        '''
        tcpdump_proc = None  # if we use tcpdump, keep a handle to the process
        try:
            if not self.__setup():
                logging.error('Error setting up loader')
                self.__teardown()
                return

            for url in urls:
                try:
                    # make sure URL is well-formed (e.g., has protocol, etc.)
                    url = self._check_url(url)

                    # make sure URL is accessible over specified protocol
                    if self._check_protocol_availability and \
                        not self._check_protocol_available(url):
                        logging.info('%s is not accessible', url)
                        self._urls.append(url)
                        self._page_results[url] = PageResult(url,\
                            status=PageResult.FAILURE_NOT_ACCESSIBLE)
                        continue

                    # Load page once before actual trials (e.g., to prime DNS cache)
                    if self._primer_load_first:
                        tries_so_far = 0
                        while tries_so_far <= self._retries_per_trial:
                            tries_so_far += 1
                            result = self._load_page(url, self._outdir, None, tag='primer')
                            if result.status == LoadResult.SUCCESS:
                                break
                        

                    # Load URLs for each config
                    for config in self._configs:

                        tag = config['tag']
                        for k, v in config['settings'].iteritems():
                            self.__dict__[k] = v  # FIXME: hacky
                        self.__restart()


                        # If all is well, load URL num_trials times
                        for i in range(0, self._num_trials):
                            try:
                                # if load fails, keep trying self._retries_per_trial times
                                tries_so_far = 0
                                while tries_so_far <= self._retries_per_trial:
                                    tries_so_far += 1

                                    # start tcpdump if we want a packet capture
                                    if self._save_packet_capture:
                                        pcap_path = self._outfile_path(url, suffix='.pcap', trial=i, tag=tag)
                                        tcpdump_command = 'sudo %s -w %s' % (TCPDUMP, pcap_path)
                                        logging.debug('Starting tcpdump: %s', tcpdump_command)
                                        tcpdump_proc = subprocess.Popen(tcpdump_command.split(),\
                                            stdout=self._stdout_file, stderr=self._stdout_file)

                                    # load the page
                                    result = self._load_page(url, self._outdir, i, tag=tag)
                                    logging.debug('Trial %d, try %d: %s' % (i, tries_so_far, result))

                                    # stop tcpdump (if it's running)
                                    if tcpdump_proc:
                                        logging.debug('Stopping tcpdump')
                                        os.system("sudo kill %s" % tcpdump_proc.pid)
                                        tcpdump_proc = None

                                    # count consecutive timeouts (if too many, we might restart)
                                    if result.status == LoadResult.FAILURE_TIMEOUT:
                                        self._consecutive_timeouts += 1
                                    else:
                                        self._consecutive_timeouts = 0

                                    # restart if things are going wrong or just to clean up
                                    if ((result.status == LoadResult.FAILURE_UNKNOWN\
                                            or self._consecutive_timeouts >= 3)\
                                            and self._restart_on_fail)\
                                            or self._restart_each_time:
                                        self.__restart()

                                    # record load status
                                    if result.status == LoadResult.SUCCESS:
                                        self._urls.append(url)
                                        self._load_results[url].append(result)
                                        break  # success, don't retry
                                    elif tries_so_far > self._retries_per_trial:
                                        # this was the last try, record the failure
                                        self._urls.append(url)
                                        self._load_results[url].append(result)

                            # trial level try block
                            except:
                                logging.exception('Error loading URL (trial %d): %s ', url, i)

                    # Save PageResult summarizing the individual trial LoadResults
                    self._page_results[url] = PageResult(url,\
                        load_results=self._load_results[url])

                # url level try block
                except:
                    logging.exception('Error loading URL: %s' % url)

        # load_pages level try block
        except:
            logging.exception('Error loading pages')
        finally:
            # stop tcpdump (if it's running)
            try:
                if tcpdump_proc:
                    logging.debug('Stopping tcpdump')
                    os.system("sudo kill %s" % tcpdump_proc.pid)
                    tcpdump_proc = None
            except:
                logging.exception('Error stopping tcpdump.')
            self.__teardown()
