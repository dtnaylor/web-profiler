import re
import logging
import urlparse
import requests
import signal
import pprint
import traceback
import numpy
from collections import defaultdict


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


class LoadResult(object):
    '''Status and stats for a single URL *load*.'''
    def __init__(self, status, url, final_url=None, time=None, size=None,\
        har=None, img=None):

        self.status = status
        self.url = url  # the initial URL we requested
        self.final_url = final_url  # we may have been redirected
        self.time = time  # load time in seconds
        self.size = size  # ??? all objects?
        self.har_path = har
        self.image_path = img

    def __str__(self):
        return 'LoadResult (%s): %s' % (self.status,  pprint.saferepr(self.__dict__))

    def __repr__(self):
        return self.__str__()


class PageResult(object):
    '''Status and stats for one URL (all trials).'''
    def __init__(self, url, status=None, load_results=None):
        self.status = Loader.FAILURE_UNSET
        self.url = url
        self.times = []
        self.sizes = []

        if load_results:
            was_a_failure = False
            was_a_success = False
            for result in load_results:
                if result.status == Loader.SUCCESS:
                    was_a_success = True
                    if result.time: self.times.append(result.time)
                    if result.size: self.sizes.append(result.size)
                else:
                    was_a_failure = True
            if was_a_failure and was_a_success:
                self.status = Loader.PARTIAL_SUCCESS
            elif was_a_success:
                self.status = Loader.SUCCESS
            else:
                self.status = Loader.FAILURE_UNKNOWN

        if status:
            self.status = status
    
    @property
    def mean_time(self):
        return numpy.mean(self.times)
    
    @property
    def median_time(self):
        return numpy.median(self.times)
    
    @property
    def stddev_time(self):
        return numpy.std(self.times)
    
    def __str__(self):
        return 'PageResult (%s): %s' % (self.status,  pprint.saferepr(self.__dict__))

    def __repr__(self):
        return self.__str__()


class Loader(object):
    '''Superclass for URL loader. Subclasses implement actual page load
    functionality (e.g., using Chrome, PhantomJS, etc.).'''

    def __init__(self, outdir='.', num_trials=1, http2=False, timeout=60):
        '''Initialize a Loader object.

        Keyword arguments:
        outdir -- directory for HAR files, screenshots, etc.
        num_trials -- number of times to load each URL
        http2 -- use HTTP 2 (not all subclasses support this)
        timeout -- timeout in seconds
        '''
        self._outdir = outdir
        self._num_trials = num_trials
        self._http2 = http2
        self._timeout = timeout
        
        # cummulative list of all URLs (one per trial)
        self._urls = []

        # Map URLs to lists of LoadResults (there will be multiple results per
        # URL if there are multiple trials)
        self._load_results = defaultdict(list)
        
        # Map URLs to PageResults (there is only one PageResult per URL; it
        # summarizes the LoadResults for the individual trials)
        self._page_results = {}

    ##
    ## Constants
    ##
    SUCCESS = 'SUCCESS'
    PARTIAL_SUCCESS = 'PARTIAL_SUCCESS'
    FAILURE_NOT_ACCESSIBLE = 'FAILURE_NOT_ACCESSIBLE'
    FAILURE_TIMEOUT = 'FAILURE_TIMEOUT'
    FAILURE_NO_HTTP = 'FAILURE_NO_HTTP'
    FAILURE_NO_HTTPS = 'FAILURE_NO_HTTPS'
    FAILURE_UNKNOWN = 'FAILURE_UNKNOWN'
    FAILURE_NO_200 = 'FAILURE_NO_200'
    FAILURE_ARITHMETIC = 'FAILURE_ARITHMETIC'
    FAILURE_UNSET = 'FAILURE_UNSET'
    


    ##
    ## Internal helper methods
    ##
    def _sanitize_url(self, url):
        '''Returns a version of the URL suitable for use in a file name.'''
        return re.sub(r'[/\;,><&*:%=+@!#^()|?^]', '-', url)

    def _check_url(self, url):
        '''Make sure URL is well-formed'''

        if '://' not in url:
            logging.warn('URL %s has no protocol; using http.' % url)
            url = 'http://%s' % url

        return url

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
                response = requests.get(url, timeout=self._timeout)
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
    
    def _teardown(self):
        '''Subclasses can override to clean up (e.g., kill Xvfb)'''
        return True




    ##
    ## Properties
    ##
    @property
    def urls(self):
        '''Return a cummulative list of the URLs this instance has loaded
        in the order they were loaded. Each trial is listed separately.'''
        return self._urls

    @property
    def load_results(self):
        '''Return a dict mapping URLs to a list of LoadResults.'''
        return self._load_results
    
    @property
    def page_results(self):
        '''Return a dict mapping URLs to a PageResult.'''
        return self._page_results
    
    

    ##
    ## Public methods
    ##
    def load_pages(self, urls):
        '''Load a URL num_trials times and collect stats.'''
        try:
            if not self._setup():
                logging.error('Error setting up loader')
                return

            for url in urls:

                # make sure URL is well-formed (e.g., has protocol, etc.)
                url = self._check_url(url)

                # make sure URL is accessible over specified protocol
                if not self._check_protocol_available(url):
                    logging.info('%s is not accessible', url)
                    self._urls.append(url)
                    self._page_results[url] = PageResult(url,\
                        status=Loader.FAILURE_NOT_ACCESSIBLE)
                    continue

                # If all is well, load URL num_trials times
                for i in range(0, self._num_trials):
                    try:
                        result = self._load_page(url, self._outdir)
                        self._urls.append(url)
                        self._load_results[url].append(result)
                        logging.debug(result)
                    except Exception as e:
                        logging.exception('Error loading page %s: %s\n%s', url, e,\
                            traceback.format_exc())

                # Save PageResult summarizing the individual trial LoadResults
                self._page_results[url] = PageResult(url,\
                    load_results=self._load_results[url])
        except Exception as e:
            logging.exception('Error loading pages: %s\n%s', e, traceback.format_exc())
        finally:
            self._teardown()
