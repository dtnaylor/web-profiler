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

sys.path.append('..')
from webloader import PhantomJSLoader, PythonRequestsLoader, CurlLoader, PageResult

# TODO: do something about this
sys.path.append('/home/dnaylor/Documents/tools/myplot')
import myplot

SUCCESS = 'SUCCESS'
FAILURE_TIMEOUT = 'FAILURE_TIMEOUT'
FAILURE_NO_HTTP = 'FAILURE_NO_HTTP'
FAILURE_NO_HTTPS = 'FAILURE_NO_HTTPS'
FAILURE_UNKNOWN = 'FAILURE_UNKNOWN'
FAILURE_NO_200 = 'FAILURE_NO_200'
FAILURE_ARITHMETIC = 'FAILURE_ARITHMETIC'
FAILURE_UNSET = 'FAILURE_UNSET'

class URLResult(object):
    '''Status for several trials over HTTP and HTTPS for a URL'''
    def __init__(self, status, url):
        self.status = status
        self.url = url
        self.http_times = []
        self.https_times = []
        self.http_sizes = []  # shouldn't be changing, but...
        self.https_sizes = [] # shouldn't be different, but...

    def add_http_result(self, result):
        if result.status == SUCCESS:
            self.http_times.append(result.time)
            self.http_sizes.append(result.size)

    def add_https_result(self, result):
        if result.status == SUCCESS:
            self.https_times.append(result.time)
            self.https_sizes.append(result.size)

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

    def try_calc(self):
        try:
            # do the calculations just to make sure they don't throw error
            http_mean = numpy.mean(self.http_times)
            http_median = numpy.median(self.http_times)
            https_mean = numpy.mean(self.https_times)
            https_median = numpy.median(self.https_times)
            if not http_mean or\
               not http_median or\
               not https_mean or\
               not https_median:
                raise Exception()
        except Exception as e:
            logging.error('Error calculating stats for %s: %s', self.url, e)
            self.status = FAILURE_ARITHMETIC

    def __str__(self):
        return 'RESULT: < Status=%s\tHTTP/HTTPS Mean=%f/%f StdDev=%f/%f Median=%f/%f\tURL=%s >'\
            % (self.status, self.http_mean, self.https_mean, self.http_stddev,\
            self.https_stddev, self.http_median, self.https_median, self.url)
    def __repr__(self):
        return self.__str__()

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




def process_url(url):
    # numpy warnings are errors
    old_numpy_settings = numpy.seterr(all='raise')

    http_url = make_url(url, 'http', args.httpport)
    https_url = make_url(url, 'https', args.httpsport)
    logging.debug('HTTP URL:  %s' % http_url)
    logging.debug('HTTPS URL: %s' % https_url)
    
    result = URLResult(SUCCESS, url)

    # If we're loading the full page, use PhantomJSLoader; otherwise, use
    # PythonRequestsLoader
    loader = None
    if args.loadpage:
        loader = PhantomJSLoader(outdir=args.outdir, num_trials=args.numtrials,\
            timeout=args.timeout, full_page=True)
    else:
        loader = CurlLoader(outdir=args.outdir, num_trials=args.numtrials,\
            timeout=args.timeout, full_page=False)
        #loader = PythonRequestsLoader(outdir=args.outdir, num_trials=args.numtrials,\
        #    timeout=args.timeout, full_page=False)
    
    # Load the pages; 
    loader.load_pages([http_url, https_url])
    
    # Make sure the URL was accessible over both HTTP and HTTPS
    if loader.page_results[http_url].status == PageResult.FAILURE_NOT_ACCESSIBLE:
        logging.debug('The URL "%s" cannot be accessed over HTTP.' % url)
        return URLResult(FAILURE_NO_HTTP, url)
    if loader.page_results[https_url].status == PageResult.FAILURE_NOT_ACCESSIBLE:
        logging.debug('The URL "%s" cannot be accessed over HTTPS.' % url)
        return URLResult(FAILURE_NO_HTTPS, url)
    
    # grab the individual results and put them into a URLResult object
    for http_result in loader.load_results[http_url]:
        result.add_http_result(http_result)
    for https_result in loader.load_results[https_url]:
        result.add_https_result(https_result)
    result.try_calc()  # sets status to FAILURE_ARITHMETIC if there's a problem

    # reset numpy warnings
    #numpy.seterr(old_numpy_settings)

    logging.info(result)
    return result

