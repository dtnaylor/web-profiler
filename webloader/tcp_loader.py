import os
import sys
import urlparse
import logging
import traceback
import subprocess
from collections import defaultdict
from loader import Loader, LoadResult, Timeout, TimeoutError

TCPLOADER = os.path.join(os.path.dirname(__file__), 'tcp_loader/tcp_loader')


class TCPLoader(Loader):
    '''Subclass of :class:`Loader` that loads pages using custom executable so we can change TCP settings.
    
    .. note:: The :class:`TCPLoader` currently does not support HTTP2.
    .. note:: The :class:`TCPLoader` currently does not support local caching.
    .. note:: The :class:`TCPLoader` currently does not support disabling network caching.
    .. note:: The :class:`TCPLoader` currently does not support single-object loading (i.e., it always loads the full page).
    '''

    def __init__(self, **kwargs):
        super(TCPLoader, self).__init__(**kwargs)
        if self._full_page:
            raise NotImplementedError('TCPLoader does not support loading full pages.')
        if self._http2:
            raise NotImplementedError('TCPLoader does not support HTTP2')
        if not self._disable_local_cache:
            raise NotImplementedError('TCPLoader does not support local caching')
        if self._disable_network_cache:
            raise NotImplementedError('TCPLoader does not support disabling network caches.')
        if self._save_har:
            raise NotImplementedError('TCPLoader does not support saving HARs.')
        if self._save_screenshot:
            raise NotImplementedError('TCPLoader does not support saving screenshots.')


    def _load_page(self, url, outdir, trial_num=-1):
        # load the specified URL
        logging.info('Loading page: %s', url)
        try:
            # Load the page
            parsed_url = urlparse.urlparse(url)
            path = '/' if parsed_url.path == '' else parsed_url.path
            cmd = '%s %s %s %s' %\
                (TCPLOADER, parsed_url.scheme, parsed_url.netloc, path)
            if self._user_agent:
                cmd += ' "%s"' % self._user_agent

            logging.debug('Running tcploader: %s', cmd)
            with Timeout(seconds=self._timeout+5):
                output = subprocess.check_output(cmd, shell=True)

            logging.debug('tcploader returned: %s', output.strip())
            returnvals = {field.split('=')[0]: field.split('=')[1]\
                for field in output.strip().split('\n')[-1].split(';')}
            return LoadResult(LoadResult.SUCCESS,
                url,
                time=float(returnvals['time_seconds']),
                size=int(returnvals['size']),
                server=returnvals['server'],
                tcp_fast_open_supported=\
                    bool(int(returnvals['tcp_fast_open_used']))
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
                subprocess.check_output('killall tcp_loader'.split())
            except Exception as e:
                logging.debug('Error killing tcp_loader (process might not exist): %s', e)
