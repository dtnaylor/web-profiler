#! /usr/bin/env python

import os
import sys
import shutil
import logging
import argparse
import tempfile

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from webloader.phantomjs_loader import PhantomJSLoader
from webloader.curl_loader import CurlLoader
from webloader.pythonrequests_loader import PythonRequestsLoader
from webloader.chrome_loader import ChromeLoader
#from webloader.firefox_loader import FirefoxLoader


def get_loader(**kwargs):
    loader = args.loader.lower()
    if 'python' in loader or 'requests' in loader:
        return PythonRequestsLoader(full_page=False, **kwargs)
    elif 'curl' in loader:
        return CurlLoader(full_page=False, **kwargs)
    elif 'phantom' in loader or 'js' in loader:
        return PhantomJSLoader(**kwargs)
    elif 'chrome' in loader:
        return ChromeLoader(**kwargs)
    elif 'firefox' in loader:
        return FirefoxLoader(**kwargs)
    else:
        logging.error('Unknown loader: %s', args.loader)
        sys.exit(-1)

def main():

    outdir = os.path.join(tempfile.gettempdir(), 'loader-test')

    loader = get_loader(outdir=outdir)
    loader.load_pages([args.url])

    print loader.page_results
    print loader.load_results

    try:
        shutil.rmtree(outdir)
    except:
        pass



if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Test a loader by requesting a single URL.')
    parser.add_argument('url', help='The URL to load.')
    parser.add_argument('-l', '--loader', default="python-requests", help='The loader to test.')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()

    
    # set up logging
    if args.quiet:
        level = logging.WARNING
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    config = {
        'format' : "%(levelname) -10s %(asctime)s %(module)s:%(lineno) -7s %(message)s",
        'level' : level
    }
    logging.basicConfig(**config)

    main()
