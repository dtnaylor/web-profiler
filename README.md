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
`Loader` superclass in `loader.py`) and currently supports the following
backends:

* PhantomJS (`PhantomJSLoader` in `phantomjs_loader.py`)
* Chrome (`ChromeLoader` in `chrome_loader.py`)
* Firefox (`FirefoxLoader` in `firefox_loader.py`)
* Python Requests (`PythonRequestsLoader` in `pythonrequests_loader.py`)
* Curl (`CurlLoader` in `curl_loader.py`)
* NodeJS (`NodeJsLoader` in `nodejs_loader.py`)

API documentation available [here](http://webloader.readthedocs.org/en/latest/).
	
	
### Dependencies:

* [PhantomJS](http://phantomjs.org)

	Needed by the `PhantomJSLoader`.

	If the loader can't find PhantomJS, try harding-coding the path to
	PhantomJS at the top of `phantomjs_loader.py`.

* [Xvfb](http://www.x.org/archive/X11R7.7/doc/man/man1/Xvfb.1.xhtml)

	Needed to run Firefox or Chrome in headless mode.
	
* [chrome-har-capturer](https://github.com/cyrus-and/chrome-har-capturer)

	Needed by the `ChromeLoader`.

	Set path to binary at top of `chrome_loader.py`.

* [node.js](https://nodejs.org)

	Needed by the `ChromeLoader`. (On Ubuntu, be sure to install nodejs package
	and not node.)

* [Python Requests](http://docs.python-requests.org)

    Used to test the availability of sites of HTTP or HTTPS and by the 
    `PythonRequestsLoader`.

* [node-http2](https://github.com/scoky/node-http2)

    Needed by the `NodeJsLoader` and `ZombieJsLoader`. Location of the module must be hardcoded 
    in `webloader/nodejs_loader.py` and `webloader/zombiejs_loader.py`.
z
