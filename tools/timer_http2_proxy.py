#!/usr/bin/env python
import os
import sys
import logging
import argparse
import urlparse
import numpy
import pprint
import cPickle
import subprocess
import multiprocessing
from collections import defaultdict
from datetime import datetime

TSHARK_STAT = 'tshark -q -z io,stat,0.001 -r %s'
TSHARK_CAP = 'tshark -i %s -w %s port %s'
FIREFOX_CMD = '/home/b.kyle/Downloads/firefox-35.0a1/firefox -P nightly -no-remote "%s"'

class Trial(object):
  def __init__(self, trial_hash, pcap_filename, use_proxy):
	self.root, ext = os.path.splitext(pcap_filename)
	self.trial_hash = trial_hash
	self.use_proxy = use_proxy
	self.time = datetime.now()

class URLResult(object):
    '''Statistics of a single URL'''
    def __init__(self, url):
        self.url = url
	self.proxy_trials = []
	self.noproxy_trials = []

    def add_trial(self, trial):
        if trial.use_proxy:
		self.proxy_trials.append(trial)
	else:
		self.noproxy_trials.append(trial)

    def _get_http_mean(self):
        return numpy.mean(self.http_times)
    http_mean = property(_get_http_mean)
    
    def _get_http_median(self):
        return numpy.median(self.http_times)
    http_median = property(_get_http_median)

    def _get_http_stddev(self):
        return numpy.std(self.http_times)
    http_stddev = property(_get_http_stddev)
    
    def _get_https_mean(self):
        return numpy.mean(self.https_times)
    https_mean = property(_get_https_mean)
    
    def _get_https_median(self):
        return numpy.median(self.https_times)
    https_median = property(_get_https_median)

    def _get_https_stddev(self):
        return numpy.std(self.https_times)
    https_stddev = property(_get_https_stddev)

    def _get_size(self):
        return self.http_sizes[0] if len(self.http_sizes) > 0 else None
    size = property(_get_size)

def make_url(url, protocol, port=None):
    # make sure it's a complete URL to begin with, or urlparse can't parse it
    if '://' not in url:
        url = 'http://%s' % url
    comps = urlparse.urlparse(url)

    new_netloc = comps.netloc
    if port:
        new_netloc = new_netloc.split(':')[0]
        new_netloc = '%s:%s' % (new_netloc, port)

    new_comps = urlparse.ParseResult(scheme=protocol, netloc=new_netloc,\
        path=comps.path, params=comps.params, fragment=comps.fragment,\
        query=comps.query)

    return urlparse.urlunparse(new_comps)

def id_generator(size=10, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def fetch_url(url, proxy):
  while True:
    trial_hash = id_generator()
    filename = args.outdir+'/'+trial_hash+'.pcap'
    if not os.path.isfile(filename):
	break

  # Clear cache
  subprocess.call('rm ~/.mozilla/firefox/*.nightly/*.sqlite ~/.mozilla/firefox/*nightly/sessionstore.js')
  subprocess.call('rm -r ~/.cache/mozilla/firefox/*.nightly/*')

  try:
    cmd = TSHARK_CAP % (args.interface, filename, '4567' if proxy else '443')
    logging.debug(cmd)
    tcpdump_proc = subprocess.Popen(cmd, shell=True)
  except Exception as e:
    logging.error('Error starting tshark. Skipping this trial. (%s)', e)
    time.sleep(5)
    return None, None

  try:
    cmd = FIREFOX_CMD % url
    logging.debug(cmd)
    firefox_proc = subprocess.Popen(cmd, shell=True)
    time.sleep(15) # Give Firefox 15 seconds to load the webpage, otherwise, give up
  except Exception as e:
    logging.error('Error starting firefox. Skipping this trial. (%s)', e)
    time.sleep(5)
    return None, None
  finally:
    if tcpdump_proc:
      logging.debug('Stopping tcpdump')
      tcpdump_proc.kill()
      tcpdump_proc.wait()
    if firefox_proc:
      logging.debug('Stopping firefox')
      firefox_proc.kill()
      firefox_proc.wait()

  return trial_hash, filename

def main():

    filename_to_results = {}
    filenames = []  # so we know the original order
    if args.process:
        for file in args.readfile:
            with open(file, 'r') as f:
                results = cPickle.load(f)
                filename_to_results[file] = results
                filenames.append(file)
            f.closed
    else:
        if args.urlfile:
            with open(args.urlfile, 'r') as f:
                for line in f:
                    args.urls.append(line.strip())
            f.closed
        
	# Create results dictionary
	results = {}
	for url in args.urls:
	    results[url] = URLResult(url)

	for i in range(args.numtrials):
	  # Set DNS server
	  for url in args.urls:
	    trial_hash, pcap_file = fetch_url(url, True)
	    if trial_hash != None:
		results[url].add_trial(Trial(trial_hash, pcap_file, True))

	  # Revert DNS server
	  for url in args.urls:
	    trial_hash, pcap_file = fetch_url(url, False)
	    if trial_hash != None:
		results[url].add_trial(Trial(trial_hash, pcap_file, False))

	  while True:
    	    filename = os.path.join(args.outdir,'round.'+id_generator()+'.result')
     	    if not os.path.isfile(filename):
	      break
          with open(filename, 'w') as f:
            cPickle.dump(results, f)
	    results = {}


if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Experiment for loading pages with and without Awazza')
    parser.add_argument('urls', nargs='*', help='URLs of the objects to load')
    parser.add_argument('-f', '--urlfile', help='File containing list of URLs, one per line')
    parser.add_argument('-n', '--numtrials', type=int, default=20, help='How many times to fetch each URL with each protocol')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='Timeout for requests, in seconds')
    parser.add_argument('-i', '--interface', default='eth0', help='Interface to use')
    parser.add_argument('-p', '--process', default='.', help='Do not perform page fetch, reprocess files')
    parser.add_argument('-x', '--proxy', default='mplane.pdi.tid.es:4567', help='Proxy to use in experiments')
    parser.add_argument('-g', '--tag', help='Tag to prepend to output files')
    parser.add_argument('-o', '--outdir', default='.', help='Output directory')
    parser.add_argument('-c', '--numcores', type=int, help='Number of cores to use')
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
