#!/usr/bin/env python
import os
import sys
import string
import logging
import argparse
import urlparse
import random
import pprint
import cPickle
import time
import signal
import subprocess
import glob
import numpy
from collections import defaultdict
from datetime import datetime
from timer_http2_proxy import Trial,URLResult,id_generator,analyzeResult,fetch_url,URLStat

EC2_SERVER = '54.171.86.168'
NGHTTP2_AWAZZA_PROXY = '8071'
NGHTTP2_PROXY = '8074'
NGHTTP2_SERVER = '8073'
NODEJS_AWAZZA_PROXY = '8081'
NODEJS_PROXY = '8084'
NODEJS_SERVER = '8083'

def process_results():
  results = {}
  for directory in args.process:
    result_files = glob.glob(os.path.join(directory, 'round.*.result'))
    for result_file in result_files:
      with open(result_file, 'r') as f:
        res = cPickle.load(f)
        for url in res:
          if url not in results:
            results[url] = res[url]
          else:
            res[url].add_to_results(results[url])

  for url, result in results.iteritems():
    analyzeResult(getResult(result, True, EC2_SERVER+':'+NGHTTP2_PROXY, 'NGHTTP2'),\
	          getResult(result, False, EC2_SERVER+':'+NGHTTP2_SERVER, 'NGHTTP2'),\
	          'NGHTTP2')
    analyzeResult(getResult(result, True, EC2_SERVER+':'+NODEJS_PROXY, 'NODEJS'),\
    		  getResult(result, False, EC2_SERVER+':'+NODEJS_SERVER, 'NODEJS'),\
		  'NDOEJS')
    

def getResult(res, wproxy = True, proxy = None, code = ''):
	result = URLStat(res.url)
	for trial in (res.proxy_trials if wproxy else res.noproxy_trials):
                if trial.proxy != proxy:
                        continue
		r = trial.getResult()
		if not r or r.InitSize == -1 or r.TotalSize == -1: # Ignore trials where the root object was not downloaded
			continue
		result.sum_init_time.append(r.InitTime)
		result.sum_init_size.append(r.InitSize)
		result.sum_time.append(r.TotalTime)
		result.sum_size.append(r.TotalSize)
		result.objs.append(r.Objects)
		result.r.append(r)
		if args.all:
			print 'ALL', code, res.url, 'YESPROXY' if wproxy else 'NOPROXY', r.toString()
	return result

def main():

    # Processing already collected results
    if args.process:
	process_results()
    # Running an experiment
    else:
        if args.urlfile:
            with open(args.urlfile, 'r') as f:
                for line in f:
                    args.urls.append(line.strip().split()[0])
            f.closed

        for url in args.urls:
	  results = {}
	  results[url] = URLResult(url)
	  # Prevents writing the result file if none of the trials succeed
	  at_least_1_success = False

	  for i in range(args.numtrials):
	    # With Proxy
	    trial_hash = fetch_url(url, EC2_SERVER+':'+NGHTTP2_PROXY, args.outdir, args.timeout)
	    if trial_hash != None:
                trial = Trial(trial_hash, args.outdir, True)
                trial.proxy = EC2_SERVER+':'+NGHTTP2_PROXY
		results[url].add_trial(trial)
		at_least_1_success = True
	    # Without Proxy
	    trial_hash = fetch_url(url, EC2_SERVER+':'+NGHTTP2_SERVER, args.outdir, args.timeout)
	    if trial_hash != None:
                trial = Trial(trial_hash, args.outdir, False)
                trial.proxy = EC2_SERVER+':'+NGHTTP2_SERVER
		results[url].add_trial(trial)
		at_least_1_success = True

	    # With Proxy
	    trial_hash = fetch_url(url, EC2_SERVER+':'+NODEJS_PROXY, args.outdir, args.timeout)
	    if trial_hash != None:
                trial = Trial(trial_hash, args.outdir, True)
                trial.proxy = EC2_SERVER+':'+NODEJS_PROXY
		results[url].add_trial(trial)
		at_least_1_success = True
	    # Without Proxy
	    trial_hash = fetch_url(url, EC2_SERVER+':'+NODEJS_SERVER, args.outdir, args.timeout)
	    if trial_hash != None:
                trial = Trial(trial_hash, args.outdir, False)
                trial.proxy = EC2_SERVER+':'+NODEJS_SERVER
		results[url].add_trial(trial)
		at_least_1_success = True

          if not at_least_1_success:
	    continue

	  
	  while True:
    	    filename = os.path.join(args.outdir,'round.'+id_generator()+'.result')
     	    if not os.path.isfile(filename):
	      break
          with open(filename, 'w') as f:
            cPickle.dump(results, f)
	    results = {}
	    for url in args.urls:
	      results[url] = URLResult(url)


if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Experiment for loading pages with and without Awazza')
    parser.add_argument('urls', nargs='*', help='URLs of the objects to load')
    parser.add_argument('-f', '--urlfile', help='File containing list of URLs, one per line')
    parser.add_argument('-n', '--numtrials', type=int, default=20, help='How many times to fetch each URL with each protocol')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='Timeout for requests, in seconds')
    parser.add_argument('-i', '--interface', default='eth0', help='Interface to use')
    parser.add_argument('-p', '--process', nargs='+', default=None, help='Do not perform page fetch, reprocess files')
    parser.add_argument('-a', '--all', action='store_true', default=False, help='Output all trials')
    parser.add_argument('-g', '--tag', help='Tag to prepend to output files')
    parser.add_argument('-o', '--outdir', default='.', help='Output directory')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()
    
    if not os.path.isdir(args.outdir):
        try:
            os.makedirs(args.outdir)
        except Exception as e:
            logging.error('Error making output directory: %s' % args.outdir)
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
