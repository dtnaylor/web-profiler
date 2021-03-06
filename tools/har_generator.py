#! /usr/bin/env python

import os
import sys
import logging
import argparse
import pickle

from logging import handlers

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from webloader.phantomjs_loader import PhantomJSLoader
from webloader.chrome_loader import ChromeLoader


def main():
    logging.info('=============== HAR GENERATOR LAUNCHED ===============')

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

    # load experiment configurations
    configs=[{'tag':'default', 'settings':{}}]
    if args.configs:
        with open(args.configs, 'r') as f:
            configs = eval(f.read())

    save_content='never'
    if args.save_content_first_trial:
        save_content='first'

    # load pages and save HARs
    if len(urls) > 0:
        loader = ChromeLoader(outdir=args.outdir, user_agent=args.useragent,\
            num_trials=args.numtrials, restart_on_fail=True, save_har=True,\
            retries_per_trial=1, stdout_filename=args.stdoutfile,\
            disable_network_cache=args.disable_network_cache,\
            log_ssl_keys=args.log_ssl_keys,\
            disable_spdy=args.disable_spdy,\
            save_packet_capture=args.packet_trace,\
            check_protocol_availability=args.disable_protocol_check,\
            ignore_certificate_errors=True,\
            restart_each_time=args.restart_each_time,\
            timeout=args.timeout,\
            delay_after_onload=args.delay_after_onload,\
            delay_first_trial_only=args.delay_first_trial_only,\
            primer_load_first=args.primer_load_first,\
            save_content=save_content,\
            configs=configs)
        loader.load_pages(urls)

        # pickle load results
        try:
            with open(os.path.join(args.outdir, 'har_generator_results.pickle'), 'w') as f:
                pickle.dump(loader, f)
        except:
            logging.exception('Error saving pickled results.')



if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Web page profiler.')
    parser.add_argument('-l', '--load_pages', nargs='+', help='URL(s) to load (to load multiple pages, separate URLs with spaces). A HAR will be generated for each page in outdir.')
    parser.add_argument('-f', '--url_file', default=None, help='Generate HARs for the URLs in the specified file (one URL per line)')
    parser.add_argument('-o', '--outdir', default='.', help='Destination directory for HAR files.')
    parser.add_argument('-c', '--configs', default=None, help='File path for experiment configurations file.')
    parser.add_argument('-n', '--numtrials', default=1, type=int, help='Number of times to load each URL.')
    parser.add_argument('-u', '--useragent', default=None, help='Custom user agent. If None, use browser default.')
    parser.add_argument('-d', '--delay-after-onload', type=int, default=0, help='Time in ms to continue recording objects after onLoad fires.')
    parser.add_argument('--delay-first-trial-only', action='store_true', default=False, help='Apply onLoad delay only to the first trial.')
    parser.add_argument('--disable-network-cache', action='store_true', default=False, help='Send cache-control headers telling caches not to respond.')
    parser.add_argument('--restart-each-time', action='store_true', default=False, help='Restart Chrome before each page load.')
    parser.add_argument('--disable-protocol-check', action='store_true', help='Do not check if the site supports HTTPS')
    parser.add_argument('--packet-trace', action='store_true', default=False, help='Save a packet trace for each page load.')
    parser.add_argument('--log-ssl-keys', action='store_true', default=False, help='Log SSL keys')
    parser.add_argument('--disable-spdy', action='store_true', default=False, help='Disable SPDY/HTTP2')
    parser.add_argument('--timeout', type=int, default=30, help='Timout in seconds')
    parser.add_argument('--primer-load-first', action='store_true', default=False, help='Load page once before actual trials (e.g., to prime DNS cache.')
    parser.add_argument('--save-content-first-trial', action='store_true', default=False, help='Save HTTP bodies for first trial of each URL.')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    parser.add_argument('-g', '--logfile', default=None, help='Path for log file.')
    parser.add_argument('-t', '--stdoutfile', default=None, help='Log file path for loader\'s stdout and stderr.')
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
    logfmt = "%(levelname) -10s %(asctime)s %(module)s:%(lineno) -7s %(message)s"
    config = {
        'format' : logfmt,
        'level' : level
    }
    logging.basicConfig(**config)
    #if args.logfile:
    #    config['filename'] = args.logfile
    if args.logfile:
        handler = handlers.RotatingFileHandler(args.logfile,\
            maxBytes=10*1024*1024, backupCount=3)
        logging.getLogger('').addHandler(handler)
        handler.setFormatter(logging.Formatter(fmt=logfmt))
        handler.setLevel(level)

    main()
