#! /usr/bin/env python

import os
import sys
import logging
import argparse

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from webloader.phantomjs_loader import PhantomJSLoader


def main():
    # make url list
    urls = []
    if args.url_file:
        with open(args.url_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line != '': urls.append(line.strip())
        f.closed
    if args.load_pages:
        urls += args.load_pages

    if len(urls) == 0:
        logging.getLogger(__name__).error('No URLs were specified.')
        sys.exit(-1)

    # load pages and save HARs
    if len(urls) > 0:
        loader = PhantomJSLoader(outdir=args.outdir, user_agent=args.useragent)
        loader.load_pages(urls)



if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Web page profiler.')
    parser.add_argument('-l', '--load_pages', nargs='+', help='URL(s) to load (to load multiple pages, separate URLs with spaces). A HAR will be generated for each page in outdir.')
    parser.add_argument('-f', '--url_file', default=None, help='Generate HARs for the URLs in the specified file (one URL per line)')
    parser.add_argument('-o', '--outdir', default='.', help='Destination directory for HAR files.')
    parser.add_argument('-u', '--useragent', default=None, help='Custom user agent. If None, use browser default.')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    parser.add_argument('-g', '--logfile', default=None, help='Path for log file.')
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
    config = {
        'format' : "%(levelname) -10s %(asctime)s %(module)s:%(lineno) -7s %(message)s",
        'level' : level
    }
    if args.logfile:
        config['filename'] = args.logfile
    logging.basicConfig(**config)

    main()
