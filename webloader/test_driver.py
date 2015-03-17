#!/usr/bin/env python

import os
import sys
import logging
import argparse
import pprint
from phantomjs_loader import PhantomJSLoader
from chrome_loader import ChromeLoader
from firefox_loader import FirefoxLoader
from pythonrequests_loader import PythonRequestsLoader
from curl_loader import CurlLoader
from nodejs_loader import NodeJsLoader
from tcp_loader import TCPLoader

def main():
    #loader = NodeJsLoader(num_trials=1, full_page=False, http2=True)
    #loader = CurlLoader(num_trials=1, full_page=False)
    #loader = PythonRequestsLoader(num_trials=1)
    #loader = FirefoxLoader(num_trials=1, headless=False, selenium=False)
    #loader = PhantomJSLoader(num_trials=5)
    loader = TCPLoader(num_trials=1, full_page=False, user_agent='Test User Agent')
    loader.load_pages(['http://www.cnn.com'])
    print loader.urls
    pprint.pprint(dict(loader.load_results))
    pprint.pprint(dict(loader.page_results))

if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Web page profiler.')
    parser.add_argument('-o', '--outdir', default='.', help='Destination directory for HAR files.')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()

    if not os.path.isdir(args.outdir):
        try:
            os.makedirs(args.outdir)
        except Exception as e:
            logging.getLogger(__name__).error('Error making output directory: %s' % args.outdir)
            sys.exit(-1)
    
    # set up logging
    if args.quiet:
        level = logging.WARNING
    elif args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        format = "%(levelname) -10s %(asctime)s %(module)s:%(lineno) -7s %(message)s",
        level = level
    )

    main()
