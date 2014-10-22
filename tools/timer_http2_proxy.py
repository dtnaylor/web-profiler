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

sys.path.append('..')
from webloader.zombiejs_loader import ZombieJSLoader
from webloader.loader import LoadResult

TSHARK_STAT = 'tshark -q -z io,stat,0.001 -r %s'
TSHARK_CAP = 'tshark -i %s -w %s port %s'
#FIREFOX_CMD = '/home/b.kyle/Downloads/firefox-35.0a1/firefox -P nightly -no-remote "%s"'

HTTP_METHODS = ['GET', 'PUT', 'OPTIONS', 'HEAD', 'POST', 'DELETE', 'TRACE', 'CONNECT']

# Parsed output file results from a single trial
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

# Trial instance store in filesystem
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

  # Parse trial output and generate a TrialResult object
  def getResult(self):
	first_time = last_time = -1
	first = True
	req = {}
	init_time = init_size = total_time = -1
	total_size = objs = 0
	try:
          with open(self.getOutput(), "r") as f:
	    for line in f:
	      chunks = line.rstrip().split()
	      if len(chunks) < 1:
		continue

	      if chunks[0] == 'REQUEST':
		if first_time == -1:
		  first_time = int(chunks[1])
		req[chunks[2]] = int(chunks[1])
	      elif chunks[0] == 'RESPONSE':
		if first:
		  first = False
		  init_time = int(chunks[1]) - req[chunks[2]]
		  init_size = int(chunks[3])
		total_size += int(chunks[3])
		objs += 1
		last_time = int(chunks[1])
#	      elif chunks[0].startswith('LOAD_TIME'):
#		total_time = int(float(chunks[0].split('=')[1].rstrip('s'))*1000)
        except Exception as e:
	  logging.error('Error processing trial output. Skipping. (%s) (%s) (%s)', self.getOutput(), line, e)
	  return None
	return TrialResult(init_size, init_time, total_size, last_time-first_time, objs)

# Accumulated results for a URL
class URLStat(object):
  def __init__(self, url):
    self.url = url
    self.sum_init_time = []
    self.sum_init_size = []
    self.sum_time = [] 
    self.sum_size = [] 
    self.objs = []
    self.r = []

  def subset(self, indices):
    self.sum_init_time = getSublist(self.sum_init_time, indices)
    self.sum_init_size = getSublist(self.sum_init_size, indices)
    self.sum_time = getSublist(self.sum_time, indices)
    self.sum_size = getSublist(self.sum_size, indices)
    self.objs = getSublist(self.objs, indices)
    self.r = getSublist(self.r, indices)

# URL experiment instance stored in file system
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

    # Parse the output of all trials in the experiment and generate a URLStat result
    def getResult(self, wproxy = True):
	result = URLStat(self.url)
	for trial in (self.proxy_trials if wproxy else self.noproxy_trials):
		r = trial.getResult()
		if not r or r.InitSize == -1 or r.TotalSize == -1: # Ignore trials where the root object was not downloaded
			continue
		result.sum_init_time.append(r.InitTime)
		result.sum_init_size.append(r.InitSize)
		result.sum_time.append(r.TotalTime)
		result.sum_size.append(r.TotalSize)
		result.objs.append(r.Objects)
		result.r.append(r)
		#print 'TRIAL', self.url, 'YESPROXY' if wproxy else 'NOPROXY', r.toString()
	return result

# Process output of all trials for all URLS stored in file system  and output the analyzed results
def process_results(results):
  for url, result in results.iteritems():
    analyzeResult(result.getResult(True), result.getResult(False))

