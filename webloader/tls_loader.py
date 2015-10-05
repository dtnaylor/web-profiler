import os
import sys
import urlparse
import logging
import traceback
import subprocess
from collections import defaultdict
from loader import Loader, LoadResult, Timeout, TimeoutError

OPENSSL_BINARY = '/home/dnaylor/Documents/OpenSSL_stable/openssl-1.0.1f/apps/openssl'


class TLSLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using OpenSSL s_client to
    test server's False Start and session resumption support.
    
    .. note:: The :class:`TLSLoader` currently does not support HTTP2.
    .. note:: The :class:`TLSLoader` currently does not support local caching.
    .. note:: The :class:`TLSLoader` currently does not support disabling network caching.
    .. note:: The :class:`TLSLoader` currently does not support single-object loading (i.e., it always loads the full page).
    .. note:: The :class:`TLSLoader` currently does not support saving content.
    '''

    def __init__(self, test_false_start=False, test_session_resumption=False,\
        **kwargs):
        super(TLSLoader, self).__init__(**kwargs)
        if self._full_page:
            raise NotImplementedError('TLSLoader does not support loading full pages.')
        if self._http2:
            raise NotImplementedError('TLSLoader does not support HTTP2')
        if not self._disable_local_cache:
            raise NotImplementedError('TLSLoader does not support local caching')
        if self._disable_network_cache:
            raise NotImplementedError('TLSLoader does not support disabling network caches.')
        if self._save_har:
            raise NotImplementedError('TLSLoader does not support saving HARs.')
        if self._save_screenshot:
            raise NotImplementedError('TLSLoader does not support saving screenshots.')
        if self._delay_after_onload != 0:
            raise NotImplementedError('TLSLoader does not support delay after onload')
        if self._save_content != 'never':
            raise NotImplementedError('TLSLoader does not support saving content')

        self._test_false_start = test_false_start
        self._test_session_resumption = test_session_resumption
        if self._test_false_start and self._test_session_resumption:
            logging.warn('Testing False Start and Session Resumption together\
                result in unintended behavior.')


    def _load_page(self, url, outdir, trial_num=-1):
        # load the specified URL
        logging.info('Loading page: %s', url)
        try:
            # Load the page
            parsed_url = urlparse.urlparse(url)
            path = '/' if parsed_url.path == '' else parsed_url.path
            if parsed_url.scheme != 'https':
                logging.warn('Specified protocol was not HTTPS; using HTTPS anyway.')
            get_request = 'GET %s HTTP/1.1\r\nHost: %s\r\n\r\n' %\
                (path, parsed_url.netloc)

            options = ''
            if self._test_false_start: options += ' -cutthrough'
            if self._test_session_resumption: options += ' -reconnect'
            cmd = '%s s_client -connect %s:443 %s' %\
                (OPENSSL_BINARY, parsed_url.netloc, options)

            logging.debug('Running tcploader: %s', cmd)
            with Timeout(seconds=self._timeout+5):
                p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,\
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                (stdout, stderr) = p.communicate(input=get_request)
                #output = subprocess.check_output(cmd, shell=True)

            logging.debug('s_client returned: %s', stdout.strip())
            # TODO: better OpenSSL error checking here
            return LoadResult(LoadResult.SUCCESS,
                url,
                tls_false_start_supported=('false_start=yes' in stdout),
                tls_session_resumption_supported=('session_resumption=yes' in stdout)
                )

        # problem running tcp_loader
        except TimeoutError:
            logging.exception('* Timeout fetching %s', url)
            return LoadResult(LoadResult.FAILURE_TIMEOUT, url)
        except subprocess.CalledProcessError as e:
            logging.exception('Error loading %s: %s\n%s\n%s' % (url, e, e.output, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        except Exception as e:
            logging.exception('Error loading %s: %s\n%s' % (url, e, traceback.format_exc()))
            return LoadResult(LoadResult.FAILURE_UNKNOWN, url)
        finally:
            try:
                subprocess.check_output('killall openssl'.split())
            except Exception as e:
                logging.debug('Error killing openssl (process might not exist): %s', e)
