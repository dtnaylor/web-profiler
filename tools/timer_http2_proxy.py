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
from collections import defaultdict
from datetime import datetime

sys.path.append('..')
from webloader.zombiejs_loader import ZombieJSLoader
from webloader.loader import LoadResult

TSHARK_STAT = 'tshark -q -z io,stat,0.001 -r %s'
TSHARK_CAP = 'tshark -i %s -w %s port %s'
#FIREFOX_CMD = '/home/b.kyle/Downloads/firefox-35.0a1/firefox -P nightly -no-remote "%s"'

HTTP_METHODS = ['GET', 'PUT', 'OPTIONS', 'HEAD', 'POST', 'DELETE', 'TRACE', 'CONNECT']

class TrialResult(object):
  def __init__(self, init_obj_size, init_obj_time, total_size, total_time, objs):
	self._init_obj_size = init_obj_size
	self._init_obj_time = init_obj_time
	self._total_size = total_size
	self._total_time = total_time
	self._objs = objs

  def _get_init_obj_size(self):
       	return self._init_obj_size
  InitSize = property(_get_init_obj_size)

  def _get_init_obj_time(self):
       	return self._init_obj_time
  InitTime = property(_get_init_obj_time)

  def _get_total_size(self):
       	return self._total_size
  TotalSize = property(_get_total_size)

  def _get_total_time(self):
       	return self._total_time
  TotalTime = property(_get_total_time)

  def _get_objs(self):
       	return self._objs
  Objects = property(_get_objs)

  def toString(self):
	return 'rootSize=%s rootTime=%s totalSize=%s totalTime=%s objects=%s' % (self._init_obj_size,\
	  self._init_obj_time, self._total_size, self._total_time, self._objs)

class Trial(object):
  def __init__(self, trial_hash, directory, use_proxy):
	self.directory = directory
	self.trial_hash = trial_hash
	self.use_proxy = use_proxy
	self.time = datetime.now()

  def getPcapFile(self):
	return os.path.join(self.directory, self.trial_hash+'.pcap')

  def getOutput(self):
	return os.path.join(self.directory, self.trial_hash+'.output')

  def getResult(self):
	first_time = first_size = True
	init_time = init_size = total_time = total_size = -1
	objs = 0
	try:
          with open(self.getOutput(), "r") as f:
	    for line in f:
	      chunks = line.rstrip().split()
	      if len(chunks) > 2 and chunks[0] in HTTP_METHODS:
		if first_time:
	          value = int(chunks[-1].rstrip('ms'))
		  init_time = value
		  first_time = False
		objs += 1
	      elif len(chunks) == 2 and chunks[0].lower() == 'content-length:':
		if first_size:
		  init_size = int(chunks[1])
		  first_size = False
		total_size += int(chunks[1])
	      elif len(chunks) == 1 and chunks[0].startswith('LOAD_TIME'):
		total_time = int(float(chunks[0].split('=')[1].rstrip('s'))*1000)
        except Exception as e:
	  logging.error('Error processing trial output. Skipping. (%s) (%s) (%s)', self.getOutput(), line, e)
	  return None
	return TrialResult(init_size, init_time, total_size, total_time, objs)

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

    def add_to_results(self, results):
	for trial in self.proxy_trials:
		results.add_trial(trial)
	for trial in self.noproxy_trials:
		results.add_trial(trial)

    def getResult(self, wproxy = True):
	sum_init_time = sum_init_size = sum_time = sum_size = count = objs = 0
	for trial in (self.proxy_trials if wproxy else self.noproxy_trials):
		r = trial.getResult()
		if not r:
			continue
		count += 1
		sum_init_time += r.InitTime
		sum_init_size += r.InitSize
		sum_time += r.TotalTime		
		sum_size += r.TotalSize
		objs += r.Objects
		print 'TRIAL', self.url, 'YESPROXY' if wproxy else 'NOPROXY', r.toString()
	if count == 0:
		return
	print 'FINAL', self.url, 'YESPROXY' if wproxy else 'NOPROXY',\
	  'rootSize=%s rootTime=%s totalSize=%s totalTime=%s objects=%s' % (sum_init_size/count,\
	  sum_init_time/count, sum_size/count, sum_time/count, objs/count)

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