# Analyze a specific URL result
def analyzeResult(proxy, noproxy):
  while True:
  	objs = proxy.objs + noproxy.objs
  	if len(objs) == 0:
    		return
	# Get the most frequently occuring number of objects
  	mode = getMode(objs)
	# Check to see that both with proxy and without proxy have data points in the mode
	if len(getIndices(proxy.objs, mode)) > 0 and len(getIndices(noproxy.objs, mode)) > 0:
		break
	# Remove the bad mode
	proxy.subset([i for i in range(len(proxy.objs)) if i not in getIndices(proxy.objs, mode)])
	noproxy.subset([i for i in range(len(proxy.objs)) if i not in getIndices(noproxy.objs, mode)])

  # Proxy
  indices = getIndices(proxy.objs, mode)
  if len(indices) > 0: 
	proxy.subset(indices)  

        for r in proxy.r:
	  print 'TRIAL', proxy.url, 'YESPROXY', r.toString()

  	print 'FINAL_MEAN', proxy.url, 'YESPROXY',\
	  'rootSize=%s rootTime=%s totalSize=%s totalTime=%s objects=%s trials=%s' % (numpy.mean(proxy.sum_init_size),\
	  numpy.mean(proxy.sum_init_time), numpy.mean(proxy.sum_size), numpy.mean(proxy.sum_time), mode, len(indices))

	print 'FINAL_MEDIAN', proxy.url, 'YESPROXY',\
	  'rootSize=%s rootTime=%s totalSize=%s totalTime=%s objects=%s trials=%s' % (numpy.median(proxy.sum_init_size),\
	  numpy.median(proxy.sum_init_time), numpy.median(proxy.sum_size), numpy.median(proxy.sum_time), mode, len(indices))

  # No Proxy
  indices = getIndices(noproxy.objs, mode)
  if len(indices) > 0: 
	noproxy.subset(indices)  

        for r in noproxy.r:
	  print 'TRIAL', noproxy.url, 'NOPROXY', r.toString()

  	print 'FINAL_MEAN', noproxy.url, 'NOPROXY',\
	  'rootSize=%s rootTime=%s totalSize=%s totalTime=%s objects=%s trials=%s' % (numpy.mean(noproxy.sum_init_size),\
	  numpy.mean(noproxy.sum_init_time), numpy.mean(noproxy.sum_size), numpy.mean(noproxy.sum_time), mode, len(indices))

	print 'FINAL_MEDIAN', noproxy.url, 'NOPROXY',\
	  'rootSize=%s rootTime=%s totalSize=%s totalTime=%s objects=%s trials=%s' % (numpy.median(noproxy.sum_init_size),\
	  numpy.median(noproxy.sum_init_time), numpy.median(noproxy.sum_size), numpy.median(noproxy.sum_time), mode, len(indices))

# Get the sublist of a list with given indices
def getSublist(vals, indices):
  return [v for i,v in enumerate(vals) if i in indices]

# Get the mode of a list
def getMode(vals):
  return sorted(vals, key=vals.count)[-1]

# Get the indices in a list that match with given value
def getIndices(vals, val):
  return [i for i,v in enumerate(vals) if v == val]

# ------------------CODE FOR RUNNING THE EXPERIMENT---------------------------#

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
    dump_file = os.path.join(args.outdir,trial_hash+'.pcap')
    output_file = os.path.join(args.outdir,trial_hash+'.output')
    if not os.path.isfile(dump_file) and not os.path.isfile(output_file):
	break


  # Clear cache
  #try:
  #  subprocess.call('rm /home/b.kyle/.mozilla/firefox/*.nightly/*.sqlite /home/b.kyle/.mozilla/firefox/*nightly/sessionstore.js')
  #  subprocess.call('rm -r /home/b.kyle/.cache/mozilla/firefox/*.nightly/*')
  #except Exception as e:
  #  logging.error('Error clearing cache. (%s)', e)

  tcpdump_proc = None
  #try:
  #  cmd = TSHARK_CAP % (args.interface, dump_file, args.proxy_port if proxy else '443')
  #  logging.debug(cmd)
  #  tcpdump_proc = subprocess.Popen(cmd, shell=True)
  #except Exception as e:
  #  logging.error('Error starting tshark. Skipping this trial. (%s)', e)
  #  time.sleep(5)
  #  return None

  loader = ZombieJSLoader(outdir=args.outdir, num_trials=1,\
    	disable_local_cache=True, http2=True,\
    	timeout=args.timeout, full_page=True, proxy= args.proxy if proxy else args.proxy_ip+':6789')
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
    #os.remove(dump_file)
    return None
  else:
    with open(output_file, "w") as outf:
	outf.write(result.raw)
    return trial_hash

def main():

    # Processing already collected results
    if args.process:
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
	process_results(results)
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
    parser.add_argument('-p', '--process', nargs='+', default=None, help='Do not perform page fetch, reprocess files')
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