def plot_results(filename_to_results, filenames=None):
    # use the filenames list to make sure we process files in order
    # (so we can control the order of the series on the plot)
    if not filenames: filenames = filename_to_results.keys()
    
    filename_to_data = defaultdict(lambda: defaultdict(list))
    fraction_data = []
    fraction_labels = []
    absolute_data = []
    absolute_labels = []
    mean_percents_by_size = []
    mean_absolutes_by_size = []
    mean_by_size_xs = []
    mean_by_size_ys = []
    mean_by_size_yerrs = []
    mean_by_size_labels = []
    
    for filename in filenames:
        results = filename_to_results[filename]
        for r in results:
            if r.status == SUCCESS:
                filename_to_data[filename]['both_success'].append(r.url)

                filename_to_data[filename]['mean_percent_inflations'].append(r.https_mean / r.http_mean)
                filename_to_data[filename]['mean_absolute_inflations'].append(r.https_mean - r.http_mean)
                filename_to_data[filename]['median_percent_inflations'].append(r.https_median / r.http_median)
                filename_to_data[filename]['median_absolute_inflations'].append(r.https_median - r.http_median)
                if r.size:
                    filename_to_data[filename]['mean_percent_by_size'].append( (r.size/1000.0, r.https_mean / r.http_mean, r.http_stddev) )
                    filename_to_data[filename]['mean_absolute_by_size'].append( (r.size/1000.0, r.https_mean - r.http_mean, r.http_stddev) )
                    filename_to_data[filename]['mean_http_by_size'].append( (r.size/1000.0, r.http_mean, r.http_stddev) )
                    filename_to_data[filename]['mean_https_by_size'].append( (r.size/1000.0, r.https_mean, r.http_stddev) )
            elif r.status == FAILURE_NO_HTTP:
                filename_to_data[filename]['no_http'].append(r.url)
            elif r.status == FAILURE_NO_HTTPS:
                filename_to_data[filename]['no_https'].append(r.url)
            else:
                filename_to_data[filename]['other_error'].append(r.url)

        print '%i sites were accessible over both protocols' %\
            len(filename_to_data[filename]['both_success'])
        print '%i sites were not accessible over HTTP' %\
            len(filename_to_data[filename]['no_http'])
        print '%i sites were not accessible over HTTPS' %\
            len(filename_to_data[filename]['no_https'])
        print '%i sites were not accessible for other reasons' %\
            len(filename_to_data[filename]['other_error'])

        if 'pit' in filename:
            location = 'PIT'
        elif '3g' in filename:
            location = '3G'
        else:
            location = 'Fiber'

        fraction_data.append(filename_to_data[filename]['mean_percent_inflations'])
        fraction_labels.append('Mean (%s)' % location)
        fraction_data.append(filename_to_data[filename]['median_percent_inflations'])
        fraction_labels.append('Median (%s)' % location)

        absolute_data.append(numpy.array(filename_to_data[filename]['mean_absolute_inflations']))# * 1000)  # s -> ms
        absolute_labels.append('Mean (%s)' % location)
        absolute_data.append(numpy.array(filename_to_data[filename]['median_absolute_inflations']))# * 1000)  # s -> ms
        absolute_labels.append('Median (%s)' % location)

        try:
            mean_by_size_xs.append(zip(*sorted(filename_to_data[filename]['mean_http_by_size']))[0])
            mean_by_size_ys.append(zip(*sorted(filename_to_data[filename]['mean_http_by_size']))[1])
            mean_by_size_yerrs.append(zip(*sorted(filename_to_data[filename]['mean_http_by_size']))[2])
            mean_by_size_labels.append('Mean HTTP (%s)' % location)
            mean_by_size_xs.append(zip(*sorted(filename_to_data[filename]['mean_https_by_size']))[0])
            mean_by_size_ys.append(zip(*sorted(filename_to_data[filename]['mean_https_by_size']))[1])
            mean_by_size_yerrs.append(zip(*sorted(filename_to_data[filename]['mean_https_by_size']))[2])
            mean_by_size_labels.append('Mean HTTPS (%s)' % location)
        except Exception as e:
            logging.warn('Error processing size data: %s' % e)

        if location == 'BCN':
            mean_percents_by_size.append(filename_to_data[filename]['mean_percent_by_size'])
            mean_absolutes_by_size.append(filename_to_data[filename]['mean_absolute_by_size'])
    

    myplot.cdf(fraction_data,
        xlabel='Load Time Ratio (HTTPS/HTTP)', labels=fraction_labels,
        filename=os.path.join(args.outdir, '%s_fraction_inflation.pdf' % args.tag),
        height_scale=0.7, numbins=10000, xlim=(1, 3), legend='lower right')

    myplot.cdf(absolute_data,
        xlabel='Load Time Difference (HTTPS-HTTP) [s]', labels=absolute_labels,
        filename=os.path.join(args.outdir, '%s_absolute_inflation.pdf' % args.tag),
        height_scale=0.7, numbins=10000, xlim=(0,3), legend='lower right')
    
    myplot.cdf(absolute_data,
        xlabel='Load Time Difference (HTTPS-HTTP) [s]', labels=absolute_labels,
        filename=os.path.join(args.outdir, '%s_absolute_inflation_log.pdf' % args.tag),
        height_scale=0.7, numbins=10000, xscale='log', xlim=(0, 10), legend='lower right')

    # Plot fraction and absolute in same figure as subplots
    fig, ax_array = myplot.subplots(1, 2, height_scale=0.75, width_scale=1.2)
    myplot.cdf(fraction_data, fig=fig, ax=ax_array[0],
        xlabel='Load Time Ratio\n(HTTPS/HTTP)', labels=fraction_labels,
        numbins=10000, xlim=(1, 3), show_legend=False)

    lines, labels = myplot.cdf(absolute_data, fig=fig, ax=ax_array[1],
        xlabel='Load Time Difference\n(HTTPS-HTTP) [s]', labels=absolute_labels,
        numbins=10000, xlim=(0,3), legend='lower right', labelspacing=0.1, handletextpad=0.4)

    # shrink plots to make room for legend underneath
    #for ax in ax_array:
    #    box = ax.get_position()
    #    ax.set_position([box.x0, box.y0 + box.height * 0.25,
    #             box.width, box.height * 0.75])
    
    # shrink plots to make room for title above
    for ax in ax_array:
        box = ax.get_position()
        ax.set_position([box.x0, box.y0,
                 box.width, box.height * 0.95])

    #myplot.save_plot(os.path.join(args.outdir, '%s_combined_inflation_no_legend.pdf' % args.tag))
    #fig.legend(lines, labels, loc='lower center', ncol=2, prop={'size':20}, frameon=False,
    #    bbox_to_anchor=(.5, -.03))
    fig.suptitle('O-Proxy Top 2000 Objects')
    myplot.save_plot(os.path.join(args.outdir, '%s_combined_inflation.pdf' % args.tag))


    try:
        myplot.plot([zip(*mean_percents_by_size[0])[0]], [zip(*mean_percents_by_size[0])[1]],
            xlabel='Object Size (KB)', ylabel='Fraction Inflation (HTTPS/HTTP)',
            linestyles=[''], xscale='log', 
            filename=os.path.join(args.outdir, '%s_fraction_by_size.pdf' % args.tag))
    
        myplot.plot([zip(*mean_absolutes_by_size[0])[0]], [zip(*mean_absolutes_by_size[0])[1]],
            xlabel='Object Size (KB)', ylabel='Absolute Inflation (HTTPS-HTTP) [sec]',
            linestyles=[''], xscale='log',
            filename=os.path.join(args.outdir, '%s_absolute_by_size.pdf' % args.tag))
    
        myplot.plot(mean_by_size_xs, mean_by_size_ys, yerrs=mean_by_size_yerrs,
            xlabel='Object Size (KB)', ylabel='Load Time [sec]', xscale='log',
            marker=None, labels=mean_by_size_labels,# legend='lower left',
            legend_cols=2, width_scale=2,
            filename=os.path.join(args.outdir, '%s_mean_lt_by_size.pdf' % args.tag))
    except Exception as e:
        logging.warn('Error processing size data: %s', e)