def id_generator(size=15, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def fetch_url(url, proxy):
  url = make_url(url, 'https')

  while True:
    trial_hash = id_generator()
    filename = os.path.join(args.outdir,trial_hash+'.pcap')
    if not os.path.isfile(filename):
	break
  output_file = os.path.join(args.outdir,trial_hash+'.output')

  # Clear cache
  #try:
  #  subprocess.call('rm /home/b.kyle/.mozilla/firefox/*.nightly/*.sqlite /home/b.kyle/.mozilla/firefox/*nightly/sessionstore.js')
  #  subprocess.call('rm -r /home/b.kyle/.cache/mozilla/firefox/*.nightly/*')
  #except Exception as e:
  #  logging.error('Error clearing cache. (%s)', e)

  tcpdump_proc = None
  #try:
  #  cmd = TSHARK_CAP % (args.interface, filename, args.proxy_port if proxy else '443')
  #  logging.debug(cmd)
  #  tcpdump_proc = subprocess.Popen(cmd, shell=True)
  #except Exception as e:
  #  logging.error('Error starting tshark. Skipping this trial. (%s)', e)
  #  time.sleep(5)
  #  return None

  loader = ZombieJSLoader(outdir=args.outdir, num_trials=1,\
    	disable_local_cache=True, http2=True,\
    	timeout=args.timeout, full_page=True, proxy= args.proxy if proxy else None)
  result = loader._load_page(url, args.outdir)

  if tcpdump_proc:
    logging.debug('Stopping tcpdump')
    tcpdump_proc.terminate()
    tcpdump_proc.wait()
    # Make sure its dead
    try:
      subprocess.check_output(['killall','tshark'])
    except:
      pass

  time.sleep(1)
  if result.status != LoadResult.SUCCESS:
    #os.remove(filename)
    return None
  else:
    with open(output_file, "w") as outf:
	outf.write(result.raw)
    return trial_hash

def process_results(results):
  for url, result in results.iteritems():
    result.getResult(True)
    result.getResult(False)

def main():

    if args.process:
        result_files = glob.glob(os.path.join(args.outdir, 'round.*.result'))
	results = {}
        for result_file in result_files:
            with open(result_file, 'r') as f:
                res = cPickle.load(f)
		for url in res:
			if url not in results:
				results[url] = res[url]
			else:
				res[url].add_to_results(results[url])
	process_results(results)
    else:
        if args.urlfile:
            with open(args.urlfile, 'r') as f:
                for line in f:
                    args.urls.append(line.strip().split()[0])
            f.closed
        
	# Create results dictionary
	results = {}
	for url in args.urls:
	    results[url] = URLResult(url)

	for i in range(args.numtrials):
	  at_least_1_success = False	  

	  random.shuffle(args.urls)
	  for url in args.urls:
	    # With Proxy
	    trial_hash = fetch_url(url, True)
	    if trial_hash != None:
		results[url].add_trial(Trial(trial_hash, args.outdir, True))
		at_least_1_success = True
	    # Without Proxy
	    trial_hash = fetch_url(url, False)
	    if trial_hash != None:
		results[url].add_trial(Trial(trial_hash, args.outdir, False))
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
    parser.add_argument('-p', '--process', action='store_true', default=False, help='Do not perform page fetch, reprocess files')
    parser.add_argument('-x', '--proxy', default='mplane.pdi.tid.es:4567', help='Proxy to use in experiments')
    parser.add_argument('-g', '--tag', help='Tag to prepend to output files')
    parser.add_argument('-o', '--outdir', default='.', help='Output directory')
    parser.add_argument('-q', '--quiet', action='store_true', default=False, help='only print errors')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='print debug info. --quiet wins if both are present')
    args = parser.parse_args()
    args.proxy_ip = args.proxy.split(':')[0]
    args.proxy_port = args.proxy.split(':')[1]
    
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
