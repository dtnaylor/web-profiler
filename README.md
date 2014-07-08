Web Profiler
============

Tools for gathering statistics about contents and performance of Web sites.
There are two parts:

1. Python "loader" classes that load Web pages (using various backends, like
PhantomJS, Chrome, and Firefox) and produce summary statistics, HAR files,
and/or screenshots.

2. Scripts that use these loaders to gather particular statistics (e.g.,
compare the load times of the HTTP and HTTPS versions of a site).


Loaders
-------

The loaders are Python classes that encapsulate the logic for loading Web pages
and saving statistics. Each one implements a common interface (specified by the
`Loader` superclass in `loader.py`) and supports various backends:

* PhantomJS (`phantomjs_loader.py`)
* Chrome (`chrome_loader.py`)
* Firefox (`firefox_loader.py`)

API documentation available [here](...).
	
	
### Dependencies:

* [PhantomJS](http://phantomjs.org)

	Needed by the `PhantomJSLoader`.

	If the loader can't find PhantomJS, try harding-coding the path to
	PhantomJS at the top of `phantomjs_loader.py`.
	
* [chrome-har-capturer](https://github.com/cyrus-and/chrome-har-capturer)

	Needed by the `ChromeLoader`.

	Set path to binary at top of `chrome_loader.py`.