def summarize_results(filename_to_results):
    for results in filename_to_results.values():
        for result in results:
            print result

def main():

    filename_to_results = {}
    filenames = []  # so we know the original order
    if args.readfile:
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
            
        # process logs individually in separate processes
        pool = multiprocessing.Pool(args.numcores)
        try:
            results = pool.map_async(process_url, args.urls).get(0xFFFF)
        except KeyboardInterrupt:
            sys.exit()
        except multiprocessing.TimeoutError:
            logging.warn('Multiprocessing timeout')
        
        filename = os.path.join(args.outdir, '%s_fetcher.pickle'%args.tag)
        with open(filename, 'w') as f:
            cPickle.dump(results, f)
        f.closed

        filename_to_results[filename] = results
        filenames.append(filename)

    if args.summary:
        summarize_results(filename_to_results)
    else:
        plot_results(filename_to_results, filenames)



if __name__ == "__main__":
    # set up command line args
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                                     description='Calculate difference in load time over HTTP and HTTPS.')
    parser.add_argument('urls', nargs='*', help='URLs of the objects to load. If object is HTML, sub-resources are *not* fetched unless the "-p" flag is supplied.')
    parser.add_argument('-f', '--urlfile', help='File containing list of URLs, one per line.')
    parser.add_argument('-r', '--readfile', nargs='+', help='Read previously pickled results instead of fetching URLs.')
    parser.add_argument('-y', '--summary', action='store_true', default=False, help='Show a summary of results instead of generating plots.')
    parser.add_argument('-n', '--numtrials', type=int, default=20, help='How many times to fetch each URL with each protocol.')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='Timeout for requests, in seconds')
    parser.add_argument('-p', '--loadpage', action='store_true', default=False, help='Load the full page, not just the object.')
    parser.add_argument('-x', '--httpport', default=None, help='Port used for HTTP connections')
    parser.add_argument('-s', '--httpsport', default=None, help='Port used for HTTPS connections')
    parser.add_argument('-g', '--tag', help='Tag to prepend to output files')
    parser.add_argument('-o', '--outdir', default='.', help='Output directory (for plots, etc.)')
    parser.add_argument('-c', '--numcores', type=int, help='Number of cores to use.')
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
